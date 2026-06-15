from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.db.types import RiskLevel
from app.models.security import Alert
from app.scripts import evaluate_alerts


class ScriptAlertSession:
    def __init__(self):
        self.created: list[Alert] = [
            Alert(
                id=uuid4(),
                title="关键风险情报",
                threat_intelligence_id=uuid4(),
                triggering_rule="critical-intelligence",
                risk_level=RiskLevel.CRITICAL,
                triggered_at=datetime.now(timezone.utc),
                status="open",
                notes=None,
                metadata_={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
        ]
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def commit(self):
        self.commits += 1


def test_alert_evaluation_script_commits_and_returns_summary(monkeypatch):
    session = ScriptAlertSession()

    def fake_evaluate(session_arg, *, limit: int):
        assert session_arg is session
        assert limit == 25
        return session.created

    result = evaluate_alerts.evaluate_alerts(limit=25, session_factory=lambda: session, alert_evaluator=fake_evaluate)

    assert result == {"evaluated": 25, "created": 1, "alert_ids": [str(session.created[0].id)]}
    assert session.commits == 1
