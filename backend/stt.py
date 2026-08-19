import os
import wave
import tempfile
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

groq_api_key = os.getenv("GROQ_API_KEY")
client = Groq(api_key=groq_api_key, timeout=30.0) if groq_api_key else None


PROMPT_TEXT = "営業担当者と顧客による電話セールス対話の文字起こしです。日本語の標準的なビジネス会話として、誤漢字・言い淀み・発音崩れ（例：今ちょっと、コミュニケーション、ウェアラブル、生体情報）を正確な標準日本語表記で認識し、文字起こしを行ってください。"


def transcribe_audio(file_path: str):
    """
    Groq APIを利用して文字起こしを実行する。
    25MBのファイルサイズ制限を回避するため、長時間の音声は自動的に10分ごとに分割処理する。
    """
    CHUNK_LENGTH_SEC = 120  # 2分 (Whisperのデコーダー長文スキップを完全防止する最適チャンク幅)
    
    if not client:
        raise RuntimeError("GROQ_API_KEY is not set.")

    with wave.open(file_path, 'rb') as wf:
        framerate = wf.getframerate()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        n_frames = wf.getnframes()
        total_duration = n_frames / float(framerate)
        
    # 2分以下の短いファイルの場合はそのまま処理
    if total_duration <= CHUNK_LENGTH_SEC:
        try:
            with open(file_path, "rb") as file:
                transcription = client.audio.transcriptions.create(
                    file=(os.path.basename(file_path), file.read()),
                    model="whisper-large-v3-turbo",
                    language="ja",
                    temperature=0.0,
                    prompt=PROMPT_TEXT,
                    response_format="verbose_json",
                    timestamp_granularities=["word", "segment"]
                )
            return transcription
        except Exception as e:
            print(f"Groq Whisper STT Error: {e}")
            raise e

    # 2分を超える場合はチャンク分割処理
    print(f"Audio duration ({total_duration:.1f}s) exceeds limit. Splitting into chunks...")
    all_words = []
    all_segments = []
    current_frame = 0
    frames_per_chunk = CHUNK_LENGTH_SEC * framerate
    chunk_index = 0
    
    with wave.open(file_path, 'rb') as wf:
        while current_frame < n_frames:
            frames_to_read = min(frames_per_chunk, n_frames - current_frame)
            chunk_data = wf.readframes(frames_to_read)
            chunk_path = None
            
            try:
                # 切り出した音声を一時ファイルに保存
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_chunk:
                    chunk_path = temp_chunk.name
                    with wave.open(chunk_path, 'wb') as chunk_wf:
                        chunk_wf.setnchannels(n_channels)
                        chunk_wf.setsampwidth(sampwidth)
                        chunk_wf.setframerate(framerate)
                        chunk_wf.writeframes(chunk_data)
                
                # 分割したチャンクの文字起こし
                with open(chunk_path, "rb") as chunk_file:
                    chunk_transcription = client.audio.transcriptions.create(
                        file=(os.path.basename(chunk_path), chunk_file.read()),
                        model="whisper-large-v3-turbo",
                        language="ja",
                        temperature=0.0,
                        prompt=PROMPT_TEXT,
                        response_format="verbose_json",
                        timestamp_granularities=["word", "segment"]
                    )
                
                # タイムスタンプに「分割した分の時間（オフセット）」を加算して結合
                offset = chunk_index * CHUNK_LENGTH_SEC
                words = getattr(chunk_transcription, 'words', [])
                if not words and isinstance(chunk_transcription, dict):
                    words = chunk_transcription.get('words', [])
                    
                for w in words:
                    if isinstance(w, dict):
                        w['start'] += offset
                        w['end'] += offset
                        all_words.append(w)
                    else:
                        all_words.append({
                            'word': getattr(w, 'word', getattr(w, 'text', '')),
                            'start': getattr(w, 'start', 0.0) + offset,
                            'end': getattr(w, 'end', 0.0) + offset
                        })

                segs = getattr(chunk_transcription, 'segments', [])
                if not segs and isinstance(chunk_transcription, dict):
                    segs = chunk_transcription.get('segments', [])

                for s in segs:
                    if isinstance(s, dict):
                        s['start'] += offset
                        s['end'] += offset
                        all_segments.append(s)
                    else:
                        all_segments.append({
                            'text': getattr(s, 'text', ''),
                            'start': getattr(s, 'start', 0.0) + offset,
                            'end': getattr(s, 'end', 0.0) + offset
                        })
            except Exception as e:
                raise RuntimeError(
                    f"Chunk {chunk_index + 1} transcription failed"
                ) from e
            finally:
                if chunk_path and os.path.exists(chunk_path):
                    os.remove(chunk_path)  # 使い終わった分割ファイルを必ず削除
                
            current_frame += frames_to_read
            chunk_index += 1
            
    print("Chunk transcription complete.")
    # tasks.py でそのまま扱えるように辞書型で返す
    return {"words": all_words, "segments": all_segments}