"""
Serviço do job diário de classificação e envio de emails.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.services import gmail_service
from app.services.processor import process_email
from app.repositories import email_repository
from app.models import EmailStatus


def _parse_gmail_date(date_str: Optional[str]) -> Optional[datetime]:
    """Converte string de data do Gmail para datetime."""
    if not date_str:
        return None
    try:
        from email.utils import parsedate_to_datetime
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def run_daily_job(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    only_productive: bool = False,
    max_emails: int = 100,
) -> dict:
    """
    Executa o job diário:
    1. Busca emails do Gmail no período
    2. Classifica os não classificados
    3. Envia respostas para os selecionados (evita duplicados)
    """
    if not gmail_service.is_authenticated():
        return {"success": False, "error": "Gmail não autenticado"}

    if not date_from:
        date_from = datetime.utcnow() - timedelta(days=1)
    if not date_to:
        date_to = datetime.utcnow()

    # Query Gmail com filtro de data
    after_str = date_from.strftime("%Y/%m/%d")
    before_str = date_to.strftime("%Y/%m/%d")
    query = f"after:{after_str} before:{before_str}"
    messages = gmail_service.list_messages(max_results=max_emails, query=query)

    classified_count = 0
    sent_count = 0
    skipped_count = 0
    errors = []

    for msg in messages:
        gmail_id = msg["id"]
        thread_id = msg.get("threadId")
        subject = msg.get("subject", "")
        sender = msg.get("from", "")
        snippet = msg.get("snippet", "")
        date_str = msg.get("date", "")
        internal_date = msg.get("internalDate")

        received_at = None
        if internal_date:
            received_at = datetime.utcfromtimestamp(int(internal_date) / 1000)
        else:
            received_at = _parse_gmail_date(date_str)

        # Criar ou obter registro
        record = email_repository.get_or_create_email_record(
            db, gmail_id, thread_id, subject, sender, snippet, received_at
        )

        # Se já enviado, pular
        if record.status == EmailStatus.SENT:
            skipped_count += 1
            continue

        # Classificar se necessário
        if not record.classification:
            try:
                content = gmail_service.get_message_content(gmail_id)
                result = process_email(content)
                email_repository.save_classification(
                    db,
                    record.id,
                    result["category"],
                    result["confidence"],
                    result["suggested_response"],
                    result.get("processed_text"),
                )
                record.status = EmailStatus.CLASSIFIED
                record.updated_at = datetime.utcnow()
                db.commit()
                classified_count += 1
            except Exception as e:
                errors.append({"gmail_id": gmail_id, "error": str(e)})
                continue

        # Verificar se deve enviar (only_productive = só produtivos)
        if only_productive and record.classification.category != "Produtivo":
            skipped_count += 1
            continue

        # Enviar
        to_email = gmail_service._extract_email_from_header(sender)
        if not to_email:
            errors.append({"gmail_id": gmail_id, "error": "Email do destinatário não encontrado"})
            continue

        try:
            gmail_service.send_email(
                to_email=to_email,
                subject=f"Re: {subject}" if not subject.startswith("Re:") else subject,
                body=record.classification.suggested_response,
                thread_id=thread_id,
            )
            email_repository.mark_as_sent(db, record.id)
            email_repository.add_log(db, record.id, "sent", "Resposta enviada com sucesso")
            sent_count += 1
        except Exception as e:
            email_repository.mark_as_failed(db, record.id)
            email_repository.add_log(db, record.id, "failed", str(e))
            errors.append({"gmail_id": gmail_id, "error": str(e)})

    return {
        "success": True,
        "classified": classified_count,
        "sent": sent_count,
        "skipped": skipped_count,
        "errors": errors,
    }
