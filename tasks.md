# BetterLabs Research Studio — Build Tasks

Each task is atomic. Complete one, commit, move to next. Do not skip ahead.

**MVP-first choices baked in:**
- Polling, not SSE (simpler, endorsed by PRD as fallback).
- Plain `asyncio.gather` for writer fan-out. CrewAI deferred to stretch task.
- No `react-query`. Plain `fetch` + `useState`.
- Single IndexedDB table (`messages`). Run history not persisted — backend owns it.

---

## PHASE 1 — Monorepo Scaffold

### T01 — Create root folder structure
**Start:** Empty `Hackathon/` directory.
**End:** Folders `apps/web/`, `apps/api/` exist. No files yet.
**Action:** `mkdir -p apps/web apps/api`

---

### T02 — Create root `package.json`
**Start:** No `package.json`.
**End:** Root `package.json` with `dev` script that runs both apps.
**Content:**
```json
{
  "name": "betterlabs-research-studio",
  "private": true,
  "workspaces": ["apps/web"],
  "scripts": {
    "dev": "concurrently \"pnpm --filter web dev\" \"cd apps/api && .venv/bin/uvicorn main:app --reload --port 8000\""
  },
  "devDependencies": {
    "concurrently": "^8.2.2"
  }
}
```

---

### T03 — Create root `.env.example`
**Start:** No `.env.example`.
**End:** File with three placeholder keys.
**Content:**
```
OPENAI_API_KEY=sk-...
PARALLEL_API_KEY=...
AUTOCONTENT_API_KEY=...
```

---

### T04 — Create root `.gitignore`
**Start:** No `.gitignore`.
**End:** Covers `node_modules`, `.env`, `__pycache__`, `.venv`, `dist`, `/tmp`.

---

## PHASE 2 — Vite + React Frontend Scaffold

### T05 — Scaffold Vite React app in `apps/web`
**Start:** `apps/web/` empty.
**End:** Vite + React + TypeScript project initialised. `pnpm dev` boots on port 5173.
**Action:** `cd apps/web && pnpm create vite@latest . -- --template react-ts`

---

### T06 — Install frontend dependencies
**Start:** Only Vite defaults installed.
**End:** Added: `zustand`, `dexie`, `clsx`, `lucide-react`.
**Action:** `pnpm add zustand dexie clsx lucide-react`

---

### T07 — Install and init shadcn/ui
**Start:** No shadcn.
**End:** `components.json` present. Tailwind + shadcn base installed.
**Action:** `pnpm dlx shadcn@latest init` (TypeScript, CSS vars, `src/components/ui`).

---

### T08 — Add shadcn components
**Start:** shadcn init done, no components.
**End:** Installed: `button`, `card`, `input`, `textarea`, `select`, `slider`.
**Action:** `pnpm dlx shadcn@latest add button card input textarea select slider`

---

### T09 — Configure Vite proxy to backend
**Start:** `vite.config.ts` has no proxy.
**End:** `/api/*` proxied to `http://localhost:8000`.
**Edit `vite.config.ts`:**
```ts
server: {
  proxy: {
    '/api': { target: 'http://localhost:8000', rewrite: path => path.replace(/^\/api/, '') }
  }
}
```

---

### T10 — Clear default Vite boilerplate
**Start:** Default Vite content.
**End:** `App.tsx` renders `<div>BetterLabs Research Studio</div>`. `App.css` deleted. `index.css` keeps only Tailwind directives.

---

## PHASE 3 — FastAPI Backend Scaffold

### T11 — Create `apps/api/pyproject.toml`
**Start:** `apps/api/` empty.
**End:** `pyproject.toml` with Python `>=3.11` and deps: `fastapi`, `uvicorn[standard]`, `python-dotenv`, `pydantic`, `openai`, `httpx`, `weasyprint`.
**Note:** CrewAI NOT installed yet — added only in stretch task if time permits.

---

