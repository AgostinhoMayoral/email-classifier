"""
Repositório para operações de emails no banco de dados.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models import EmailRecord, EmailClassification, EmailLog, EmailStatus


def get_or_create_email_record(
    db: Session,
    gmail_message_id: str,
    thread_id: Optional[str],
    subject: str,
    sender: str,
    snippet: Optional[str],
    received_at: Optional[datetime],
) -> EmailRecord:
    """Obtém ou cria registro de email pelo ID do Gmail."""
    record = db.query(EmailRecord).filter(
        EmailRecord.gmail_message_id == gmail_message_id
    ).first()
    if record:
        return record
    record = EmailRecord(
        gmail_message_id=gmail_message_id,
        thread_id=thread_id,
        subject=subject or "(sem assunto)",
        sender=sender or "",
        snippet=snippet,
        received_at=received_at,
        status=EmailStatus.PENDING,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def save_classification(
    db: Session,
    email_record_id: int,
    category: str,
    confidence: float,
    suggested_response: str,
    processed_text: Optional[str] = None,
) -> EmailClassification:
    """Salva ou atualiza classificação do email."""
    existing = db.query(EmailClassification).filter(
        EmailClassification.email_record_id == email_record_id
    ).first()
    if existing:
        existing.category = category
        existing.confidence = confidence
        existing.suggested_response = suggested_response
        existing.processed_text = processed_text
        db.commit()
        db.refresh(existing)
        return existing

    classification = EmailClassification(
        email_record_id=email_record_id,
        category=category,
        confidence=confidence,
        suggested_response=suggested_response,
        processed_text=processed_text,
    )
    db.add(classification)
    db.commit()
    db.refresh(classification)
    return classification


def add_log(db: Session, email_record_id: int, action: str, message: Optional[str] = None, details: Optional[str] = None) -> EmailLog:
    """Adiciona entrada de log."""
    log = EmailLog(
        email_record_id=email_record_id,
        action=action,
        message=message,
        details=details,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def list_emails_paginated(
    db: Session,
    page: int = 1,
    per_page: int = 10,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    status: Optional[str] = None,
    category: Optional[str] = None,
) -> tuple[list[EmailRecord], int]:
    """
    Lista emails com paginação e filtros.
    Retorna (lista, total_count).
    """
    q = db.query(EmailRecord)
    if date_from:
        q = q.filter(EmailRecord.received_at >= date_from)
    if date_to:
        q = q.filter(EmailRecord.received_at <= date_to)
    if status:
        q = q.filter(EmailRecord.status == status)
    if category:
        q = q.join(EmailClassification).filter(EmailClassification.category == category)

    total = q.count()
    offset = (page - 1) * per_page
    items = q.order_by(desc(EmailRecord.received_at)).offset(offset).limit(per_page).all()
    return items, total


def get_email_with_classification(db: Session, email_record_id: int) -> Optional[EmailRecord]:
    """Obtém email com classificação."""
    return db.query(EmailRecord).filter(EmailRecord.id == email_record_id).first()


def get_by_gmail_id(db: Session, gmail_message_id: str) -> Optional[EmailRecord]:
    """Obtém registro pelo ID do Gmail."""
    return db.query(EmailRecord).filter(
        EmailRecord.gmail_message_id == gmail_message_id
    ).first()


def mark_as_sent(db: Session, email_record_id: int) -> None:
    """Marca email como enviado."""
    record = db.query(EmailRecord).filter(EmailRecord.id == email_record_id).first()
    if record:
        record.status = EmailStatus.SENT
        record.updated_at = datetime.utcnow()
        db.commit()


def mark_as_failed(db: Session, email_record_id: int) -> None:
    """Marca email como falha no envio."""
    record = db.query(EmailRecord).filter(EmailRecord.id == email_record_id).first()
    if record:
        record.status = EmailStatus.FAILED
        record.updated_at = datetime.utcnow()
        db.commit()


def get_ids_already_sent(db: Session, gmail_ids: list[str]) -> set[str]:
    """Retorna set de gmail_message_ids que já foram enviados (do conjunto informado)."""
    if not gmail_ids:
        return set()
    rows = db.query(EmailRecord.gmail_message_id).filter(
        EmailRecord.gmail_message_id.in_(gmail_ids),
        EmailRecord.status == EmailStatus.SENT,
    ).all()
    return {r[0] for r in rows if r[0]}


def get_all_sent_gmail_ids(db: Session) -> set[str]:
    """Retorna todos os gmail_message_ids que já foram respondidos (para excluir da lista)."""
    rows = db.query(EmailRecord.gmail_message_id).filter(
        EmailRecord.status == EmailStatus.SENT,
    ).all()
    return {r[0] for r in rows if r[0]}
