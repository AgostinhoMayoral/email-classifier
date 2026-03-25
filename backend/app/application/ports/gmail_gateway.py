from __future__ import annotations

from typing import Any, Optional, Protocol, Set


class GmailGatewayPort(Protocol):
    """Porta para operações Gmail usadas pelos casos de uso e pela API."""

    def is_authenticated(self) -> bool: ...

    def get_auth_url(self) -> tuple[str, str]: ...

    def exchange_code_for_tokens(self, code: str) -> dict: ...

    def revoke_credentials(self) -> None: ...

    def get_stored_scopes(self) -> list[str]: ...

    def get_user_info(self) -> Optional[dict]: ...

    def list_messages(
        self,
        max_results: int = 20,
        query: str = "",
        exclude_ids: Optional[Set[str]] = None,
    ) -> list[dict]: ...

    def list_messages_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        query: str = "",
        exclude_ids: Optional[Set[str]] = None,
    ) -> tuple[list[dict], int]: ...

    def get_message_metadata(self, message_id: str) -> dict: ...

    def get_message_content(self, message_id: str) -> str: ...

    def extract_display_name_from_header(self, header_value: str) -> str: ...

    def extract_reply_to_email(self, header_value: str) -> str:
        """Endereço do remetente para Reply-To (ex-era _extract_email_from_header)."""

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        thread_id: Optional[str] = None,
    ) -> None: ...
