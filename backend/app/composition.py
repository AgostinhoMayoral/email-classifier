"""Instanciação de serviços e adaptadores (DI manual, sem framework)."""

from __future__ import annotations

from functools import lru_cache

from app.application.ports.gmail_gateway import GmailGatewayPort
from app.application.services.email_processing_application_service import (
    EmailProcessingApplicationService,
)
from app.infrastructure.adapters.gmail_gateway_adapter import GmailServiceGatewayAdapter
from app.infrastructure.llm.huggingface_email_llm import HuggingFaceEmailLLM
from app.services.nlp_preprocessor import preprocess_text


@lru_cache
def get_gmail_gateway() -> GmailGatewayPort:
    return GmailServiceGatewayAdapter()


@lru_cache
def get_email_processing_application_service() -> EmailProcessingApplicationService:
    return EmailProcessingApplicationService(
        llm=HuggingFaceEmailLLM(),
        preprocess=preprocess_text,
    )
