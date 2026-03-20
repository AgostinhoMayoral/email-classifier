"""
Processador principal: classificação e geração de respostas.
Utiliza Hugging Face Inference API com fallback para lógica baseada em regras.
"""

import logging
import os
import time
import httpx
from typing import Dict, Any

from app.services.nlp_preprocessor import preprocess_text, get_key_phrases

logger = logging.getLogger(__name__)

# Nova API Hugging Face (api-inference foi descontinuada em 2025)
HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", ""))

# Modelo para chat (classificação + geração via prompt)
# meta-llama/Llama-3.1-8B-Instruct disponível em novita, cerebras, etc.
# :cheapest = tier gratuito quando disponível
CHAT_MODEL = os.getenv("HF_CHAT_MODEL", "meta-llama/Llama-3.1-8B-Instruct:cheapest")

# Retry para modelo em carregamento (503)
HF_MAX_RETRIES = 3
HF_RETRY_DELAY = 5


def _chat_completion(prompt: str, max_tokens: int = 150) -> str | None:
    """Chama a API de chat do Hugging Face (nova API router.huggingface.co)."""
    if not HF_TOKEN:
        return None
    headers = {
        "Authorization": f"Bearer {HF_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": CHAT_MODEL,
        "messages": [{"role": "user", "content": prompt[:2000]}],
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }
    for attempt in range(HF_MAX_RETRIES):
        try:
            with httpx.Client(timeout=45.0) as client:
                response = client.post(HF_CHAT_URL, headers=headers, json=payload)
                if response.status_code == 200:
                    data = response.json()
                    content = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
                    if content and content.strip():
                        return content.strip()
                elif response.status_code == 503 and attempt < HF_MAX_RETRIES - 1:
                    est = 5
                    try:
                        est = response.json().get("estimated_time", 5)
                    except Exception:
                        pass
                    logger.info("Modelo carregando (503), aguardando %ss...", min(est, HF_RETRY_DELAY))
                    time.sleep(min(est, HF_RETRY_DELAY))
                else:
                    logger.warning("HF chat API: %s %s", response.status_code, response.text[:300])
        except Exception as e:
            logger.warning("Erro HF chat: %s", e)
            if attempt < HF_MAX_RETRIES - 1:
                time.sleep(HF_RETRY_DELAY)
    return None


def _classify_with_hf(text: str) -> Dict[str, Any] | None:
    """
    Classifica texto usando Hugging Face Chat API.
    Categorias: Produtivo (requer ação) vs Improdutivo (não requer ação).
    """
    prompt = f"""Classifique este email em UMA palavra: Produtivo ou Improdutivo.
Produtivo = solicita ação, suporte, informação, pedido.
Improdutivo = cumprimento, agradecimento, mensagem sem ação necessária.

Email: "{text[:400]}"

Responda APENAS com a palavra: Produtivo ou Improdutivo"""
    result = _chat_completion(prompt, max_tokens=20)
    if not result:
        return None
    r = result.strip().lower()
    if "produtivo" in r:
        return {"category": "Produtivo", "confidence": 0.85}
    if "improdutivo" in r:
        return {"category": "Improdutivo", "confidence": 0.85}
    return {"category": "Produtivo", "confidence": 0.65}  # default


def _classify_rule_based(text: str, preprocessed: str) -> tuple[str, float]:
    """
    Classificação baseada em regras quando API não está disponível.
    Usa indicadores linguísticos para determinar produtividade.
    """
    text_lower = text.lower()
    preprocessed_lower = preprocessed.lower()

    # Indicadores de email PRODUTIVO (requer ação)
    productive_indicators = [
        "solicito", "solicitação", "requisição", "status", "atualização",
        "suporte", "problema", "erro", "dúvida", "pergunta", "urgente",
        "prazo", "documento", "arquivo", "sistema", "caso", "processo",
        "aprovação", "pendente", "andamento", "resolver", "ajuda",
        "informação", "informações", "preciso", "necessito", "gostaria"
    ]

    # Indicadores de email IMPRODUTIVO (não requer ação)
    unproductive_indicators = [
        "feliz natal", "feliz ano novo", "boas festas", "parabéns",
        "obrigado", "obrigada", "agradeço", "agradecimento", "cumprimentos",
        "atenciosamente", "abraço", "abração", "bom dia", "boa tarde",
        "boa noite", "olá", "oi ", "só para", "apenas para", "só queria"
    ]

    productive_count = sum(1 for ind in productive_indicators if ind in text_lower or ind in preprocessed_lower)
    unproductive_count = sum(1 for ind in unproductive_indicators if ind in text_lower)

    # Heurística: emails muito curtos com apenas cumprimentos tendem a ser improdutivos
    word_count = len(text.split())
    if word_count < 15 and unproductive_count > 0 and productive_count == 0:
        return "Improdutivo", 0.75

    if productive_count > unproductive_count:
        confidence = min(0.95, 0.6 + (productive_count * 0.08))
        return "Produtivo", confidence
    elif unproductive_count > productive_count:
        confidence = min(0.95, 0.6 + (unproductive_count * 0.08))
        return "Improdutivo", confidence
    else:
        # Empate: considerar produtivo por padrão (melhor errar por excesso de atenção)
        return "Produtivo", 0.65


