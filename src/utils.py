from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

try:
    from openpyxl.utils.datetime import from_excel
except Exception:  # pragma: no cover
    from_excel = None


AIRCRAFT_RE = re.compile(r"^(?:N\d{2,5}[A-Z]{1,3}|[A-Z]{2}-[A-Z0-9]{3,4})$")


def clean_text(value: Any) -> str:
    """Normalize values read from Excel without destroying meaningful words."""
    if value is None:
        return ""
    text = str(value)
    text = text.replace("_x000D_", "\n")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\xa0", " ")
    text = text.replace("–", "-").replace("—", "-")
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    return "\n".join(lines).strip()


def one_line(value: Any) -> str:
    return re.sub(r"\s+", " ", clean_text(value)).strip()


def is_aircraft_register(value: Any) -> bool:
    text = one_line(value).upper()
    return bool(AIRCRAFT_RE.match(text))


def normalize_register(value: Any) -> str:
    return one_line(value).upper()


def excel_time_to_hhmm(value: Any) -> str:
    """Convert Excel time fractions or datetime/time-like values to HH:MM."""
    if value is None or value == "":
        return ""
    if hasattr(value, "strftime"):
        try:
            return value.strftime("%H:%M")
        except Exception:
            pass
    try:
        number = float(value)
        if 0 <= number < 1:
            total_minutes = round(number * 24 * 60)
            h = (total_minutes // 60) % 24
            m = total_minutes % 60
            return f"{h:02d}:{m:02d}"
    except Exception:
        pass
    return one_line(value)


def excel_serial_to_date(value: Any) -> date | None:
    """Return a date from a real date, datetime or Excel serial number."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        number = float(value)
        if number > 20000 and from_excel is not None:
            return from_excel(number).date()
    except Exception:
        return None
    return None


def format_short_date(value: date | None) -> str:
    if value is None:
        return ""
    return value.strftime("%m/%d/%y")


def normalize_status(value: Any) -> str:
    return one_line(value).upper()


def should_exclude_task(done_value: Any, include_cancelled: bool = False) -> bool:
    """Exclude cancelled/closed rows by default, because the reference PDFs omit them."""
    if include_cancelled:
        return False
    done = normalize_status(done_value)
    excluded_tokens = ("CANCELLED", "CANCELED", "CLOSED")
    return any(token in done for token in excluded_tokens)

MONTH_ABBR = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
    "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}


def extract_month_day_from_text(value: Any) -> tuple[int, int] | None:
    """Extract dates like 'JUN 19' or 'JUN19' from a WO cell."""
    text = one_line(value).upper()
    match = re.search(r"\b(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)\s*([0-3]?\d)\b", text)
    if not match:
        return None
    month = MONTH_ABBR[match.group(1)]
    day = int(match.group(2))
    return month, day


def wo_date_matches_tally_date(wo_text: Any, tally_date: date | None) -> bool:
    """If a WO contains month/day, include it only when it matches the tally date.

    If the WO does not contain a month/day token, keep it eligible. This matches
    rows whose WO is only a number, e.g. '367227'.
    """
    month_day = extract_month_day_from_text(wo_text)
    if month_day is None or tally_date is None:
        return True
    month, day = month_day
    return month == tally_date.month and day == tally_date.day
