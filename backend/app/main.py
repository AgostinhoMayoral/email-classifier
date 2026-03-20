"""
API principal para classificação e geração de respostas de emails.
Solução para automatização de leitura e classificação de emails corporativos.
"""

from dotenv import load_dotenv
load_dotenv()

import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)

from datetime import datetime
from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
from urllib.parse import quote
import os

from sqlalchemy.orm import Session

from app.database import get_db, init_db
from app.services.processor import process_email
from app.services.text_extractor import extract_text_from_file
from app.services import gmail_service
from app.repositories import email_repository
from app.models import EmailStatus
from app.services.job_service import run_daily_job
from app.scheduler import start_scheduler, stop_scheduler
from app.models import JobConfig

app = FastAPI(
    title="Email Classifier API",
    description="API para classificação de emails em Produtivo/Improdutivo e sugestão de respostas automáticas",
    version="2.0.0"
)

# CORS para permitir requisições do frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Inicializa o banco de dados e o agendador de jobs."""
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def shutdown():
    """Para o agendador ao encerrar."""
    stop_scheduler()


# ============ Models ============

class TextInput(BaseModel):
    text: str


class ClassificationResult(BaseModel):
    category: str
    confidence: float
    suggested_response: str
    processed_text: str


class SendBatchRequest(BaseModel):
    message_ids: list[str]


class JobRunRequest(BaseModel):
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None   # YYYY-MM-DD
    only_productive: bool = False


# ============ Health ============

@app.get("/")
async def root():
    return {"status": "ok", "message": "Email Classifier API está funcionando"}


@app.get("/health")
async def health():
    return {"status": "healthy"}


# ============ Classify (file/text) ============

@app.post("/api/classify", response_model=ClassificationResult)
async def classify_email(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    """Classifica email por arquivo ou texto."""
    email_content = None
    if file:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")
        ext = file.filename.lower().split(".")[-1]
        if ext not in ["txt", "pdf"]:
            raise HTTPException(status_code=400, detail="Formato não suportado. Use .txt ou .pdf")
        content = await file.read()
        email_content = extract_text_from_file(content, ext)
        if not email_content or not email_content.strip():
            raise HTTPException(status_code=400, detail="Não foi possível extrair texto do arquivo")
    elif text and text.strip():
        email_content = text.strip()
    else:
        raise HTTPException(status_code=400, detail="Envie um arquivo (.txt ou .pdf) ou insira o texto do email")

    try:
        result = process_email(email_content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar email: {str(e)}")


# ============ Gmail OAuth ============

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@app.get("/api/auth/gmail/url")
async def gmail_auth_url():
    try:
        auth_url, _ = gmail_service.get_auth_url()
        return {"auth_url": auth_url}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/auth/gmail/callback")
async def gmail_callback(code: Optional[str] = Query(None), error: Optional[str] = Query(None)):
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(error)}")
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error=missing_code")
    try:
        user_info = gmail_service.exchange_code_for_tokens(code)
        email = user_info.get("email", "")
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_success=1&email={quote(email)}")
    except Exception as e:
        logging.getLogger("gmail").exception("OAuth callback falhou: %s", e)
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(str(e))}")


@app.get("/api/auth/gmail/status")
async def gmail_status():
    if not gmail_service.is_authenticated():
        return {"authenticated": False}
    user = gmail_service.get_user_info()
    scopes = gmail_service.get_stored_scopes()
    has_send = "https://www.googleapis.com/auth/gmail.send" in scopes
    return {
        "authenticated": True,
        "email": user.get("email") if user else None,
        "name": user.get("name") if user else None,
        "can_send": has_send,
        "scopes": scopes,
    }


@app.post("/api/auth/gmail/revoke")
async def gmail_revoke():
    gmail_service.revoke_credentials()
    return {"success": True}


# ============ Emails (Gmail + DB) ============

