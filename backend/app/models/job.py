from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import JobStatus, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class JobLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "job_logs"
    __table_args__ = (
        Index("ix_job_logs_source_status_started", "source_id", "status", "started_at"),
        Index("ix_job_logs_job_name_status", "job_name", "status"),
    )

    job_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus, name="job_status", values_callable=enum_values),
        default=JobStatus.QUEUED,
        nullable=False,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    items_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_created: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    items_updated: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
