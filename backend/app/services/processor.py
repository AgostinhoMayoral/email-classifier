"""
Fachada legada: classificação e geração de respostas (usa serviço de aplicação).
"""

from __future__ import annotations

from typing import Any, Dict

from app.composition import get_email_processing_application_service


def process_email(
    email_text: str,
    recipient_name: str | None = None,
    sender_name: str | None = None,
) -> Dict[str, Any]:
    svc = get_email_processing_application_service()
    return svc.process(
        email_text,
        recipient_name=recipient_name,
        sender_name=sender_name,
    ).as_dict()