def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD ou DD/MM/YYYY."""
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str.strip()[:10], fmt)
        except ValueError:
            continue
    return None


@app.get("/api/emails")
async def list_emails(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    date_from: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD ou DD/MM/YYYY)"),
    date_to: Optional[str] = Query(None, description="Data final (YYYY-MM-DD ou DD/MM/YYYY)"),
    db: Session = Depends(get_db),
):
    """
    Lista emails do Gmail com paginação e filtro de data.
    Sincroniza com o banco: retorna classificação e status de envio quando existir.
    """
    try:
        if not gmail_service.is_authenticated():
            raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")

        # Montar query Gmail
        gmail_query_parts = []
        df = _parse_date(date_from)
        dt = _parse_date(date_to)
        if df:
            gmail_query_parts.append(f"after:{df.strftime('%Y/%m/%d')}")
        if dt:
            # Gmail before é exclusivo; adicionar 1 dia para incluir o dia final
            from datetime import timedelta
            dt_adj = dt + timedelta(days=1)
            gmail_query_parts.append(f"before:{dt_adj.strftime('%Y/%m/%d')}")
        gmail_query = " ".join(gmail_query_parts) if gmail_query_parts else ""

        # Buscar mais do Gmail para paginar (Gmail não tem offset nativo)
        max_fetch = page * per_page
        messages = gmail_service.list_messages(max_results=min(max_fetch, 100), query=gmail_query or None)

        # IDs já enviados (evitar duplicados)
        gmail_ids = [m["id"] for m in messages]
        sent_ids = email_repository.get_ids_already_sent(db, gmail_ids)

        # Enriquecer com dados do DB
        for m in messages:
            m["already_sent"] = m["id"] in sent_ids
            record = email_repository.get_by_gmail_id(db, m["id"])
            if record:
                m["record_id"] = record.id
                m["status"] = record.status
                if record.classification:
                    m["category"] = record.classification.category
                    m["confidence"] = record.classification.confidence
                    m["suggested_response"] = record.classification.suggested_response
                else:
                    m["category"] = None
                    m["confidence"] = None
                    m["suggested_response"] = None
            else:
                m["record_id"] = None
                m["status"] = "pending"
                m["category"] = None
                m["confidence"] = None
                m["suggested_response"] = None

        # Paginar
        total = len(messages)
        start = (page - 1) * per_page
        emails_page = messages[start:start + per_page]

        return {
            "emails": emails_page,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
            },
        }
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/emails/records")
async def list_email_records(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=50),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Lista emails persistidos no banco com paginação e filtros."""
    df = _parse_date(date_from)
    dt = _parse_date(date_to)
    if dt:
        from datetime import timedelta
        dt = dt.replace(hour=23, minute=59, second=59, microsecond=999999)

    items, total = email_repository.list_emails_paginated(
        db, page=page, per_page=per_page,
        date_from=df, date_to=dt, status=status, category=category,
    )

    result = []
    for r in items:
        rec = {
            "id": r.id,
            "gmail_message_id": r.gmail_message_id,
            "thread_id": r.thread_id,
            "subject": r.subject,
            "sender": r.sender,
            "snippet": r.snippet,
            "received_at": r.received_at.isoformat() if r.received_at else None,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        if r.classification:
            rec["category"] = r.classification.category
            rec["confidence"] = r.classification.confidence
            rec["suggested_response"] = r.classification.suggested_response
        else:
            rec["category"] = None
            rec["confidence"] = None
            rec["suggested_response"] = None
        result.append(rec)

    return {
        "emails": result,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": (total + per_page - 1) // per_page if total > 0 else 1,
        },
    }


@app.post("/api/emails/send-batch")
async def send_batch(
    body: SendBatchRequest,
    db: Session = Depends(get_db),
):
    """
    Envia respostas sugeridas pela IA para os emails selecionados.
    Evita duplicados: não envia se já foi enviado.
    Se o email não estiver classificado, classifica automaticamente antes de enviar.
    """
    if not gmail_service.is_authenticated():
        raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")

    sent_ids = email_repository.get_ids_already_sent(db, body.message_ids)
    to_send = [mid for mid in body.message_ids if mid not in sent_ids]
    if not to_send:
        return {"sent": 0, "skipped": len(body.message_ids), "errors": [], "message": "Todos já foram enviados."}

    results = {"sent": 0, "skipped": len(sent_ids), "errors": []}

    for gmail_id in to_send:
        record = email_repository.get_by_gmail_id(db, gmail_id)
        if not record:
            # Criar registro e classificar
            try:
                msg_data = gmail_service.get_message_metadata(gmail_id)
                content = gmail_service.get_message_content(gmail_id)
                classification_result = process_email(content)
                received_at = None
                if msg_data.get("internalDate"):
                    received_at = datetime.utcfromtimestamp(int(msg_data["internalDate"]) / 1000)
                record = email_repository.get_or_create_email_record(
                    db, gmail_id, msg_data.get("threadId"),
                    msg_data.get("subject", "(sem assunto)"), msg_data.get("from", ""),
                    msg_data.get("snippet"), received_at,
                )
                email_repository.save_classification(
                    db, record.id,
                    classification_result["category"], classification_result["confidence"],
                    classification_result["suggested_response"], classification_result.get("processed_text"),
                )
                record.status = EmailStatus.CLASSIFIED
                record.updated_at = datetime.utcnow()
                db.commit()
            except Exception as e:
                results["errors"].append({"gmail_id": gmail_id, "error": str(e)})
                continue
        if not record.classification:
            results["errors"].append({"gmail_id": gmail_id, "error": "Falha ao classificar o email."})
            continue
        if record.status == EmailStatus.SENT:
            results["skipped"] += 1
            continue

        to_email = gmail_service._extract_email_from_header(record.sender)
        if not to_email:
            results["errors"].append({"gmail_id": gmail_id, "error": "Email do destinatário não encontrado"})
            continue

        subject = record.subject
        if not subject.startswith("Re:"):
            subject = f"Re: {subject}"

        try:
            gmail_service.send_email(
                to_email=to_email,
                subject=subject,
                body=record.classification.suggested_response,
                thread_id=record.thread_id,
            )
            email_repository.mark_as_sent(db, record.id)
            email_repository.add_log(db, record.id, "sent", "Resposta enviada com sucesso")
            results["sent"] += 1
        except Exception as e:
            email_repository.mark_as_failed(db, record.id)
            email_repository.add_log(db, record.id, "failed", str(e))
            results["errors"].append({"gmail_id": gmail_id, "error": str(e)})

    return results


