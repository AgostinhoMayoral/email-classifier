"""Templates de resposta quando o LLM não está disponível — ajustável com o tom do negócio."""

from __future__ import annotations

from app.domain.value_objects.email_category import EmailCategory


def render_fallback_reply(
    category: str,
    email_preview: str,
    recipient_name: str | None = None,
    sender_name: str | None = None,
) -> str:
    """
    Gera resposta por template (comportamento legado).
    `email_preview` é mantido na assinatura por compatibilidade; não era usado nos templates fixos.
    """
    _ = email_preview
    saudacao = (
        f"Prezado(a) {recipient_name},\n\n"
        if (recipient_name and recipient_name.strip())
        else "Prezado(a),\n\n"
    )
    assinatura = (
        f"Atenciosamente,\n{sender_name}"
        if (sender_name and sender_name.strip())
        else "Atenciosamente,\nEquipe de Suporte"
    )

    if category == EmailCategory.PRODUCTIVE:
        return (
            f"{saudacao}"
            "Agradecemos o contato. Sua solicitação foi recebida e está sendo analisada por nossa equipe. "
            "Retornaremos em breve com as informações solicitadas.\n\n"
            "Em caso de urgência, por favor entre em contato através dos nossos canais oficiais.\n\n"
            f"{assinatura}"
        )
    return (
        f"{saudacao}"
        "Agradecemos sua mensagem e os votos. Desejamos a você e à sua equipe um excelente ano!\n\n"
        f"{assinatura}"
    )
