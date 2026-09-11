from datetime import UTC, datetime

from app.agents.investigator import build_investigator_graph
from app.schemas.investigation import (
    EvidenceCollection,
    EvidenceItem,
    IncidentContext,
    InvestigationDraft,
    InvestigationFact,
    InvestigationOutcome,
)


def incident() -> IncidentContext:
    return IncidentContext(
        incident_id="inc_test",
        service="chatwoot",
        title="Elevated error rate",
        severity="high",
        status="PROBLEM",
        occurred_at=datetime(2026, 9, 11, 12, 0, tzinfo=UTC),
    )


class EmptyCollector:
    async def collect(self, _: IncidentContext) -> EvidenceCollection:
        return EvidenceCollection(
            sources_consulted=["loki"],
            unavailable_sources=["loki"],
        )


class FailingCollector:
    async def collect(self, _: IncidentContext) -> EvidenceCollection:
        raise RuntimeError("sensitive upstream detail")


class LokiCollector:
    async def collect(self, _: IncidentContext) -> EvidenceCollection:
        return EvidenceCollection(
            items=[
                EvidenceItem(
                    reference="loki:1710000000",
                    source="loki",
                    service="chatwoot",
                    observed_at=datetime(2026, 9, 11, 12, 1, tzinfo=UTC),
                    summary="Database connection failed.",
                )
            ],
            sources_consulted=["loki"],
        )


class RecordingAnalyzer:
    def __init__(self, *, evidence_ref: str = "loki:1710000000") -> None:
        self.calls = 0
        self.evidence_ref = evidence_ref

    async def analyze(self, _, evidence) -> InvestigationDraft:
        self.calls += 1
        assert len(evidence) == 1
        return InvestigationDraft(
            outcome=InvestigationOutcome.CONFIRMED,
            facts=[
                InvestigationFact(
                    text="Chatwoot could not connect to its database.",
                    evidence_refs=[self.evidence_ref],
                )
            ],
            hypothesis="Database connectivity failure.",
            confidence=0.9,
            next_check="Check PostgreSQL availability.",
        )


class FailingAnalyzer:
    async def analyze(self, _, __) -> InvestigationDraft:
        raise RuntimeError("sensitive model detail")


async def test_agent_returns_inconclusive_without_evidence() -> None:
    analyzer = RecordingAnalyzer()
    graph = build_investigator_graph(EmptyCollector(), analyzer).compile()

    result = await graph.ainvoke({"incident": incident()})

    assert result["report"].outcome == InvestigationOutcome.INCONCLUSIVE
    assert result["report"].confidence == 0
    assert result["report"].unavailable_sources == ["loki"]
    assert analyzer.calls == 0


async def test_agent_uses_evidence_and_returns_grounded_report() -> None:
    analyzer = RecordingAnalyzer()
    graph = build_investigator_graph(LokiCollector(), analyzer).compile()

    result = await graph.ainvoke({"incident": incident()})

    report = result["report"]
    assert report.outcome == InvestigationOutcome.CONFIRMED
    assert report.facts[0].evidence_refs == ["loki:1710000000"]
    assert report.sources_consulted == ["loki"]
    assert analyzer.calls == 1


async def test_agent_fails_closed_for_unknown_evidence_reference() -> None:
    analyzer = RecordingAnalyzer(evidence_ref="loki:unknown")
    graph = build_investigator_graph(LokiCollector(), analyzer).compile()

    result = await graph.ainvoke({"incident": incident()})

    assert result["report"].outcome == InvestigationOutcome.INCONCLUSIVE
    assert result["report"].facts == []
    assert result["report"].confidence == 0


async def test_agent_hides_collector_error_details() -> None:
    analyzer = RecordingAnalyzer()
    graph = build_investigator_graph(FailingCollector(), analyzer).compile()

    result = await graph.ainvoke({"incident": incident()})

    assert result["evidence"].errors == ["RuntimeError"]
    assert "sensitive" not in result["evidence"].model_dump_json()
    assert result["report"].outcome == InvestigationOutcome.INCONCLUSIVE


async def test_agent_returns_failed_when_analysis_fails() -> None:
    graph = build_investigator_graph(LokiCollector(), FailingAnalyzer()).compile()

    result = await graph.ainvoke({"incident": incident()})

    report = result["report"]
    assert report.outcome == InvestigationOutcome.FAILED
    assert report.confidence == 0
    assert "sensitive" not in report.model_dump_json()
