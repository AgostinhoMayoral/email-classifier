"""
Serviço de integração com Gmail API via OAuth 2.0.
"""

import os
import json
import base64
from pathlib import Path
from typing import Optional
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Escopos necessários para leitura de emails
# openid é exigido pelo Google quando usamos userinfo.email e userinfo.profile
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]

# Diretório do backend para arquivos de credenciais
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
TOKENS_PATH = BACKEND_DIR / "gmail_tokens.json"


def _get_credentials_path() -> Path:
    """Retorna o caminho do arquivo credentials.json"""
    path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    if path:
        return Path(path)
    return BACKEND_DIR / "credentials.json"


def _get_redirect_uri() -> str:
    """Retorna a URI de redirect para OAuth"""
    base_url = os.getenv("API_BASE_URL", "http://localhost:8000")
    return f"{base_url.rstrip('/')}/api/auth/gmail/callback"


def get_auth_url() -> tuple[str, str]:
    """
    Gera a URL de autorização OAuth para o usuário.
    Retorna (auth_url, state).
    """
    creds_path = _get_credentials_path()
    if not creds_path.exists():
        raise FileNotFoundError(
            f"Arquivo credentials.json não encontrado em {creds_path}. "
            "Configure as credenciais do Google Cloud Console."
        )

    flow = Flow.from_client_secrets_file(
        str(creds_path),
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
    )

    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return auth_url, state


def exchange_code_for_tokens(code: str) -> dict:
    """
    Troca o código de autorização por tokens e salva em arquivo.
    Retorna informações do usuário (email, nome).
    """
    creds_path = _get_credentials_path()
    if not creds_path.exists():
        raise FileNotFoundError("Arquivo credentials.json não encontrado.")

    flow = Flow.from_client_secrets_file(
        str(creds_path),
        scopes=SCOPES,
        redirect_uri=_get_redirect_uri(),
    )

    flow.fetch_token(code=code)

    credentials = flow.credentials

    # Carregar client_id e client_secret do arquivo (necessário para refresh)
    with open(creds_path) as f:
        client_config = json.load(f)
    web_config = client_config.get("web", client_config.get("installed", {}))
    client_id = credentials.client_id or web_config.get("client_id")
    client_secret = credentials.client_secret or web_config.get("client_secret")

    # Salvar tokens
    tokens_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri or "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
    }
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens_data, f, indent=2)

    # Obter email do usuário
    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()
    return {
        "email": user_info.get("email"),
        "name": user_info.get("name"),
    }


def get_credentials() -> Optional[Credentials]:
    """Carrega credenciais salvas e retorna se válidas."""
    if not TOKENS_PATH.exists():
        return None

    with open(TOKENS_PATH) as f:
        tokens = json.load(f)

    creds = Credentials(
        token=tokens.get("token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=tokens.get("client_id"),
        client_secret=tokens.get("client_secret"),
        scopes=tokens.get("scopes", SCOPES),
    )

    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        # Atualizar token no arquivo
        tokens["token"] = creds.token
        with open(TOKENS_PATH, "w") as f:
            json.dump(tokens, f, indent=2)

    return creds


def is_authenticated() -> bool:
    """Verifica se há credenciais válidas."""
    return get_credentials() is not None


def revoke_credentials() -> None:
    """Remove as credenciais salvas (desconectar)."""
    if TOKENS_PATH.exists():
        TOKENS_PATH.unlink()


def get_user_info() -> Optional[dict]:
    """Retorna email e nome do usuário autenticado."""
    creds = get_credentials()
    if not creds:
        return None

    try:
        service = build("oauth2", "v2", credentials=creds)
        return service.userinfo().get().execute()
    except Exception:
        return None


def list_messages(max_results: int = 20, query: str = "") -> list[dict]:
    """
    Lista mensagens da caixa de entrada.
    Retorna lista com id, threadId, snippet, subject, from, date.
    """
    creds = get_credentials()
    if not creds:
        raise PermissionError("Não autenticado. Conecte sua conta Gmail primeiro.")

    service = build("gmail", "v1", credentials=creds)

    results = (
        service.users()
        .messages()
        .list(userId="me", maxResults=max_results, q=query or None)
        .execute()
    )

    messages = results.get("messages", [])
    result = []

    for msg_ref in messages:
        msg = (
            service.users()
            .messages()
            .get(userId="me", id=msg_ref["id"], format="metadata")
            .execute()
        )
        headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
        result.append(
            {
                "id": msg["id"],
                "threadId": msg.get("threadId"),
                "snippet": msg.get("snippet", ""),
                "subject": headers.get("subject", "(sem assunto)"),
                "from": headers.get("from", ""),
                "date": headers.get("date", ""),
                "labelIds": msg.get("labelIds", []),
            }
        )

    return result


def get_message_content(message_id: str) -> str:
    """
    Obtém o conteúdo completo (corpo) de uma mensagem.
    Retorna o texto decodificado.
    """
    creds = get_credentials()
    if not creds:
        raise PermissionError("Não autenticado. Conecte sua conta Gmail primeiro.")

    service = build("gmail", "v1", credentials=creds)
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="full")
        .execute()
    )

    payload = msg.get("payload", {})
    body = ""

    if "parts" in payload:
        for part in payload["parts"]:
            if part.get("mimeType") == "text/plain" and "body" in part and part["body"].get("data"):
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
                break
            if part.get("mimeType") == "text/html" and "body" in part and part["body"].get("data") and not body:
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
    elif "body" in payload and payload["body"].get("data"):
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    # Headers para contexto
    headers = {h["name"].lower(): h["value"] for h in payload.get("headers", [])}
    subject = headers.get("subject", "")
    from_addr = headers.get("from", "")
    date = headers.get("date", "")

    full_text = f"De: {from_addr}\nAssunto: {subject}\nData: {date}\n\n{body}"
    return full_text.strip()