### T12 — Create venv and install deps
**Start:** No venv.
**End:** `.venv/` created, deps installed.
**Action:** `cd apps/api && uv venv && uv pip install -e .`

---

### T13 — Create `apps/api/main.py` — bare FastAPI app
**Start:** No `main.py`.
**End:** FastAPI app with CORS middleware (`allow_origins=["*"]`), `GET /healthz` returning `{"ok": true}`. `uvicorn main:app --reload --port 8000` starts cleanly.

---

### T14 — Create `apps/api/src/` folder structure
**Start:** No `src/`.
**End:** Empty `__init__.py` files in: `src/`, `src/routes/`, `src/tools/`, `src/store/`.

---

### T15 — Create `src/config.py`
**Start:** No config module.
**End:** Loads `.env` via `python-dotenv`. Exposes `OPENAI_API_KEY`, `PARALLEL_API_KEY`, `AUTOCONTENT_API_KEY`. Raises `ValueError` if any missing.

---

### T16 — Create `src/models.py`
**Start:** No models.
**End:** Pydantic models:
- `RunRequest`: `prompt`, `urls: list[str]`, `template: str`, `depth: str`, `outputs: list[str]`
- `Stage`: `name: str`, `status: str`, `error: str | None`
- `ArtifactMeta`: `id: str`, `type: str`, `status: str`, `filename: str`, `error: str | None`
- `RunState`: `run_id`, `status`, `stages: list[Stage]`, `artifacts: list[ArtifactMeta]`, `research_payload: str | None`

---

### T17 — Create `src/store/runs.py`
**Start:** No store.
**End:** Module with `runs: dict[str, RunState] = {}`. Functions: `create_run(run_id, request)`, `get_run(run_id)`, `update_run(run_id, **kwargs)`, `update_stage(run_id, stage_name, status, error=None)`, `upsert_artifact(run_id, artifact)`. In-memory only.

---

### T18 — Create `src/store/artifacts_dir.py`
**Start:** No helper.
**End:** `get_artifact_path(run_id, artifact_id, ext) -> Path` creates `/tmp/betterlabs-artifacts/{run_id}/` if needed, returns full path. `artifacts_base() -> Path`.

---

## PHASE 4 — Core Tools (Parallel + OpenAI)

### T19 — Create `src/tools/parallel.py` — Task API client
**Start:** No Parallel client.
**End:** Async `run_research(prompt, urls, template, depth) -> dict`:
1. Map `depth` → processor tier (`quick`→`base`, `standard`→`core`, `deep`→`pro`, `exhaustive`→`ultra`).
2. POST to Parallel Task API.
3. Poll every 5s until `completed` or `failed`.
4. Return parsed result.
Uses `httpx.AsyncClient`. `# TODO: confirm Parallel API endpoint URLs when keys provided` comment + placeholder URLs.

---

### T20 — Create `src/tools/llm.py` — OpenAI wrappers
**Start:** No LLM tool.
**End:** Two async functions:
- `synthesize(research_payload: dict) -> str` — calls OpenAI `gpt-4o` with research + system prompt "distil into exec summary + findings + sources", returns brief markdown.
- `write_report(brief: str, report_type: str) -> str` — calls OpenAI with length/style per `report_type` (`report_1pg`, `report_5pg`, `competitor_doc`), returns report markdown.

---

## PHASE 5 — Runs Route + Runner

### T21 — Create `src/routes/runs.py`
**Start:** No runs route.
**End:**
- `POST /runs`: accept `RunRequest`, generate `run_id = uuid4()`, store `RunState(status="pending", stages=[], artifacts=[])`, start `asyncio.create_task(runner.start(run_id, request))`, return `{run_id}`.
- `GET /runs/{run_id}`: return full `RunState` (so polling client sees `stages` + `artifacts` with statuses) or 404.

---

