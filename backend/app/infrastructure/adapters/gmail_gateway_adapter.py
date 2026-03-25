"""Adaptador: expõe o módulo Gmail legado como GmailGatewayPort."""

from __future__ import annotations

from typing import Optional, Set

from app.services import gmail_service as _gmail


class GmailServiceGatewayAdapter:
    __slots__ = ()

    def is_authenticated(self) -> bool:
        return _gmail.is_authenticated()

    def get_auth_url(self) -> tuple[str, str]:
        return _gmail.get_auth_url()

    def exchange_code_for_tokens(self, code: str) -> dict:
        return _gmail.exchange_code_for_tokens(code)

    def revoke_credentials(self) -> None:
        return _gmail.revoke_credentials()

    def get_stored_scopes(self) -> list[str]:
        return _gmail.get_stored_scopes()

    def get_user_info(self) -> Optional[dict]:
        return _gmail.get_user_info()

    def list_messages(
        self,
        max_results: int = 20,
        query: str = "",
        exclude_ids: Optional[Set[str]] = None,
    ) -> list[dict]:
        return _gmail.list_messages(max_results=max_results, query=query, exclude_ids=exclude_ids)

    def list_messages_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        query: str = "",
        exclude_ids: Optional[Set[str]] = None,
    ) -> tuple[list[dict], int]:
        return _gmail.list_messages_paginated(
            page=page, per_page=per_page, query=query, exclude_ids=exclude_ids
        )

    def get_message_metadata(self, message_id: str) -> dict:
        return _gmail.get_message_metadata(message_id)

    def get_message_content(self, message_id: str) -> str:
        return _gmail.get_message_content(message_id)

    def extract_display_name_from_header(self, header_value: str) -> str:
        return _gmail.extract_display_name_from_header(header_value)

    def extract_reply_to_email(self, header_value: str) -> str:
        return _gmail._extract_email_from_header(header_value)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> None:
        return _gmail.send_email(to_email=to_email, subject=subject, body=body, thread_id=thread_id)
