"""Envia respostas sugeridas para mensagens Gmail selecionadas (com classificação sob demanda)."""

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


def execute_send_batch_replies(
    db: Session,
    gmail: GmailGatewayPort,
    repo: EmailRepositoryPort,
    classifier: EmailProcessingApplicationService,
    message_ids: list[str],
    gmail_account_email: str,
) -> dict:
    sent_ids = repo.get_ids_already_sent(message_ids)
    to_send = [mid for mid in message_ids if mid not in sent_ids]
    if not to_send:
        return {
            "sent": 0,
            "skipped": len(message_ids),
            "errors": [],
            "message": "Todos já foram enviados.",
        }

    results: dict = {"sent": 0, "skipped": len(sent_ids), "errors": []}

    for gmail_id in to_send:
        record = repo.get_by_gmail_id(gmail_id)
        if not record:
            try:
                msg_data = gmail.get_message_metadata(gmail_id)
                content = gmail.get_message_content(gmail_id)
                recipient = gmail.extract_display_name_from_header(msg_data.get("from", ""))
                user_info = gmail.get_user_info()
                sender = (
                    (user_info.get("name") or "").strip()
                    if user_info
                    else os.getenv("USER_NAME", "").strip() or None
                )
                classification_result = classifier.process(
                    content,
                    recipient_name=recipient or None,
                    sender_name=sender or None,
                ).as_dict()
                received_at = None
                if msg_data.get("internalDate"):
                    received_at = datetime.utcfromtimestamp(int(msg_data["internalDate"]) / 1000)
                record = repo.get_or_create_email_record(
                    gmail_id,
                    msg_data.get("threadId"),
                    msg_data.get("subject", "(sem assunto)"),
                    msg_data.get("from", ""),
                    msg_data.get("snippet"),
                    received_at,
                    gmail_account_email=gmail_account_email,
                )
                repo.save_classification(
                    record.id,
                    classification_result["category"],
                    classification_result["confidence"],
                    classification_result["suggested_response"],
                    classification_result.get("processed_text"),
                )
                record.status = EmailRecordStatus.CLASSIFIED
                record.updated_at = datetime.utcnow()
                db.commit()
            except Exception as e:
                results["errors"].append({"gmail_id": gmail_id, "error": str(e)})
                continue
        if not record.classification:
            results["errors"].append({"gmail_id": gmail_id, "error": "Falha ao classificar o email."})
            continue
        if record.status == EmailRecordStatus.SENT:
            results["skipped"] += 1
            continue

        to_email = gmail.extract_reply_to_email(record.sender)
        if not to_email:
            results["errors"].append({"gmail_id": gmail_id, "error": "Email do destinatário não encontrado"})
            continue

        subject = record.subject
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"

        try:
            gmail.send_email(
                to_email=to_email,
                subject=subject,
                body=record.classification.suggested_response,
                thread_id=record.thread_id,
            )
            repo.mark_as_sent(record.id)
            repo.add_log(record.id, "sent", "Resposta enviada com sucesso")
            results["sent"] += 1
        except Exception as e:
            repo.mark_as_failed(record.id)
            repo.add_log(record.id, "failed", str(e))
            results["errors"].append({"gmail_id": gmail_id, "error": str(e)})

    return results
