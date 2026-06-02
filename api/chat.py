"""Vercel serverless function for the ACR Concierge chat.

Deployed at /api/chat (Vercel maps api/<name>.py -> /api/<name>). Mirrors the
local server.py proxy: forwards the messages array to the Anthropic Messages API
using the ANTHROPIC_API_KEY set in the Vercel project's environment variables.

If no key is configured, it falls back to a built-in keyword responder so the
deployed demo never looks broken.

Zero dependencies — Python standard library only, so no requirements.txt needed.
"""

import json
import os
import re
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 400

SYSTEM_PROMPT = (
    "You are the ACR Concierge, the friendly AI assistant for ACR — a premium "
    "home backyard renovation design-and-build studio. ACR creates extraordinary "
    "outdoor spaces: architectural pools and water features, outdoor kitchens, "
    "fire pits, pergolas and outdoor living rooms, landscape design, patios, decks, "
    "and smart outdoor lighting. ACR is a single accountable team handling everything "
    "from concept and 3D renders through to construction. "
    "Tone: warm, confident, concise, premium — like a great studio's front desk. "
    "Help visitors understand services, ballpark process and timelines, and gently "
    "encourage them to book a complimentary design consultation. Visitors can book a "
    "design visit right on this site using the calendar in the booking section, or by "
    "email hello@acr.studio or phone +1 (800) 555-0199. If someone is ready to book, "
    "point them to the on-site calendar. Keep replies to 2-4 short sentences. You may also "
    "be reached by voice. Do not invent exact prices; instead explain that pricing depends "
    "on scope and offer a consultation."
)

FALLBACK_RULES = [
    (r"\b(price|cost|quote|budget|how much)\b",
     "Every backyard is bespoke, so pricing depends on scope — pool, hardscape, planting, and finishes. "
     "We'd love to give you a tailored estimate during a free design consultation. Want me to point you to booking?"),
    (r"\b(pool|water|spa|hot tub)\b",
     "Pools and water features are one of our signatures — infinity edges, spas, and architectural water elements "
     "engineered to be the centerpiece of the yard. Shall I tell you about our design-and-build process?"),
    (r"\b(kitchen|fire|pergola|living|lounge|bbq|grill)\b",
     "Outdoor living is our favorite work: kitchens, fire pits, pergolas, and lounges that become your favorite room. "
     "We can sketch a first concept for you in a complimentary consultation."),
    (r"\b(garden|landscap|plant|lawn|tree)\b",
     "Our landscape team composes planting, lighting, and hardscape for year-round beauty with easy upkeep. "
     "Would you like to see more of our portfolio?"),
    (r"\b(time|long|timeline|schedule|when)\b",
     "Timelines vary with scope, but most full backyard transformations run roughly 8–16 weeks from approved design. "
     "We'll give you a firm schedule after the site visit."),
    (r"\b(contact|book|consult|appointment|talk|call|email|reach)\b",
     "Wonderful — book a complimentary design visit right here using the calendar, or reach us at hello@acr.studio "
     "or +1 (800) 555-0199, and we'll sketch the first vision of your new backyard."),
    (r"\b(hi|hello|hey|greetings)\b",
     "Hi there! I'm the ACR Concierge. I can tell you about our pools, outdoor kitchens, landscaping, "
     "and design-build process — what are you dreaming up for your backyard?"),
]
FALLBACK_DEFAULT = (
    "I'm the ACR Concierge — I can help with pools, outdoor kitchens, patios, landscaping, and our design-build "
    "process. Tell me about your space, or book a free design visit using the calendar on this page."
)


def fallback_reply(messages):
    last_user = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            last_user = (m.get("content") or "").lower()
            break
    for pattern, reply in FALLBACK_RULES:
        if re.search(pattern, last_user):
            return reply
    return FALLBACK_DEFAULT


def call_anthropic(messages):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    payload = json.dumps({
        "model": os.environ.get("ANTHROPIC_MODEL", DEFAULT_MODEL),
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": messages,
    }).encode("utf-8")

    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return "".join(
        block.get("text", "")
        for block in data.get("content", [])
        if block.get("type") == "text"
    ).strip()


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
            messages = req.get("messages", [])
            if not isinstance(messages, list) or not messages:
                self._send_json(400, {"error": "messages required"})
                return
            try:
                text = call_anthropic(messages)
                source = "anthropic"
            except RuntimeError:
                text = fallback_reply(messages)
                source = "fallback"
            self._send_json(200, {"text": text, "source": source})
        except urllib.error.HTTPError:
            self._send_json(200, {"text": fallback_reply(req.get("messages", [])), "source": "fallback"})
        except Exception as e:  # noqa: BLE001
            self._send_json(500, {"error": str(e)})
