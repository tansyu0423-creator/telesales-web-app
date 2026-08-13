from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class AnalysisResultBase(BaseModel):
    rank: str = Field(..., description="S, A, B, C, D, Eのいずれか1文字")
    purchase_probability: int = Field(..., ge=0, le=100, description="0から100までの整数（%）")
    customer_interest: str = Field(..., description="顧客が示唆した関心点や評価しているポイント")
    concerns: str = Field(..., description="顧客の懸念点、反論、またはボトルネック")
    recommended_action: str = Field(..., description="営業担当者が次にとるべき具体的な推奨アクション")

class AnalysisResultCreate(AnalysisResultBase):
    call_record_id: int

class AnalysisResult(AnalysisResultBase):
    id: int
    call_record_id: int

    model_config = ConfigDict(from_attributes=True)

class TranscriptBase(BaseModel):
    speaker: str
    text: str
    start_time: float
    end_time: float

class Transcript(TranscriptBase):
    id: int
    call_record_id: int

    model_config = ConfigDict(from_attributes=True)

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
    transcripts: List[Transcript] = []
    analysis: Optional[AnalysisResult] = None
    task_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)