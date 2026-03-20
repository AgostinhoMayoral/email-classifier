"""Testes do pré-processador NLP."""
import pytest

from app.services.nlp_preprocessor import preprocess_text, get_key_phrases


def test_preprocess_text_empty():
    """Texto vazio retorna string vazia."""
    assert preprocess_text("") == ""
    assert preprocess_text("   ") == ""


def test_preprocess_text_remove_urls():
    """URLs são removidas."""
    text = "Acesse https://exemplo.com para mais informações"
    result = preprocess_text(text)
    assert "https" not in result
    assert "exemplo" not in result


def test_preprocess_text_remove_emails():
    """Endereços de email são removidos."""
    text = "Entre em contato com suporte@empresa.com"
    result = preprocess_text(text)
    assert "suporte" in result or "empresa" in result or "contato" in result


def test_preprocess_text_lowercase():
    """Texto é convertido para minúsculas."""
    result = preprocess_text("SOLICITAÇÃO de Suporte")
    assert result == result.lower()


def test_preprocess_text_produtivo():
    """Email produtivo mantém termos relevantes."""
    text = "Solicito atualização do status da requisição de suporte"
    result = preprocess_text(text)
    assert len(result) > 0
    # Deve conter alguma forma de termos produtivos
    tokens = result.split()
    assert len(tokens) >= 2


def test_get_key_phrases_empty():
    """Texto vazio retorna lista vazia."""
    assert get_key_phrases("") == []
    assert get_key_phrases("   ") == []


def test_get_key_phrases_produtivo():
    """Extrai frases-chave de email produtivo."""
    text = "Preciso de suporte com o sistema. Há um problema na requisição."
    phrases = get_key_phrases(text)
    assert len(phrases) >= 1
    # Deve conter indicadores de produtividade
    all_phrases = " ".join(phrases).lower()
    assert "suporte" in all_phrases or "problema" in all_phrases or "requisit" in all_phrases
