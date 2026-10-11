from datetime import date, datetime
from zoneinfo import ZoneInfo

from app.core.config import settings


def business_now() -> datetime:
    return datetime.now(ZoneInfo(settings.business_timezone))


def business_today() -> date:
    return business_now().date()
