from datetime import date, datetime, time, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def start_of_utc_day(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=timezone.utc)
