from sqlalchemy import Column, Integer, String, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
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

    # GL-Canny (fractional) results
    fractional_filename = Column(String, nullable=False)
    fractional_time_ms = Column(Float, nullable=False)
    fractional_alpha = Column(Float, nullable=True)
    fractional_edge_density = Column(Float, nullable=True)
    fractional_mean_edge_strength = Column(Float, nullable=True)
    fractional_num_components = Column(Integer, nullable=True)
    fractional_mean_component_length = Column(Float, nullable=True)
    fractional_fragmentation = Column(Float, nullable=True)
    fractional_contrast_ratio = Column(Float, nullable=True)

    # Sobel results
    sobel_filename = Column(String, nullable=False)
    sobel_time_ms = Column(Float, nullable=False)
    sobel_edge_density = Column(Float, nullable=True)
    sobel_mean_edge_strength = Column(Float, nullable=True)
    sobel_num_components = Column(Integer, nullable=True)
    sobel_mean_component_length = Column(Float, nullable=True)
    sobel_fragmentation = Column(Float, nullable=True)
    sobel_contrast_ratio = Column(Float, nullable=True)

    processed_at = Column(DateTime(timezone=True), server_default=func.now())

    # Noise-robustness rows are persisted together with the processed pair and
    # removed together with it (cascade on delete).
    noise_tests = relationship(
        "NoiseRobustnessTest",
        back_populates="result",
        cascade="all, delete-orphan",
        order_by="NoiseRobustnessTest.noise_sigma",
    )


class NoiseRobustnessTest(Base):
    __tablename__ = "noise_robustness_tests"

    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(
        Integer,
        ForeignKey("processing_results.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    noise_sigma = Column(Float, nullable=False)
    sobel_iou = Column(Float, nullable=True)
    gl_canny_iou = Column(Float, nullable=True)

    result = relationship("ProcessingResult", back_populates="noise_tests")
