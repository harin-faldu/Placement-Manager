from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP

from app.domain.catalog import COURSES


def clean_placement_id(value: str) -> str:
    cleaned = " ".join(value.strip().split()).upper()
    if not re.fullmatch(r"[A-Z0-9][A-Z0-9-]{2,39}", cleaned):
        raise ValueError("Placement ID must be 3–40 letters, numbers, or hyphens")
    return cleaned


def clean_name(value: str) -> str:
    cleaned = " ".join(value.strip().split())
    if len(cleaned) < 2 or len(cleaned) > 120:
        raise ValueError("Enter the student's full name")
    if any(ord(char) < 32 or char in "<>" for char in cleaned):
        raise ValueError("Name cannot contain markup or control characters")
    return cleaned


def clean_mobile(value: str) -> str:
    raw = value.strip().replace(" ", "").replace("-", "")
    if raw.startswith("+"):
        digits = "+" + re.sub(r"\D", "", raw[1:])
    else:
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 10:
            digits = "+91" + digits
    if not re.fullmatch(r"\+[1-9]\d{9,14}", digits):
        raise ValueError("Enter a valid mobile number")
    return digits


def clean_email(value: str) -> str:
    email = value.strip().lower()
    if len(email) > 255:
        raise ValueError("Email is too long")
    return email


def clean_batch(value: str) -> str:
    batch = value.strip()
    if not re.fullmatch(r"20[2-3]\d", batch):
        raise ValueError("Batch must be an academic year such as 2026")
    return batch


def clean_text(value: str | None, limit: int = 2000) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return ""
    if len(cleaned) > limit:
        raise ValueError(f"Text must be {limit} characters or fewer")
    if any(ord(char) < 32 and char not in "\n\t" for char in cleaned):
        raise ValueError("Text contains unsupported characters")
    return cleaned


def like_contains(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _normalise(value: str) -> str:
    return " ".join(value.lower().replace("–", "-").replace("—", "-").split())


def resolve_course(value: str) -> str:
    wanted = _normalise(value)
    for course in COURSES:
        options = {_normalise(course["code"]), _normalise(course["name"]), _normalise(course["short"])}
        if wanted in options:
            return course["code"]
    raise ValueError("Course must be one of the five placement programmes")
