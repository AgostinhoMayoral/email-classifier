"""
Serviço de integração com Gmail API via OAuth 2.0.
"""

import os
import json
import logging

# Permite que o Google retorne escopos diferentes dos solicitados (ex: menos escopos)
# sem que oauthlib lance "Scope has changed". Depois verificamos manualmente.
os.environ.setdefault("OAUTHLIB_RELAX_TOKEN_SCOPE", "1")

logger = logging.getLogger("gmail_service")
import base64
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Set

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

# Escopos necessários para leitura e envio de emails
SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.compose",
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


def _expiry_to_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _expiry_from_json(raw: Any) -> Optional[datetime]:
    """Parse da data de expiração do access token; None se ausente ou inválida."""
    if not raw or not isinstance(raw, str):
        return None
    try:
        normalized = raw.replace("Z", "+00:00")
        dt = datetime.fromisoformat(normalized)
        # google.auth compara expiry com utcnow() naive — usar UTC naive evita TypeError (py3.12+).
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt
    except ValueError:
        logger.warning("expiry inválida em gmail_tokens.json: %s", raw)
        return None


def _write_tokens_file(tokens: dict) -> None:
    with open(TOKENS_PATH, "w") as f:
        json.dump(tokens, f, indent=2)


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
    logger.info("get_auth_url: scopes solicitados=%s", SCOPES)
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
    granted = set(credentials.scopes or [])
    logger.info("exchange_code_for_tokens: escopos concedidos pelo Google=%s", sorted(granted))

    # Verificar se temos permissão de envio (necessário para send-batch)
    required_send = "https://www.googleapis.com/auth/gmail.send"
    if required_send not in granted:
        logger.warning("gmail.send não concedido. Concedidos: %s", sorted(granted))
        raise PermissionError(
            "Permissão de envio não concedida. Adicione os escopos gmail.send e gmail.compose "
            "na Tela de consentimento OAuth do Google Cloud Console (APIs e Serviços → Tela de consentimento → Escopos). "
            "Depois apague gmail_tokens.json e conecte novamente."
        )

    # Carregar client_id e client_secret do arquivo (necessário para refresh)
    with open(creds_path) as f:
        client_config = json.load(f)
    web_config = client_config.get("web", client_config.get("installed", {}))
    client_id = credentials.client_id or web_config.get("client_id")
    client_secret = credentials.client_secret or web_config.get("client_secret")

    # Salvar tokens (expiry é obrigatória para detectar token expirado nas próximas sessões)
    tokens_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri or "https://oauth2.googleapis.com/token",
        "client_id": client_id,
        "client_secret": client_secret,
        "scopes": list(credentials.scopes) if credentials.scopes else SCOPES,
        "expiry": _expiry_to_iso(credentials.expiry),
    }
    _write_tokens_file(tokens_data)
    logger.info("Tokens salvos com escopos: %s", tokens_data.get("scopes"))

    # Obter email do usuário
    service = build("oauth2", "v2", credentials=credentials)
    user_info = service.userinfo().get().execute()
    return {
        "email": user_info.get("email"),
        "name": user_info.get("name"),
    }


def get_credentials() -> Optional[Credentials]:
    """
    Carrega credenciais salvas, renova o access token quando expirado e persiste.

    Sem o campo `expiry` no JSON (versões antigas do app), a biblioteca google-auth
    considera `expired == False` para sempre e o refresh nunca rodava — após ~1h a
    API do Gmail falhava até o Google renovar por outros meios ou dar timeout.
    """
    if not TOKENS_PATH.exists():
        return None

    try:
        with open(TOKENS_PATH) as f:
            tokens = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("get_credentials: não foi possível ler gmail_tokens.json: %s", e)
        return None

    expiry_raw = tokens.get("expiry")
    expiry = _expiry_from_json(expiry_raw) if expiry_raw else None
    expiry_corrupt = bool(expiry_raw) and expiry is None

    creds = Credentials(
        token=tokens.get("token"),
        refresh_token=tokens.get("refresh_token"),
        token_uri=tokens.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=tokens.get("client_id"),
        client_secret=tokens.get("client_secret"),
        scopes=tokens.get("scopes", SCOPES),
        expiry=expiry,
    )

    # Arquivos legados sem `expiry`: forçar um refresh para gravar expiração e obter token válido.
    must_refresh = bool(creds.refresh_token) and (
        creds.expired or not expiry_raw or expiry_corrupt
    )
    if must_refresh:
        reason = "expirado" if creds.expired else "sem expiry confiável no arquivo"
        logger.info(
            "get_credentials: renovando token (%s). Escopos armazenados=%s",
            reason,
            tokens.get("scopes"),
        )
        try:
            creds.refresh(Request())
        except RefreshError as e:
            logger.warning("get_credentials: refresh falhou (reconecte o Gmail): %s", e)
            return None
        logger.info("get_credentials: após refresh, escopos=%s", creds.scopes)
        tokens["token"] = creds.token
        exp_iso = _expiry_to_iso(creds.expiry)
        if exp_iso:
            tokens["expiry"] = exp_iso
        _write_tokens_file(tokens)

    if not creds.token or not creds.valid:
        return None

    return creds


