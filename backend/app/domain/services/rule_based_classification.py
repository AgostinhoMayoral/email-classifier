"""Serviço de domínio: classificação heurística sem I/O."""

from __future__ import annotations

from app.domain.policies.classification_rules import RuleBasedClassificationRules
from app.domain.value_objects.email_category import EmailCategory


def classify_by_rules(
    text: str,
    preprocessed: str,
    rules: RuleBasedClassificationRules,
) -> tuple[str, float]:
    """
    Retorna (categoria canônica, confiança) usando apenas indicadores lexicais.
    Preserva a semântica da implementação original (incl. empate → produtivo).
    """
    text_lower = text.lower()
    preprocessed_lower = preprocessed.lower()

    productive_count = sum(
        1
        for ind in rules.productive_indicators
        if ind in text_lower or ind in preprocessed_lower
    )
    if rules.unproductive_indicators_raw_text_only:
        unproductive_count = sum(
            1 for ind in rules.unproductive_indicators if ind in text_lower
        )
    else:
        unproductive_count = sum(
            1
            for ind in rules.unproductive_indicators
            if ind in text_lower or ind in preprocessed_lower
        )

    word_count = len(text.split())
    if (
        word_count < rules.short_email_max_words
        and unproductive_count > 0
        and productive_count == 0
    ):
        return EmailCategory.UNPRODUCTIVE, rules.short_email_improductive_confidence

    if productive_count > unproductive_count:
        conf = min(
            rules.score_max_confidence,
            rules.score_base_confidence + (productive_count * rules.score_per_indicator_step),
        )
        return EmailCategory.PRODUCTIVE, conf
    if unproductive_count > productive_count:
        conf = min(
            rules.score_max_confidence,
            rules.score_base_confidence + (unproductive_count * rules.score_per_indicator_step),
        )
        return EmailCategory.UNPRODUCTIVE, conf

    if rules.tie_defaults_to_productive:
        return EmailCategory.PRODUCTIVE, rules.tie_confidence
    return EmailCategory.UNPRODUCTIVE, rules.tie_confidence
