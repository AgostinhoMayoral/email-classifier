from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EmailProcessingResultDTO:
    category: str
    confidence: float
    suggested_response: str
    processed_text: str
    ai_used: bool

    def as_dict(self) -> dict:
        return {
            "category": self.category,
            "confidence": round(self.confidence, 2),
            "suggested_response": self.suggested_response.strip(),
            "processed_text": self.processed_text[:500],
            "ai_used": self.ai_used,
        }
