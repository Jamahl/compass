# Project Overview — BetterLabs Compass

Living doc. Updated as we build. Single source of truth for contracts, conventions, routes, data shapes. MVP-first — normalise now so adding features later is cheap.

---

## 1. What we're building

Single-user localhost web app. User submits research prompt → backend runs Parallel deep research → LLM synthesises brief → fan-out generates artifacts (reports, podcast, slides, video) → user downloads + chats with research context.

4-hour hackathon MVP. Not for production.

---

## 2. Stack (decided)

| Layer | Choice | Notes |
|---|---|---|
| Frontend | Vite + React + TS | shadcn/ui + Tailwind v4 + react-markdown |
| State (client) | zustand (UI) + Dexie/IndexedDB (chat persistence) | No react-query — plain `fetch` + `useState` |
| Backend | FastAPI (Python 3.11+) | **SQLite store** (persists runs), plain `sqlite3` stdlib |
| Python env | `python -m venv .venv` + `pip install -e .` | Not uv |
| Pkg mgr (web) | `npm` + workspaces | Not pnpm |
| Orchestration | `asyncio.gather` fan-out | CrewAI = stretch only |
| Transport | REST + **polling** (2s interval) | No SSE for MVP |
| PDF | `fpdf2` (markdown → HTML → PDF) | Pure Python, no pango/cairo |
| Persistence | SQLite (`apps/api/data/runs.db`) + file artifacts (`apps/api/data/artifacts/` or `ARTIFACTS_BASE` env) | Survives restarts |
| External | OpenAI (`gpt-5.4-nano`), Parallel Task API, AutoContent API, ElevenLabs TTS | 4 keys; ElevenLabs optional |
| Video mux (EL) | `imageio-ffmpeg` (bundled binary) + Pillow title-card | No system ffmpeg/libjpeg needed |
| Runtime | Localhost **or** Docker Compose | `docker compose up` runs api + web + named volume |

---

## 3. Monorepo layout

```
Hackathon/
├── package.json          # npm workspaces, dev script boots both
├── .env                  # keys (gitignored)
├── .env.example
├── .gitignore
├── PRD.md
├── tasks.md
├── project_overview.md   # <-- this file
│
├── apps/
│   ├── web/              # Vite + React + TS
│   │   └── src/
│   │       ├── api/      # client.ts, polling.ts
│   │       ├── db/       # dexie.ts (messages table)
│   │       ├── state/    # zustand store
│   │       ├── components/ (+ ui/ shadcn)
│   │       └── lib/      # formats.ts (OUTPUT_FORMATS, TEMPLATES, DEPTH_LEVELS)
│   │
│   └── api/              # FastAPI
│       ├── main.py
│       ├── pyproject.toml
│       └── src/
│           ├── config.py
│           ├── models.py
│           ├── routes/   (runs, artifacts, chat, contexts, prompts)
│           ├── tools/    (parallel, llm, reportgen, autocontent)
│           ├── orchestrator/ (runner, writer)
│           └── store/    (runs, events, artifacts_dir, contexts_dir, prompts)
```

Artifacts saved to `/tmp/betterlabs-artifacts/{run_id}/{artifact_id}.{ext}`.

---

## 4. Data model (canonical)

All models in `apps/api/src/models.py` (pydantic). Frontend mirrors via TS interfaces in `apps/web/src/api/client.ts`.

### 4.1 Enums (string literals — keep in sync web↔api)

```ts
type Template  = "market_sizing" | "competitor_scan" | "customer_pain" | "company_deep_dive" | "product_teardown" | "custom";
type Depth     = "quick" | "standard" | "deep" | "exhaustive";
// 14 output types, grouped for UI:
type OutputType =
  // Reports (OpenAI → fpdf2 PDF)
  | "report_1pg" | "report_5pg" | "competitor_doc"
  // AutoContent media
  | "podcast" | "slides" | "video" | "infographic"
  // AutoContent PDF
  | "briefing_doc"
  // AutoContent structured text (saved as .md)
  | "faq" | "study_guide" | "timeline" | "quiz" | "datatable" | "text"
  // ElevenLabs (independent pipeline, runs parallel to AutoContent)
  | "elevenlabs_audio" | "elevenlabs_video";
type Status    = "pending" | "running" | "done" | "error";           // stages + artifacts
type RunStatus = "pending" | "research_done" | "completed" | "failed";
```

