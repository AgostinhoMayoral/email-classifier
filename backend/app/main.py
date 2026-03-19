"""
API principal para classificação e geração de respostas de emails.
Solução para automatização de leitura e classificação de emails corporativos.
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import io

from app.services.processor import process_email
from app.services.text_extractor import extract_text_from_file

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
