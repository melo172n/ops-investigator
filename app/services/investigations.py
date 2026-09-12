from typing import Protocol

from app.agents.investigator import build_investigator_graph
from app.core.config import Settings
from app.integrations.loki import LokiEvidenceCollector
from app.integrations.openai_analyzer import (
    OpenAIConfigurationError,
    OpenAIInvestigationAnalyzer,
)
from app.schemas.investigation import (
    IncidentContext,
    InvestigationDraft,
    InvestigationReport,
)


class IncidentInvestigator(Protocol):
    async def investigate(self, incident: IncidentContext) -> InvestigationReport: ...


class LangGraphIncidentInvestigator:
    """Runs the bounded Loki and OpenAI investigation for one incident."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def investigate(self, incident: IncidentContext) -> InvestigationReport:
        collector = LokiEvidenceCollector(self._settings)
        try:
            analyzer = OpenAIInvestigationAnalyzer(self._settings)
        except OpenAIConfigurationError:
            analyzer = _UnavailableAnalyzer()
        graph = build_investigator_graph(collector, analyzer).compile()
        result = await graph.ainvoke({"incident": incident})
        return result["report"]


class _UnavailableAnalyzer:
    async def analyze(self, *_: object) -> InvestigationDraft:
        raise RuntimeError("OpenAI analyzer is unavailable")
