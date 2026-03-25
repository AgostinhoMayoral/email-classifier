"""
Configuração do banco de dados PostgreSQL.
"""

import os
import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/email_classifier"
)
# psycopg3: use postgresql+psycopg://
if DATABASE_URL.startswith("postgresql://") and "+" not in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Para testes sem PostgreSQL, usa SQLite em memória
if os.getenv("USE_SQLITE") == "1":
    DATABASE_URL = "sqlite:///:memory:"
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
else:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency para obter sessão do banco."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_email_records_gmail_account_column():
    """Adiciona coluna gmail_account_email em bases já existentes (create_all não altera tabelas)."""
    try:
        inspector = inspect(engine)
        if not inspector.has_table("email_records"):
            return
        cols = {c["name"] for c in inspector.get_columns("email_records")}
        if "gmail_account_email" in cols:
            return
        dialect = engine.dialect.name
        with engine.begin() as conn:
            if dialect == "postgresql":
                conn.execute(
                    text(
                        "ALTER TABLE email_records ADD COLUMN gmail_account_email VARCHAR(320) NULL"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_email_records_gmail_account_email "
                        "ON email_records (gmail_account_email)"
                    )
                )
            else:
                conn.execute(
                    text(
                        "ALTER TABLE email_records ADD COLUMN gmail_account_email VARCHAR(320) NULL"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_email_records_gmail_account_email "
                        "ON email_records (gmail_account_email)"
                    )
                )
        logger.info("Migração: coluna email_records.gmail_account_email adicionada.")
    except Exception as e:
        logger.warning("Não foi possível garantir coluna gmail_account_email: %s", e)


def _run_alembic_upgrade_head():
    """Aplica revisões Alembic (PostgreSQL apenas). Testes em SQLite não usam Alembic."""
    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parent.parent
    cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(cfg, "head")
    logger.info("Alembic: revisões aplicadas (head).")


def init_db():
    """Cria tabelas em falta e aplica migrações versionadas (Alembic em PostgreSQL)."""
    from app.models import EmailRecord, EmailClassification, EmailLog, JobConfig  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _ensure_email_records_gmail_account_column()
    if engine.dialect.name != "sqlite":
        _run_alembic_upgrade_head()
