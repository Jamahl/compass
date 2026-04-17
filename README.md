# BetterLabs Research Studio

Localhost hackathon app. Run a research prompt through the Parallel Task API,
synthesise a brief with OpenAI, then fan-out to generate 14 possible output
artifacts (reports, podcast, slides, video, infographic, briefing doc, FAQ,
study guide, timeline, quiz, data table, plain text). Each artifact previews
inline in a modal (PDF iframe, `<audio>`, `<video>`, `<img>`, rendered
markdown) and has a Download button.

Chat with the research context after the research stage completes.

## Prereqs

- Node 20+ and npm
- Python 3.11+
- macOS / Linux

## Setup

```bash
cd Hackathon

# Frontend workspace + tooling (installs at root)
npm install

# Backend venv + deps
cd apps/api
python3 -m venv .venv
.venv/bin/pip install -e .
cd ../..

# API keys
cp .env.example .env   # then edit .env and paste real keys
```

`.env` needs:

```
OPENAI_API_KEY=sk-...
PARALLEL_API_KEY=...
AUTOCONTENT_API_KEY=...
```

## Run

Two terminals (or use `npm run dev` to concurrently boot both):

```bash
# terminal 1 — API on :8000
cd apps/api
.venv/bin/uvicorn main:app --reload --port 8000

# terminal 2 — web on :5173 (proxies /api/* -> :8000)
npm --workspace web run dev
```

Open http://localhost:5173

## Output types (14)

**Reports (OpenAI → PDF via fpdf2):** 1-page report · 5-page report · competitor analysis

**AutoContent media:** podcast (mp3) · slides (narrated mp4) · video (mp4) · infographic (png) · briefing doc (pdf)

**AutoContent structured text (saved as .md):** FAQ · study guide · timeline · quiz · data table · plain text

## Architecture

See [project_overview.md](project_overview.md) for data model, routes,
run lifecycle, and conventions. See [tasks.md](tasks.md) for the original
build plan.

- Frontend: Vite + React + TS + Tailwind v4 + shadcn/ui + zustand + Dexie
- Backend: FastAPI, in-memory run store, `asyncio.gather` writer fan-out
- Transport: REST + 2s polling (no SSE)
- Artifacts: `/tmp/betterlabs-artifacts/{run_id}/{artifact_id}.{ext}`
