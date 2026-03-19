"""
API principal para classificação e geração de respostas de emails.
Solução para automatização de leitura e classificação de emails corporativos.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional
from urllib.parse import quote
import os

from app.services.processor import process_email
from app.services.text_extractor import extract_text_from_file
from app.services import gmail_service

app = FastAPI(
    title="Email Classifier API",
    description="API para classificação de emails em Produtivo/Improdutivo e sugestão de respostas automáticas",
    version="1.0.0"
)

# CORS para permitir requisições do frontend Next.js
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Em produção, especificar domínio
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TextInput(BaseModel):
    """Modelo para entrada de texto direto"""
    text: str


class ClassificationResult(BaseModel):
    """Modelo de resposta da classificação"""
    category: str
    confidence: float
    suggested_response: str
    processed_text: str


@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Email Classifier API está funcionando"}


@app.get("/health")
async def health():
    """Endpoint para verificação de saúde (deploy)"""
    return {"status": "healthy"}


@app.post("/api/classify", response_model=ClassificationResult)
async def classify_email(
    file: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None)
):
    """
    Classifica um email e sugere resposta automática.
    Aceita upload de arquivo (.txt ou .pdf) ou texto direto.
    """
    email_content = None

    if file:
        # Validar tipo de arquivo
        if not file.filename:
            raise HTTPException(status_code=400, detail="Nome do arquivo não fornecido")
        
        ext = file.filename.lower().split(".")[-1]
        if ext not in ["txt", "pdf"]:
            raise HTTPException(
                status_code=400,
                detail="Formato não suportado. Use .txt ou .pdf"
            )

        content = await file.read()
        email_content = extract_text_from_file(content, ext)
        
        if not email_content or not email_content.strip():
            raise HTTPException(status_code=400, detail="Não foi possível extrair texto do arquivo")

    elif text and text.strip():
        email_content = text.strip()

    else:
        raise HTTPException(
            status_code=400,
            detail="Envie um arquivo (.txt ou .pdf) ou insira o texto do email"
        )

    try:
        result = process_email(email_content)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao processar email: {str(e)}")


# ============ Gmail OAuth ============

FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")


@app.get("/api/auth/gmail/url")
async def gmail_auth_url():
    """Retorna a URL para o usuário autorizar acesso ao Gmail."""
    try:
        auth_url, _ = gmail_service.get_auth_url()
        return {"auth_url": auth_url}
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/api/auth/gmail/callback")
async def gmail_callback(code: Optional[str] = Query(None), error: Optional[str] = Query(None)):
    """Callback OAuth: troca o código por tokens e redireciona para o frontend."""
    if error:
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(error)}")
    if not code:
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error=missing_code")
    try:
        user_info = gmail_service.exchange_code_for_tokens(code)
        email = user_info.get("email", "")
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_success=1&email={quote(email)}")
    except Exception as e:
        return RedirectResponse(url=f"{FRONTEND_URL}?gmail_error={quote(str(e))}")


@app.get("/api/auth/gmail/status")
async def gmail_status():
    """Verifica se o usuário está autenticado no Gmail."""
    if not gmail_service.is_authenticated():
        return {"authenticated": False}
    user = gmail_service.get_user_info()
    return {
        "authenticated": True,
        "email": user.get("email") if user else None,
        "name": user.get("name") if user else None,
    }


@app.post("/api/auth/gmail/revoke")
async def gmail_revoke():
    """Desconecta a conta Gmail."""
    gmail_service.revoke_credentials()
    return {"success": True}


@app.get("/api/emails")
async def list_emails(
    max_results: int = Query(20, ge=1, le=50),
    query: str = Query(""),
):
    """Lista emails da caixa de entrada do Gmail."""
    try:
        messages = gmail_service.list_messages(max_results=max_results, query=query or None)
        return {"emails": messages}
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/emails/{message_id}")
async def get_email(message_id: str):
    """Obtém o conteúdo completo de um email e opcionalmente classifica."""
    try:
        content = gmail_service.get_message_content(message_id)
        return {"content": content}
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/emails/{message_id}/classify")
async def classify_gmail_email(message_id: str):
    """Obtém o email do Gmail e classifica com IA."""
    try:
        content = gmail_service.get_message_content(message_id)
        result = process_email(content)
        return result
    except PermissionError as e:
        raise HTTPException(status_code=401, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
