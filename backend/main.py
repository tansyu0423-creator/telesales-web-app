import os
import tempfile
import uuid
import csv
import io
from typing import List

from fastapi import FastAPI, Depends, HTTPException, File, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select  
from minio import Minio
from minio.error import S3Error
from celery.result import AsyncResult

try:
    from . import models, schemas, crud, stt, llm_analysis, diarization, summary_analysis, tasks
    from .celery_app import celery_app
    from .config import settings
    from .database import SessionLocal
except ImportError:
    import models, schemas, crud, stt, llm_analysis, diarization, summary_analysis, tasks
    from celery_app import celery_app
    from config import settings
    from database import SessionLocal

app = FastAPI(title="Telesales Lead Scoring System", version="0.1.0")

# CORSミドルウェアの設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------
# MinIOクライアントの設定
# ---------------------------------------------
minio_client = Minio(
    settings.minio_endpoint,
    access_key=settings.minio_access_key,
    secret_key=settings.minio_secret_key,
    secure=settings.minio_secure
)

def ensure_bucket_exists(bucket_name: str):
    try:
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
    except Exception as e:
        print(f"Warning: MinIO bucket check/creation failed: {e}")

# データベースセッションを取得する関数
async def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        await db.close()

@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/records/", response_model=schemas.CallRecord, tags=["Call Records"])
async def create_record(record: schemas.CallRecordCreate, db: AsyncSession = Depends(get_db)):
    """新しい通話データを登録するAPI"""
    return await crud.create_call_record(db=db, record=record)

@app.get("/records/", response_model=List[schemas.CallRecord], tags=["Call Records"])
async def read_records(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """通話データの一覧を取得するAPI"""
    return await crud.get_call_records(db, skip=skip, limit=limit)

@app.get("/records/{record_id}", response_model=schemas.CallRecord, tags=["Call Records"])
async def read_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """指定したIDの通話データを取得するAPI"""
    db_record = await crud.get_call_record(db, record_id=record_id)
    if db_record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return db_record

# ---------------------------------------------
# 音声ファイルアップロードAPIを追加
# ---------------------------------------------
@app.post("/upload/", tags=["Audio Upload"])
async def upload_audio(file: UploadFile = File(...)):
    """音声ファイルをMinIOにアップロードするAPI"""
    if not file.filename or not file.filename.lower().endswith(('.wav', '.mp3')):
        raise HTTPException(status_code=400, detail="許可されているのは .wav または .mp3 のみです")

    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    try:
        ensure_bucket_exists(settings.minio_bucket_name)
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        content_type = file.content_type or ("audio/mpeg" if file_extension.lower() == "mp3" else "audio/wav")

        minio_client.put_object(
            bucket_name=settings.minio_bucket_name,
            object_name=unique_filename,
            data=file.file,
            length=file_size,
            content_type=content_type
        )

        return {
            "message": "ファイルのアップロードに成功しました",
            "original_filename": file.filename,
            "saved_filename": unique_filename
        }
    except S3Error as e:
        raise HTTPException(status_code=500, detail=f"ストレージエラー: {str(e)}")

# ---------------------------------------------
# 音声ファイルストリーミング再生APIを追加
# ---------------------------------------------
@app.get("/audio/{filename}", tags=["Audio Stream"])
def stream_audio(filename: str):
    """MinIOから音声ファイルをダウンロード/ストリーミング再生するAPI"""
    try:
        response = minio_client.get_object(settings.minio_bucket_name, filename)
        content_type = response.headers.get("content-type") or ("audio/mpeg" if filename.endswith(".mp3") else "audio/wav")
        return StreamingResponse(response.stream(32 * 1024), media_type=content_type)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"音声ファイルが見つかりません: {str(e)}")

