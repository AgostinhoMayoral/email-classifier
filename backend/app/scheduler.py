"""
Agendador do job diário de classificação e envio de emails.
"""

import os
from datetime import datetime, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.services.job_service import run_daily_job
from app.models import JobConfig


def _run_scheduled_job():
    """Executa o job com a configuração salva no banco."""
    db = SessionLocal()
    try:
        config = db.query(JobConfig).filter(JobConfig.enabled == True).first()
        date_from = datetime.utcnow() - timedelta(days=1)
        date_to = datetime.utcnow()
        only_productive = False
        if config:
            date_from = config.date_from or date_from
            date_to = config.date_to or date_to
            only_productive = config.only_productive
            config.last_run_at = datetime.utcnow()
            db.commit()
        run_daily_job(db, date_from=date_from, date_to=date_to, only_productive=only_productive)
    except Exception:
        pass
    finally:
        db.close()


def get_cron_from_config() -> str:
    """Retorna expressão cron da config (padrão: 9h todo dia)."""
    db = SessionLocal()
    try:
        config = db.query(JobConfig).first()
        if config and config.cron_expression:
            return config.cron_expression
    except Exception:
        pass
    finally:
        db.close()
    return "0 9 * * *"  # 9h todo dia


_scheduler: BackgroundScheduler | None = None


def start_scheduler():
    """Inicia o agendador em background."""
    global _scheduler
    if os.getenv("DISABLE_JOB_SCHEDULER") == "1":
        return
    cron = get_cron_from_config()
    parts = cron.split()
    if len(parts) >= 5:
        # cron: min hour day month day_of_week
        minute, hour = parts[0], parts[1]
        _scheduler = BackgroundScheduler()
        _scheduler.add_job(_run_scheduled_job, CronTrigger(minute=minute, hour=hour))
        _scheduler.start()


def stop_scheduler():
    """Para o agendador."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown()
        _scheduler = None
