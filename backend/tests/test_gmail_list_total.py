"""Total da listagem Gmail após exclude_ids (paginação)."""
from unittest.mock import MagicMock, patch

from app.services import gmail_service


def _msg_meta(mid: str):
    return {
        "id": mid,
        "threadId": "t",
        "snippet": "",
        "payload": {
            "headers": [
                {"name": "Subject", "value": "S"},
                {"name": "From", "value": "a@b"},
                {"name": "Date", "value": "Mon, 1 Jan 2024 00:00:00 +0000"},
            ]
        },
        "internalDate": "1704067200000",
        "labelIds": ["INBOX"],
    }


@patch("app.services.gmail_service.get_credentials")
@patch("app.services.gmail_service.build")
def test_total_after_exclude_when_gmail_list_ends(mock_build, mock_creds):
    """Não usar resultSizeEstimate como total se ele incluir IDs excluídos."""
    mock_creds.return_value = MagicMock()

    list_exec = MagicMock(
        return_value={
            "messages": [{"id": "a"}, {"id": "b"}, {"id": "c"}],
            "resultSizeEstimate": 23,
        }
    )

    def get_side_effect(**kw):
        mid = kw.get("id", "")
        m = MagicMock()
        m.execute.return_value = _msg_meta(mid)
        return m

    mock_messages = MagicMock()
    mock_messages.list.return_value.execute = list_exec
    mock_messages.get.side_effect = get_side_effect

    mock_users = MagicMock()
    mock_users.messages.return_value = mock_messages

    mock_service = MagicMock()
    mock_service.users.return_value = mock_users
    mock_build.return_value = mock_service

    msgs, total = gmail_service.list_messages_paginated(
        page=1,
        per_page=50,
        query="",
        exclude_ids={"b", "c"},
    )

    assert total == 1
    assert len(msgs) == 1
    assert msgs[0]["id"] == "a"


@patch("app.services.gmail_service.get_credentials")
@patch("app.services.gmail_service.build")
def test_total_uses_estimate_when_more_pages_exist(mock_build, mock_creds):
    """Com nextPageToken, ainda não sabemos o total filtrado; mantém estimativa."""
    mock_creds.return_value = MagicMock()

    ids = [{"id": f"m{i}"} for i in range(60)]
    list_exec = MagicMock(
        return_value={
            "messages": ids[:50],
            "resultSizeEstimate": 60,
            "nextPageToken": "next",
        }
    )

    def get_side_effect(**kw):
        mid = kw.get("id", "")
        m = MagicMock()
        m.execute.return_value = _msg_meta(mid)
        return m

    mock_messages = MagicMock()
    mock_messages.list.return_value.execute = list_exec
    mock_messages.get.side_effect = get_side_effect

    mock_users = MagicMock()
    mock_users.messages.return_value = mock_messages

    mock_service = MagicMock()
    mock_service.users.return_value = mock_users
    mock_build.return_value = mock_service

    msgs, total = gmail_service.list_messages_paginated(
        page=1,
        per_page=50,
        query="",
        exclude_ids=set(),
    )

    assert len(msgs) == 50
    assert total == 60
