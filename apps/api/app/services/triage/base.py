from typing import Protocol

from app.models.report import FarmerReport
from app.schemas.triage import TriageResponse


class TriageService(Protocol):
    """Produces a triage assessment for a validated farmer report.

    Implementations: MockTriageService (Milestone 0). A Gemini-backed orchestrator that
    also consumes weather/satellite/knowledge adapters will implement this later.
    """

    async def assess(self, report: FarmerReport) -> TriageResponse: ...
