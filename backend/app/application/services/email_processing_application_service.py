"""Orquestra pré-processamento, classificação (LLM + regras) e geração de resposta."""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.application.dto.classification import EmailProcessingResultDTO
from app.application.ports.email_llm import EmailLLMPort
from app.domain.policies.classification_rules import (
    RuleBasedClassificationRules,
    get_active_rule_based_rules,
)
from app.domain.policies.response_templates import render_fallback_reply
from app.domain.services.rule_based_classification import classify_by_rules
from app.domain.value_objects.email_category import EmailCategory, normalize_category_label

logger = logging.getLogger(__name__)


class EmailProcessingApplicationService:
    def __init__(
        self,
        llm: EmailLLMPort,
        preprocess: Callable[[str], str],
        rules_supplier: Callable[[], RuleBasedClassificationRules] | None = None,
    ):
        self._llm = llm
        self._preprocess = preprocess
        self._rules_supplier = rules_supplier or get_active_rule_based_rules

    def process(
        self,
        email_text: str,
        recipient_name: str | None = None,
        sender_name: str | None = None,
    ) -> EmailProcessingResultDTO:
        processed_text = self._preprocess(email_text)
        hf_result = self._llm.classify(email_text)
        if hf_result:
            category = normalize_category_label(
                hf_result.get("category", EmailCategory.PRODUCTIVE)
            )
            confidence = float(hf_result.get("confidence", 0.8))
        else:
            category, confidence = classify_by_rules(
                email_text, processed_text, self._rules_supplier()
            )

        category = normalize_category_label(category)

        suggested_response = self._llm.generate_reply(
            email_text,
            category,
            recipient_name=recipient_name,
            sender_name=sender_name,
        )
        ai_used = bool(suggested_response)
        if not suggested_response:
            logger.warning("Usando template de fallback (IA indisponível ou falhou)")
            suggested_response = render_fallback_reply(
                category,
                email_text[:100],
                recipient_name=recipient_name,
                sender_name=sender_name,
            )

        return EmailProcessingResultDTO(
            category=category,
            confidence=confidence,
            suggested_response=suggested_response,
            processed_text=processed_text,
            ai_used=ai_used,
        )
