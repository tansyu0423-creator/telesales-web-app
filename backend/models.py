from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship, Mapped, mapped_column
try:
    from .database import Base
except ImportError:
    from database import Base
from datetime import datetime, timezone
from typing import List, Optional

class CallRecord(Base):
    __tablename__ = "call_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sales_code: Mapped[str] = mapped_column(String(50), index=True) 
    customer_phone: Mapped[str] = mapped_column(String(20))         
    call_duration: Mapped[int] = mapped_column(Integer)             
    audio_file_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)       
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    transcripts: Mapped[List["Transcript"]] = relationship("Transcript", back_populates="call_record", cascade="all, delete-orphan", lazy="selectin", order_by="Transcript.start_time")
    analysis: Mapped[Optional["AnalysisResult"]] = relationship("AnalysisResult", back_populates="call_record", uselist=False, lazy="selectin")

class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    call_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("call_records.id"))
    speaker: Mapped[str] = mapped_column(String(20)) 
    text: Mapped[str] = mapped_column(Text)          
    start_time: Mapped[float] = mapped_column(Float)   
    end_time: Mapped[float] = mapped_column(Float)     

    call_record: Mapped["CallRecord"] = relationship("CallRecord", back_populates="transcripts")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    call_record_id: Mapped[int] = mapped_column(Integer, ForeignKey("call_records.id"), unique=True)
    rank: Mapped[str] = mapped_column(String(5))             
    purchase_probability: Mapped[float] = mapped_column(Float) 
    customer_interest: Mapped[str] = mapped_column(Text)     
    concerns: Mapped[str] = mapped_column(Text)              
    recommended_action: Mapped[str] = mapped_column(Text)    

    call_record: Mapped["CallRecord"] = relationship("CallRecord", back_populates="analysis")