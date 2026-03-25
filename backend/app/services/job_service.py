"""
Fachada do job diário — reexporta o caso de uso com dependências resolvidas pela composição.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.application.use_cases.daily_email_job import execute_daily_email_job
from app.composition import get_email_processing_application_service, get_gmail_gateway
from app.infrastructure.adapters.sqlalchemy_email_repository import SqlAlchemyEmailRepository


def run_daily_job(
    db: Session,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    only_productive: bool = False,
    max_emails: int = 100,
) -> dict:
    return execute_daily_email_job(
        db,
        get_gmail_gateway(),
        SqlAlchemyEmailRepository(db),
        get_email_processing_application_service(),
        date_from=date_from,
        date_to=date_to,
        only_productive=only_productive,
        max_emails=max_emails,
    )


__all__ = ["run_daily_job"]