### T22 — Create `src/orchestrator/runner.py` — minimal happy path
**Start:** No runner.
**End:** `async def start(run_id, request)`:
1. `update_stage(run_id, "research", "running")`.
2. `try`: `payload = await parallel.run_research(...)`; store in `RunState.research_payload`; `update_stage(..., "done")`.
3. `except`: `update_stage(..., "error", str(e))`; set run status `failed`; return.
4. Set run status `research_done` (so chat can unlock).
5. (Writer fan-out added in T28.)

---

### T23 — Create `src/orchestrator/__init__.py`
**Start:** Folder doesn't exist.
**End:** `apps/api/src/orchestrator/__init__.py` empty file.

---

### T24 — Register runs router in `main.py`
**Start:** Runs router not mounted.
**End:** `main.py` includes runs router. Routes live at `/runs` and `/runs/{id}`.

---

### T25 — Smoke test: POST /runs + poll GET /runs/{id}
**Start:** Backend running, OPENAI/PARALLEL keys set.
**End:** `curl -X POST http://localhost:8000/runs -d '{...}'` returns `run_id`. `curl http://localhost:8000/runs/{id}` repeated shows stage transition `research: running → done` and `research_payload` populated. No uvicorn errors.

---

## PHASE 6 — Report PDF Tool

### T26 — Create `src/tools/reportgen.py`
**Start:** No PDF generator.
**End:** `generate_report_pdf(run_id, artifact_id, content_md, title) -> Path`:
1. Render markdown to HTML (use `markdown` lib or manual — keep simple).
2. Wrap in minimal HTML+inline CSS (readable body font, 1in margins).
3. `weasyprint.HTML(string=html).write_pdf(output_path)`.
4. Return saved path.

---

## PHASE 7 — AutoContent Tool

### T27 — Create `src/tools/autocontent.py`
**Start:** No AutoContent client.
**End:** Async `generate_autocontent(run_id, artifact_id, output_type, brief) -> Path`:
1. Map `output_type` → AutoContent endpoint (`podcast`→audio, `slides`→slides, `video`→video).
2. POST job, poll until done.
3. Download result to artifacts dir.
4. Return path.
`# TODO: confirm AutoContent API endpoint URLs when keys provided` + placeholders.

---

## PHASE 8 — Writer Fan-out + Runner Integration

### T28 — Create `src/orchestrator/writer.py`
**Start:** No writer module.
**End:** `async generate_output(run_id, output_type, brief) -> ArtifactMeta`:
1. Generate `artifact_id = uuid4()`.
2. If output_type in `{report_1pg, report_5pg, competitor_doc}`: call `llm.write_report(brief, output_type)` → `reportgen.generate_report_pdf(...)`.
3. Else (`podcast`, `slides`, `video`): call `autocontent.generate_autocontent(...)`.
4. On success: return `ArtifactMeta(id, type=output_type, status="ready", filename=path.name)`.
5. On error: return `ArtifactMeta(..., status="error", error=str(e))`.

---

### T29 — Extend `runner.py` with synthesis + writer fan-out
**Start:** Runner stops after research (T22).
**End:** After research success:
1. `update_stage(run_id, "synthesize", "running")` → `brief = await llm.synthesize(payload)` → `"done"`.
2. For each `output_type` in request: seed `ArtifactMeta(status="pending")` into `RunState.artifacts`.
3. `asyncio.gather(*[generate_output(...) for output_type in outputs])` — update each artifact in store as it resolves.
4. Set run status `completed` when all done (even if some artifacts errored).

---

## PHASE 9 — Artifacts Route

### T30 — Create `src/routes/artifacts.py`
**Start:** No download route.
**End:** `GET /artifacts/{artifact_id}` globs `/tmp/betterlabs-artifacts/**/{artifact_id}.*`, returns `FileResponse` with `Content-Disposition: attachment`. 404 if missing.

---

### T31 — Register artifacts router
**Start:** Not mounted.
**End:** `main.py` includes artifacts router with prefix `/artifacts`.

---

## PHASE 10 — Chat Route

