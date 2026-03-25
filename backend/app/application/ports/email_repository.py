from __future__ import annotations

from datetime import datetime
from typing import Any, Optional, Protocol


class EmailRepositoryPort(Protocol):
    """Porta de persistência de emails — implementação em infraestrutura (SQLAlchemy)."""

    def get_or_create_email_record(
        self,
        gmail_message_id: str,
        thread_id: Optional[str],
        subject: str,
        sender: str,
        snippet: Optional[str],
        received_at: Optional[datetime],
        gmail_account_email: Optional[str] = None,
    ) -> Any: ...

    def save_classification(
        self,
        email_record_id: int,
        category: str,
        confidence: float,
        suggested_response: str,
        processed_text: Optional[str] = None,
    ) -> Any: ...

    def add_log(
        self,
        email_record_id: int,
        action: str,
        message: Optional[str] = None,
        details: Optional[str] = None,
    ) -> Any: ...

    def list_emails_paginated(
        self,
        page: int = 1,
        per_page: int = 10,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        status: Optional[str] = None,
        category: Optional[str] = None,
        gmail_account_email: Optional[str] = None,
    ) -> tuple[list[Any], int]: ...

    def get_by_gmail_id(self, gmail_message_id: str) -> Any | None: ...

    def mark_as_sent(self, email_record_id: int) -> None: ...

    def mark_as_failed(self, email_record_id: int) -> None: ...

    def get_ids_already_sent(self, gmail_ids: list[str]) -> set[str]: ...

    def get_all_sent_gmail_ids(self) -> set[str]: ...
