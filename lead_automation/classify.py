"""Intent classification + lead scoring.

Intent answers "what does this person want?" (sales, support, partnership,
job application, spam). It uses an LLM when an API key is configured and a
keyword classifier otherwise, so the pipeline always works offline.

Scoring answers "how likely is this to close?" with transparent rules: every
point added or removed is recorded in `lead.reasons`, so sales reps can see
*why* a lead is hot.
"""

from __future__ import annotations

import json
import os
import re

import httpx

from lead_automation.models import Lead

INTENTS = ("sales", "support", "partnership", "job_application", "spam")

KEYWORDS = {
    "spam": ("seo services", "backlinks", "crypto", "casino", "guaranteed traffic", "rank #1"),
    "job_application": ("my cv", "resume attached", "job opening", "busco trabajo", "curriculum", "vacante"),
    "support": ("not working", "error", "refund", "my order", "password", "no funciona", "reclamo"),
    "partnership": ("partnership", "reseller", "affiliate", "alianza", "distribuidor"),
    "sales": ("pricing", "price", "quote", "demo", "buy", "plan", "presupuesto", "cotización", "cotizacion",
              "precio", "contratar", "comprar"),
}
FREE_EMAIL = ("gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "live.com")
URGENT = ("asap", "urgent", "this week", "this month", "urgente", "esta semana", "este mes", "lo antes posible")
SOURCE_POINTS = {"website": 15, "email": 10, "referral": 20, "ads_csv": 5}


def keyword_intent(text: str) -> str:
    text = text.lower()
    for intent in ("spam", "job_application", "support", "partnership", "sales"):
        if any(word in text for word in KEYWORDS[intent]):
            return intent
    return "sales"  # an unknown inquiry to sales@ is treated as a potential customer


def llm_intent(text: str) -> str | None:
    """Ask an LLM for the intent. Returns None when no provider is configured or the call fails."""
    prompt = (f"Classify this inbound message into exactly one of {list(INTENTS)}. "
              f'Answer only JSON like {{"intent": "sales"}}.\n\nMessage:\n{text[:2000]}')
    try:
        if os.environ.get("ANTHROPIC_API_KEY"):
            resp = httpx.post(
                "https://api.anthropic.com/v1/messages", timeout=30,
                headers={"x-api-key": os.environ["ANTHROPIC_API_KEY"], "anthropic-version": "2023-06-01"},
                json={"model": os.environ.get("LLM_MODEL", "claude-haiku-4-5"), "max_tokens": 50,
                      "messages": [{"role": "user", "content": prompt}]},
            )
            answer = resp.json()["content"][0]["text"]
        elif os.environ.get("GEMINI_API_KEY"):
            resp = httpx.post(
                "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", timeout=30,
                headers={"Authorization": f"Bearer {os.environ['GEMINI_API_KEY']}"},
                json={"model": os.environ.get("LLM_MODEL", "gemini-3.5-flash-lite"),
                      "messages": [{"role": "user", "content": prompt}]},
            )
            answer = resp.json()["choices"][0]["message"]["content"]
        else:
            return None
        intent = json.loads(re.search(r"\{.*\}", answer, re.DOTALL).group())["intent"]
        return intent if intent in INTENTS else None
    except Exception:
        return None


def classify_intent(lead: Lead, use_llm: bool = True) -> str:
    text = f"{lead.message} {lead.company or ''}"
    return (llm_intent(text) if use_llm else None) or keyword_intent(text)


def score(lead: Lead) -> None:
    """Score 0-100 and tier (Hot / Warm / Cold / Disqualified), recording each reason."""
    points, reasons = 30, ["Base score +30"]

    def add(value: int, reason: str) -> None:
        nonlocal points
        points += value
        reasons.append(f"{reason} {value:+d}")

    if lead.intent in ("spam", "job_application", "support"):
        lead.score, lead.tier = 0, "Disqualified"
        lead.reasons = [f"Intent is {lead.intent} -> routed outside sales"]
        return

    add(SOURCE_POINTS.get(lead.source, 0), f"Source {lead.source}")
    if lead.budget:
        if lead.budget >= 5000:
            add(25, "Budget >= 5,000")
        elif lead.budget >= 1000:
            add(15, "Budget >= 1,000")
        else:
            add(5, "Budget stated")
    if lead.employees:
        add(15 if lead.employees >= 50 else 8, f"Company size {lead.employees}")
    text = lead.message.lower()
    if any(word in text for word in URGENT):
        add(15, "Urgent timeline")
    if any(word in text for word in ("demo", "pricing", "quote", "presupuesto", "cotización", "precio")):
        add(10, "Asked for pricing/demo")
    if lead.email and lead.email.split("@")[-1] in FREE_EMAIL and not lead.company:
        add(-10, "Personal email and no company")
    if not lead.phone:
        add(-5, "No phone")
    if lead.intent == "partnership":
        add(-10, "Partnership (not a direct sale)")

    lead.score = max(0, min(100, points))
    lead.tier = "Hot" if lead.score >= 70 else "Warm" if lead.score >= 45 else "Cold"
    lead.reasons = reasons
