"""
Modelos do banco de dados para persistência de emails e logs.
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.database import Base


class EmailStatus:
    """Status do processamento do email."""
    PENDING = "pending"
    CLASSIFIED = "classified"
    SENT = "sent"
    SKIPPED = "skipped"
    FAILED = "failed"


class EmailRecord(Base):
    """Registro de email processado (Gmail ou manual)."""
    __tablename__ = "email_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    gmail_message_id = Column(String(255), unique=True, nullable=True, index=True)  # ID do Gmail
    thread_id = Column(String(255), nullable=True, index=True)
    subject = Column(String(500), nullable=False, default="")
    sender = Column(String(500), nullable=False, default="")
    snippet = Column(Text, nullable=True)
    received_at = Column(DateTime, nullable=True)  # Data de recebimento do email
    status = Column(String(20), default=EmailStatus.PENDING, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    classification = relationship("EmailClassification", back_populates="email_record", uselist=False)
    logs = relationship("EmailLog", back_populates="email_record", order_by="EmailLog.created_at")


class EmailClassification(Base):
    """Classificação e sugestão de resposta gerada pela IA."""
    __tablename__ = "email_classifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_record_id = Column(Integer, ForeignKey("email_records.id"), nullable=False, unique=True)
    category = Column(String(50), nullable=False)  # Produtivo, Improdutivo
    confidence = Column(Float, nullable=False, default=0.0)
    suggested_response = Column(Text, nullable=False)
    processed_text = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    email_record = relationship("EmailRecord", back_populates="classification")


class EmailLog(Base):
    """Log de ações (envio, erro, etc.) para auditoria."""
    __tablename__ = "email_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email_record_id = Column(Integer, ForeignKey("email_records.id"), nullable=False)
    action = Column(String(50), nullable=False)  # classified, sent, failed, skipped
    message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON ou texto com detalhes
    created_at = Column(DateTime, default=datetime.utcnow)

    email_record = relationship("EmailRecord", back_populates="logs")


class JobConfig(Base):
    """Configuração do job diário de envio automático."""
    __tablename__ = "job_configs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, default="Job Diário")
    enabled = Column(Boolean, default=True)
    cron_expression = Column(String(50), default="0 9 * * *")  # 9h todo dia
    date_from = Column(DateTime, nullable=True)  # Filtro: emails a partir de
    date_to = Column(DateTime, nullable=True)    # Filtro: emails até
    only_productive = Column(Boolean, default=False)  # Enviar só produtivos
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
