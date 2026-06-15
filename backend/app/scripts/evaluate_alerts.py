from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Any

from app.services.alerts import evaluate_and_create_alerts

SessionFactory = Callable[[], Any]
AlertEvaluator = Callable[..., list[Any]]


def evaluate_alerts(
    limit: int = 100,
    *,
    session_factory: SessionFactory | None = None,
    alert_evaluator: AlertEvaluator = evaluate_and_create_alerts,
) -> dict[str, int | list[str]]:
    factory = session_factory or default_session_factory()
    with factory() as session:
        created = alert_evaluator(session, limit=limit)
        session.commit()
        alert_ids = [str(alert.id) for alert in created]
    return {"evaluated": limit, "created": len(alert_ids), "alert_ids": alert_ids}


def default_session_factory() -> SessionFactory:
    from app.db.session import SessionLocal

    return SessionLocal


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate stored threat intelligence and create eligible alerts.")
    parser.add_argument("--limit", type=int, default=100, help="Maximum intelligence records to evaluate.")
    args = parser.parse_args()
    result = evaluate_alerts(limit=args.limit)
    print(f"Alert evaluation completed: created={result['created']} limit={result['evaluated']}")


if __name__ == "__main__":
    main()
