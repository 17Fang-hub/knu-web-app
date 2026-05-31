from sqlalchemy import Column, Integer, String, DateTime, Float
from sqlalchemy.sql import func
from database import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, unique=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class ProcessingResult(Base):
    __tablename__ = "processing_results"

    id = Column(Integer, primary_key=True, index=True)
    source_filename = Column(String, nullable=False)
    classical_filename = Column(String, nullable=False)
    classical_time_ms = Column(Float, nullable=False)
    classical_snr = Column(Float, nullable=True)
    secondary_filename = Column(String, nullable=False)
    secondary_time_ms = Column(Float, nullable=False)
    secondary_snr = Column(Float, nullable=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
