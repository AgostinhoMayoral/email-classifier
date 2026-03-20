"""
Configuração do banco de dados PostgreSQL.
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import StaticPool

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


def init_db():
    """Cria todas as tabelas no banco."""
    from app.models import EmailRecord, EmailClassification, EmailLog, JobConfig  # noqa: F401
    Base.metadata.create_all(bind=engine)
