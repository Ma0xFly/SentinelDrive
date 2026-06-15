from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import ExportFormat, ExportStatus, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class ExportJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "export_jobs"
    __table_args__ = (
        Index("ix_export_jobs_requested_by_status", "requested_by_user_id", "status"),
        Index("ix_export_jobs_format_status", "export_format", "status"),
        Index("ix_export_jobs_created_at", "created_at"),
    )

    requested_by_user_id: Mapped[UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    export_format: Mapped[ExportFormat] = mapped_column(
        Enum(ExportFormat, name="export_format", values_callable=enum_values),
        nullable=False,
    )
    status: Mapped[ExportStatus] = mapped_column(
        Enum(ExportStatus, name="export_status", values_callable=enum_values),
        default=ExportStatus.PENDING,
        nullable=False,
    )
    filter_spec: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    artifact_path: Mapped[str | None] = mapped_column(Text)
    artifact_hash: Mapped[str | None] = mapped_column(String(128))
    redaction_summary: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    requested_by = relationship("User", back_populates="export_jobs")
