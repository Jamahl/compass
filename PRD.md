# BetterLabs Research Studio — PRD + Architecture

**Scope:** 4-hour hackathon. Minimal web app. BetterLabs venture studio runs product/company research via agents, then generates a chosen output artifact (podcast, slides, 1-pg report, 5-pg report, competitor doc, video). Single user, no auth.

---

## 1. Product Requirements

### 1.1 User Flow

1. User lands on single-page app.
2. **Input panel:** picks context sources
   - Free-text prompt (goal / company / product thesis)
   - URL list (paste links, one per line)
   - Preset research template (dropdown: Market Sizing, Competitor Scan, Customer Pain, Company Deep-Dive, Product Teardown)
3. **Research depth toggle:** slider → maps to Parallel Task API processor tier
   - `Quick` → `base` (~30s)
   - `Standard` → `core` (~2min)
   - `Deep` → `pro` (~5min)
   - `Exhaustive` → `ultra` (~10min+)
4. **Output selector:** pick one or many
   - Podcast (AutoContent audio)
   - Slides (AutoContent slides)
   - 1-page report (markdown → PDF)
   - 5-page in-depth report (markdown → PDF)
   - Competitor analysis doc (markdown → PDF)
   - Video overview (AutoContent video)
5. User clicks **Run Research**. Backend spawns CrewAI orchestration.
6. **Dashboard view:** live status per stage (research → outputs). Cards show progress.
7. **Artifacts view:** when each output finishes, card activates with view/download buttons.
8. **Chat view:** once research completes, chat panel unlocks. User chats with research context (OpenAI + research payload as grounding).

### 1.2 Non-Goals (hackathon)

- Auth, multi-user, billing
- Saving runs across browser sessions beyond IndexedDB history
- Editing artifacts, regenerating individual sections
- Streaming token-level updates (stage-level polling fine)
- Mobile polish

### 1.3 Success Criteria

- End-to-end: prompt → research → ≥2 artifacts downloaded → chat works.
- Runs on localhost for demo.
- No crashes in happy path.

---

## 2. External Dependencies

| Service | Use | Key env var |
|---|---|---|
| Parallel Web Systems Task API | Deep research (primary) | `PARALLEL_API_KEY` |
| AutoContent API | Podcast, slides, video generation | `AUTOCONTENT_API_KEY` |
| OpenAI | CrewAI agent LLM + chat + markdown→report writing | `OPENAI_API_KEY` |
| CrewAI | Agent orchestration (Python) | — |

---

## 3. Architecture

### 3.1 High-Level

```
┌────────────────────────┐        ┌─────────────────────────────┐
│  React + Vite (SPA)    │ HTTP   │  FastAPI (Python)           │
│  IndexedDB (sessions)  │◄──────►│  CrewAI orchestrator        │
│  shadcn/ui dashboard   │  SSE   │  Parallel / AutoContent /   │
│                        │        │  OpenAI clients             │
└────────────────────────┘        │  /artifacts on disk (tmp)   │
                                  └─────────────────────────────┘
```

- **Frontend** owns session history, UI state, chat transcript (IndexedDB via `dexie`).
- **Backend** owns research execution, tool calls, file generation, artifact storage.
- **Transport:** REST for create/query; SSE (`/runs/{id}/events`) for stage progress.

### 3.2 Monorepo Layout

