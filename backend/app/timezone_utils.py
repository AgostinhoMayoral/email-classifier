"""
Datas no calendário de America/Sao_Paulo (envio, job, filtros alinhados ao Gmail BR).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from zoneinfo import ZoneInfo

APP_TZ = ZoneInfo("America/Sao_Paulo")
UTC = timezone.utc


def now_app_tz() -> datetime:
    return datetime.now(APP_TZ)


def naive_calendar_to_sp_start(naive: datetime) -> datetime:
    """Dia civil (parse YYYY-MM-DD naive) à meia-noite em São Paulo."""
    return datetime(naive.year, naive.month, naive.day, tzinfo=APP_TZ)


def resolve_gmail_date_range_sp(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> Tuple[datetime, datetime]:
    """
    Intervalo Gmail: after:D inclusivo, before:D2 exclusivo (datas em São Paulo).
    date_from / date_to da API são interpretados como dias civis em SP.
    """
    today_start = now_app_tz().replace(hour=0, minute=0, second=0, microsecond=0)

    if date_from is None and date_to is None:
        return today_start, today_start + timedelta(days=1)
    if date_from is None:
        start = naive_calendar_to_sp_start(date_to)
        return start, start + timedelta(days=1)
    if date_to is None:
        start = naive_calendar_to_sp_start(date_from)
        return start, start + timedelta(days=1)
    start = naive_calendar_to_sp_start(date_from)
    end_day = naive_calendar_to_sp_start(date_to)
    return start, end_day + timedelta(days=1)


def gmail_after_before_strings_sp(
    date_from: Optional[datetime],
    date_to: Optional[datetime],
) -> Tuple[str, str]:
    start, end_excl = resolve_gmail_date_range_sp(date_from, date_to)
    return start.strftime("%Y/%m/%d"), end_excl.strftime("%Y/%m/%d")


def sp_day_start_utc_naive(naive: datetime) -> datetime:
    """Início do dia civil SP como instante UTC naive (coluna received_at)."""
    return naive_calendar_to_sp_start(naive).astimezone(UTC).replace(tzinfo=None)


def sp_day_end_utc_naive(naive: datetime) -> datetime:
    """Fim do dia civil SP como instante UTC naive (coluna received_at)."""
    end_sp = naive_calendar_to_sp_start(naive) + timedelta(days=1) - timedelta(microseconds=1)
    return end_sp.astimezone(UTC).replace(tzinfo=None)


def sp_calendar_bounds_to_utc_naive(
    date_from_naive: datetime,
    date_to_naive: datetime,
) -> Tuple[datetime, datetime]:
    """Intervalo inclusivo de dias civis SP traduzido para UTC naive do banco."""
    return sp_day_start_utc_naive(date_from_naive), sp_day_end_utc_naive(date_to_naive)
