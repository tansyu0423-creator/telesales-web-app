from fastapi import FastAPI, Depends, HTTPException
# 変更点: 同期の Session ではなく、非同期の AsyncSession をインポート
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List

import models, schemas, crud
from database import SessionLocal, engine

app = FastAPI(title="Telesales Lead Scoring System", version="0.1.0")

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

# 変更点: 関数を async def にし、crudの呼び出しに await を追加
@app.get("/records/", response_model=List[schemas.CallRecord], tags=["Call Records"])
async def read_records(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    """通話データの一覧を取得するAPI"""
    return await crud.get_call_records(db, skip=skip, limit=limit)

# 変更点: 関数を async def にし、crudの呼び出しに await を追加
@app.get("/records/{record_id}", response_model=schemas.CallRecord, tags=["Call Records"])
async def read_record(record_id: int, db: AsyncSession = Depends(get_db)):
    """指定したIDの通話データを取得するAPI"""
    db_record = await crud.get_call_record(db, record_id=record_id)
    if db_record is None:
        raise HTTPException(status_code=404, detail="Record not found")
    return db_record