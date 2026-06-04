from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base


class Image(Base):
    __tablename__ = "images"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False, unique=True)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())


class ProcessingRun(Base):
    """
    Один запуск обробки зображення для конкретного рівня шуму σ.
    Sobel не залежить від α, тому його метрики зберігаються один раз тут;
    результати GL-Canny для кожного α — у дочірніх рядках DetectionResult.
    """
    __tablename__ = "processing_runs"

    id = Column(Integer, primary_key=True, index=True)
    source_filename = Column(String, nullable=False)
    sigma = Column(Float, nullable=False)

    # Метрики Sobel (один раз на запуск)
    sobel_filename = Column(String, nullable=False)
    sobel_edge_density = Column(Float, nullable=True)
    sobel_time_ms = Column(Float, nullable=False)

    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    detections = relationship(
        "DetectionResult",
        back_populates="run",
        cascade="all, delete-orphan",
        order_by="DetectionResult.alpha",
    )


class DetectionResult(Base):
    """Результат GL-Canny для одного значення α у межах запуску (σ фіксований)."""
    __tablename__ = "detection_results"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(
        Integer,
        ForeignKey("processing_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    alpha = Column(Float, nullable=False)

    # Метрики GL-Canny (залежать від α)
    gl_filename = Column(String, nullable=False)
    gl_edge_density = Column(Float, nullable=True)
    gl_time_ms = Column(Float, nullable=True)

    # Метрики порівняння GL-Canny (I1) vs Sobel (I2)
    der = Column(Float, nullable=True)
    dcr = Column(Float, nullable=True)
    dcs = Column(Float, nullable=True)

    run = relationship("ProcessingRun", back_populates="detections")
