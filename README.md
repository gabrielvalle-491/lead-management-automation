# Lead Management Automation

Español: [README.es.md](README.es.md)

![CI](https://github.com/gabrielvalle-491/lead-management-automation/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

Captures, classifies and organizes leads automatically.

Leads arrive from ad-platform CSV exports, the website contact form and the
`sales@` inbox. This tool merges all of them into one pipeline, removes duplicates,
detects what each person wants (with AI or keyword rules), scores them 0-100 with
**explained reasons**, assigns an owner, schedules the follow-up, and produces an
Excel pipeline report plus a CSV ready to import into a CRM.

## The business problem

A small company spends money on Facebook/LinkedIn ads and receives leads in three
different places. Nobody knows which lead to call first, the same person is
contacted twice, spam and job applications get mixed with real customers, and hot
leads go cold because no one followed up in time.

## How it works

```
 CSV exports ─┐
 Web form  ───┼─► normalize ─► dedupe ─► intent (AI / rules) ─► score + reasons ─► route ─► SQLite
 Emails .eml ─┘                                                                       │
                                                       Excel pipeline report ◄────────┤
                                                       CRM import CSV        ◄────────┘
```

| Feature | Detail |
|---------|--------|
| **Capture** | Lead Ads CSV, website JSON payloads, `.eml` emails (extracts company, phone and budget from the text) and a **real-time webhook** (`POST /lead`) for Zapier / Make / n8n or a website form |
| **Deduplicate** | Same email/phone across sources = one lead (`times_seen` counter instead of duplicate rows) |
| **Intent** | `sales`, `support`, `partnership`, `job_application`, `spam`. Uses Claude or Gemini when an API key is set, keyword rules otherwise (always works offline) |
| **Score** | Transparent rules: source, budget, company size, urgency, asked for pricing/demo, personal email without company, missing phone. Every point is recorded in `reasons` |
| **Route** | Hot / Warm / Cold with next action + follow-up time; support → `support@`, CVs → `hr@`, spam → archive; round-robin between sales reps |
| **Report** | Excel with **Summary**, color-coded **Pipeline** and **Follow-ups due**; `crm_import.csv` (HubSpot/Pipedrive style columns) |

## Quick start

```bash
pip install -r requirements.txt

python -m lead_automation.generate_samples samples   # demo leads in the 3 formats
python -m lead_automation samples --out output --no-llm --now 2026-10-01T10:00
```

```
Leads received: 16 | new: 14 | duplicates merged: 2
Tiers: Hot: 6 | Warm: 4 | Cold: 1 | Disqualified: 3
Follow-ups due: 6
Report: output/lead_pipeline.xlsx
CRM import: output/crm_import.csv
```

Use AI intent classification by setting one key (optional):

```bash
export ANTHROPIC_API_KEY=...   # Claude
# or
export GEMINI_API_KEY=...      # Google Gemini (free tier)
python -m lead_automation samples --out output
```

Real-time capture:

```bash
python -m lead_automation.webhook --db output/leads.db --port 8000
curl -X POST localhost:8000/lead -H "Content-Type: application/json" \
     -d '{"name": "Ana Gil", "email": "ana@acme.com", "message": "Need a quote ASAP", "budget": 8000}'
# {"status": "created", "tier": "Hot", "score": 90, "owner": "Sales Rep A", "next_action": "Call within 1 hour"}
```

## Sample output (real output of the demo)

| Score | Tier | Intent | Name | Company | Source | Owner | Next action | Why |
|---:|---|---|---|---|---|---|---|---|
| 100 | Hot | sales | Sofía Navarro | AgroAndes | ads_csv | Sales Rep A | Call within 1 hour | Budget ≥ 5,000 +25 · Company size 260 +15 · Urgent +15 · Asked for pricing +10 |
| 93 | Hot | sales | Lucas Ferreyra | Tienda Ferreyra | website | Sales Rep B | Call within 1 hour | Website +15 · Budget ≥ 1,000 +15 · Urgent +15 · Pricing +10 |
| 53 | Warm | sales | Valentina Paz | Inmobiliaria Paz | website | Sales Rep A | Send case study + book a call | Website +15 · Company size 18 +8 |
| 33 | Cold | partnership | Carla Vega | Estudio Vega | ads_csv | Sales Rep A | Add to nurture sequence | Partnership −10 |
| 0 | Disqualified | spam | Seo Master | – | email | archive | – | Spam |
| 0 | Disqualified | job_application | Pablo Candidato | – | email | hr@ | – | Routed to HR |

## Project structure

```
lead_automation/
├── models.py            # Lead dataclass + normalization
├── sources.py           # CSV / JSON web form / .eml parsers
├── classify.py          # intent (LLM or keywords) + explainable scoring
├── pipeline.py          # dedupe, routing, follow-ups, SQLite storage
├── report.py            # Excel report + CRM CSV
├── webhook.py           # real-time capture endpoint (stdlib only)
└── generate_samples.py
tests/                   # 17 pytest tests incl. a live webhook test
```

## Tests

```bash
pytest -q
```

## Notes

- All leads are synthetic demo data. No real people or companies.
- Scoring weights live in `classify.py` and are meant to be tuned with the sales team.
- Built with Python and [Claude Code](https://claude.com/claude-code) as an AI pair programmer.

## How I would deliver this to a client

If you hire me for this, I would:

- **Agree on the inputs first:** your Lead Ads CSV exports (any of the column names in `sources.py`, e.g. `full_name` / `nombre`), website form submissions as JSON (or pushed live to the webhook), and emails to `sales@` saved as `.eml` files.
- **Set up one folder and one command:** you drop the week's files into the input folder (`*.csv`, `web_forms/`, `emails/`) and run `python -m lead_automation <folder> --out output`, or I schedule it as a Windows Task Scheduler / cron job every Monday morning.
- **Tune the rules with your sales team:** scoring weights, keywords, sales rep names and follow-up times live in `classify.py` and `pipeline.py`, so they can be adjusted without touching the rest.
- **Hand over the outputs you actually use:** `lead_pipeline.xlsx` (Summary, Pipeline, Follow-ups due) for the team and `crm_import.csv` for HubSpot / Pipedrive.
- **Make problems visible:** every run prints a summary (leads received, duplicates merged, tiers, follow-ups due); the command exits with a non-zero code (and a Python traceback) on bad arguments or a file it cannot parse, such as broken JSON, so a scheduled task shows it as failed; an empty or wrong folder shows up as `Leads received: 0`; the webhook answers `400` for invalid JSON and `422` when a lead has no email or phone.
- **Keep it working offline:** without an API key (or if the AI call fails) intent falls back to the keyword rules, so the weekly run never depends on an external service.
- **Document and test it:** a short run guide for your team plus the automated tests (`pytest -q`) so changes to the rules can be checked before they are used.

## Author

**Gabriel Valle** — Data & AI automation (Excel, PDF, workflows) · Villa Mercedes, Argentina · Remote
