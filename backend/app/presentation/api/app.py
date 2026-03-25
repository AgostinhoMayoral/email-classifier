"""API HTTP (FastAPI): apenas adaptação HTTP → casse de uso."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Optional
from urllib.parse import quote

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.application.use_cases.classify_gmail_message import execute_classify_gmail_message
from app.application.use_cases.send_batch_replies import execute_send_batch_replies
from app.composition import get_email_processing_application_service, get_gmail_gateway
from app.database import get_db, init_db
from app.infrastructure.adapters.sqlalchemy_email_repository import SqlAlchemyEmailRepository
from app.models import JobConfig
from app.scheduler import start_scheduler, stop_scheduler
from app.services.job_service import run_daily_job
from app.services.text_extractor import extract_text_from_file
from app.timezone_utils import (
    gmail_after_before_strings_current_month_sp,
    sp_calendar_bounds_to_utc_naive,
    sp_day_end_utc_naive,
    sp_day_start_utc_naive,
)

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


def _parse_date(date_str: Optional[str]) -> Optional[datetime]:
    if not date_str:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y"):
        try:
            return datetime.strptime(date_str.strip()[:10], fmt)
        except ValueError:
            continue
    return None


def _current_gmail_account_email() -> Optional[str]:
    info = get_gmail_gateway().get_user_info()
    if not info:
        return None
    e = (info.get("email") or "").strip().lower()
    return e or None


class TextInput(BaseModel):
    text: str


class ClassificationResult(BaseModel):
    category: str
    confidence: float
    suggested_response: str
    processed_text: str
    ai_used: bool = True


class SendBatchRequest(BaseModel):
    message_ids: list[str]


class SendSingleRequest(BaseModel):
    to_email: str
    subject: str
    body: str


class JobRunRequest(BaseModel):
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    only_productive: bool = False


class JobConfigUpdate(BaseModel):
    enabled: Optional[bool] = None
    cron_expression: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    only_productive: Optional[bool] = None


def create_app() -> FastAPI:
    app = FastAPI(
        title="Email Classifier API",
        description="API para classificação de emails em Produtivo/Improdutivo e sugestão de respostas automáticas",
        version="2.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.on_event("startup")
    def startup():
        init_db()
        start_scheduler()

    @app.on_event("shutdown")
    def shutdown():
        stop_scheduler()

    @app.get("/")
    async def root():
        return {"status": "ok", "message": "Email Classifier API está funcionando"}

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    @app.post("/api/classify", response_model=ClassificationResult)
    async def classify_email(
        file: Optional[UploadFile] = File(None),
        text: Optional[str] = Form(None),
        recipient_name: Optional[str] = Form(None),
        sender_name: Optional[str] = Form(None),
    ):
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
            raise HTTPException(
                status_code=400,
                detail="Envie um arquivo (.txt ou .pdf) ou insira o texto do email",
            )

        try:
            gmail = get_gmail_gateway()
            sender = (sender_name or "").strip()
            if not sender and gmail.is_authenticated():
                user_info = gmail.get_user_info()
                if user_info and user_info.get("name"):
                    sender = user_info.get("name", "").strip()
            if not sender:
                sender = os.getenv("USER_NAME", "").strip() or None

            classifier = get_email_processing_application_service()
            result = classifier.process(
                email_content,
                recipient_name=(recipient_name or "").strip() or None,
                sender_name=sender or None,
            ).as_dict()
            return result
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Erro ao processar email: {str(e)}") from e

    @app.post("/api/send-single")
    async def send_single_email(body: SendSingleRequest):
        gmail = get_gmail_gateway()
        if not gmail.is_authenticated():
            raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")
        email = (body.to_email or "").strip().lower()
        if not email or "@" not in email:
            raise HTTPException(status_code=400, detail="Informe um email de destinatário válido.")
        subject = (body.subject or "").strip() or "Resposta"
        body_text = (body.body or "").strip()
        if not body_text:
            raise HTTPException(status_code=400, detail="O corpo da mensagem não pode estar vazio.")
        try:
            gmail.send_email(to_email=email, subject=subject, body=body_text)
            return {"success": True, "message": "Email enviado com sucesso."}
        except PermissionError as e:
            raise HTTPException(status_code=403, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/auth/gmail/debug-redirect-uri")
    async def gmail_debug_redirect_uri():
        redirect = f"{os.getenv('API_BASE_URL', 'http://localhost:8000').rstrip('/')}/api/auth/gmail/callback"
        return {"redirect_uri": redirect, "api_base_url": os.getenv("API_BASE_URL")}

    @app.get("/api/auth/gmail/url")
    async def gmail_auth_url():
        try:
            auth_url, _ = get_gmail_gateway().get_auth_url()
            return {"auth_url": auth_url}
        except FileNotFoundError as e:
            raise HTTPException(status_code=503, detail=str(e)) from e

    @app.get("/api/auth/gmail/callback")
    async def gmail_callback(code: Optional[str] = Query(None), error: Optional[str] = Query(None)):
        if error:
            return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(error)}")
        if not code:
            return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error=missing_code")
        try:
            user_info = get_gmail_gateway().exchange_code_for_tokens(code)
            email = user_info.get("email", "")
            return RedirectResponse(url=f"{FRONTEND_URL}?gmail_success=1&email={quote(email)}")
        except Exception as e:
            err_str = str(e)
            logging.getLogger("gmail").exception("OAuth callback falhou: %s", e)
            if "invalid_client" in err_str.lower() or "unauthorized" in err_str.lower():
                hint = (
                    "Verifique: 1) Tipo de credencial = Aplicativo da Web (não Desktop). "
                    "2) redirect_uri exato no Google Cloud: http://localhost:8000/api/auth/gmail/callback. "
                    "3) credentials.json com estrutura 'web'. Veja GMAIL_SETUP.md"
                )
                return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(hint)}")
            return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(err_str)}")

    @app.get("/api/auth/gmail/status")
    async def gmail_status():
        gmail = get_gmail_gateway()
        if not gmail.is_authenticated():
            return {"authenticated": False}
        user = gmail.get_user_info()
        scopes = gmail.get_stored_scopes()
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
        get_gmail_gateway().revoke_credentials()
        return {"success": True}

    @app.get("/api/emails")
    async def list_emails(
        page: int = Query(1, ge=1),
        per_page: int = Query(10, ge=1, le=50),
        date_from: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD ou DD/MM/YYYY)"),
        date_to: Optional[str] = Query(None, description="Data final (YYYY-MM-DD ou DD/MM/YYYY)"),
        db: Session = Depends(get_db),
    ):
        try:
            gmail = get_gmail_gateway()
            repo = SqlAlchemyEmailRepository(db)
            if not gmail.is_authenticated():
                raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")

            gmail_query_parts = []
            df = _parse_date(date_from)
            dt = _parse_date(date_to)
            if df is None and dt is None:
                after_s, before_s = gmail_after_before_strings_current_month_sp()
                gmail_query_parts.append(f"after:{after_s}")
                gmail_query_parts.append(f"before:{before_s}")
            else:
                if df:
                    gmail_query_parts.append(f"after:{df.strftime('%Y/%m/%d')}")
                if dt:
                    from datetime import timedelta

                    dt_adj = dt + timedelta(days=1)
                    gmail_query_parts.append(f"before:{dt_adj.strftime('%Y/%m/%d')}")
            gmail_query = " ".join(gmail_query_parts) if gmail_query_parts else ""

            sent_ids = repo.get_all_sent_gmail_ids()
            messages, total = gmail.list_messages_paginated(
                page=page,
                per_page=per_page,
                query=gmail_query or "",
                exclude_ids=sent_ids,
            )

            gmail_ids = [m["id"] for m in messages]
            sent_ids_page = repo.get_ids_already_sent(gmail_ids)

            for m in messages:
                m["already_sent"] = m["id"] in sent_ids_page
                record = repo.get_by_gmail_id(m["id"])
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

            return {
                "emails": messages,
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
            raise HTTPException(status_code=500, detail=str(e)) from e

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
        gmail = get_gmail_gateway()
        repo = SqlAlchemyEmailRepository(db)
        if not gmail.is_authenticated():
            raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")
        account = _current_gmail_account_email()
        if not account:
            raise HTTPException(
                status_code=401,
                detail="Não foi possível obter o email da conta Google. Reconecte o Gmail.",
            )

        df = _parse_date(date_from)
        dt = _parse_date(date_to)
        df_utc = None
        dt_utc = None
        if df is not None and dt is not None:
            df_utc, dt_utc = sp_calendar_bounds_to_utc_naive(df, dt)
        elif df is not None:
            df_utc = sp_day_start_utc_naive(df)
        elif dt is not None:
            dt_utc = sp_day_end_utc_naive(dt)

        items, total = repo.list_emails_paginated(
            page=page,
            per_page=per_page,
            date_from=df_utc,
            date_to=dt_utc,
            status=status,
            category=category,
            gmail_account_email=account,
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
        gmail = get_gmail_gateway()
        if not gmail.is_authenticated():
            raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")

        account = _current_gmail_account_email()
        if not account:
            raise HTTPException(
                status_code=401,
                detail="Não foi possível obter o email da conta Google. Reconecte o Gmail.",
            )

        return execute_send_batch_replies(
            db,
            gmail,
            SqlAlchemyEmailRepository(db),
            get_email_processing_application_service(),
            body.message_ids,
            account,
        )

    @app.get("/api/emails/{message_id}")
    async def get_email(message_id: str):
        try:
            content = get_gmail_gateway().get_message_content(message_id)
            return {"content": content}
        except PermissionError as e:
            raise HTTPException(status_code=401, detail=str(e)) from e
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.post("/api/emails/{message_id}/classify")
    async def classify_gmail_email(
        message_id: str,
        db: Session = Depends(get_db),
    ):
        try:
            gmail = get_gmail_gateway()
            if not gmail.is_authenticated():
                raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")

            account = _current_gmail_account_email()
            if not account:
                raise HTTPException(
                    status_code=401,
                    detail="Não foi possível obter o email da conta Google. Reconecte o Gmail.",
                )
            return execute_classify_gmail_message(
                db,
                gmail,
                SqlAlchemyEmailRepository(db),
                get_email_processing_application_service(),
                message_id,
                account,
            )
        except HTTPException:
            raise
        except PermissionError:
            raise HTTPException(status_code=401, detail="Conecte sua conta Gmail primeiro.")
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e)) from e

    @app.get("/api/jobs/config")
    async def get_job_config(db: Session = Depends(get_db)):
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
        req = body or JobRunRequest()
        df = _parse_date(req.date_from)
        dt = _parse_date(req.date_to)
        result = run_daily_job(db, date_from=df, date_to=dt, only_productive=req.only_productive)
        return result

    return app
