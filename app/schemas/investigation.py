from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class InvestigationOutcome(StrEnum):
    CONFIRMED = "confirmed"
    INCONCLUSIVE = "inconclusive"
    FAILED = "failed"


class IncidentContext(BaseModel):
    incident_id: str
    service: str
    title: str
    severity: str
    status: str
    occurred_at: datetime
    description: str | None = None


class EvidenceItem(BaseModel):
    reference: str
    source: str
    service: str
    observed_at: datetime
    summary: str = Field(min_length=1, max_length=2_000)


class EvidenceCollection(BaseModel):
    items: list[EvidenceItem] = Field(default_factory=list, max_length=100)
    sources_consulted: list[str] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class InvestigationFact(BaseModel):
    text: str = Field(min_length=1, max_length=1_000)
    evidence_refs: list[str] = Field(min_length=1)


class InvestigationDraft(BaseModel):
    outcome: InvestigationOutcome
    facts: list[InvestigationFact] = Field(default_factory=list, max_length=20)
    hypothesis: str | None = Field(default=None, max_length=2_000)
    confidence: float = Field(ge=0, le=1)
    next_check: str = Field(min_length=1, max_length=1_000)


class InvestigationReport(InvestigationDraft):
    incident_id: str
    sources_consulted: list[str] = Field(default_factory=list)
    unavailable_sources: list[str] = Field(default_factory=list)
