from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from sqlalchemy import Select, case, select, update
from sqlalchemy.orm import Session

from sentineldrive_worker.persistence.database import create_engine_from_url, create_session_factory
from sentineldrive_worker.persistence.tables import threat_intelligence
from sentineldrive_worker.scoring.rules import ScoringResult, score_threat_intelligence


@dataclass
class ScoringService:
    session_factory: Callable[[], Session]

    def score_pending(self, *, limit: int = 100, force: bool = False) -> dict[str, Any]:
        with self.session_factory() as session:
            rows = list(session.execute(scoring_candidate_query(limit, force=force)).mappings().all())

        records: list[dict[str, Any]] = []
        for row in rows:
            with self.session_factory() as session:
                try:
                    refreshed = session.execute(
                        select(threat_intelligence).where(threat_intelligence.c.id == row["id"])
                    ).mappings().one_or_none()
                    if refreshed is None:
                        records.append({"threat_intelligence_id": str(row["id"]), "status": "missing"})
                        continue
                    records.append(self.score_row(session, refreshed, force=force))
                    session.commit()
                except Exception as exc:
                    session.rollback()
                    records.append(
                        {
                            "threat_intelligence_id": str(row["id"]),
                            "status": "failed",
                            "error_message": sanitize_error(exc),
                        }
                    )

        return {
            "status": "completed",
            "rows_seen": len(rows),
            "scored": sum(1 for record in records if record["status"] == "scored"),
            "unchanged": sum(1 for record in records if record["status"] == "unchanged"),
            "failed": sum(1 for record in records if record["status"] == "failed"),
            "records": records,
        }

    def score_row(self, session: Session, row: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
        result = score_threat_intelligence(row)
        metadata = metadata_with_scoring(row.get("metadata"), result)
        if scoring_is_current(row, result, metadata):
            return {
                "threat_intelligence_id": str(row["id"]),
                "status": "unchanged",
                "risk_score": result.risk_score,
                "risk_level": result.risk_level,
            }

        session.execute(
            update(threat_intelligence)
            .where(threat_intelligence.c.id == row["id"])
            .values(
                risk_score=result.risk_score,
                risk_level=result.risk_level,
                metadata=metadata,
                updated_at=datetime.now(timezone.utc),
            )
        )
        return {
            "threat_intelligence_id": str(row["id"]),
            "status": "scored",
            "risk_score": result.risk_score,
            "risk_level": result.risk_level,
        }


def score_pending_threat_intelligence(
    *,
    limit: int = 100,
    force: bool = False,
    session_factory: Callable[[], Session] | None = None,
    database_url: str | None = None,
) -> dict[str, Any]:
    factory = session_factory
    if factory is None:
        engine = create_engine_from_url(database_url)
        factory = create_session_factory(engine)
    return ScoringService(factory).score_pending(limit=limit, force=force)


def scoring_candidate_query(limit: int, *, force: bool = False) -> Select:
    priority = case(
        (threat_intelligence.c.risk_score.is_(None), 0),
        (threat_intelligence.c.risk_level == "info", 1),
        else_=2,
    )
    query = (
        select(threat_intelligence)
        .where(threat_intelligence.c.processing_status == "normalized")
        .order_by(priority, threat_intelligence.c.updated_at.asc(), threat_intelligence.c.created_at.asc())
        .limit(limit)
    )
    if force:
        return query
    return query.where(threat_intelligence.c.risk_score.is_(None) | (threat_intelligence.c.risk_level == "info"))


def metadata_with_scoring(value: object, result: ScoringResult) -> dict[str, Any]:
    metadata = dict(value) if isinstance(value, dict) else {}
    metadata["scoring"] = result.explanation
    return metadata


def scoring_is_current(row: dict[str, Any], result: ScoringResult, metadata: dict[str, Any]) -> bool:
    existing_metadata = dict(row.get("metadata") or {})
    return (
        numeric_equal(row.get("risk_score"), result.risk_score)
        and row.get("risk_level") == result.risk_level
        and existing_metadata.get("scoring") == metadata.get("scoring")
    )


def numeric_equal(value: object, expected: float) -> bool:
    try:
        return abs(float(value) - expected) < 0.005
    except (TypeError, ValueError):
        return False


def sanitize_error(error: BaseException) -> str:
    text = str(error) or error.__class__.__name__
    text = re.sub(
        r"(?i)(api[_-]?key|authorization|password|secret|token)\s*[:=]\s*[^&\s]+",
        "[redacted]=[redacted]",
        text,
    )
    text = re.sub(r"(?i)api[_-]?key|authorization|password|secret|token", "[redacted]", text)
    return text[:500]
