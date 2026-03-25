"""Rótulos canônicos de classificação (agregado Email / conceito de produtividade)."""

from __future__ import annotations


class EmailCategory:
    """Constantes de categoria — única fonte para comparações no domínio."""

    PRODUCTIVE = "Produtivo"
    UNPRODUCTIVE = "Improdutivo"

    @classmethod
    def all_labels(cls) -> tuple[str, str]:
        return (cls.PRODUCTIVE, cls.UNPRODUCTIVE)


def normalize_category_label(value: object) -> str:
    """
    Garante rótulo canônico Produtivo | Improdutivo.
    Mantém o mesmo comportamento de tolerância a variações da implementação anterior.
    """
    if value in EmailCategory.all_labels():
        return str(value)
    lower = str(value).lower()
    if "improdutivo" in lower:
        return EmailCategory.UNPRODUCTIVE
    if "produtivo" in lower:
        return EmailCategory.PRODUCTIVE
    return EmailCategory.PRODUCTIVE
