"""Lead capture from the three places leads usually arrive:

1. CSV exports (Facebook / LinkedIn Lead Ads, trade-show lists)
2. Website form submissions (JSON, e.g. from a webhook)
3. Plain emails sent to sales@ (.eml files)
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

from lead_automation.models import Lead

CSV_COLUMNS = {
    "name": ("full_name", "name", "nombre"),
    "email": ("email", "e-mail", "correo"),
    "phone": ("phone_number", "phone", "telefono", "teléfono"),
    "company": ("company_name", "company", "empresa"),
    "message": ("message", "comments", "mensaje"),
    "budget": ("budget", "presupuesto"),
    "employees": ("company_size", "employees", "empleados"),
}


def _to_number(value: object) -> float | None:
    if value in (None, ""):
        return None
    digits = re.sub(r"[^\d.]", "", str(value))
    try:
        return float(digits) if digits else None
    except ValueError:
        return None


def _pick(row: dict, field: str) -> str | None:
    lowered = {k.strip().lower(): v for k, v in row.items() if k}
    return next((lowered[c] for c in CSV_COLUMNS[field] if c in lowered and lowered[c]), None)


def from_csv(path: str | Path, source: str = "ads_csv") -> list[Lead]:
    """Read a lead-ads style CSV (column names are matched flexibly, see CSV_COLUMNS)."""
    leads = []
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            employees = _to_number(_pick(row, "employees"))
            leads.append(Lead(
                name=_pick(row, "name") or "", email=_pick(row, "email"), phone=_pick(row, "phone"),
                company=_pick(row, "company"), message=_pick(row, "message") or "", source=source,
                budget=_to_number(_pick(row, "budget")), employees=int(employees) if employees else None,
                received_at=_parse_time(row.get("created_time")),
            ))
    return leads


def from_web_form(payload: dict) -> Lead:
    """Website contact form payload (also what the webhook receives)."""
    return Lead(
        name=payload.get("name", ""), email=payload.get("email"), phone=payload.get("phone"),
        company=payload.get("company"), message=payload.get("message", ""), source="website",
        budget=_to_number(payload.get("budget")), employees=payload.get("employees"),
        received_at=_parse_time(payload.get("submitted_at")),
    )


def from_json_folder(folder: str | Path) -> list[Lead]:
    """Load every *.json web form payload in `folder` (missing folder -> empty list)."""
    return [from_web_form(json.loads(p.read_text(encoding="utf-8"))) for p in sorted(Path(folder).glob("*.json"))]


def from_email(path: str | Path) -> Lead:
    """Parse an .eml file, extracting company, phone and budget from the body text."""
    with open(path, "rb") as fh:
        msg = BytesParser(policy=policy.default).parse(fh)
    display_name, address = parseaddr(msg["From"])
    body = msg.get_body(preferencelist=("plain",))
    text = body.get_content() if body else ""
    phone = re.search(r"(\+?\d[\d\s\-()]{8,}\d)", text)
    company = re.search(r"(?:Company|Empresa)\s*:\s*(.+)", text, re.IGNORECASE)
    budget = re.search(r"(?:budget|presupuesto)[^\d]{0,20}([\d.,]+)", text, re.IGNORECASE)
    return Lead(
        name=display_name or address.split("@")[0], email=address,
        phone=phone.group(1) if phone else None, company=company.group(1).strip() if company else None,
        message=f"{msg['Subject'] or ''}\n{text}".strip(), source="email",
        budget=_to_number(budget.group(1).replace(",", "")) if budget else None,
        received_at=parsedate_to_datetime(msg["Date"]).replace(tzinfo=None) if msg["Date"] else datetime.now(),
    )


def from_email_folder(folder: str | Path) -> list[Lead]:
    """Load every *.eml email in `folder` (missing folder -> empty list)."""
    return [from_email(p) for p in sorted(Path(folder).glob("*.eml"))]


def _parse_time(value: object) -> datetime:
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.now()
