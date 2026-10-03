from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Lead:
    name: str
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    message: str = ""
    source: str = "unknown"
    budget: float | None = None
    employees: int | None = None
    received_at: datetime = field(default_factory=datetime.now)

    # Filled by the pipeline
    intent: str | None = None
    score: int = 0
    tier: str | None = None
    reasons: list[str] = field(default_factory=list)
    owner: str | None = None
    next_action: str | None = None
    follow_up: datetime | None = None

    def __post_init__(self) -> None:
        self.name = re.sub(r"\s+", " ", (self.name or "").strip()).title() or "Unknown"
        self.email = (self.email or "").strip().lower() or None
        self.phone = re.sub(r"[^\d+]", "", self.phone or "") or None
        self.company = (self.company or "").strip() or None
        self.message = (self.message or "").strip()

    @property
    def key(self) -> str:
        """Identity used for deduplication."""
        return self.email or self.phone or f"{self.name}|{self.company}"
