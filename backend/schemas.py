from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- AnalysisResult (AI分析結果) ---
class AnalysisResultBase(BaseModel):
    rank: str
    purchase_probability: float
    customer_interest: Optional[str] = None
    concerns: Optional[str] = None
    recommended_action: Optional[str] = None

class AnalysisResult(AnalysisResultBase):
    id: int
    call_record_id: int
    
    # Pydantic v2のORMモード設定 (DBモデルを自動変換)
    model_config = ConfigDict(from_attributes=True)

# --- Transcript (文字起こし) ---
class TranscriptBase(BaseModel):
    speaker: str
    text: str
    start_time: float
    end_time: float

class Transcript(TranscriptBase):
    id: int
    call_record_id: int

    model_config = ConfigDict(from_attributes=True)

# --- CallRecord (通話記録) ---
class CallRecordBase(BaseModel):
    sales_code: str
    customer_phone: str
    call_duration: int
    audio_file_path: Optional[str] = None

class CallRecordCreate(CallRecordBase):
    pass

class CallRecord(CallRecordBase):
    id: int
    created_at: datetime
    # リレーション先のデータも一緒に取得できるようにする
    transcripts: List[Transcript] = []
    analysis: Optional[AnalysisResult] = None

    model_config = ConfigDict(from_attributes=True)