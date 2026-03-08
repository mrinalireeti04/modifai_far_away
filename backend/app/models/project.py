from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Text, ForeignKey, Enum
from app.models.base import Base, TimestampMixin
import enum


class ProjectStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStepName(str, enum.Enum):
    UPLOAD = "upload"
    OCR = "ocr"
    CHUNKING = "chunking"
    DATASET_GEN = "dataset_gen"
    QUALITY_CONTROL = "quality_control"
    FINE_TUNING = "fine_tuning"
    DEPLOYMENT = "deployment"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Project(Base, TimestampMixin):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus), default=ProjectStatus.PENDING
    )
    
    # S3 and Model Config
    mode: Mapped[str] = mapped_column(String, default="full")
    s3_prefix: Mapped[str | None] = mapped_column(String, nullable=True)
    base_model: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # Pipeline execution
    intent: Mapped[str | None] = mapped_column(String, nullable=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # Serialized JSON config
    execution_arn: Mapped[str | None] = mapped_column(String, nullable=True)  # Step Functions ARN
    
    # Relationships
    steps: Mapped[list["PipelineStep"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class PipelineStep(Base, TimestampMixin):
    __tablename__ = "pipeline_steps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    step_name: Mapped[PipelineStepName] = mapped_column(Enum(PipelineStepName))
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus), default=StepStatus.PENDING)
    
    logs: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for metadata

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="steps")
