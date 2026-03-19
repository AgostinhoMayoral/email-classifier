"""
Processador principal: classificação e geração de respostas.
Utiliza Hugging Face Inference API com fallback para lógica baseada em regras.
"""

import os
import httpx
from typing import Dict, Any

from app.services.nlp_preprocessor import preprocess_text, get_key_phrases


# Configuração da API
HF_API_URL = "https://api-inference.huggingface.co/models"
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", ""))

# Modelos Hugging Face
CLASSIFICATION_MODEL = "facebook/bart-large-mnli"  # Zero-shot classification
TEXT_GENERATION_MODEL = "google/flan-t5-base"  # Geração de texto


def _classify_with_hf(text: str) -> Dict[str, Any] | None:
    """
    Classifica texto usando Hugging Face Inference API (zero-shot).
    Categorias: Produtivo (requer ação) vs Improdutivo (não requer ação).
    """
    if not HF_TOKEN:
        return None

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": text[:512],  # Limitar tamanho
        "parameters": {
            "candidate_labels": [
                "solicitação de suporte ou ação específica",
                "mensagem de cumprimento ou agradecimento sem ação necessária"
            ],
            "multi_label": False
        }
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{HF_API_URL}/{CLASSIFICATION_MODEL}",
                headers=headers,
                json=payload
            )
            if response.status_code == 200:
                result = response.json()
                if result and isinstance(result, dict):
                    labels = result.get("labels", [])
                    scores = result.get("scores", [])
                    if labels and scores:
                        # labels[0] = solicitação (Produtivo), labels[1] = mensagem (Improdutivo)
                        idx_produtivo = 0 if "solicitação" in str(labels[0]).lower() else 1
                        idx_improdutivo = 1 - idx_produtivo
                        if scores[idx_produtivo] > scores[idx_improdutivo]:
                            return {"category": "Produtivo", "confidence": float(scores[idx_produtivo])}
                        else:
                            return {"category": "Improdutivo", "confidence": float(scores[idx_improdutivo])}
    except Exception:
        pass
    return None


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


def _generate_response_with_hf(email_text: str, category: str) -> str | None:
    """
    Gera resposta sugerida usando Hugging Face.
    """
    if not HF_TOKEN:
        return None

    if category == "Produtivo":
        prompt = f"""Email recebido: "{email_text[:300]}"

Gere uma resposta profissional e cordial em português para este email que solicita uma ação. A resposta deve:
- Reconhecer o pedido
- Informar que a solicitação será analisada
- Dar um prazo estimado se possível
- Ser concisa (2-4 frases)

Resposta:"""
    else:
        prompt = f"""Email recebido: "{email_text[:300]}"

Este é um email de cumprimento ou agradecimento. Gere uma resposta breve e cordial em português (1-2 frases) agradecendo e desejando o mesmo.

Resposta:"""

    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    payload = {
        "inputs": prompt[:1024],
        "parameters": {
            "max_new_tokens": 150,
            "temperature": 0.7,
            "do_sample": True
        }
    }

    try:
        with httpx.Client(timeout=30.0) as client:
            response = client.post(
                f"{HF_API_URL}/{TEXT_GENERATION_MODEL}",
                headers=headers,
                json=payload
            )
            if response.status_code == 200:
                result = response.json()
                if isinstance(result, list) and result:
                    generated = result[0].get("generated_text", "")
                    # Extrair apenas a parte da resposta (após o prompt)
                    if "Resposta:" in generated:
                        return generated.split("Resposta:")[-1].strip()
                    return generated.strip()
    except Exception:
        pass
    return None


def _generate_response_template(category: str, email_preview: str) -> str:
    """
    Gera resposta usando templates quando API não está disponível.
    """
    if category == "Produtivo":
        return (
            "Prezado(a),\n\n"
            "Agradecemos o contato. Sua solicitação foi recebida e está sendo analisada por nossa equipe. "
            "Retornaremos em breve com as informações solicitadas.\n\n"
            "Em caso de urgência, por favor entre em contato através dos nossos canais oficiais.\n\n"
            "Atenciosamente,\nEquipe de Suporte"
        )
    else:
        return (
            "Prezado(a),\n\n"
            "Agradecemos sua mensagem e os votos. Desejamos a você e à sua equipe um excelente ano!\n\n"
            "Atenciosamente,\nEquipe"
        )


def process_email(email_text: str) -> Dict[str, Any]:
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

    # Geração de resposta
    suggested_response = _generate_response_with_hf(email_text, category)
    if not suggested_response:
        suggested_response = _generate_response_template(category, email_text[:100])

    return {
        "category": category,
        "confidence": round(confidence, 2),
        "suggested_response": suggested_response.strip(),
        "processed_text": processed_text[:500]  # Para debug/transparência
    }
