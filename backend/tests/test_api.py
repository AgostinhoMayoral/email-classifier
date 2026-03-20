"""Testes da API de classificação."""
import io

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_root():
    """Endpoint raiz retorna status ok."""
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"


def test_health():
    """Health check retorna healthy."""
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"


def test_classify_sem_entrada():
    """Classificar sem arquivo nem texto retorna erro."""
    r = client.post("/api/classify", data={})
    assert r.status_code in (400, 422)


def test_classify_com_texto_vazio():
    """Classificar com texto vazio retorna erro."""
    r = client.post("/api/classify", data={"text": "   "})
    assert r.status_code == 400
    assert "arquivo" in r.json().get("detail", "").lower() or "texto" in r.json().get("detail", "").lower()


def test_classify_com_texto(email_produtivo):
    """Classificar por texto retorna categoria e resposta."""
    r = client.post("/api/classify", data={"text": email_produtivo})
    assert r.status_code == 200
    data = r.json()
    assert data["category"] in ["Produtivo", "Improdutivo"]
    assert "confidence" in data
    assert "suggested_response" in data
    assert "processed_text" in data
    assert len(data["suggested_response"]) > 0


def test_classify_com_arquivo_txt(email_produtivo):
    """Classificar por arquivo .txt funciona."""
    content = email_produtivo.encode("utf-8")
    r = client.post(
        "/api/classify",
        files={"file": ("email.txt", io.BytesIO(content), "text/plain")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "category" in data
    assert "suggested_response" in data


def test_classify_formato_invalido():
    """Arquivo com formato não suportado retorna 400."""
    r = client.post(
        "/api/classify",
        files={"file": ("doc.docx", io.BytesIO(b"conteudo"), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
    )
    assert r.status_code == 400
    assert "não suportado" in r.json().get("detail", "").lower() or "txt" in r.json().get("detail", "").lower()
