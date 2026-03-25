"""Implementação do repositório de emails sobre as funções SQLAlchemy existentes."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.application.ports.email_repository import EmailRepositoryPort
from app.repositories import email_repository as _repo


class SqlAlchemyEmailRepository:
    __slots__ = ("_db",)

    def __init__(self, db: Session):
        self._db = db

    def get_or_create_email_record(
        self,
        gmail_message_id: str,
        thread_id: Optional[str],
        subject: str,
        sender: str,
        snippet: Optional[str],
        received_at: Optional[datetime],
        gmail_account_email: Optional[str] = None,
    ) -> Any:
        return _repo.get_or_create_email_record(
            self._db,
            gmail_message_id,
            thread_id,
            subject,
            sender,
            snippet,
            received_at,
            gmail_account_email=gmail_account_email,
        )

    def save_classification(
        self,
        email_record_id: int,
        category: str,
        confidence: float,
        suggested_response: str,
        processed_text: Optional[str] = None,
    ) -> Any:
        return _repo.save_classification(
            self._db,
            email_record_id,
            category,
            confidence,
            suggested_response,
            processed_text,
        )

    def add_log(
        self,
        email_record_id: int,
        action: str,
        message: Optional[str] = None,
        details: Optional[str] = None,
    ) -> Any:
        return _repo.add_log(self._db, email_record_id, action, message, details)

    def list_emails_paginated(
        self,
        page: int = 1,
        per_page: int = 10,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        gmail_account_email: Optional[str] = None,
    ) -> tuple[list[Any], int]:
        return _repo.list_emails_paginated(
            self._db,
            page=page,
            per_page=per_page,
            date_from=date_from,
            date_to=date_to,
            status=status,
            category=category,
            gmail_account_email=gmail_account_email,
        )

    def get_by_gmail_id(self, gmail_message_id: str) -> Any | None:
        return _repo.get_by_gmail_id(self._db, gmail_message_id)

    def mark_as_sent(self, email_record_id: int) -> None:
        return _repo.mark_as_sent(self._db, email_record_id)

    def mark_as_failed(self, email_record_id: int) -> None:
        return _repo.mark_as_failed(self._db, email_record_id)

    def get_ids_already_sent(self, gmail_ids: list[str]) -> set[str]:
        return _repo.get_ids_already_sent(self._db, gmail_ids)

    def get_all_sent_gmail_ids(self) -> set[str]:
        return _repo.get_all_sent_gmail_ids(self._db)
