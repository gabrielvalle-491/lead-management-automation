"""Process leads end to end: dedupe -> classify -> score -> route -> store."""

from __future__ import annotations

import itertools
import json
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path

from lead_automation.classify import classify_intent, score
from lead_automation.models import Lead

FOLLOW_UP = {
    "Hot": (timedelta(hours=1), "Call within 1 hour"),
    "Warm": (timedelta(days=1), "Send case study + book a call"),
    "Cold": (timedelta(days=7), "Add to nurture email sequence"),
    "Disqualified": (None, "No sales follow-up"),
}
ROUTING = {"support": "support@", "job_application": "hr@", "spam": "archive"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS leads (
    key TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, company TEXT, source TEXT,
    message TEXT, budget REAL, employees INTEGER, received_at TEXT, intent TEXT, score INTEGER,
    tier TEXT, reasons TEXT, owner TEXT, next_action TEXT, follow_up TEXT, times_seen INTEGER DEFAULT 1
)"""


class LeadPipeline:
    def __init__(self, db_path: str | Path = ":memory:", sales_reps: list[str] | None = None,
                 use_llm: bool = True) -> None:
        # The webhook serves requests from worker threads; a lock keeps writes serialized.
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.Lock()
        self.conn.row_factory = sqlite3.Row
        self.conn.execute(SCHEMA)
        self._reps = itertools.cycle(sales_reps or ["Sales Rep A", "Sales Rep B"])
        self.use_llm = use_llm

    def process(self, lead: Lead) -> tuple[Lead, bool]:
        """Returns (lead, is_new). Repeated leads only bump `times_seen` (no duplicate rows)."""
        with self._lock:
            return self._process(lead)

    def _process(self, lead: Lead) -> tuple[Lead, bool]:
        existing = self.conn.execute("SELECT key FROM leads WHERE key = ?", (lead.key,)).fetchone()
        if existing:
            self.conn.execute("UPDATE leads SET times_seen = times_seen + 1 WHERE key = ?", (lead.key,))
            self.conn.commit()
            return lead, False

        lead.intent = classify_intent(lead, self.use_llm)
        score(lead)
        delay, lead.next_action = FOLLOW_UP[lead.tier]
        lead.follow_up = lead.received_at + delay if delay else None
        lead.owner = ROUTING.get(lead.intent) or next(self._reps)

        self.conn.execute(
            "INSERT INTO leads (key, name, email, phone, company, source, message, budget, employees, received_at,"
            " intent, score, tier, reasons, owner, next_action, follow_up) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (lead.key, lead.name, lead.email, lead.phone, lead.company, lead.source, lead.message, lead.budget,
             lead.employees, lead.received_at.isoformat(timespec="minutes"), lead.intent, lead.score, lead.tier,
             json.dumps(lead.reasons), lead.owner, lead.next_action,
             lead.follow_up.isoformat(timespec="minutes") if lead.follow_up else None),
        )
        self.conn.commit()
        return lead, True

    def process_many(self, leads: list[Lead]) -> dict:
        stats = {"received": 0, "new": 0, "duplicates": 0}
        for lead in leads:
            stats["received"] += 1
            _, is_new = self.process(lead)
            stats["new" if is_new else "duplicates"] += 1
        return stats

    def all_leads(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM leads ORDER BY score DESC, received_at").fetchall()
        return [dict(r) for r in rows]

    def due_follow_ups(self, now: datetime | None = None) -> list[dict]:
        limit = (now or datetime.now()).isoformat(timespec="minutes")
        rows = self.conn.execute(
            "SELECT * FROM leads WHERE follow_up IS NOT NULL AND follow_up <= ? ORDER BY follow_up", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]
