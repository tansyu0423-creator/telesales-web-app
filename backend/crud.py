from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

try:
    from . import models, schemas
except ImportError:
    import models, schemas

async def create_call_record(db: AsyncSession, record: schemas.CallRecordCreate):
    db_record = models.CallRecord(**record.model_dump())
    db.add(db_record)
    await db.commit()
    await db.refresh(db_record)
    return db_record

async def get_call_records(db: AsyncSession, skip: int = 0, limit: int = 100):
    result = await db.execute(select(models.CallRecord).offset(skip).limit(limit))
    return result.scalars().all()

async def get_call_record(db: AsyncSession, record_id: int):
    result = await db.execute(select(models.CallRecord).where(models.CallRecord.id == record_id))
    return result.scalars().first()

async def create_or_update_analysis_result(db: AsyncSession, analysis_data: schemas.AnalysisResultCreate):
    stmt = select(models.AnalysisResult).where(models.AnalysisResult.call_record_id == analysis_data.call_record_id)
    res = await db.execute(stmt)
    existing_result = res.scalars().first()

    if existing_result:
        update_data = analysis_data.model_dump(exclude={"call_record_id"})
        for key, value in update_data.items():
            setattr(existing_result, key, value)
        
        await db.commit()
        await db.refresh(existing_result)
        return existing_result
    else:
        db_analysis = models.AnalysisResult(**analysis_data.model_dump())
        db.add(db_analysis)
        await db.commit()
        await db.refresh(db_analysis)
        return db_analysis
