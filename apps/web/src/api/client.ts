/**
 * API client — mirrors pydantic models from apps/api/src/models.py.
 * See project_overview.md section 4 for canonical contract.
 */

import type { Depth, OutputType, Template } from '@/lib/formats'

export type { Depth, OutputType, Template }

export type Status = 'pending' | 'running' | 'done' | 'error'
export type RunStatus = 'pending' | 'research_done' | 'completed' | 'failed'

export interface Stage {
  name: string
  status: Status
  error: string | null
}

export interface ArtifactMeta {
  id: string
  type: OutputType
  status: Status
  filename: string
  error: string | null
}

export interface RunState {
  run_id: string
  status: RunStatus
  stages: Stage[]
  artifacts: ArtifactMeta[]
  research_payload: string | null
}

export interface RunRequest {
  prompt: string
  urls: string[]
  template: Template
  depth: Depth
  outputs: OutputType[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

async function ensureOk(res: Response): Promise<void> {
  if (!res.ok) {
    const text = await res.text()
    throw new Error(
      `Request failed: ${res.status} ${res.statusText} — ${text}`,
    )
  }
}

export async function postRun(
  body: RunRequest,
): Promise<{ run_id: string }> {
  const res = await fetch('/api/runs', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  await ensureOk(res)
  return (await res.json()) as { run_id: string }
}

export async function getRun(runId: string): Promise<RunState> {
  const res = await fetch(`/api/runs/${runId}`)
  await ensureOk(res)
  return (await res.json()) as RunState
}

export async function postChat(
  runId: string,
  message: string,
  history: ChatMessage[],
): Promise<{ reply: string }> {
  const res = await fetch(`/api/runs/${runId}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, history }),
  })
  await ensureOk(res)
  return (await res.json()) as { reply: string }
}

export function downloadArtifact(artifactId: string): void {
  // ?download=1 tells the server to send Content-Disposition: attachment
  // so the browser always saves rather than rendering inline.
  const a = document.createElement('a')
  a.href = `/api/artifacts/${artifactId}?download=1`
  a.setAttribute('download', '')
  a.style.display = 'none'
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}
