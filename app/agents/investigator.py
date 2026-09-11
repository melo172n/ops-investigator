from typing import NotRequired, Protocol, TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.investigation import (
    EvidenceCollection,
    EvidenceItem,
    IncidentContext,
    InvestigationDraft,
    InvestigationOutcome,
    InvestigationReport,
)


class EvidenceCollector(Protocol):
    async def collect(self, incident: IncidentContext) -> EvidenceCollection: ...


class InvestigationAnalyzer(Protocol):
    async def analyze(
        self,
        incident: IncidentContext,
        evidence: tuple[EvidenceItem, ...],
    ) -> InvestigationDraft: ...


class InvestigatorState(TypedDict):
    incident: IncidentContext
    evidence: NotRequired[EvidenceCollection]
    draft: NotRequired[InvestigationDraft]
    report: NotRequired[InvestigationReport]


def build_investigator_graph(
    collector: EvidenceCollector,
    analyzer: InvestigationAnalyzer,
) -> StateGraph:
    async def collect_evidence(state: InvestigatorState) -> dict:
        try:
            evidence = await collector.collect(state["incident"])
        except Exception as exc:
            evidence = EvidenceCollection(
                unavailable_sources=["evidence_collector"],
                errors=[type(exc).__name__],
            )
        return {"evidence": evidence}

    async def analyze_evidence(state: InvestigatorState) -> dict:
        evidence = state["evidence"]
        if not evidence.items:
            return {
                "draft": InvestigationDraft(
                    outcome=InvestigationOutcome.INCONCLUSIVE,
                    confidence=0,
                    next_check="Verificar a disponibilidade das fontes de evidência.",
                )
            }

        try:
            draft = await analyzer.analyze(
                state["incident"],
                tuple(evidence.items),
            )
        except Exception:
            draft = InvestigationDraft(
                outcome=InvestigationOutcome.FAILED,
                confidence=0,
                next_check="Executar novamente a análise das evidências.",
            )
        return {"draft": draft}

    async def finalize(state: InvestigatorState) -> dict:
        incident = state["incident"]
        evidence = state["evidence"]
        draft = state["draft"]
        known_refs = {item.reference for item in evidence.items}
        cited_refs = {
            reference
            for fact in draft.facts
            for reference in fact.evidence_refs
        }
        invalid_draft = bool(cited_refs - known_refs) or (
            draft.outcome == InvestigationOutcome.CONFIRMED
            and not draft.facts
        )

        if invalid_draft:
            draft = InvestigationDraft(
                outcome=InvestigationOutcome.INCONCLUSIVE,
                confidence=0,
                next_check="Revisar as evidências e suas referências.",
            )

        return {
            "report": InvestigationReport(
                incident_id=incident.incident_id,
                sources_consulted=evidence.sources_consulted,
                unavailable_sources=evidence.unavailable_sources,
                **draft.model_dump(),
            )
        }

    graph = StateGraph(InvestigatorState)
    graph.add_node("collect_evidence", collect_evidence)
    graph.add_node("analyze_evidence", analyze_evidence)
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "collect_evidence")
    graph.add_edge("collect_evidence", "analyze_evidence")
    graph.add_edge("analyze_evidence", "finalize")
    graph.add_edge("finalize", END)
    return graph
