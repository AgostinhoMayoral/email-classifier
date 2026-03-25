"""Cliente HTTP para classificação e resposta via Hugging Face (implementação da porta EmailLLMPort)."""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx

from app.application.ports.email_llm import EmailLLMPort
from app.domain.policies import llm_prompts
from app.domain.value_objects.email_category import EmailCategory

logger = logging.getLogger(__name__)

HF_CHAT_URL = "https://router.huggingface.co/v1/chat/completions"
HF_TOKEN = os.getenv("HF_TOKEN", os.getenv("HUGGINGFACE_TOKEN", ""))
CHAT_MODEL = os.getenv("HF_CHAT_MODEL", "meta-llama/Llama-3.1-8B-Instruct:cheapest")
HF_MAX_RETRIES = 3
HF_RETRY_DELAY = 5


def _chat_completion(prompt: str, max_tokens: int = 150) -> str | None:
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


class HuggingFaceEmailLLM:
    __slots__ = ()

    def classify(self, email_text: str) -> dict[str, Any] | None:
        prompt = llm_prompts.classification_user_prompt(email_text)
        result = _chat_completion(prompt, max_tokens=20)
        if not result:
            return None
        r = result.strip().lower()
        if "produtivo" in r:
            return {"category": EmailCategory.PRODUCTIVE, "confidence": 0.85}
        if "improdutivo" in r:
            return {"category": EmailCategory.UNPRODUCTIVE, "confidence": 0.85}
        return {"category": EmailCategory.PRODUCTIVE, "confidence": 0.65}

    def generate_reply(
        self,
        email_text: str,
        category: str,
        recipient_name: str | None = None,
        sender_name: str | None = None,
    ) -> str | None:
        if not HF_TOKEN:
            logger.warning("HF_TOKEN não configurado - usando template")
            return None

        name_block = llm_prompts.build_name_instructions_block(recipient_name, sender_name)
        prompt = llm_prompts.reply_user_prompt(email_text, category, name_block)
        result = _chat_completion(prompt, max_tokens=250)
        if result and len(result) > 15:
            return result
        return None
