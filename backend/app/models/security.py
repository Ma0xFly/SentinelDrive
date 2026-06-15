from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import AlertStatus, RiskLevel, enum_values
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        Index("ix_users_email", "email", unique=True),
        Index("ix_users_is_active", "is_active"),
    )

    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    audit_events = relationship("AuditEvent", back_populates="actor")
    export_jobs = relationship("ExportJob", back_populates="requested_by")


class Alert(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index("ix_alerts_intelligence_id", "threat_intelligence_id"),
        Index("ix_alerts_risk_status", "risk_level", "status"),
        Index("ix_alerts_triggered_at", "triggered_at"),
    )

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    threat_intelligence_id: Mapped[UUID] = mapped_column(
        ForeignKey("threat_intelligence.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggering_rule: Mapped[str] = mapped_column(String(240), nullable=False)
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", values_callable=enum_values),
        nullable=False,
    )
    triggered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alert_status", values_callable=enum_values),
        default=AlertStatus.OPEN,
        nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    intelligence = relationship("ThreatIntelligence", back_populates="alerts")
