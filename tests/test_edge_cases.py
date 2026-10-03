import subprocess
import sys
from pathlib import Path

import pytest

from lead_automation.cli import main
from lead_automation.models import Lead
from lead_automation.pipeline import LeadPipeline
from lead_automation.sources import from_csv, from_web_form

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def no_llm(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


def test_help_exits_zero_with_module_prog_name():
    result = subprocess.run([sys.executable, "-m", "lead_automation", "--help"], cwd=ROOT,
                            capture_output=True, text=True)
    assert result.returncode == 0
    assert result.stdout.startswith("usage: python -m lead_automation")


def test_empty_samples_folder_produces_empty_reports(tmp_path, capsys):
    samples, out = tmp_path / "samples", tmp_path / "out"
    samples.mkdir()
    assert main([str(samples), "--out", str(out), "--no-llm"]) == 0
    printed = capsys.readouterr().out
    assert "Leads received: 0 | new: 0 | duplicates merged: 0" in printed
    assert (out / "lead_pipeline.xlsx").exists()
    assert (out / "crm_import.csv").read_text(encoding="utf-8").strip().startswith("First Name,Last Name")


def test_malformed_csv_values_are_ignored_not_fatal(tmp_path):
    csv_file = tmp_path / "ads.csv"
    csv_file.write_text("full_name,email,budget,company_size,created_time,message\n"
                        "Ana Gil,ana@acme.com,n/a,lots,not-a-date,hello\n", encoding="utf-8")
    [lead] = from_csv(csv_file)
    assert lead.budget is None and lead.employees is None
    assert lead.name == "Ana Gil"


def test_web_form_employees_sent_as_text_is_scored():
    # Regression: a string "employees" value used to crash scoring with TypeError.
    pipeline = LeadPipeline(use_llm=False)
    lead, is_new = pipeline.process(from_web_form({"name": "Ana", "email": "ana@acme.com", "phone": "111",
                                                   "employees": "120", "message": "quote please"}))
    assert is_new and lead.employees == 120
    assert "Company size 120 +15" in lead.reasons


def test_duplicate_matched_case_insensitively_by_email():
    pipeline = LeadPipeline(use_llm=False)
    stats = pipeline.process_many([Lead(name="Ana", email="Ana@Acme.com", message="pricing"),
                                   Lead(name="ana gil", email=" ana@acme.com ", message="pricing again")])
    assert stats == {"received": 2, "new": 1, "duplicates": 1}
    [row] = pipeline.all_leads()
    assert row["times_seen"] == 2