### 4.1a Output type → generator / file / preview

| Output | Generator | File | Preview UI |
|---|---|---|---|
| report_1pg, report_5pg, competitor_doc | OpenAI `gpt-5.4-nano` → markdown → fpdf2 | PDF | iframe |
| briefing_doc | AutoContent `briefing_doc` | PDF | iframe |
| podcast | AutoContent `audio` | MP3 | `<audio controls>` |
| slides | AutoContent `slide_deck` | MP4 (narrated video) | `<video controls>` |
| video | AutoContent `video` | MP4 | `<video controls>` |
| infographic | AutoContent `infographic` | PNG | `<img>` |
| faq, study_guide, timeline, quiz, datatable, text | AutoContent (returns `response_text`) | MD | `react-markdown` + GFM |
| elevenlabs_audio | ElevenLabs TTS `/v1/text-to-speech/{voice_id}` | MP3 | `<audio controls>` |
| elevenlabs_video | ElevenLabs TTS + Pillow title-card + ffmpeg mux | MP4 | `<video controls>` |

### 4.2 Depth → Parallel processor tier

| Depth | Processor | Approx time |
|---|---|---|
| quick | base | ~30s |
| standard | core | ~2min |
| deep | pro | ~5min |
| exhaustive | ultra | ~10min+ |

### 4.3 Shapes

```
RunRequest {
  prompt: str,                    # required, non-empty
  urls: list[str],                # optional, may be []
  template: Template,
  depth: Depth,
  outputs: list[OutputType],      # required, >=1
}

Stage      { name: str, status: Status, error: str | None }
ArtifactMeta { id: str, type: OutputType, status: Status, filename: str, error: str | None }

RunState {
  run_id: str (uuid4),
  status: RunStatus,
  stages: list[Stage],            # appended in order: research → synthesize → (writer per output)
  artifacts: list[ArtifactMeta],
  research_payload: str | None,   # populated after research stage; gates chat
}

ChatRequest  { message: str, history: [{role: "user"|"assistant", content: str}] }
ChatResponse { reply: str }
```

---

## 5. API routes

Base: `http://localhost:8000` (Vite dev proxies `/api/*` → `:8000`).

| Method | Path | Purpose | Returns |
|---|---|---|---|
| GET | `/healthz` | liveness | `{"ok": true}` |
| POST | `/runs` | create + start run | `{"run_id": str}` |
| GET | `/runs` | list recent runs (newest first, summary) | `RunSummary[]` |
| GET | `/runs/{run_id}` | poll run state | `RunState` |
| GET | `/runs/{run_id}/events?since=N&limit=M` | incremental live-thinking event stream | `RunEvent[]` (id-ascending, `id > since`) |
| POST | `/runs/{run_id}/chat` | chat vs research | `ChatResponse` |
| GET | `/contexts` | list .md files in `Context/` with name + preview | `ContextFile[]` |
| GET | `/prompts` | fetch user-editable prompt config + shipped defaults | `{config: PromptsConfig, defaults: PromptsConfig}` |
| PUT | `/prompts` | replace full prompt config (422 if `synthesize`/`reports.*` empty) | same envelope |
| POST | `/prompts/reset` | reset everything, a section, or one key to defaults | same envelope |
| GET | `/artifacts/{artifact_id}` | preview / stream artifact | `FileResponse` (inline by default) |
| GET | `/artifacts/{artifact_id}?download=1` | force attachment download | `FileResponse` (attachment) |

**Inline vs download:** default Content-Disposition is `inline` so the browser can embed the file (PDF in iframe, media in native players, PNG in img). Pass `?download=1` to force `attachment` for the Save-As flow.

**No SSE.** Frontend polls `GET /runs/{id}` every 2s until `status ∈ {completed, failed}`. The `LiveThinking` component additionally polls `/runs/{id}/events?since=<lastSeenId>` every 1s while running (5s when terminal, stops after 2 empty drains) — pass the highest id seen so far as `since` for incremental fetch.

