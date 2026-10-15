from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReferenceVotes:
    """How the most similar labelled reference photos of one crop split across conditions."""

    crop: str
    index_version: str
    total: int
    counts: tuple[tuple[str, int], ...]
    best_similarity: float

    def score(self, condition: str) -> int:
        """Share (0-100) of the compared reference photos labelled `condition`."""
        matches = dict(self.counts).get(condition, 0)
        return round(100 * matches / self.total) if self.total else 0
