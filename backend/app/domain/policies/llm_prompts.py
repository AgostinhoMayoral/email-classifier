"""
Textos de política para o LLM (significado de Produtivo vs Improdutivo e tom de resposta).

Alterar aqui ajusta o comportamento semântico da classificação por modelo,
alinhand ao vocabulário de negócio do produto.
"""

from __future__ import annotations


def classification_user_prompt(email_excerpt: str, max_chars: int = 400) -> str:
    excerpt = email_excerpt[:max_chars]
    return f"""Classifique este email em UMA palavra: Produtivo ou Improdutivo.
Produtivo = solicita ação, suporte, informação, pedido.
Improdutivo = cumprimento, agradecimento, mensagem sem ação necessária.

Email: "{excerpt}"

Responda APENAS com a palavra: Produtivo ou Improdutivo"""


def reply_user_prompt(
    email_text: str,
    category: str,
    name_instructions_block: str,
    email_snippet_max: int = 500,
) -> str:
    body = email_text[:email_snippet_max]
    return f"""Mensagem recebida: "{body}"

Responda de forma cordial e profissional em português. Seja ESPECÍFICO ao conteúdo. Máximo 4 frases. Apenas a resposta completa, sem prefixos.

IMPORTANTE - Personalização:
{name_instructions_block}
NUNCA use [Nome], [Seu Nome] ou placeholders. Use sempre os nomes reais."""


def build_name_instructions_block(
    recipient_name: str | None,
    sender_name: str | None,
) -> str:
    lines: list[str] = []
    if recipient_name and recipient_name.strip():
        rn = recipient_name.strip()
        lines.append(
            f"- O destinatário se chama {rn}. Use o nome dele na saudação (ex: Prezado(a) {rn}, ou Prezado João)."
        )
    else:
        lines.append(
            "- Se o nome do destinatário aparecer na mensagem, use-o na saudação. Caso contrário, use 'Prezado(a)'."
        )
    if sender_name and sender_name.strip():
        sn = sender_name.strip()
        lines.append(
            f"- Assine a mensagem com o nome {sn} (ex: Atenciosamente, {sn})."
        )
    else:
        lines.append(
            "- Assine com 'Atenciosamente' ou similar, sem deixar [Seu Nome] ou placeholders."
        )
    return "\n".join(lines)
