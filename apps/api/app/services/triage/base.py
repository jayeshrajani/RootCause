from typing import Protocol

from app.models.report import FarmerReport
from app.schemas.triage import TriageResponse


class TriageService(Protocol):
    """Produces a triage assessment for a validated farmer report.

    Implementations: MockTriageService (Milestone 0). A Gemini-backed orchestrator that
        Implementations: MockTriageService and AiTriageService. AI triage may consume recent
        weather estimates when coordinates are available; satellite and knowledge adapters remain
        unintegrated.
    """

    async def assess(self, report: FarmerReport) -> TriageResponse: ...