def is_authenticated() -> bool:
    """Verifica se há credenciais válidas (access token válido ou renovado)."""
    return get_credentials() is not None


def get_stored_scopes() -> list[str]:
    """Retorna os escopos armazenados no token (sem carregar/renovar)."""
    if not TOKENS_PATH.exists():
        return []
    try:
        with open(TOKENS_PATH) as f:
            tokens = json.load(f)
        return tokens.get("scopes") or []
    except Exception:
        return []


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


# Máximo de mensagens que buscamos do Gmail (evita loops longos em caixas enormes)
MAX_MESSAGES_FETCH = 5000


def list_messages(max_results: int = 20, query: str = "", exclude_ids: Optional[Set[str]] = None) -> list[dict]:
    """
    Lista mensagens da caixa de entrada (compatibilidade).
    Para paginação completa, use list_messages_paginated.
    """
    msgs, _ = list_messages_paginated(page=1, per_page=max_results, query=query, exclude_ids=exclude_ids)
    return msgs


def list_messages_paginated(
    page: int = 1,
    per_page: int = 50,
    query: str = "",
    exclude_ids: Optional[Set[str]] = None,
) -> tuple[list[dict], int]:
    """
    Lista mensagens do Gmail com paginação real via pageToken.
    Busca apenas mensagens da caixa de entrada (INBOX), excluindo as enviadas pelo usuário.
    Se exclude_ids for informado, filtra mensagens já respondidas (não aparecem na lista).

    Returns:
        (messages, total) - lista da página; total é exato se a listagem do Gmail
        terminou nesta requisição, caso contrário é limite inferior vs. resultSizeEstimate.
    """
    creds = get_credentials()
    if not creds:
        raise PermissionError("Não autenticado. Conecte sua conta Gmail primeiro.")

    service = build("gmail", "v1", credentials=creds)

    # Apenas mensagens RECEBIDAS: INBOX + excluir as que NÓS enviamos (-from:me)
    # Crítico: não podemos responder ao que nós mesmos respondemos
    gmail_query = "in:inbox -from:me"
    if query and query.strip():
        gmail_query = f"{gmail_query} {query.strip()}"

    exclude = exclude_ids or set()
    needed_count = page * per_page

    # 1. Coletar IDs em lotes, filtrando exclude_ids até ter o suficiente para a página
    all_ids: list[dict] = []
    all_ids_filtered: list[dict] = []
    next_token: Optional[str] = None
    total_estimate = 0
    gmail_list_exhausted = False

    while len(all_ids_filtered) < needed_count and len(all_ids) < MAX_MESSAGES_FETCH:
        list_params: dict = {
            "userId": "me",
            "maxResults": 500,
            "q": gmail_query,
        }
        if next_token:
            list_params["pageToken"] = next_token

        results = (
            service.users()
            .messages()
            .list(**{k: v for k, v in list_params.items() if v is not None})
            .execute()
        )

        batch = results.get("messages", [])
        all_ids.extend(batch)
        total_estimate = results.get("resultSizeEstimate", len(all_ids))

        for m in batch:
            if m.get("id") and m["id"] not in exclude:
                all_ids_filtered.append(m)

        next_token = results.get("nextPageToken")
        if not batch or not next_token:
            gmail_list_exhausted = True
            break

    # resultSizeEstimate do Gmail não desconta exclude_ids; quando não há mais páginas,
    # o total correto é só as mensagens que passaram pelo filtro (ex.: já respondidas).
    if gmail_list_exhausted:
        total = len(all_ids_filtered)
    else:
        total = max(total_estimate, len(all_ids_filtered))

    # 2. Pegar o slice de IDs para a página atual (apenas não respondidos)
    start = (page - 1) * per_page
    end = start + per_page
    ids_for_page = [m["id"] for m in all_ids_filtered[start:end]]

    # 3. Buscar metadados apenas dos emails da página
    result = []
    for msg_id in ids_for_page:
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="metadata")
                .execute()
            )
            headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
            internal_date = msg.get("internalDate")
            result.append(
                {
                    "id": msg["id"],
                    "threadId": msg.get("threadId"),
                    "snippet": msg.get("snippet", ""),
                    "subject": headers.get("subject", "(sem assunto)"),
                    "from": headers.get("from", ""),
                    "date": headers.get("date", ""),
                    "internalDate": int(internal_date) if internal_date else None,
                    "labelIds": msg.get("labelIds", []),
                }
            )
        except Exception as e:
            logger.warning("Erro ao buscar mensagem %s: %s", msg_id, e)

    return result, total