# ---------------------------------------------
# Day 5: Whisper STT ＋ Pyannote 話者分離マージ ＋ LLM 役割構造化API
# ---------------------------------------------
@app.post("/records/{record_id}/transcribe", status_code=status.HTTP_202_ACCEPTED, tags=["STT & Diarization"])
async def transcribe_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """指定した通話レコードの音声を Whisper STT ＋ Pyannote 話者分離でマージし、LLM役割判定して保存する非同期API"""
    record = await crud.get_call_record(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    filename = record.audio_file_path
    if not filename:
        raise HTTPException(status_code=400, detail="このレコードには音声ファイルが紐づいていません")

    task = tasks.transcribe_and_diarize_task.delay(record_id)
    return {
        "status": "processing",
        "task_id": task.id,
        "message": "Whisper STT ＋ Pyannote話者分離 ＋ LLM役割構造化処理をバックグラウンドで開始しました",
        "record_id": record_id
    }



# ---------------------------------------------
# 分析レポートCSVエクスポートAPIを追加
# ---------------------------------------------
@app.get("/records/{record_id}/export/csv", tags=["Export"])
async def export_record_csv(record_id: int, db: AsyncSession = Depends(get_db)):
    """通話履歴、話者付き文字起こし、スコアリング結果をCSVとしてダウンロードするAPI"""
    
    # 1. レコード、文字起こし、分析結果を取得
    record = await crud.get_call_record(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    stmt_transcripts = select(models.Transcript).where(
        models.Transcript.call_record_id == record_id
    ).order_by(models.Transcript.start_time)
    res_transcripts = await db.execute(stmt_transcripts)
    transcripts = res_transcripts.scalars().all()

    stmt_analysis = select(models.AnalysisResult).where(
        models.AnalysisResult.call_record_id == record_id
    )
    res_analysis = await db.execute(stmt_analysis)
    analysis = res_analysis.scalars().first()

    # 2. CSVデータをメモリ上で作成
    stream = io.StringIO()
    writer = csv.writer(stream)

    # --- メタデータ・分析結果セクション ---
    writer.writerow(["=== 通話分析レポート ==="])
    writer.writerow(["レコードID", record.id])
    writer.writerow(["営業コード", record.sales_code])
    writer.writerow(["電話番号", record.customer_phone])
    writer.writerow([])
    
    if analysis:
        writer.writerow(["=== AI スコアリング結果 ==="])
        writer.writerow(["ランク", analysis.rank])
        writer.writerow(["購買確率(%)", analysis.purchase_probability])
        writer.writerow(["顧客の関心点", analysis.customer_interest])
        writer.writerow(["懸念点", analysis.concerns])
        writer.writerow(["推奨アクション", analysis.recommended_action])
    else:
        writer.writerow(["=== AI スコアリング結果 ==="])
        writer.writerow(["AI分析", "未実行"])

    writer.writerow([])
    writer.writerow(["=== 文字起こし (対話ログ) ==="])
    writer.writerow(["時間", "話者", "発言内容"])
    
    for t in transcripts:
        time_str = f"{t.start_time:.1f}s - {t.end_time:.1f}s"
        writer.writerow([time_str, t.speaker, t.text])

    # 3. レスポンスとしてストリーミングで返す（BOMを付与してExcelの文字化けを防ぐ）
    # ※ UTF-8 with BOM にしてExcelでそのまま開けるようにします
    csv_content = "\ufeff" + stream.getvalue()
    
    response = StreamingResponse(iter([csv_content]), media_type="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f"attachment; filename=report_{record_id}.csv"
    
    return response

@app.post("/records/{record_id}/summarize", tags=["Analysis"])
async def summarize_record(record_id: int, db: AsyncSession = Depends(get_db)):
    record = await crud.get_call_record(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="指定されたレコードが見つかりません")

    stmt = select(models.Transcript).where(
        models.Transcript.call_record_id == record_id
    ).order_by(models.Transcript.start_time)
    res = await db.execute(stmt)
    transcripts = res.scalars().all()
    
    if not transcripts:
        raise HTTPException(status_code=400, detail="この通話にはまだ文字起こしデータが存在しません")

    transcript_dicts = [
        {
            "speaker": t.speaker,
            "text": t.text
        }
        for t in transcripts
    ]

    try:
        analysis_result = summary_analysis.summarize_call(transcript_dicts)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI分析中にエラーが発生しました: {str(e)}")

    return {
        "status": "success",
        "record_id": record_id,
        "analysis": analysis_result
    }

@app.post("/records/{record_id}/score", status_code=status.HTTP_202_ACCEPTED, tags=["Analysis"])
async def score_record(record_id: int, db: AsyncSession = Depends(get_db)):
    record = await crud.get_call_record(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="指定されたレコードが見つかりません")

    stmt = select(models.Transcript).where(
        models.Transcript.call_record_id == record_id
    ).order_by(models.Transcript.start_time)
    res = await db.execute(stmt)
    transcripts = res.scalars().all()
    
    if not transcripts:
        raise HTTPException(status_code=400, detail="この通話にはまだ文字起こしデータが存在しません")

    task = tasks.score_record_task.delay(record_id)
    return {
        "status": "processing",
        "task_id": task.id,
        "message": "AIスコアリング処理をバックグラウンドで開始しました",
        "record_id": record_id
    }

@app.post("/records/{record_id}/pipeline", status_code=status.HTTP_202_ACCEPTED, tags=["Pipeline"])
async def run_pipeline_record(record_id: int, db: AsyncSession = Depends(get_db)):
    record = await crud.get_call_record(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="指定されたレコードが見つかりません")

    task = tasks.full_pipeline_task.delay(record_id)
    return {
        "status": "processing",
        "task_id": task.id,
        "message": "文字起こしからAIスコアリングまでの全自動パイプラインをバックグラウンドで開始しました",
        "record_id": record_id
    }

@app.get("/tasks/{task_id}", tags=["Task Status"])
def get_task_status(task_id: str):
    """Celeryバックグラウンドタスクの実行ステータスを確認するAPI"""
    task_result = AsyncResult(task_id, app=celery_app)
    response = {
        "task_id": task_id,
        "status": task_result.state,
    }
    if task_result.ready():
        if task_result.successful():
            response["result"] = task_result.result
        else:
            response["error"] = str(task_result.result)
    return response