---

## 6. Run lifecycle (stage ordering)

```
POST /runs
  → RunState(status=pending, stages=[], artifacts=[])
  → asyncio.create_task(runner.start(run_id, req))

runner.start:
  1. stages += Stage("research", running)
     parallel.run_research(...)                   # Parallel Task API
     → research_payload stored
     stages["research"] = done
     status = research_done                       # ← chat unlocks here

  2. stages += Stage("synthesize", running)
     llm.synthesize(payload) → brief (markdown)
     brief written to {artifacts_base}/{run_id}/brief.md   # chat-context sidecar
     stages["synthesize"] = done

  3. for each output in req.outputs:
       artifacts += ArtifactMeta(status=pending)
     await asyncio.gather(
        writer.generate_output(run_id, type, brief) for each
     )
     each resolves → update ArtifactMeta in store
     report types (report_1pg | report_5pg | competitor_doc) also write a
     source-markdown sidecar at {run_id}/{artifact_id}.md pre-PDF render so
     the chat route can include report content as context.

  4. status = completed  (even if some artifacts errored)

On any exception → stage.error set, status = failed.
```

**Event log (parallel side-channel).** Every meaningful step in `runner`,
`writer`, `parallel`, `llm`, `autocontent` calls
`store.events.append_event(run_id, source, type, message, data=..., level=...)`.
Events go to a **separate** SQLite DB (`apps/api/data/events.db`) so verbose
narration never bloats `runs.db`. The append helper swallows all exceptions —
**telemetry must never break a run**. Sources: `runner | writer | parallel | llm | autocontent`.
Common types: `run.start | run.done | run.fatal | stage.start | stage.done |
stage.error | context.loaded | context.empty | context.none | tool.call |
tool.created | tool.status | tool.result | tool.error | tool.skipped |
tool.timeout | tool.download | tool.stale_queue | report.render |
writer.fanout | artifact.start | artifact.done | artifact.error |
artifact.skipped`.

**Stale-queue detector (AutoContent).** `tool.stale_queue` is emitted at
warn level when an AutoContent job sits at `status=0` (queued) for 3
minutes, and a second time at 10 minutes. Each threshold fires at most
once per job. AutoContent's shared queue sometimes holds a request for
10+ minutes before picking it up; the warning tells the user the delay
is upstream, not ours. The detector does not abort or retry — the 1800s
hard timeout in `autocontent._run` still governs.

---

## 7. Tool contracts (backend-internal)

All `async`. All throw on non-recoverable error; runner catches and marks stage error.

| Module | Function | Returns |
|---|---|---|
| `tools/parallel.py` | `run_research(prompt, urls, template, depth)` | `dict` (raw Parallel result) |
| `tools/llm.py` | `synthesize(research_payload: dict) -> str` | markdown brief |
| `tools/llm.py` | `write_report(brief: str, report_type: OutputType) -> str` | markdown report |
| `tools/reportgen.py` | `generate_report_pdf(run_id, artifact_id, content_md, title) -> Path` | PDF path |
| `tools/autocontent.py` | `generate_autocontent(run_id, artifact_id, output_type, brief) -> Path` | media file path |
| `tools/elevenlabs.py` | `generate_elevenlabs(run_id, artifact_id, output_type, brief) -> Path` | MP3 / MP4 path |
| `orchestrator/writer.py` | `generate_output(run_id, output_type, brief) -> ArtifactMeta` | final meta |
| `store/events.py` | `append_event(run_id, source, type, message, *, data=None, level="info")` | `None` (never raises) |
| `store/events.py` | `list_events(run_id, since=0, limit=1000) -> list[dict]` | events with `id > since`, ascending |
| `store/prompts.py` | `get_prompts() -> PromptsConfig` | merged (defaults ∪ overrides), mtime-cached |
| `store/prompts.py` | `save_prompts(cfg)` / `reset(section?, key?)` | atomic write via tmp + `os.replace` |