```
Hackathon/
├── README.md
├── PRD.md
├── .env.example
├── package.json                 # root, runs concurrently
├── pnpm-workspace.yaml          # or npm workspaces
│
├── apps/
│   ├── web/                     # Vite + React frontend
│   │   ├── index.html
│   │   ├── vite.config.ts
│   │   ├── package.json
│   │   ├── tsconfig.json
│   │   └── src/
│   │       ├── main.tsx
│   │       ├── App.tsx
│   │       ├── api/
│   │       │   ├── client.ts        # fetch wrapper → FastAPI
│   │       │   └── sse.ts           # EventSource helper
│   │       ├── db/
│   │       │   └── dexie.ts         # IndexedDB schema (runs, messages)
│   │       ├── state/
│   │       │   └── store.ts         # zustand — current run, UI flags
│   │       ├── components/
│   │       │   ├── InputPanel.tsx   # prompt + URLs + template + depth
│   │       │   ├── OutputSelector.tsx
│   │       │   ├── RunDashboard.tsx # stage cards + progress
│   │       │   ├── ArtifactCard.tsx # view + download
│   │       │   ├── ChatPanel.tsx    # chat with research
│   │       │   └── ui/              # shadcn primitives
│   │       └── lib/
│   │           └── formats.ts       # output-type metadata
│   │
│   └── api/                     # FastAPI backend
│       ├── pyproject.toml
│       ├── main.py              # FastAPI app, route registration
│       ├── .python-version
│       └── src/
│           ├── routes/
│           │   ├── runs.py          # POST /runs, GET /runs/{id}
│           │   ├── events.py        # GET /runs/{id}/events (SSE)
│           │   ├── artifacts.py     # GET /artifacts/{id} (download)
│           │   └── chat.py          # POST /runs/{id}/chat
│           ├── orchestrator/
│           │   ├── crew.py          # CrewAI crew + tasks definition
│           │   ├── agents.py        # researcher, synthesizer, writer
│           │   └── runner.py        # async run + SSE event bus
│           ├── tools/
│           │   ├── parallel.py      # Parallel Task API client
│           │   ├── autocontent.py   # AutoContent client (audio/slides/video)
│           │   └── reportgen.py     # markdown → PDF (weasyprint or md2pdf)
│           ├── store/
│           │   ├── runs.py          # in-memory dict: run_id → state
│           │   └── artifacts_dir.py # /tmp/betterlabs-artifacts/
│           ├── models.py            # pydantic: RunRequest, RunState, Artifact
│           └── config.py            # env vars, settings
│
└── packages/
    └── shared/
        └── types.ts             # shared TS types mirrored from pydantic
```

### 3.3 What Each Part Does

**Frontend (`apps/web`)**
- `InputPanel` — collects prompt, URL list, preset template, depth toggle. Posts to `POST /runs`.
- `OutputSelector` — multi-select of artifact types. Bundled into run request.
- `RunDashboard` — subscribes to `/runs/{id}/events` SSE. Renders stage cards: `research`, then one card per requested output.
- `ArtifactCard` — when stage emits `artifact_ready`, shows preview + download button (hits `GET /artifacts/{id}`).
- `ChatPanel` — enabled after `research_done`. Sends messages to `POST /runs/{id}/chat`. Stores transcript in IndexedDB.
- `dexie.ts` — two tables: `runs` (id, prompt, createdAt, status, artifactIds) and `messages` (runId, role, content, ts). Lets user see past runs in session.
- `store.ts` — zustand for transient UI (which run is open, SSE connection status).

**Backend (`apps/api`)**
- `routes/runs.py`
  - `POST /runs` → creates run_id, kicks off async `runner.start(run_id, request)`, returns run_id.
  - `GET /runs/{id}` → current state snapshot.
- `routes/events.py` → SSE stream of events from in-memory pub/sub for that run_id.
- `routes/artifacts.py` → `FileResponse` from artifacts dir. Content-Disposition = attachment.
- `routes/chat.py` → takes research payload (cached in run state) + user message, calls OpenAI with research as system context, returns reply.
- `orchestrator/crew.py` — defines CrewAI crew:
  - **Researcher agent** — tool: `parallel.run_task(prompt, urls, template, processor)`. Returns structured research JSON.
  - **Synthesizer agent** — tool: OpenAI LLM. Normalizes research into a canonical brief (exec summary, findings, sources).
  - **Writer agent(s)** — one task per selected output type:
    - Report types → `reportgen.md_to_pdf(content)` → saves to artifacts dir.
    - Podcast/slides/video → `autocontent.generate(type, brief)` → polls, downloads, saves to artifacts dir.
- `orchestrator/runner.py` — `asyncio.create_task` runs the crew. Emits events (`stage_started`, `stage_progress`, `artifact_ready`, `run_done`, `error`) to the SSE bus keyed by run_id.
- `tools/*` — thin HTTP clients. Retries + timeouts only; no extra abstraction.
- `store/runs.py` — `dict[run_id, RunState]` in process memory. Fine for hackathon (single worker, no restart).
- `store/artifacts_dir.py` — creates and returns `/tmp/betterlabs-artifacts/{run_id}/{artifact_id}.{ext}`.

### 3.4 State — Where It Lives

| State | Location | Lifetime |
|---|---|---|
| Run request (prompt, URLs, template, depth, outputs) | POST body → `store/runs.py` dict | Process memory |
| Run status + stage events | `store/runs.py` dict + SSE bus | Process memory |
| Research payload (for chat grounding) | `RunState.research_payload` | Process memory |
| Artifact files | `/tmp/betterlabs-artifacts/{run_id}/` | Disk, wiped on reboot |
| Run history + chat transcript | IndexedDB (`dexie`) in browser | Browser session (survives reload) |
| Transient UI (open run, SSE status) | zustand in memory | Tab lifetime |
| API keys | `.env` loaded by FastAPI `config.py` | Process |

