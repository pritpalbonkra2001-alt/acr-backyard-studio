# ACR — Backyard Renovation Studio

A premium, responsive single-page site for **ACR**, a home backyard renovation
design-and-build studio. Built with a soft sky-blue palette, rounded Quicksand
display type, and an AI concierge that supports **chat, voice, and hands-free calling**.

![ACR](https://images.unsplash.com/photo-1600585154340-be6161a56a0c?auto=format&fit=crop&w=1200&q=60)

## Features

- **Responsive design** — hero with interactive image hotspots, recent projects,
  filterable portfolio, testimonials, services, and CTA.
- **3D animations** — mouse-driven parallax tilt on the hero photo and on every
  project / portfolio / service card, depth-popped hotspots, a breathing voice orb,
  and scroll-reveal transitions (all disabled under `prefers-reduced-motion`).
- **Calendar + AI booking** — pick a date and time on a live month calendar
  (past dates & Sundays disabled), enter your details, and bookings POST to
  `/api/book` and persist to `bookings.jsonl`. An AI slot-suggester turns a
  phrase like _"a weekend morning next week"_ into a selected date/time.
- **AI Concierge (chat)** — floating assistant backed by the Anthropic Messages API
  with an ACR-specific system prompt.
- **AI Voice** — speak your questions (Web Speech recognition) and have replies
  read aloud (Speech Synthesis).
- **AI Calling** — a full-screen, hands-free voice-call experience with a live
  animated orb (listening → thinking → speaking loop), mute, and end-call controls.
- **Graceful offline fallback** — with no API key set, a built-in keyword responder
  keeps the assistant working for demos.

## Run locally

```bash
# Optional — enables real Claude replies (otherwise uses the offline fallback)
export ANTHROPIC_API_KEY=sk-ant-...

python3 server.py            # serves on http://localhost:8123
PORT=9000 python3 server.py  # custom port
```

Then open <http://localhost:8123>.

### Optional environment

| Variable            | Default                        | Purpose                       |
| ------------------- | ------------------------------ | ----------------------------- |
| `ANTHROPIC_API_KEY` | _(unset → offline fallback)_   | Enables live Claude replies   |
| `ANTHROPIC_MODEL`   | `claude-haiku-4-5-20251001`    | Override the model            |
| `PORT`              | `8123`                         | Server port                   |

## Stack

- Single static `index.html` (HTML + CSS + vanilla JS — no build step)
- Zero-dependency Python proxy (`server.py`, standard library only)
- Browser-native Web Speech API for voice in/out

## Browser support for voice

Voice **calling/input** needs Chrome, Edge, or Safari with microphone permission.
Voice **output** (spoken replies) works in essentially all modern browsers. The
text chat works everywhere.
