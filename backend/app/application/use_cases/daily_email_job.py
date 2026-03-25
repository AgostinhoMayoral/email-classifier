"""Job diário: listar período no Gmail, classificar pendentes, enviar respostas."""

from __future__ import annotations

import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.application.ports.email_repository import EmailRepositoryPort
from app.application.ports.gmail_gateway import GmailGatewayPort
from app.application.services.email_processing_application_service import (
    EmailProcessingApplicationService,
)
from app.domain.value_objects.email_category import EmailCategory
from app.domain.value_objects.email_record_status import EmailRecordStatus
from app.timezone_utils import resolve_gmail_date_range_sp


def _parse_gmail_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        return parsedate_to_datetime(date_str)
    except Exception:
        return None


def execute_daily_email_job(
    db: Session,
    gmail: GmailGatewayPort,
    repo: EmailRepositoryPort,
    classifier: EmailProcessingApplicationService,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    only_productive: bool = False,
    max_emails: int = 100,
) -> dict:
    if not gmail.is_authenticated():
        return {"success": False, "error": "Gmail não autenticado"}

    user_info = gmail.get_user_info()
    account = (user_info.get("email") or "").strip().lower() if user_info else None

    range_start, range_end_excl = resolve_gmail_date_range_sp(date_from, date_to)
    after_str = range_start.strftime("%Y/%m/%d")
    before_str = range_end_excl.strftime("%Y/%m/%d")
    query = f"after:{after_str} before:{before_str}"
    sent_ids = repo.get_all_sent_gmail_ids()
    messages = gmail.list_messages(max_results=max_emails, query=query, exclude_ids=sent_ids)

    classified_count = 0
    sent_count = 0
    skipped_count = 0
    errors: list[dict] = []

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

        record = repo.get_or_create_email_record(
            gmail_id,
            thread_id,
            subject,
            sender,
            snippet,
            received_at,
            gmail_account_email=account,
        )

        if record.status == EmailRecordStatus.SENT:
            skipped_count += 1
            continue

        if not record.classification:
            try:
                content = gmail.get_message_content(gmail_id)
                recipient = gmail.extract_display_name_from_header(sender)
                user_info = gmail.get_user_info()
                sender_name = (
                    (user_info.get("name") or "").strip()
                    if user_info
                    else os.getenv("USER_NAME", "").strip() or None
                )
                result = classifier.process(
                    content,
                    recipient_name=recipient or None,
                    sender_name=sender_name or None,
                )
                dto = result.as_dict()
                repo.save_classification(
                    record.id,
                    dto["category"],
                    dto["confidence"],
                    dto["suggested_response"],
                    dto.get("processed_text"),
                )
                record.status = EmailRecordStatus.CLASSIFIED
                record.updated_at = datetime.utcnow()
                db.commit()
                classified_count += 1
            except Exception as e:
                errors.append({"gmail_id": gmail_id, "error": str(e)})
                continue

        if only_productive and record.classification.category != EmailCategory.PRODUCTIVE:
            skipped_count += 1
            continue

        to_email = gmail.extract_reply_to_email(sender)
        if not to_email:
            errors.append({"gmail_id": gmail_id, "error": "Email do destinatário não encontrado"})
            continue

        try:
            gmail.send_email(
                to_email=to_email,
                subject=f"Re: {subject}" if not subject.startswith("Re:") else subject,
                body=record.classification.suggested_response,
                thread_id=thread_id,
            )
            repo.mark_as_sent(record.id)
            repo.add_log(record.id, "sent", "Resposta enviada com sucesso")
            sent_count += 1
        except Exception as e:
            repo.mark_as_failed(record.id)
            repo.add_log(record.id, "failed", str(e))
            errors.append({"gmail_id": gmail_id, "error": str(e)})

    return {
        "success": True,
        "classified": classified_count,
        "sent": sent_count,
        "skipped": skipped_count,
        "errors": errors,
    }
