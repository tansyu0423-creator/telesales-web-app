from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class AnalysisResultBase(BaseModel):
    rank: str = Field(..., description="S, A, B, C, D, Eのいずれか1文字")
    purchase_probability: int = Field(..., ge=0, le=100, description="0から100までの整数（%）")
    customer_interest: str = Field(..., description="顧客が示唆した関心点や評価しているポイント")
    concerns: str = Field(..., description="顧客の懸念点、反論、またはボトルネック")
    recommended_action: str = Field(..., description="営業担当者が次にとるべき具体的な推奨アクション")

class AnalysisScoreResponse(BaseModel):
    interest_score: int = Field(..., ge=0, le=25)
    need_score: int = Field(..., ge=0, le=25)
    action_score: int = Field(..., ge=0, le=25)
    risk_score: int = Field(..., ge=0, le=25)
    customer_interest: str
    concerns: str
    recommended_action: str

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

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    name: str
    role: str

class UserCreate(BaseModel):
    username: str
    password: str
    name: str
    role: str

class UserResponse(BaseModel):
    username: str
    name: str
    role: str
    passwords: List[str] = []

class RankThresholds(BaseModel):
    s_rank: int = 90
    a_rank: int = 70
    b_rank: int = 50
    c_rank: int = 30
    d_rank: int = 10

class SystemConfig(BaseModel):
    gemini_api_key: Optional[str] = ""
    groq_api_key: Optional[str] = ""
    openrouter_api_key: Optional[str] = ""
    llm_provider: str = "gemini"
    rank_thresholds: RankThresholds = RankThresholds()
    custom_prompt_instructions: Optional[str] = ""