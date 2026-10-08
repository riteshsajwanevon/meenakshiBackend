"""Checks a field value against its data type, as done after OCR, on correction and on validation.

Error messages are written to follow the field label, e.g. "Rejection Qty must be a number".
"""

import calendar
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.models.enums import FieldDataType

DATE_FORMATS = ("%d/%m/%y", "%d/%m/%Y", "%d-%m-%y", "%d-%m-%Y", "%d.%m.%y", "%d.%m.%Y", "%Y-%m-%d")
_MONTHS_BY_PREFIX = {name[:3].lower(): number for number, name in enumerate(calendar.month_name) if name}
_NUMBER_NOISE = re.compile(r"[,\s]")


@dataclass(frozen=True)
class FieldCheck:
    error: str | None = None
    numeric_value: Decimal | None = None
    date_value: date | None = None
    month_label: str | None = None  # normalised month, e.g. "June 2026"

    @property
    def ok(self) -> bool:
        return self.error is None


def check_value(data_type: FieldDataType, required: bool, value: str | None) -> FieldCheck:
    text = (value or "").strip()
    if not text:
        return FieldCheck(error="is required") if required else FieldCheck()

    match data_type:
        case FieldDataType.NUMBER:
            return _check_number(text)
        case FieldDataType.DATE:
            parsed = parse_date(text)
            return FieldCheck(date_value=parsed) if parsed else FieldCheck(error="must be a valid date like 15/03/26")
        case FieldDataType.MONTH:
            label = parse_month(text)
            return FieldCheck(month_label=label) if label else FieldCheck(error="must be a month like March 2026")
        case _:
            return FieldCheck()


def _check_number(text: str) -> FieldCheck:
    try:
        number = Decimal(_NUMBER_NOISE.sub("", text))
    except InvalidOperation:
        return FieldCheck(error="must be a number")
    if not number.is_finite():
        return FieldCheck(error="must be a number")
    if number < 0:
        return FieldCheck(error="must not be negative")
    return FieldCheck(numeric_value=number)


def parse_date(text: str) -> date | None:
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text.strip(), date_format).date()
        except ValueError:
            continue
    return None


def parse_month(text: str) -> str | None:
    """Understands forms like "June-26", "JUN", "March 2026" and "06/2026"."""
    text = text.strip()
    month = year = None

    if name := re.search(r"[A-Za-z]{3,}", text):
        month = _MONTHS_BY_PREFIX.get(name.group()[:3].lower())
        if year_match := re.search(r"(?<!\d)(\d{4}|\d{2})(?!\d)", text):
            year = year_match.group(1)
    elif numeric := re.fullmatch(r"(\d{1,2})\s*[/\-. ]\s*(\d{4}|\d{2})", text):
        month = int(numeric.group(1)) if 1 <= int(numeric.group(1)) <= 12 else None
        year = numeric.group(2)

    if month is None:
        return None
    if year is None:
        return calendar.month_name[month]
    full_year = int(year) + 2000 if len(year) == 2 else int(year)
    return f"{calendar.month_name[month]} {full_year}"
