"""
Política de classificação por regras (fallback quando o LLM não está disponível).

Centralize aqui listas de indicadores, limiares e pesos — é o ponto principal
para ajustar o comportamento heurístico sem tocar em adapters ou na API.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RuleBasedClassificationRules:
    """Parâmetros da heurística baseada em indicadores linguísticos."""

    productive_indicators: tuple[str, ...] = (
        "solicito",
        "solicitação",
        "requisição",
        "status",
        "atualização",
        "suporte",
        "problema",
        "erro",
        "dúvida",
        "pergunta",
        "urgente",
        "prazo",
        "documento",
        "arquivo",
        "sistema",
        "caso",
        "processo",
        "aprovação",
        "pendente",
        "andamento",
        "resolver",
        "ajuda",
        "informação",
        "informações",
        "preciso",
        "necessito",
        "gostaria",
    )
    unproductive_indicators: tuple[str, ...] = (
        "feliz natal",
        "feliz ano novo",
        "boas festas",
        "parabéns",
        "obrigado",
        "obrigada",
        "agradeço",
        "agradecimento",
        "cumprimentos",
        "atenciosamente",
        "abraço",
        "abração",
        "bom dia",
        "boa tarde",
        "boa noite",
        "olá",
        "oi ",
        "só para",
        "apenas para",
        "só queria",
    )
    # Indicadores improdutivos avaliados apenas no texto bruto (comportamento legado)
    unproductive_indicators_raw_text_only: bool = True
    # Email muito curto + sinais de cumprimento → improdutivo
    short_email_max_words: int = 15
    short_email_improductive_confidence: float = 0.75
    # Confiança quando produtivo/improdutivo ganha por contagem
    score_base_confidence: float = 0.6
    score_per_indicator_step: float = 0.08
    score_max_confidence: float = 0.95
    # Empate: preferir produtivo (legado)
    tie_defaults_to_productive: bool = True
    tie_confidence: float = 0.65


def default_rule_based_classification_rules() -> RuleBasedClassificationRules:
    return RuleBasedClassificationRules()


# Lista mutável opcional para extensão em runtime (testes / futura config externa)
_RULE_OVERRIDE: RuleBasedClassificationRules | None = None


def get_active_rule_based_rules() -> RuleBasedClassificationRules:
    return _RULE_OVERRIDE or default_rule_based_classification_rules()


def set_rule_based_classification_rules(rules: RuleBasedClassificationRules | None) -> None:
    """Permite trocar regras globalmente (ex.: testes). None restaura o default."""
    global _RULE_OVERRIDE
    _RULE_OVERRIDE = rules