def get_message_metadata(message_id: str) -> dict:
    """Obtém metadados da mensagem (subject, from, date, etc)."""
    creds = get_credentials()
    if not creds:
        raise PermissionError("Não autenticado. Conecte sua conta Gmail primeiro.")

    service = build("gmail", "v1", credentials=creds)
    msg = (
        service.users()
        .messages()
        .get(userId="me", id=message_id, format="metadata")
        .execute()
    )
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    return {
        "id": msg["id"],
        "threadId": msg.get("threadId"),
        "snippet": msg.get("snippet", ""),
        "subject": headers.get("subject", "(sem assunto)"),
        "from": headers.get("from", ""),
        "date": headers.get("date", ""),
        "internalDate": int(msg["internalDate"]) if msg.get("internalDate") else None,
    }


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


def _extract_email_from_header(header_value: str) -> str:
    """Extrai endereço de email de string como 'Nome <email@domain.com>'."""
    if not header_value:
        return ""
    match = re.search(r"<([^>]+)>", header_value)
    if match:
        return match.group(1).strip().lower()
    return header_value.strip().lower()


def extract_display_name_from_header(header_value: str) -> str:
    """
    Extrai o nome de exibição de string como 'João Silva <joao@email.com>'.
    Retorna o nome para personalização (saudação Prezado João, etc).
    """
    if not header_value or not header_value.strip():
        return ""
    s = header_value.strip()
    # Formato: "Nome <email>" -> extrair Nome
    if " <" in s and ">" in s:
        name_part = s.split("<")[0].strip().strip('"\'')
        if name_part and "@" not in name_part:
            return name_part
    # Apenas email, sem nome
    if "@" in s:
        return ""
    return s


def send_email(
    to_email: str,
    subject: str,
    body: str,
    thread_id: Optional[str] = None,
) -> dict:
    """
    Envia um email via Gmail API.
    Se thread_id for informado, a resposta será adicionada à mesma thread.
    Retorna a mensagem enviada ou levanta exceção.
    """
    creds = get_credentials()
    if not creds:
        raise PermissionError("Não autenticado. Conecte sua conta Gmail primeiro.")

    service = build("gmail", "v1", credentials=creds)

    from email.mime.text import MIMEText
    from email.mime.multipart import MIMEMultipart

    msg = MIMEMultipart("alternative")
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain", "utf-8"))

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    payload: dict = {"raw": raw}
    if thread_id:
        payload["threadId"] = thread_id

    try:
        result = service.users().messages().send(userId="me", body=payload).execute()
        logger.info("send_email: enviado com sucesso para %s", to_email)
        return result
    except Exception as e:
        logger.exception("send_email: falha ao enviar para %s - %s", to_email, e)
        raise
