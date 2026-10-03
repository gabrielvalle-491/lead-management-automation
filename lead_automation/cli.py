"""Batch mode: ingest every source folder, then write the Excel report and the CRM CSV.

    python -m lead_automation samples --out output
"""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from lead_automation.pipeline import LeadPipeline
from lead_automation.report import write_crm_csv, write_excel
from lead_automation.sources import from_csv, from_email_folder, from_json_folder


def main(argv: list[str] | None = None) -> int:
    """Run the batch pipeline over a samples folder and write the reports. Returns the exit code."""
    parser = argparse.ArgumentParser(prog="python -m lead_automation",
                                     description="Capture, classify and organize leads")
    parser.add_argument("samples", type=Path, help="Folder with *.csv, web_forms/*.json and emails/*.eml")
    parser.add_argument("--out", type=Path, default=Path("output"))
    parser.add_argument("--db", type=Path, default=None, help="SQLite file (default: <out>/leads.db)")
    parser.add_argument("--no-llm", action="store_true", help="Use keyword intent classifier only")
    parser.add_argument("--now", default=None, help="Reference time for due follow-ups (ISO)")
    args = parser.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    db = args.db or args.out / "leads.db"
    db.unlink(missing_ok=True)  # batch mode rebuilds from sources
    pipeline = LeadPipeline(db, use_llm=not args.no_llm)

    leads = []
    for csv_file in sorted(args.samples.glob("*.csv")):
        leads += from_csv(csv_file)
    leads += from_json_folder(args.samples / "web_forms")
    leads += from_email_folder(args.samples / "emails")
    stats = pipeline.process_many(leads)

    rows = pipeline.all_leads()
    now = datetime.fromisoformat(args.now) if args.now else datetime.now()
    due = pipeline.due_follow_ups(now)
    xlsx = write_excel(rows, due, args.out / "lead_pipeline.xlsx")
    crm = write_crm_csv(rows, args.out / "crm_import.csv")

    tiers = {t: sum(r["tier"] == t for r in rows) for t in ("Hot", "Warm", "Cold", "Disqualified")}
    print(f"Leads received: {stats['received']} | new: {stats['new']} | duplicates merged: {stats['duplicates']}")
    print("Tiers: " + " | ".join(f"{k}: {v}" for k, v in tiers.items()))
    print(f"Follow-ups due: {len(due)}")
    print(f"Report: {xlsx}\nCRM import: {crm}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
