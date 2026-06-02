"""Vercel serverless function for ACR design-visit bookings.

Deployed at /api/book (Vercel maps api/<name>.py -> /api/<name>). Validates the
booking payload and acknowledges it. Vercel's filesystem is ephemeral, so the
record is appended to /tmp (best-effort, for the running instance only) and
logged — in production you'd forward this to email/CRM/a database here.

Zero dependencies — Python standard library only.
"""

import json
import os
import sys
from http.server import BaseHTTPRequestHandler


class handler(BaseHTTPRequestHandler):
    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
            name = (req.get("name") or "").strip()
            email = (req.get("email") or "").strip()
            date = req.get("date")
            time = req.get("time")
            if not (name and email and date and time):
                self._send_json(400, {"error": "name, email, date and time are required"})
                return
            record = {
                "name": name,
                "email": email,
                "phone": (req.get("phone") or "").strip(),
                "date": date,
                "dateLabel": req.get("dateLabel"),
                "time": time,
            }
            # Best-effort persistence on serverless (ephemeral /tmp). Swap this
            # block for an email/CRM/database call in production.
            try:
                with open("/tmp/acr-bookings.jsonl", "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record) + "\n")
            except OSError:
                pass
            sys.stdout.write(f"[api/book] {name} <{email}> — {req.get('dateLabel') or date} {time}\n")
            self._send_json(200, {"ok": True, "message": "Booking confirmed"})
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
