import os
import tempfile
from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
import uuid

from minio import Minio
from minio.error import S3Error

try:
    from . import models, schemas, crud, stt
    from .config import settings
    from .database import SessionLocal
except ImportError:
    import models, schemas, crud, stt
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
    # 1. ファイル形式の簡易バリデーション
    if not file.filename or not file.filename.lower().endswith(('.wav', '.mp3')):
        raise HTTPException(status_code=400, detail="許可されているのは .wav または .mp3 のみです")

    # 2. 保存用のユニークなファイル名を生成（例: 123e4567-e89b... .wav）
    file_extension = file.filename.split('.')[-1]
    unique_filename = f"{uuid.uuid4()}.{file_extension}"

    try:
        ensure_bucket_exists(settings.minio_bucket_name)

        # ファイルのサイズを取得（MinIOの要件）
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        content_type = file.content_type or ("audio/mpeg" if file_extension.lower() == "mp3" else "audio/wav")

        # MinIOのバケットに保存
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
from fastapi.responses import StreamingResponse

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
# 文字起こし(STT)APIを追加
# ---------------------------------------------
@app.post("/records/{record_id}/transcribe", tags=["STT"])
async def transcribe_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """指定した通話レコードの音声を文字起こしして保存するAPI"""
    # 1. DBから対象の通話レコードを取得
    record = await crud.get_call_record(db, record_id=record_id)
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")

    # ⚠️ 注意: record.audio_file_path の部分は、
    # models.py で定義した「ファイル名が保存されているカラム名」に合わせて変更してください。
    # 例: record.file_name, record.audio_url など
    filename = str(record.audio_file_path) 
    
    if not filename:
        raise HTTPException(status_code=400, detail="このレコードには音声ファイルが紐づいていません")

    temp_audio_path = ""
    try:
        # 2. MinIOから音声データを取得し、一時ファイルに保存
        response = minio_client.get_object(settings.minio_bucket_name, filename)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            for data in response.stream(32*1024):
                temp_audio.write(data)
            temp_audio_path = temp_audio.name
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio download failed: {str(e)}")
    finally:
        if 'response' in locals():
            response.close()
            response.release_conn()

    try:
        # 3. Groq API を呼び出して文字起こしを実行
        transcription = stt.transcribe_audio(temp_audio_path)
        
        # 4. 取得した文字起こしデータ（セグメント）をDBに保存
        for segment in transcription.segments:
            # 辞書(dict)とオブジェクトの両方に対応
            if isinstance(segment, dict):
                start = segment.get("start", 0.0)
                end = segment.get("end", 0.0)
                text = segment.get("text", "").strip()
            else:
                start = getattr(segment, "start", 0.0)
                end = getattr(segment, "end", 0.0)
                text = getattr(segment, "text", "").strip()
            transcript_data = models.Transcript(
                call_record_id=record_id,
                speaker="Customer", # Whisper単体では話者分離がないため一旦固定
                start_time=float(start),
                end_time=float(end),
                text=text
            )
            db.add(transcript_data)
        
        await db.commit()

    except Exception as e:
        await db.rollback() # エラー時はDBへの保存をキャンセル
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    finally:
        # 5. 使い終わった一時ファイルを確実に削除
        if temp_audio_path and os.path.exists(temp_audio_path):
            os.remove(temp_audio_path)

    return {"status": "success", "message": "文字起こしが完了しました", "record_id": record_id}