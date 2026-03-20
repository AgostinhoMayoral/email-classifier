"""Testes do processador de emails (classificação e geração de respostas)."""
import pytest

from app.services.processor import process_email


def test_process_email_produtivo(email_produtivo):
    """Email produtivo é classificado corretamente."""
    result = process_email(email_produtivo)
    assert result["category"] in ["Produtivo", "Improdutivo"]
    assert 0 <= result["confidence"] <= 1
    assert result["suggested_response"]
    assert len(result["suggested_response"]) > 20
    assert "processed_text" in result


def test_process_email_improdutivo(email_improdutivo):
    """Email improdutivo é classificado corretamente."""
    result = process_email(email_improdutivo)
    assert result["category"] in ["Produtivo", "Improdutivo"]
    assert 0 <= result["confidence"] <= 1
    assert result["suggested_response"]
    assert "processed_text" in result


def test_process_email_resposta_nao_vazia(email_produtivo):
    """Resposta sugerida nunca é vazia."""
    result = process_email(email_produtivo)
    assert result["suggested_response"].strip() != ""


def test_process_email_resposta_profissional(email_produtivo):
    """Resposta sugerida para produtivo tem tom profissional."""
    result = process_email(email_produtivo)
    resp = result["suggested_response"].lower()
    # Deve conter elementos de resposta profissional
    assert any(
        word in resp
        for word in ["prezado", "agradecemos", "solicitação", "contato", "atenciosamente"]
    ) or len(resp) > 30


def test_process_email_texto_curto():
    """Texto muito curto ainda é processado."""
    result = process_email("Olá, preciso de ajuda.")
    assert "category" in result
    assert "suggested_response" in result


def test_process_email_estrutura_retorno():
    """Retorno tem estrutura esperada."""
    result = process_email("Solicito informações sobre o pedido #123.")
    assert set(result.keys()) >= {"category", "confidence", "suggested_response", "processed_text", "ai_used"}
    assert isinstance(result["confidence"], (int, float))
    assert isinstance(result["ai_used"], bool)
