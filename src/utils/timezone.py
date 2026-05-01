from datetime import datetime, timedelta, timezone

ARGENTINA_TZ = timezone(timedelta(hours=-3))

def now_argentina() -> datetime:
    """Retorna la hora actual en timezone Argentina (UTC-3)."""
    return datetime.now(ARGENTINA_TZ)
