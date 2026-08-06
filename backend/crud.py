# 変更点: 同期の Session ではなく、非同期の AsyncSession をインポート
from sqlalchemy.ext.asyncio import AsyncSession
# 変更点: db.query() の代わりに select を使うためのインポート
from sqlalchemy import select

import models, schemas

# 通話記録の作成 (Create) - これはバッチリです！型の部分だけ変更しました
async def create_call_record(db: AsyncSession, record: schemas.CallRecordCreate):
    # Pydanticモデルを辞書型に変換(model_dump)してDBモデルに渡す (v2の書き方)
    db_record = models.CallRecord(**record.model_dump())
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return db_record

# 通話記録の一覧取得 (Read) - async化 & select構文に変更
async def get_call_records(db: AsyncSession, skip: int = 0, limit: int = 100):
    # 非同期では db.query() が使えないため、select を使って await db.execute() で実行します
    result = await db.execute(select(models.CallRecord).offset(skip).limit(limit))
    return result.scalars().all()

# 特定の通話記録をIDで取得 (Read) - async化 & select構文に変更
async def get_call_record(db: AsyncSession, record_id: int):
    result = await db.execute(select(models.CallRecord).where(models.CallRecord.id == record_id))
    return result.scalars().first()