@app.get("/api/emails/{message_id}")
async def get_email(message_id: str):
    try:
        content = gmail_service.get_message_content(message_id)
        return {"content": content}
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/emails/{message_id}/classify")
async def classify_gmail_email(
    message_id: str,
    db: Session = Depends(get_db),
):
    """Obtém o email do Gmail, classifica com IA e persiste no banco."""
    try:
        if not gmail_service.is_authenticated():
            raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")

        msg_data = gmail_service.get_message_metadata(message_id)
        content = gmail_service.get_message_content(message_id)
        result = process_email(content)

        received_at = None
        if msg_data.get("internalDate"):
            received_at = datetime.utcfromtimestamp(int(msg_data["internalDate"]) / 1000)

        record = email_repository.get_or_create_email_record(
            db,
            gmail_message_id=message_id,
            thread_id=msg_data.get("threadId"),
            subject=msg_data.get("subject", "(sem assunto)"),
            sender=msg_data.get("from", ""),
            snippet=msg_data.get("snippet"),
            received_at=received_at,
        )
        email_repository.save_classification(
            db,
            record.id,
            result["category"],
            result["confidence"],
            result["suggested_response"],
            result.get("processed_text"),
        )
        record.status = EmailStatus.CLASSIFIED
        record.updated_at = datetime.utcnow()
        db.commit()
        email_repository.add_log(db, record.id, "classified", "Classificação realizada com sucesso")

        return result
    except HTTPException:
        raise
    except PermissionError:
        raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============ Job Diário ============

class JobConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    only_productive: Optional[bool] = None


@app.get("/api/jobs/config")
async def get_job_config(db: Session = Depends(get_db)):
    """Retorna a configuração do job diário."""
    config = db.query(JobConfig).first()
    if not config:
        config = JobConfig(name="Job Diário", enabled=True, cron_expression="0 9 * * *")
        db.add(config)
        db.commit()
        db.refresh(config)
    return {
        "id": config.id,
        "name": config.name,
        "enabled": config.enabled,
        "cron_expression": config.cron_expression,
        "date_from": config.date_from.strftime("%Y-%m-%d") if config.date_from else None,
        "date_to": config.date_to.strftime("%Y-%m-%d") if config.date_to else None,
        "only_productive": config.only_productive,
        "last_run_at": config.last_run_at.isoformat() if config.last_run_at else None,
    }


@app.put("/api/jobs/config")
async def update_job_config(
    body: JobConfigUpdate,
    db: Session = Depends(get_db),
):
    """Atualiza a configuração do job diário."""
    config = db.query(JobConfig).first()
    if not config:
        config = JobConfig(name="Job Diário", enabled=True, cron_expression="0 9 * * *")
        db.add(config)
        db.commit()
        db.refresh(config)
    if body.enabled is not None:
        config.enabled = body.enabled
    if body.cron_expression is not None:
        config.cron_expression = body.cron_expression
    if body.date_from is not None:
        config.date_from = _parse_date(body.date_from)
    if body.date_to is not None:
        config.date_to = _parse_date(body.date_to)
    if body.only_productive is not None:
        config.only_productive = body.only_productive
    db.commit()
    db.refresh(config)
    return {"success": True}


@app.post("/api/jobs/run")
async def run_job(
    body: Optional[JobRunRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Executa o job de classificação e envio manualmente.
    Opcional: date_from, date_to (YYYY-MM-DD), only_productive.
    """
    req = body or JobRunRequest()
    df = _parse_date(req.date_from)
    dt = _parse_date(req.date_to)
    result = run_daily_job(db, date_from=df, date_to=dt, only_productive=req.only_productive)
    return result
