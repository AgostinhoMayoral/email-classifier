"""
Pré-processamento de texto com NLP.
Inclui remoção de stop words, lemmatização e normalização.
"""

import re
import string
from typing import List

# NLTK será baixado na inicialização
import nltk
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer
from nltk.tokenize import word_tokenize

# Download dos recursos NLTK necessários (executado uma vez)
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)
try:
    nltk.data.find("corpora/stopwords")
except LookupError:
    nltk.download("stopwords", quiet=True)
try:
    nltk.data.find("corpora/wordnet")
except LookupError:
    nltk.download("wordnet", quiet=True)


# Stop words em português e inglês (emails corporativos podem ser bilíngues)
STOP_WORDS_PT = set(stopwords.words("portuguese"))
STOP_WORDS_EN = set(stopwords.words("english"))
STOP_WORDS = STOP_WORDS_PT | STOP_WORDS_EN

# Palavras adicionais comuns em emails que não agregam significado
EMAIL_STOP_WORDS = {
    "re:", "fw:", "fwd:", "enviado", "de:", "para:", "assunto:",
    "obrigado", "obrigada", "att", "atenciosamente", "cordiais",
    "cumprimentos", "abs", "abs.", "grato", "grata"
}
STOP_WORDS = STOP_WORDS | EMAIL_STOP_WORDS

lemmatizer = WordNetLemmatizer()


def preprocess_text(text: str) -> str:
    """
    Pré-processa o texto do email para análise.
    
    Etapas:
    1. Normalização (lowercase, remoção de caracteres especiais)
    2. Tokenização
    3. Remoção de stop words
    4. Lemmatização
    
    Args:
        text: Texto bruto do email
        
    Returns:
        Texto pré-processado
    """
    if not text or not text.strip():
        return ""
    
    # Lowercase
    text = text.lower()
    
    # Remover URLs
    text = re.sub(r"http\S+|www\.\S+", "", text)
    
    # Remover emails
    text = re.sub(r"\S+@\S+\.\S+", "", text)
    
    # Remover números excessivos (manter números que podem ser IDs de caso)
    text = re.sub(r"\b\d{10,}\b", "", text)
    
    # Tokenização (funciona para português e inglês)
    tokens = word_tokenize(text)
    
    # Filtrar: apenas letras, remover stop words, mínimo 2 caracteres
    filtered_tokens = []
    for token in tokens:
        if len(token) < 2:
            continue
        if token in STOP_WORDS:
            continue
        # Manter apenas tokens alfanuméricos
        clean_token = re.sub(r"[^a-záéíóúâêôãõç]", "", token)
        if len(clean_token) >= 2:
            # Lemmatização
            lemma = lemmatizer.lemmatize(clean_token)
            filtered_tokens.append(lemma)
    
    return " ".join(filtered_tokens)


def get_key_phrases(text: str) -> List[str]:
    """
    Extrai frases-chave do texto para contexto na classificação.
    Mantém termos importantes como "suporte", "solicitação", "status", etc.
    """
    preprocessed = preprocess_text(text)
    if not preprocessed:
        return []
    
    # Palavras que indicam produtividade
    productive_indicators = {
        "suporte", "solicit", "requisit", "status", "atualiz", "caso",
        "problema", "erro", "dúvida", "pergunta", "urgente", "prazo",
        "documento", "arquivo", "sistema", "processo", "aprovação"
    }
    
    tokens = preprocessed.split()
    return [t for t in tokens if any(ind in t for ind in productive_indicators)]
