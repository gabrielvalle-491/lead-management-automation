"""Generate demo leads in the three source formats (CSV, JSON web forms, .eml emails)."""

from __future__ import annotations

import argparse
import csv
import json
import random
from datetime import datetime, timedelta
from email.message import EmailMessage
from email.utils import format_datetime
from pathlib import Path

PEOPLE = [
    ("Laura Méndez", "laura@ferreteriasur.com.ar", "Ferretería Sur", 35),
    ("Diego Ramos", "dramos@logisticacuyo.com", "Logística Cuyo", 120),
    ("Paula Ortiz", "paula.ortiz@gmail.com", None, None),
    ("Martín Ruiz", "mruiz@clinicadelsol.com", "Clínica del Sol", 80),
    ("Carla Vega", "carla@estudiovega.com", "Estudio Vega", 6),
    ("Tomás Ibarra", "tomas.ibarra@hotmail.com", None, None),
    ("Sofía Navarro", "snavarro@agroandes.com", "AgroAndes", 260),
    ("Lucas Ferreyra", "lucas@tiendaferreyra.com", "Tienda Ferreyra", 12),
    ("Valentina Paz", "vpaz@inmobiliariapaz.com", "Inmobiliaria Paz", 18),
    ("Nicolás Bravo", "nbravo@constructorabravo.com", "Constructora Bravo", 95),
]
MESSAGES = [
    ("We need a quote for automating our invoices, ideally this month.", 6000),
    ("Hola, quisiera un presupuesto para automatizar reportes en Excel. Es urgente.", 2500),
    ("Can we book a demo? We are comparing options.", 1200),
    ("Me interesa conocer precios del plan mensual.", None),
    ("Just browsing, maybe next year.", None),
    ("We'd like to become a reseller / partnership in Chile.", None),
]
NOISE = [
    ("SEO Master", "offers@seo-rank.biz", "We offer SEO services and backlinks, guaranteed traffic, rank #1!"),
    ("Pablo Candidato", "pablo.cv@gmail.com", "Hola, adjunto mi curriculum por la vacante publicada."),
    ("Cliente Enojado", "reclamos@gmail.com", "Mi pedido no funciona y quiero un refund."),
]


def generate(folder: Path, seed: int = 3) -> None:
    """Write deterministic demo leads (CSV, JSON web forms, .eml emails) into `folder`."""
    rng = random.Random(seed)
    now = datetime(2026, 10, 1, 9, 0)
    (folder / "web_forms").mkdir(parents=True, exist_ok=True)
    (folder / "emails").mkdir(parents=True, exist_ok=True)

    with open(folder / "facebook_lead_ads.csv", "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["created_time", "full_name", "email", "phone_number", "company_name", "company_size",
                         "budget", "message"])
        for i, (name, email, company, size) in enumerate(PEOPLE[:7]):
            msg, budget = rng.choice(MESSAGES)
            writer.writerow([(now - timedelta(hours=i * 5)).isoformat(), name, email,
                             f"+54 9 266 {rng.randint(4000000, 4999999)}", company or "", size or "",
                             budget or "", msg])

    for i, (name, email, company, size) in enumerate(PEOPLE[5:]):  # overlaps with CSV -> duplicates
        msg, budget = rng.choice(MESSAGES)
        payload = {"name": name, "email": email, "phone": f"11{rng.randint(40000000, 49999999)}",
                   "company": company, "employees": size, "budget": budget, "message": msg,
                   "submitted_at": (now - timedelta(minutes=30 * i)).isoformat()}
        (folder / "web_forms" / f"form_{i + 1:03d}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                                                     encoding="utf-8")

    for i, (name, email, body) in enumerate(NOISE + [("Julieta Sosa", "compras@clinicadelsur.com",
                                                      "Company: Clínica del Sur\nNecesitamos cotización para "
                                                      "digitalizar 3.000 facturas por mes, presupuesto 9000 USD. "
                                                      "Tel +54 9 266 455 1234")]):
        msg = EmailMessage()
        msg["From"], msg["To"] = f"{name} <{email}>", "sales@example.com"
        msg["Subject"] = body.splitlines()[-1].split(".")[0][:60]
        msg["Date"] = format_datetime(now - timedelta(hours=i))
        msg.set_content(body)
        (folder / "emails" / f"email_{i + 1:03d}.eml").write_bytes(bytes(msg))


def main() -> None:
    """Command-line entry point for generating the demo samples."""
    parser = argparse.ArgumentParser()
    parser.add_argument("folder", type=Path, nargs="?", default=Path("samples"))
    args = parser.parse_args()
    generate(args.folder)
    print(f"Sample leads written to {args.folder}")


if __name__ == "__main__":
    main()
