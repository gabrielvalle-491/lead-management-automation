"""Minimal webhook so a website form (or Zapier / Make / n8n) can push leads in real time.

    python -m lead_automation.webhook --db output/leads.db --port 8000

    curl -X POST localhost:8000/lead -H "Content-Type: application/json" \
         -d '{"name": "Ana Gil", "email": "ana@acme.com", "message": "Need a quote ASAP", "budget": 8000}'
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from lead_automation.pipeline import LeadPipeline
from lead_automation.sources import from_web_form


def make_handler(pipeline: LeadPipeline) -> type[BaseHTTPRequestHandler]:
    """Build a request handler class bound to `pipeline` (POST /lead)."""
    class Handler(BaseHTTPRequestHandler):
        def _reply(self, status: int, body: dict) -> None:
            data = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_POST(self) -> None:  # noqa: N802 (http.server naming)
            if self.path != "/lead":
                return self._reply(404, {"error": "not found"})
            try:
                length = int(self.headers.get("Content-Length", 0))
                payload = json.loads(self.rfile.read(length) or b"{}")
            except (ValueError, json.JSONDecodeError):
                return self._reply(400, {"error": "invalid JSON"})
            if not payload.get("email") and not payload.get("phone"):
                return self._reply(422, {"error": "email or phone is required"})
            lead, is_new = pipeline.process(from_web_form(payload))
            return self._reply(201 if is_new else 200, {
                "status": "created" if is_new else "duplicate",
                "tier": lead.tier, "score": lead.score, "owner": lead.owner, "next_action": lead.next_action,
            })

        def log_message(self, fmt: str, *args: object) -> None:  # quieter console
            pass

    return Handler


def main() -> None:
    """Start the webhook server on 127.0.0.1."""
    parser = argparse.ArgumentParser(description="Lead capture webhook")
    parser.add_argument("--db", default="output/leads.db")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = HTTPServer(("127.0.0.1", args.port), make_handler(LeadPipeline(args.db)))
    print(f"Listening on http://127.0.0.1:{args.port}/lead")
    server.serve_forever()


if __name__ == "__main__":
    main()
