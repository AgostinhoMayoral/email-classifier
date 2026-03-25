"""Classifica uma mensagem Gmail e persiste no banco."""

from __future__ import annotations

import os
from datetime import datetime

from sqlalchemy.orm import Session

from app.application.ports.email_repository import EmailRepositoryPort
from app.application.ports.gmail_gateway import GmailGatewayPort
from app.application.services.email_processing_application_service import (
    EmailProcessingApplicationService,
)
from app.domain.value_objects.email_record_status import EmailRecordStatus


def execute_classify_gmail_message(
    db: Session,
    gmail: GmailGatewayPort,
    repo: EmailRepositoryPort,
    classifier: EmailProcessingApplicationService,
    message_id: str,
    gmail_account_email: str,
) -> dict:
    msg_data = gmail.get_message_metadata(message_id)
    content = gmail.get_message_content(message_id)

    recipient = gmail.extract_display_name_from_header(msg_data.get("from", ""))
    user_info = gmail.get_user_info()
    sender = (user_info.get("name") or "").strip() if user_info else ""
    if not sender:
        sender = os.getenv("USER_NAME", "").strip() or None

    result = classifier.process(
        content,
        recipient_name=recipient or None,
        sender_name=sender or None,
    ).as_dict()

    received_at = None
    if msg_data.get("internalDate"):
        received_at = datetime.utcfromtimestamp(int(msg_data["internalDate"]) / 1000)

    record = repo.get_or_create_email_record(
        message_id,
        msg_data.get("threadId"),
        msg_data.get("subject", "(sem assunto)"),
        msg_data.get("from", ""),
        msg_data.get("snippet"),
        received_at,
        gmail_account_email=gmail_account_email,
    )
    repo.save_classification(
        record.id,
        result["category"],
        result["confidence"],
        result["suggested_response"],
        result.get("processed_text"),
    )
    record.status = EmailRecordStatus.CLASSIFIED
    record.updated_at = datetime.utcnow()
    db.commit()
    repo.add_log(record.id, "classified", "Classificação realizada com sucesso")
    return result
