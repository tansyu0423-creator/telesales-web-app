import os
import sys
import tempfile
import time
import asyncio
from typing import List, Dict, Any

from sqlalchemy import select
from minio import Minio

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from .celery_app import celery_app
    from .database import SessionLocal
    from .config import settings
    from . import models, crud, stt, diarization, llm_analysis, summary_analysis
except ImportError:
    from celery_app import celery_app
    from database import SessionLocal
    from config import settings
    import models, crud, stt, diarization, llm_analysis, summary_analysis

minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure
)


def _run_async(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    else:
        return asyncio.run(coro)


def safe_update_state(task_self, state: str, meta: dict):
    if task_self and getattr(task_self, "request", None) and getattr(task_self.request, "id", None):
        try:
            task_self.update_state(state=state, meta=meta)
        except Exception:
            pass


@celery_app.task(bind=True, name="backend.tasks.transcribe_and_diarize_task")
def transcribe_and_diarize_task(self, record_id: int) -> Dict[str, Any]:
    """
    音声をMinIOから取得し、STT + 話者分離 + LLM役割同定を実行してDBに保存するタスク
    """
    async def _async_transcribe() -> Dict[str, Any]:
        async with SessionLocal() as db:
            t_start = time.perf_counter()
            record = await crud.get_call_record(db, record_id=record_id)
            if not record:
                raise ValueError(f"Record ID {record_id} not found")

            filename = str(record.audio_file_path)
            if not filename:
                raise ValueError(f"No audio file linked to record {record_id}")

            raw_audio_path = ""
            wav_audio_path = ""
            
            # 1. MinIOから元ファイルのままダウンロード
            ext = os.path.splitext(filename)[1]
            if not ext:
                ext = ".mp3"
            
            response = None
            try:
                response = minio_client.get_object(settings.minio_bucket_name, filename)
                with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as temp_audio:
                    for data in response.stream(32 * 1024):
                        temp_audio.write(data)
                    raw_audio_path = temp_audio.name
            finally:
                if response is not None:
                    response.close()
                    response.release_conn()

            try:
                # 2. 管理者権限なしで音声を本物のWAVに変換する
                import imageio_ffmpeg
                import subprocess
                ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_wav:
                    wav_audio_path = temp_wav.name
                    
                # MP3等の圧縮音源を 16kHz モノラルのWAVに変換（AIが一番読みやすい形式）
                subprocess.run([
                    ffmpeg_exe, "-y", "-i", raw_audio_path, 
                    "-ar", "16000", "-ac", "1", wav_audio_path
                ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                t_convert = time.perf_counter() - t_start

                # 3. Groq Whisper による文字起こし（変換した wav_audio_path を使う）
                t_stt_start = time.perf_counter()
                safe_update_state(self, 'PROGRESS', {'step': 1, 'phase': 'stt'})
                transcription = stt.transcribe_audio(wav_audio_path)
                t_stt = time.perf_counter() - t_stt_start
                
                words = getattr(transcription, 'words', [])
                if not words and isinstance(transcription, dict):
                    words = transcription.get('words', [])
                
                if not words:
                    words = getattr(transcription, 'segments', [])
                    if not words and isinstance(transcription, dict):
                        words = transcription.get('segments', [])

                # 4. Pyannote による話者分離（変換した wav_audio_path を使う）
                t_diar_start = time.perf_counter()
                safe_update_state(self, 'PROGRESS', {'step': 2, 'phase': 'diarization'})
                diarization_segments = diarization.diarize_audio(wav_audio_path)
                t_diarize = time.perf_counter() - t_diar_start

                # 5. 単語レベルのタイムスタンプ・マージ ＆ 6. LLM 役割同定
                t_role_start = time.perf_counter()
                merged_segments = llm_analysis.merge_whisper_and_diarization(words, diarization_segments)
                final_segments = llm_analysis.identify_roles_by_llm(merged_segments)
                t_role = time.perf_counter() - t_role_start

                t_total = time.perf_counter() - t_start
                print(f"[Performance Profile] Record #{record_id} (Transcribe & Diarize): "
                      f"Convert={t_convert:.2f}s, STT={t_stt:.2f}s, Diarize={t_diarize:.2f}s, "
                      f"RoleID={t_role:.2f}s, Total={t_total:.2f}s")

                # 7. DBクリア & 保存
                record.transcripts.clear()
                for seg in final_segments:
                    db.add(models.Transcript(
                        call_record_id=record_id,
                        speaker=str(seg["speaker"]),
                        start_time=float(seg["start"]),
                        end_time=float(seg["end"]),
                        text=str(seg["text"])
                    ))
                await db.commit()

                return {
                    "status": "success",
                    "record_id": record_id,
                    "transcript_count": len(final_segments),
                    "execution_times": {
                        "convert_sec": round(t_convert, 3),
                        "stt_sec": round(t_stt, 3),
                        "diarize_sec": round(t_diarize, 3),
                        "role_id_sec": round(t_role, 3),
                        "total_sec": round(t_total, 3)
                    }
                }
            finally:
                # 使い終わった一時ファイルを両方とも削除
                if raw_audio_path and os.path.exists(raw_audio_path):
                    os.remove(raw_audio_path)
                if wav_audio_path and os.path.exists(wav_audio_path):
                    os.remove(wav_audio_path)

    try:
        return _run_async(_async_transcribe())
    except Exception as e:
        error_msg = f"文字起こし・話者分離処理でエラーが発生しました: {str(e)}"
        print(f"Task Error [transcribe_and_diarize_task]: {error_msg}")
        return {
            "status": "failure",
            "record_id": record_id,
            "error": error_msg
        }


@celery_app.task(bind=True, name="backend.tasks.score_record_task")
def score_record_task(self, record_id: int) -> Dict[str, Any]:
    async def _async_score() -> Dict[str, Any]:
        async with SessionLocal() as db:
            t_start = time.perf_counter()
            record = await crud.get_call_record(db, record_id=record_id)
            if not record:
                raise ValueError(f"Record ID {record_id} not found")

            stmt = select(models.Transcript).where(
                models.Transcript.call_record_id == record_id
            ).order_by(models.Transcript.start_time)
            res = await db.execute(stmt)
            transcripts = res.scalars().all()

            if not transcripts:
                raise ValueError(f"No transcripts found for record ID {record_id}")

            transcript_dicts = [{"speaker": t.speaker, "text": t.text} for t in transcripts]

            safe_update_state(self, 'PROGRESS', {'step': 3, 'phase': 'scoring'})
            analysis_data = llm_analysis.analyze_and_score_call(record_id, transcript_dicts)
            saved_result = await crud.create_or_update_analysis_result(db, analysis_data)
            t_score = time.perf_counter() - t_start

            print(f"[Performance Profile] Record #{record_id} (Scoring): ScoreTime={t_score:.2f}s")

            return {
                "status": "success",
                "record_id": record_id,
                "rank": saved_result.rank,
                "purchase_probability": saved_result.purchase_probability,
                "recommended_action": saved_result.recommended_action,
                "execution_times": {
                    "score_sec": round(t_score, 3)
                }
            }

    try:
        return _run_async(_async_score())
    except Exception as e:
        error_msg = f"AIスコアリング処理でエラーが発生しました: {str(e)}"
        print(f"Task Error [score_record_task]: {error_msg}")
        return {
            "status": "failure",
            "record_id": record_id,
            "error": error_msg
        }


@celery_app.task(bind=True, name="backend.tasks.full_pipeline_task")
def full_pipeline_task(self, record_id: int) -> Dict[str, Any]:
    t_start = time.perf_counter()
    try:
        safe_update_state(self, 'PROGRESS', {'step': 1, 'phase': 'stt'})
        t_res = transcribe_and_diarize_task(record_id)
        if isinstance(t_res, dict) and t_res.get("status") == "failure":
            return {
                "status": "failure",
                "record_id": record_id,
                "error": t_res.get("error", "文字起こし処理に失敗しました。")
            }
        safe_update_state(self, 'PROGRESS', {'step': 3, 'phase': 'scoring'})
        s_res = score_record_task(record_id)
        if isinstance(s_res, dict) and s_res.get("status") == "failure":
            return {
                "status": "failure",
                "record_id": record_id,
                "transcribe_result": t_res,
                "error": s_res.get("error", "AIスコアリングに失敗しました。")
            }
        t_total = time.perf_counter() - t_start
        print(f"[Performance Profile] Record #{record_id} (Full Pipeline Total): {t_total:.2f}s")

        return {
            "status": "success",
            "record_id": record_id,
            "transcribe_result": t_res,
            "score_result": s_res,
            "execution_times": {
                "full_pipeline_total_sec": round(t_total, 3)
            }
        }
    except Exception as e:
        error_msg = f"パイプライン実行中に予期せぬエラーが発生しました: {str(e)}"
        print(f"Task Error [full_pipeline_task]: {error_msg}")
        return {
            "status": "failure",
            "record_id": record_id,
            "error": error_msg
        }