**Writer contract caveat:** `writer.generate_output` **never raises** — it
catches every exception internally and returns `ArtifactMeta(status="error",
error=...)`. Don't `try/except` around it expecting failures; check
`result.status == "error"` instead. The runner's `isinstance(result, Exception)`
branch only fires for unexpected `asyncio.gather` failures.

**Tool wrappers take optional `run_id`** for event emission:
- `parallel.run_research(..., *, run_id=None)`
- `llm.synthesize(payload, *, run_id=None)`
- `llm.write_report(brief, type, *, run_id=None)`
- `autocontent.generate_autocontent(run_id, ...)` (always takes `run_id`)

When omitted, the wrapper still works but emits no events.

---

## 8. Frontend conventions

- **Data fetching:** `fetch` + `useState`/`useEffect`. No react-query.
- **Polling:** `src/api/polling.ts` — `pollRun(runId, onUpdate, 2000)` returns cleanup fn. Stops on terminal status.
- **Live thinking:** `LiveThinking.tsx` polls `listEvents(runId, since)` from `src/api/client.ts`. Cursor (`sinceRef`) is reset **inside** the polling effect, guarded by `lastRunIdRef`, so the reset cannot race with the first tick when `runId` changes. Don't move the reset to a separate `useEffect` — both effects fire after commit and the polling tick will fire with the stale cursor.
- **Persistence:** IndexedDB via Dexie. Single table `messages` (`++id, runId, role, content, ts`). Run history NOT persisted — backend owns.
- **State:** zustand store holds `currentRunId` + latest `runState`.
- **Metadata:** `src/lib/formats.ts` = single source for OUTPUT_FORMATS (6), TEMPLATES (6 incl. custom), DEPTH_LEVELS (4).
- **Download:** invisible `<a href download>` click → `/api/artifacts/{id}`.

---

## 9. Environment + config

Root `.env` (gitignored):
```
OPENAI_API_KEY=...
PARALLEL_API_KEY=...
AUTOCONTENT_API_KEY=...
ELEVENLABS_API_KEY=...            # optional — enables elevenlabs_audio / _video outputs
ELEVENLABS_VOICE_ID=...           # optional — defaults to JBFqnCBsd6RMkjVDRZzb (George)
ELEVENLABS_MODEL_ID=...           # optional — defaults to eleven_turbo_v2_5
```

Loaded by `apps/api/src/config.py` via `python-dotenv`. Config resolves `.env` at `Path(__file__).parents[2] / ".env"` (root). Raises `ValueError` on missing key.

**Optional overrides:**
- `ARTIFACTS_BASE` — artifact root (default `apps/api/data/artifacts`).
- `CONTEXT_BASE` — `Context/` dir (default `<repo>/Context`).
- `PROMPTS_PATH` — user prompt overrides JSON (default `<apps/api>/Config/prompts.json`; Docker sets it to `/app/data/prompts.json` so edits survive rebuilds).

---

## 10. Running locally

### Option A — host-native

```bash
# one-time
npm install                              # root (installs concurrently + web workspace)
cd apps/api
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
cd ../..
cp .env.example .env                     # then paste keys

# dev
npm run dev                              # boots web :5173 + api :8000
```

### Option B — Docker Compose

```bash
cp .env.example .env   # paste keys
docker compose up --build
```

- API: http://localhost:8000
- Web: http://localhost:5173
- Named volume `api_data` holds SQLite + artifacts (persists across rebuilds).
- `./Context` mounted read-only into the api container so host edits surface instantly.

