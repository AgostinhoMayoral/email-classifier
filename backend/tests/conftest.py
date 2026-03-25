"""
Configuração de testes: variáveis de ambiente e fixtures.
"""
import os

import pytest

# Testes: SQLite em memória (rápido); produção/dev real usam PostgreSQL + Alembic.
os.environ.setdefault("USE_SQLITE", "1")
os.environ.setdefault("DISABLE_JOB_SCHEDULER", "1")


@pytest.fixture
def email_produtivo():
    """Email de exemplo que requer ação."""
    return """Assunto: Solicitação de status - Requisição #4521

Prezados,

Gostaria de solicitar uma atualização sobre o status da minha requisição de suporte técnico, protocolo #4521, que foi aberta há 5 dias úteis.

Preciso dessa informação com urgência pois há um prazo interno a ser cumprido. O problema relatado era relacionado à integração do sistema com a API de pagamentos.

Aguardo retorno.

Atenciosamente,
João Silva"""


@pytest.fixture
def email_improdutivo():
    """Email de exemplo que não requer ação."""
    return """Assunto: Feliz Natal!

Olá equipe,

Apenas queria passar para desejar um Feliz Natal e um próspero Ano Novo a todos!

Obrigado por todo o suporte durante o ano. Que 2025 seja repleto de conquistas!

Abraços,
Maria Santos"""
