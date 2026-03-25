from __future__ import annotations

from typing import Any, Protocol


class EmailLLMPort(Protocol):
    """Porta para classificação e geração de resposta via modelo de linguagem."""

    def classify(self, email_text: str) -> dict[str, Any] | None:
        """Retorna {'category': str, 'confidence': float} ou None se indisponível."""

    def generate_reply(
        self,
        email_text: str,
        category: str,
        recipient_name: str | None = None,
        sender_name: str | None = None,
    ) -> str | None:
        """Texto da resposta ou None para acionar fallback de template."""