def _generate_response_with_hf(
    email_text: str,
    category: str,
    recipient_name: str | None = None,
    sender_name: str | None = None,
) -> str | None:
    """
    Gera resposta sugerida usando Hugging Face Chat API.
    Usa recipient_name na saudação (Prezado João) e sender_name na assinatura.
    """
    if not HF_TOKEN:
        logger.warning("HF_TOKEN não configurado - usando template")
        return None

    name_instructions = []
    if recipient_name and recipient_name.strip():
        name_instructions.append(f"- O destinatário se chama {recipient_name.strip()}. Use o nome dele na saudação (ex: Prezado(a) {recipient_name.strip()}, ou Prezado João).")
    else:
        name_instructions.append("- Se o nome do destinatário aparecer na mensagem, use-o na saudação. Caso contrário, use 'Prezado(a)'.")

    if sender_name and sender_name.strip():
        name_instructions.append(f"- Assine a mensagem com o nome {sender_name.strip()} (ex: Atenciosamente, {sender_name.strip()}).")
    else:
        name_instructions.append("- Assine com 'Atenciosamente' ou similar, sem deixar [Seu Nome] ou placeholders.")

    name_block = "\n".join(name_instructions)

    prompt = f"""Mensagem recebida: "{email_text[:500]}"

Responda de forma cordial e profissional em português. Seja ESPECÍFICO ao conteúdo. Máximo 4 frases. Apenas a resposta completa, sem prefixos.

IMPORTANTE - Personalização:
{name_block}
NUNCA use [Nome], [Seu Nome] ou placeholders. Use sempre os nomes reais."""

    result = _chat_completion(prompt, max_tokens=250)
    if result and len(result) > 15:
        return result
    return None


def _generate_response_template(
    category: str,
    email_preview: str,
    recipient_name: str | None = None,
    sender_name: str | None = None,
) -> str:
    """Gera resposta usando templates quando API não está disponível."""
    saudacao = f"Prezado(a) {recipient_name},\n\n" if (recipient_name and recipient_name.strip()) else "Prezado(a),\n\n"
    assinatura = f"Atenciosamente,\n{sender_name}" if (sender_name and sender_name.strip()) else "Atenciosamente,\nEquipe de Suporte"

    if category == "Produtivo":
        return (
            f"{saudacao}"
            "Agradecemos o contato. Sua solicitação foi recebida e está sendo analisada por nossa equipe. "
            "Retornaremos em breve com as informações solicitadas.\n\n"
            "Em caso de urgência, por favor entre em contato através dos nossos canais oficiais.\n\n"
            f"{assinatura}"
        )
    else:
        return (
            f"{saudacao}"
            "Agradecemos sua mensagem e os votos. Desejamos a você e à sua equipe um excelente ano!\n\n"
            f"{assinatura}"
        )


def process_email(
    email_text: str,
    recipient_name: str | None = None,
    sender_name: str | None = None,
) -> Dict[str, Any]:
    """
    Processa o email completo: pré-processamento, classificação e geração de resposta.
    
    Args:
        email_text: Texto bruto do email
        
    Returns:
        Dicionário com category, confidence, suggested_response, processed_text
    """
    # Pré-processamento NLP
    processed_text = preprocess_text(email_text)

    # Classificação
    hf_result = _classify_with_hf(email_text)
    
    if hf_result:
        category = hf_result.get("category", "Produtivo")
        confidence = hf_result.get("confidence", 0.8)
    else:
        category, confidence = _classify_rule_based(email_text, processed_text)

    # Garantir que category está no formato correto
    if category not in ["Produtivo", "Improdutivo"]:
        category = "Produtivo" if "produtivo" in str(category).lower() else "Improdutivo"

    # Geração de resposta - sempre tenta IA primeiro (com nomes para personalização)
    suggested_response = _generate_response_with_hf(
        email_text, category,
        recipient_name=recipient_name,
        sender_name=sender_name,
    )
    ai_used = bool(suggested_response)
    if not suggested_response:
        logger.warning("Usando template de fallback (IA indisponível ou falhou)")
        suggested_response = _generate_response_template(
            category, email_text[:100],
            recipient_name=recipient_name,
            sender_name=sender_name,
        )

    return {
        "category": category,
        "confidence": round(confidence, 2),
        "suggested_response": suggested_response.strip(),
        "processed_text": processed_text[:500],
        "ai_used": ai_used,
    }