> ⚠️ **Source is baked into the image — there is NO bind-mount for `apps/api/src` or `apps/web/src`.**
> Code changes do **not** hot-reload in Docker. After ANY backend or frontend
> change, rebuild + recreate:
>
> ```bash
> docker compose up -d --build api web
> ```
>
> **Symptom you'll see if you forget:** new routes return `{"detail":"Not Found"}`
> (route doesn't exist) instead of the expected validation error. New frontend
> components simply don't appear. Always verify with a route-existence probe
> (e.g. `curl /runs/nope/events` should return `"run not found"`, not `"Not Found"`).
>
> Port 8000 / 5173 collisions also tell on this: if you have Docker running and
> separately try `npm run dev`, uvicorn silently fails to bind 8000 and the
> browser keeps hitting the **stale** Docker container.

Frontend: http://localhost:5173
Backend:  http://localhost:8000

---

## 11. Decisions log (short)

- **No SSE** — polling 2s is enough, simpler, no reconnect logic.
- **No react-query** — single-screen app, 1 polling loop.
- **No CrewAI for MVP** — plain `asyncio.gather`. Stretch task T57 wraps later if time.
- **SQLite run store** — persists across restarts. Single table `runs` (see `apps/api/src/store/runs.py`).
- **Single IndexedDB table (messages)** — chat persistence, per-browser.
- **Artifacts** live under `apps/api/data/artifacts/{run_id}/{artifact_id}.{ext}`. Override via `ARTIFACTS_BASE` env var (Docker sets this to `/app/data/artifacts`).
- **Pkg mgr: npm** (not pnpm). **Py env: venv+pip** (not uv).
- **Context folder** — any `.md` at `<repo>/Context/*.md` shows as a tickable tile in InputPanel; selected files are prepended to the research prompt as "INTERNAL CONTEXT". README.md is skipped.
- **Pro-only outputs** — runtime detection: backend catches AutoContent error messages containing "pro/subscription/upgrade/plan" tokens and raises `AutoContentProRequiredError` → artifact shows "Coming soon — requires AutoContent Pro plan" in amber. Static gating: `OutputFormat.pro = true` disables the tile in OutputSelector and shows a "Coming soon" pill.
- **Explainer Video is Amateur-eligible (50 credits/run).** We call `/content/Create` with `outputType: "video"` and inject `format: "explainer"` explicitly so the request is unambiguous. **Video Shorts** (vertical 9:16, 400 credits) is a separate endpoint at `POST /video/CreateShortsFromContent` that requires the Professional tier — we do not expose it. Earlier "mark video as Pro" was a pre-emptive tag without evidence; removed once confirmed against the pricing page.
- **Live thinking events in a separate DB** — `events.db` is intentionally split from `runs.db`. Verbose narration would bloat the run state model; `RunState` stays small and JSON-serialisable for polling, while events are append-only and queried by id-cursor. `append_event` swallows all exceptions so logging cannot break a run.
- **Tool-wrapper output sizes are tuned for fast demo runs.** Synthesize ≤250w; report_1pg ≤250w; report_5pg ≤900w; competitor_doc ≤500w / max 5 rows. AutoContent brief is capped at 2000 chars and per-output-type brevity guidance is appended to the `text` field (e.g. "podcast: 2-3 min", "video: <90s"). Audio jobs also get `duration: "short"`. Bump these only when an output looks too thin.
- **Tool timeouts symmetric at 1800s.** Both `parallel.run_research` and `autocontent.generate_autocontent` use a 1800s overall `asyncio.wait_for`. Was 600s/900s before — bumped because deep tier + slide/video can legitimately exceed 10 min.
- **Prompts are user-editable at runtime.** The synth prompt, three report writers, and 11 media-guidance strings live in `apps/api/src/store/prompts.py`. Defaults are the source of truth; overrides persist to a JSON file (path from `PROMPTS_PATH`, else `<repo>/Config/prompts.json` under apps/api). Reads are mtime-cached so runs pick up edits with no restart. `llm.synthesize`, `llm.write_report`, and `autocontent.generate_autocontent` all resolve their prompts from the store each call. Atomic writes via `tmp + os.replace`. Schema is forward-compat: missing keys fall back to defaults so adding a new output type later doesn't break old saved files.
- **ElevenLabs is a fully independent pipeline.** `tools/elevenlabs.py` handles `elevenlabs_audio` (TTS → MP3) and `elevenlabs_video` (TTS + Pillow title-card + ffmpeg mux → MP4). Dispatched from `writer.generate_output` via `_ELEVENLABS_TYPES`; does not share state with AutoContent and runs concurrently in the same `asyncio.gather` fan-out. ffmpeg binary ships with `imageio-ffmpeg` (no apt-get needed). Brief narration capped at 2500 chars with markdown stripped before TTS. Missing key raises `ElevenLabsKeyMissingError` → artifact errors gracefully with a "not set" message; other outputs in the run are unaffected. Video intermediates use `{artifact_id}__narration.mp3` / `{artifact_id}__card.png` names so the artifact route's `{id}.*` resolver never mis-serves them. Overall timeout: 600s.

---

## 12. Status

| Phase | Tasks | State |
|---|---|---|
| 1 Monorepo scaffold | T01–T04 | ✅ done |
| 2 Frontend scaffold | T05–T10 | ✅ done |
| 3 Backend scaffold | T11–T18 | ✅ done |
| 4 Tools (Parallel/OpenAI) | T19–T20 | ✅ done |
| 5 Runs route + runner | T21–T24 | ✅ done |
| 6 Report PDF | T26 | ✅ done (swapped weasyprint → fpdf2 for zero system-deps) |
| 7 AutoContent | T27 | ✅ done (placeholder endpoints — verify with live keys) |
| 8 Writer fan-out | T28–T29 | ✅ done |
| 9 Artifacts route | T30–T31 | ✅ done |
| 10 Chat route | T32–T33 | ✅ done |
| 11 FE API + state | T34–T37 | ✅ done |
| 12 FE components | T38–T50 | ✅ done (3-column: sidebar / input / dashboard+chat) |
| 13 E2E smoke | T25, T51–T53 | ✅ verified E2E: prompt → Parallel research → synth → PDF download; /contexts, /runs listing, SQLite persistence across restarts, Docker build all green |
| 14 Polish | T54–T56 | ✅ loading/error states in RunDashboard, .env path robust (host + container), README present |
| 15 Stretch (CrewAI) | T57 | ⏭ skipped — plain `asyncio.gather` is good enough for MVP |
| Post-MVP | — | ✅ context files, SQLite, sidebar, preview modal, Pro-only coming-soon, Docker compose |

### Post-MVP additions (beyond tasks.md)

- **InputPanel helper text** — helper paragraphs under Prompt, URLs, Template (with scope pill), Depth. Example query provided for Prompt.
- **Context files** — `/Context/*.md` folder, `GET /contexts` route, tickable tiles in InputPanel, content prepended to research prompt as "INTERNAL CONTEXT". Path-traversal protected. Ships with sample `willow.md` and `townsquare.md`.
- **Session persistence** — SQLite `runs.db` under `apps/api/data/`. New `GET /runs` list route. **Sidebar** (`RunSidebar.tsx`) shows all past runs with status dot, relative time, output icons; click to switch run; "+ New Research" button.
- **3-column layout** — sidebar | input or current-run summary | dashboard+chat.
- **Pro-only outputs** — graceful error detection (`AutoContentProRequiredError`) + amber "Coming soon — requires AutoContent Pro plan" in card; static `pro: true` flag on OutputFormat disables tile with "Coming soon" pill.
- **Docker Compose** — `Dockerfile` per service, `docker-compose.yml` with `api_data` volume + read-only Context mount. Web container proxies via `VITE_API_URL=http://api:8000`. **Source is baked, not bind-mounted — see Section 10 Option B for the rebuild rule.**
- **Live thinking event log** — `apps/api/src/store/events.py` (separate `events.db`), `GET /runs/{id}/events?since=N`, `LiveThinking.tsx` poll component on the dashboard. Surfaces tool calls, status transitions, OpenAI token usage, AutoContent poll status, errors, timing — color-coded by source, expandable JSON `data`, pause toggle, auto-scroll with manual override. Confirmed live: context files reach Parallel as INTERNAL CONTEXT block (event `runner/context.loaded` shows `prompt_chars` and file names).
- **Prompt settings page** — gear in `RunSidebar` swaps the main panel for `SettingsPanel.tsx`: editable textareas for the brief-synth prompt, the three report writers (collapsible), and the 11 media-guidance strings (2-col grid). Per-field Reset + global Reset-everything + Discard + dirty indicator. Backend: `apps/api/src/store/prompts.py` holds defaults + mtime-cached JSON store with atomic writes; `apps/api/src/routes/prompts.py` exposes `GET/PUT /prompts` and `POST /prompts/reset`. Runs pick up edits with no restart. `llm.synthesize`, `llm.write_report`, `autocontent.generate_autocontent` all read from the store each call.
- **Chat panel relocation + markdown rendering + enriched context** — `ChatPanel.tsx` moved from the right column into the middle column (under the "Current Run" card), wrapped in a `Card` with a header/badge showing `Research ready · N/M outputs` and fixed at `h-[640px]`. Assistant replies render through the prompt-kit `Markdown` component (installed via `npx shadcn add https://prompt-kit.com/c/markdown.json`, pulls `ui/markdown.tsx` + `ui/code-block.tsx`, uses the existing `react-markdown` + `remark-gfm` and adds `marked` + `remark-breaks` + `shiki` + `@tailwindcss/typography` via `@plugin` in `index.css`). Empty state shows a "Chat context loaded" card (Parallel payload + done artifact types + still-generating count) and three suggestion chips. Backend chat context now includes: the Parallel JSON payload (first 15k chars), the synthesized brief from `brief.md` (8k chars, when present), inlined text bodies from AutoContent text outputs and report `.md` sidecars (per-artifact 4k, total 24k), and an `ARTIFACTS PRODUCED` list summarising every artifact + status. Sidecar writes are best-effort (`OSError` caught, warn event appended); a failed sidecar never blocks the pipeline. `chat.py` rejects PDF/binary filenames by `suffix` check and falls back to `{artifact_id}.md` only when it exists.

### Known deviations from tasks.md

- **PDF lib:** `weasyprint` (tasks.md) → `fpdf2` (pure Python, no pango/cairo system deps). Slight loss of HTML fidelity; still tables + headings + lists.
- **shadcn pkg:** used `npx shadcn@latest` (tasks.md said `pnpm dlx`) since pkg mgr is npm.
- **Tailwind:** v4 via `@tailwindcss/vite` plugin + `@import "tailwindcss";` — not v3 postcss. shadcn init handled `tw-animate-css` + `shadcn/tailwind.css` imports automatically.
- **python-dotenv path:** `config.py` loads `.env` from repo root (3 dirs up) — confirmed working.
- **Parallel API (verified 2026-04-17):** header is `x-api-key` (not Bearer). POST `/v1/tasks/runs`, body `{input, processor, task_spec: {output_schema: {type: "text"}}}`. Poll `/v1/tasks/runs/{run_id}` then fetch `/v1/tasks/runs/{run_id}/result`. `urls` + `template` are folded into the prompt text since the basic output_schema doesn't expose them as separate fields.
- **AutoContent API (verified 2026-04-17):** header is `Authorization: Bearer`. POST `/content/Create`, body `{resources: [{type:"text", content}], outputType, text: title}`. Poll `/content/Status/{id}` — `status` is numeric: 0=queued, 10..80=in-progress, 100=done, <0=error. Completion fields: `audio_url`, `video_url`, `image_url`, `briefing_doc_url`, `response_text`, `document_content` depending on outputType.
- **14 output types (not 6 in tasks.md).** Text-based AutoContent outputs saved as `.md`; previewed via react-markdown+GFM.
- **Artifact preview:** every type has a modal viewer sized to `90vw × 90vh` — PDFs via `<iframe>`, media via native `<audio>`/`<video>`, images via `<img>`, markdown via `react-markdown` + GFM. `DialogContent` uses `flex flex-col` so the body's `flex-1` fills the remaining height beneath the header. Download button in both the card and the modal (uses `?download=1` to force attachment).
- **Slider defensive handling.** base-ui's Slider emits `onValueChange` with either a `number` or `number[]` depending on internal state. `InputPanel` normalises (`Array.isArray ? v[0] : v`), rounds, clamps to `[0, DEPTH_LEVELS.length-1]`, and falls back to `DEPTH_LEVELS[0]` when re-rendering, so a stray NaN/out-of-range value from a track click can never null out `currentDepth` and white-screen the page.

### Running

```bash
# start API (:8000)
cd apps/api && .venv/bin/uvicorn main:app --reload --port 8000

# start web (:5173) — proxies /api/* → :8000
npm --workspace web run dev
```

Both already running in this session.