### T32 — Create `src/routes/chat.py`
**Start:** No chat route.
**End:** `POST /runs/{run_id}/chat` body `{message, history}`:
1. Load `RunState.research_payload`. If missing → 400.
2. Build messages: `system = "Research context:\n\n{payload}"`, then history, then user message.
3. `openai.chat.completions.create(model="gpt-4o", messages=...)`.
4. Return `{reply: str}`.

---

### T33 — Register chat router
**Start:** Not mounted.
**End:** `main.py` includes chat router (routes at `/runs/{id}/chat`).

---

## PHASE 11 — Frontend: API + State

### T34 — Create `src/api/client.ts`
**Start:** No client.
**End:** Module exports:
- `postRun(body) -> Promise<{run_id}>`
- `getRun(runId) -> Promise<RunState>`
- `downloadArtifact(artifactId)` — triggers browser download via invisible `<a href download>` click.
- `postChat(runId, message, history) -> Promise<{reply}>`
All call `/api/...`. TS interfaces mirror backend models.

---

### T35 — Create `src/api/polling.ts`
**Start:** No polling helper.
**End:** `pollRun(runId, onUpdate: (s: RunState) => void, intervalMs = 2000) -> () => void`:
1. Immediately fetch once.
2. `setInterval` fetches + calls `onUpdate`.
3. Stops interval when `run.status` in `{completed, failed}`.
4. Returns cleanup function to clear interval.

---

### T36 — Create `src/db/dexie.ts`
**Start:** No DB.
**End:** Dexie DB `ResearchStudio` with single table `messages`: `++id, runId, role, content, ts`. Export `db`.

---

### T37 — Create `src/state/store.ts`
**Start:** No zustand.
**End:** Store with: `currentRunId: string | null`, `runState: RunState | null`, `setCurrentRun(id)`, `setRunState(state)`.

---

## PHASE 12 — Frontend: Components

### T38 — Create `src/lib/formats.ts`
**Start:** No metadata.
**End:**
- `OUTPUT_FORMATS` — 6 entries `{id, label, description, icon}`.
- `TEMPLATES` — 5 presets + custom `{id, label}`.
- `DEPTH_LEVELS` — 4 entries `{id, label, approxTime}`.

---

### T39 — Build `InputPanel.tsx` — prompt + URL fields
**Start:** No InputPanel.
**End:** Controlled `<Textarea>` for prompt (required). Controlled `<Textarea>` for URLs (one per line, optional). Values in parent via props.

---

### T40 — Add template `<Select>` to InputPanel
**Start:** Prompt + URLs only.
**End:** Template dropdown added. Options from `TEMPLATES`.

---

### T41 — Add depth `<Slider>` to InputPanel
**Start:** No depth control.
**End:** `<Slider min=0 max=3>`. Below slider: label + approxTime from `DEPTH_LEVELS[value]`.

---

### T42 — Build `OutputSelector.tsx`
**Start:** No OutputSelector.
**End:** Grid of 6 toggle cards (`OUTPUT_FORMATS`). Click toggles selection (stored as `Set<string>`). At least one must be selected. Selected IDs passed via callback.

---

### T43 — Add submit button + validation to InputPanel
**Start:** No submit.
**End:** "Run Research" `<Button>`. Disabled if prompt empty or no outputs selected. On click → `onSubmit({prompt, urls, template, depth, outputs})`.

---

### T44 — Wire submit in `App.tsx`
**Start:** No wiring.
**End:** `App.tsx` handles submit: calls `postRun`, stores `run_id` in zustand, switches UI to dashboard view.

---

### T45 — Build `RunDashboard.tsx` — polling + stage cards
**Start:** No dashboard.
**End:** On mount, starts `pollRun(runId, setRunState)`. Cleanup on unmount. Renders one `<Card>` per stage in `runState.stages` with name + status badge (pending / running / done / error).

---

### T46 — Build `ArtifactCard.tsx`
**Start:** No artifact card.
**End:** `<Card>` showing icon (from `OUTPUT_FORMATS`), label, status. If `status === "ready"`: "Download" button → `downloadArtifact(id)`. If `"pending"` or `"running"`: spinner. If `"error"`: red error text.

