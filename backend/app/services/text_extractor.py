"""
Extração de texto de arquivos .txt e .pdf
"""

import io
from PyPDF2 import PdfReader


def extract_text_from_file(content: bytes, extension: str) -> str:
    """
    Extrai texto de arquivo baseado na extensão.
    
    Args:
        content: Conteúdo binário do arquivo
        extension: Extensão do arquivo (txt ou pdf)
    
    Returns:
        Texto extraído do arquivo
    """
    if extension == "txt":
        return content.decode("utf-8", errors="ignore")
    
    elif extension == "pdf":
        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        return "\n".join(text_parts)
    
    else:
        raise ValueError(f"Formato não suportado: {extension}")
