from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class CallRecord(Base):
    __tablename__ = "call_records"

    id = Column(Integer, primary_key=True, index=True)
    sales_code = Column(String(50), index=True) 
    customer_phone = Column(String(20))         
    call_duration = Column(Integer)             
    audio_file_path = Column(String(255))       
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    transcripts = relationship("Transcript", back_populates="call_record")
    analysis = relationship("AnalysisResult", back_populates="call_record", uselist=False)

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    call_record_id = Column(Integer, ForeignKey("call_records.id"))
    speaker = Column(String(20)) 
    text = Column(Text)          
    start_time = Column(Float)   
    end_time = Column(Float)     

    call_record = relationship("CallRecord", back_populates="transcripts")

class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id = Column(Integer, primary_key=True, index=True)
    call_record_id = Column(Integer, ForeignKey("call_records.id"), unique=True)
    rank = Column(String(5))             
    purchase_probability = Column(Float) 
    customer_interest = Column(Text)     
    concerns = Column(Text)              
    recommended_action = Column(Text)    

    call_record = relationship("CallRecord", back_populates="analysis")