**Rule:** backend is stateless across restarts (hackathon trade-off). Browser remembers run history but artifact files only exist while backend process is alive. Acceptable — demo restarts are rare.

### 3.5 How Services Connect

```
User action → fetch POST /runs
  → FastAPI creates run_id, stores RunState(status=pending)
  → asyncio task: runner.start(run_id)
      → CrewAI crew kickoff
          → Researcher: tools/parallel.run_task() [Parallel API]
              ↳ emit stage_progress
          → Synthesizer: OpenAI call
          → Writer fan-out (one per output):
              - reportgen.md_to_pdf()  OR  autocontent.generate() [poll until done]
              ↳ emit artifact_ready per artifact
      → emit run_done

Frontend EventSource("/runs/{id}/events")
  → updates zustand → renders dashboard cards
  → on artifact_ready: ArtifactCard active → download via GET /artifacts/{id}

Chat:
User message → POST /runs/{id}/chat { message }
  → backend loads RunState.research_payload
  → OpenAI chat completion (system=research_payload, history=frontend-supplied)
  → returns { reply }
  → frontend persists to IndexedDB
```

### 3.6 API Contract (minimal)

```
POST /runs
  body: {
    prompt: string,
    urls: string[],
    template: "market_sizing" | "competitor_scan" | "customer_pain" | "company_deep_dive" | "product_teardown" | "custom",
    depth: "quick" | "standard" | "deep" | "exhaustive",
    outputs: ("podcast" | "slides" | "report_1pg" | "report_5pg" | "competitor_doc" | "video")[]
  }
  → { run_id: string }

GET /runs/{id}
  → { run_id, status, stages: [...], artifacts: [{id, type, status, filename}], research_summary? }

GET /runs/{id}/events  (SSE)
  → event: stage_started | stage_progress | artifact_ready | run_done | error

GET /artifacts/{artifact_id}
  → binary file download

POST /runs/{id}/chat
  body: { message: string, history: {role, content}[] }
  → { reply: string }
```

### 3.7 Output Type → Generator Map

| Output | Generator | Format |
|---|---|---|
| Podcast | AutoContent audio endpoint | mp3 |
| Slides | AutoContent slides endpoint | pdf or pptx |
| 1-page report | OpenAI → markdown → weasyprint | pdf |
| 5-page report | OpenAI → markdown → weasyprint | pdf |
| Competitor doc | OpenAI → markdown (table-heavy) → weasyprint | pdf |
| Video | AutoContent video endpoint | mp4 |

### 3.8 Dev Setup

```
# root
pnpm i
cp .env.example .env   # fill OPENAI_API_KEY, PARALLEL_API_KEY, AUTOCONTENT_API_KEY

# backend
cd apps/api
uv venv && source .venv/bin/activate
uv pip install -e .
uvicorn main:app --reload --port 8000

# frontend
cd apps/web
pnpm dev   # http://localhost:5173, proxies /api → :8000
```

Root `package.json` script: `"dev": "concurrently 'pnpm --filter web dev' 'cd apps/api && uvicorn main:app --reload --port 8000'"`.

---

## 4. Build Order (4 hours)

1. **0:00–0:30** — scaffold monorepo, FastAPI hello, Vite hello, `.env` wiring, CORS.
2. **0:30–1:15** — Parallel Task API client + one end-to-end `POST /runs` → research JSON returned. No UI yet.
3. **1:15–2:00** — CrewAI crew (research → synthesizer). SSE event bus. Frontend `InputPanel` + `RunDashboard` showing research stage.
4. **2:00–2:45** — Report PDF generator + AutoContent client (pick ONE AutoContent format first — slides — then add others). `ArtifactCard` download.
5. **2:45–3:30** — Chat endpoint + `ChatPanel` + IndexedDB persistence.
6. **3:30–4:00** — Polish UI (shadcn cards, loading states), end-to-end run, README.

## 5. Risk / Cuts

- If AutoContent integration slow → ship with podcast + slides only, defer video.
- If CrewAI setup painful → replace with straight `asyncio.gather` of tool calls. Same API surface.
- If SSE flaky → 2s polling of `GET /runs/{id}` fallback.
