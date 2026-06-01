#!/usr/bin/env python3
"""ACR backyard studio demo server.

Serves the static ACR site AND proxies the AI concierge chat to the Anthropic
Messages API, so the assistant works standalone.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 server.py            # serves on http://localhost:8123
    PORT=9000 python3 server.py  # custom port

Optional:
    ANTHROPIC_MODEL   override the model (default: claude-haiku-4-5-20251001)

Zero dependencies — standard library only. If ANTHROPIC_API_KEY is unset, the
site still works and the chat falls back to a built-in keyword responder so the
demo never looks broken.
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

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
    "encourage them to book a complimentary design consultation (email hello@acr.studio "
    "or call +1 (800) 555-0199). Keep replies to 2-4 short sentences. Do not invent "
    "exact prices; instead explain that pricing depends on scope and offer a consultation."
)

# Lightweight offline fallback so the demo works with no API key.
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
     "Wonderful — book a complimentary design consultation at hello@acr.studio or call +1 (800) 555-0199, "
     "and we'll sketch the first vision of your new backyard."),
    (r"\b(hi|hello|hey|greetings)\b",
     "Hi there! I'm the ACR Concierge. I can tell you about our pools, outdoor kitchens, landscaping, "
     "and design-build process — what are you dreaming up for your backyard?"),
]
FALLBACK_DEFAULT = (
    "I'm the ACR Concierge — I can help with pools, outdoor kitchens, patios, landscaping, and our design-build "
    "process. Tell me about your space, or book a free consultation at hello@acr.studio."
)


def fallback_reply(messages):
    """Keyword-matched reply used when no API key is configured."""
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
    """Forward a messages array to the Anthropic Messages API, return reply text."""
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


class Handler(SimpleHTTPRequestHandler):
    def _send_json(self, status, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path.rstrip("/") != "/api/chat":
            self.send_error(404, "Not found")
            return
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
                # No API key — graceful offline fallback.
                text = fallback_reply(messages)
                source = "fallback"
            self._send_json(200, {"text": text, "source": source})
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")
            sys.stderr.write(f"[api/chat] Anthropic {e.code}: {detail}\n")
            # Still answer the visitor with the offline responder.
            self._send_json(200, {"text": fallback_reply(req.get("messages", [])), "source": "fallback"})
        except Exception as e:  # noqa: BLE001
            sys.stderr.write(f"[api/chat] {type(e).__name__}: {e}\n")
            self._send_json(500, {"error": str(e)})


def main():
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8123))
    directory = os.path.dirname(os.path.abspath(__file__))
    handler = partial(Handler, directory=directory)
    server = ThreadingHTTPServer(("", port), handler)
    keyed = "set" if os.environ.get("ANTHROPIC_API_KEY") else "NOT set — chat uses offline fallback"
    print(f"ACR studio on http://localhost:{port}  (ANTHROPIC_API_KEY: {keyed})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