---

### T47 — Render artifact cards in RunDashboard
**Start:** Dashboard shows stages only.
**End:** Below stage cards, renders `<ArtifactCard>` for each item in `runState.artifacts`.

---

### T48 — Build `ChatPanel.tsx`
**Start:** No ChatPanel.
**End:**
- Scrollable message list (user right, assistant left).
- `<Input>` + send `<Button>` at bottom.
- Overlay "Waiting for research to complete…" shown until `runState.research_payload` truthy (or `status === "research_done"` / `"completed"`).
- Local component state only in this task — persistence in T49.

---

### T49 — Wire ChatPanel to `/chat` + IndexedDB
**Start:** Local state only.
**End:**
- On send: append user message → `postChat(runId, message, history)` → append reply.
- Both persisted to `db.messages`.
- On mount: load prior messages for `runId` from IndexedDB.

---

### T50 — Assemble layout in `App.tsx`
**Start:** Components built, not laid out.
**End:** Two-panel layout (CSS grid or flex):
- Left: `InputPanel` + `OutputSelector` before run. After run starts: compact "current run" summary card.
- Right: `RunDashboard` (top) + `ChatPanel` (bottom) when `currentRunId` exists.

---

## PHASE 13 — End-to-End Smoke Tests

### T51 — Happy path: prompt → 1-page report download
**Start:** All built.
**End:** User enters prompt, selects "1-page report", depth "Quick", clicks Run. Dashboard polls, stages progress, PDF downloads, opens correctly. Zero console errors.

---

### T52 — Happy path: podcast via AutoContent
**Start:** T51 passing.
**End:** User selects "Podcast", runs. MP3 downloads and plays. AutoContent polling confirmed working.

---

### T53 — Happy path: chat after research
**Start:** Research completed in a prior run.
**End:** Chat panel unlocks when research done. User sends question. Reply references research content. After page reload, prior messages rehydrate from IndexedDB.

---

## PHASE 14 — Polish

### T54 — Loading state + error state in RunDashboard
**Start:** No explicit loading/error UI.
**End:** Before first `runState` arrives: spinner. If `runState.status === "failed"` OR any stage has `error`: red error card with message shown at top.

---

### T55 — Verify `.env` loading path
**Start:** `config.py` loads `.env`.
**End:** Confirm FastAPI picks up root-level `.env` (one dir above `apps/api/`). If not, adjust `load_dotenv(Path(__file__).parents[2] / ".env")`. Document in README.

---

### T56 — Write `README.md`
**Start:** No README.
**End:** Under 60 lines: what it does, prereqs (Node 20, Python 3.11, pnpm, uv), setup (clone, `.env`, `pnpm i`, venv, `pnpm dev`), output types list.

---

## PHASE 15 — Stretch (only if time remains)

### T57 — (Optional) Wrap writer in CrewAI
**Start:** Plain `asyncio.gather` working.
**End:** Install `crewai`. Replace `runner.py` writer fan-out with 3-agent crew (researcher, synthesizer, writer). Same public behaviour — no frontend changes. Skip entirely if <30min remains.

---

## Completion Checklist

- [ ] T01 – T04  Monorepo scaffold
- [ ] T05 – T10  Frontend scaffold
- [ ] T11 – T18  Backend scaffold + models + store
- [ ] T19 – T20  Parallel + OpenAI tools
- [ ] T21 – T25  Runs route + minimal runner + smoke test
- [ ] T26        Report PDF tool
- [ ] T27        AutoContent tool
- [ ] T28 – T29  Writer fan-out + runner integration
- [ ] T30 – T31  Artifacts route
- [ ] T32 – T33  Chat route
- [ ] T34 – T37  Frontend API + state
- [ ] T38 – T50  Frontend components + layout
- [ ] T51 – T53  End-to-end smoke tests
- [ ] T54 – T56  Polish + README
- [ ] T57        (Stretch) CrewAI wrap
