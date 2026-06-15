from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import (
    AttackSurface,
    ConfidenceLevel,
    ExploitStatus,
    IntelligenceType,
    ProcessingStatus,
    RiskLevel,
    Severity,
    SourceType,
    VehicleComponent,
    enum_values,
)
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class RawIntelligence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "raw_intelligence"
    __table_args__ = (
        UniqueConstraint("raw_hash", name="uq_raw_intelligence_raw_hash"),
        UniqueConstraint("source_id", "external_id", name="uq_raw_intelligence_source_external_id"),
        Index("ix_raw_intelligence_source_fetch", "source_id", "fetched_at"),
        Index("ix_raw_intelligence_status_parsing", "processing_status", "parsing_status"),
        Index("ix_raw_intelligence_source_url", "source_url"),
    )

    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="source_type", values_callable=enum_values),
        nullable=False,
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(240))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str | None] = mapped_column(String(500))
    summary: Mapped[str | None] = mapped_column(Text)
    snippet: Mapped[str | None] = mapped_column(Text)
    raw_content: Mapped[dict | None] = mapped_column(JSONB)
    raw_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(128))
    parsing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status", values_callable=enum_values),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status", values_callable=enum_values),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    retained_payload_mode: Mapped[str] = mapped_column(String(40), default="metadata_only", nullable=False)

    source = relationship("Source", back_populates="raw_items")
    normalized_records = relationship("ThreatIntelligence", back_populates="raw_item")


class ThreatIntelligence(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "threat_intelligence"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_threat_intelligence_dedup_key"),
        Index("ix_threat_intelligence_cve_id", "cve_id"),
        Index("ix_threat_intelligence_cwe_id", "cwe_id"),
        Index("ix_threat_intelligence_risk_status", "risk_level", "processing_status"),
        Index("ix_threat_intelligence_seen", "first_seen_at", "last_seen_at"),
        Index("ix_threat_intelligence_vendor_product", "affected_vendor", "affected_product"),
        Index("ix_threat_intelligence_component", "vehicle_component"),
        Index("ix_threat_intelligence_attack_surface", "attack_surface"),
        Index("ix_threat_intelligence_tags", "tags", postgresql_using="gin"),
        Index("ix_threat_intelligence_search", "search_vector", postgresql_using="gin"),
    )

    raw_intelligence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("raw_intelligence.id", ondelete="SET NULL")
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    intelligence_type: Mapped[IntelligenceType] = mapped_column(
        Enum(IntelligenceType, name="intelligence_type", values_callable=enum_values),
        nullable=False,
    )
    source_names: Mapped[list[str]] = mapped_column(ARRAY(String(160)), default=list, nullable=False)
    source_urls: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, nullable=False)
    canonical_source_url: Mapped[str | None] = mapped_column(Text)
    external_ids: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    cve_id: Mapped[str | None] = mapped_column(String(32))
    cwe_id: Mapped[str | None] = mapped_column(String(32))
    cvss_score: Mapped[float | None] = mapped_column(Float)
    cvss_vector: Mapped[str | None] = mapped_column(String(160))
    severity: Mapped[Severity] = mapped_column(
        Enum(Severity, name="severity", values_callable=enum_values),
        default=Severity.UNKNOWN,
        nullable=False,
    )
    affected_vendor: Mapped[str | None] = mapped_column(String(160))
    affected_product: Mapped[str | None] = mapped_column(String(200))
    affected_version: Mapped[str | None] = mapped_column(String(200))
    vehicle_component: Mapped[VehicleComponent | None] = mapped_column(
        Enum(VehicleComponent, name="vehicle_component", values_callable=enum_values)
    )
    attack_surface: Mapped[AttackSurface | None] = mapped_column(
        Enum(AttackSurface, name="attack_surface", values_callable=enum_values)
    )
    exploit_status: Mapped[ExploitStatus] = mapped_column(
        Enum(ExploitStatus, name="exploit_status", values_callable=enum_values),
        default=ExploitStatus.UNKNOWN,
        nullable=False,
    )
    confidence: Mapped[ConfidenceLevel] = mapped_column(
        Enum(ConfidenceLevel, name="confidence_level", values_callable=enum_values),
        default=ConfidenceLevel.MEDIUM,
        nullable=False,
    )
    risk_score: Mapped[float | None] = mapped_column(Numeric(5, 2))
    risk_level: Mapped[RiskLevel] = mapped_column(
        Enum(RiskLevel, name="risk_level", values_callable=enum_values),
        default=RiskLevel.INFO,
        nullable=False,
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(80)), default=list, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    dedup_key: Mapped[str] = mapped_column(String(320), nullable=False)
    normalized_text_hash: Mapped[str | None] = mapped_column(String(128))
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus, name="processing_status", values_callable=enum_values),
        default=ProcessingStatus.PENDING,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(40), default="active", nullable=False)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR)
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)

    raw_item = relationship("RawIntelligence", back_populates="normalized_records")
    source_links = relationship("ThreatIntelligenceSource", back_populates="intelligence")
    alerts = relationship("Alert", back_populates="intelligence")


class ThreatIntelligenceSource(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "threat_intelligence_sources"
    __table_args__ = (
        UniqueConstraint("threat_intelligence_id", "source_url", name="uq_threat_intelligence_sources_url"),
        Index("ix_threat_intelligence_sources_source_name", "source_name"),
        Index("ix_threat_intelligence_sources_external_id", "external_id"),
    )

    threat_intelligence_id: Mapped[UUID] = mapped_column(
        ForeignKey("threat_intelligence.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_id: Mapped[UUID | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))
    raw_intelligence_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("raw_intelligence.id", ondelete="SET NULL")
    )
    source_name: Mapped[str] = mapped_column(String(160), nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(240))
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    intelligence = relationship("ThreatIntelligence", back_populates="source_links")
