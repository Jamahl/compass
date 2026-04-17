import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import compassLogo from '@/assets/compass.png'
import { cn } from '@/lib/utils'
import { listRuns, type RunSummary, type RunStatus } from '@/api/client'
import { OUTPUT_FORMAT_BY_ID } from '@/lib/formats'

interface RunSidebarProps {
  currentRunId: string | null
  onSelect: (runId: string | null) => void
}

const STATUS_DOT: Record<RunStatus, string> = {
  pending: 'bg-gray-400',
  research_done: 'bg-amber-400',
  completed: 'bg-green-500',
  failed: 'bg-red-500',
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s
  return s.slice(0, n - 1).trimEnd() + '…'
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  if (Number.isNaN(then)) return ''
  const now = Date.now()
  const diffSec = Math.floor((now - then) / 1000)

  if (diffSec < 30) return 'just now'
  if (diffSec < 60) return `${diffSec} sec ago`

  const diffMin = Math.floor(diffSec / 60)
  if (diffMin < 60) return `${diffMin} min ago`

  const diffHr = Math.floor(diffMin / 60)
  if (diffHr < 24) return `${diffHr} hr ago`

  const diffDay = Math.floor(diffHr / 24)
  if (diffDay === 1) return 'yesterday'
  if (diffDay < 7) return `${diffDay} days ago`

  const diffWk = Math.floor(diffDay / 7)
  if (diffWk < 5) return `${diffWk} wk ago`

  const diffMo = Math.floor(diffDay / 30)
  if (diffMo < 12) return `${diffMo} mo ago`

  const diffYr = Math.floor(diffDay / 365)
  return `${diffYr} yr ago`
}

export function RunSidebar({ currentRunId, onSelect }: RunSidebarProps) {
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    const fetchRuns = async () => {
      try {
        const list = await listRuns()
        if (cancelled) return
        setRuns(list)
        setError(null)
      } catch (e) {
        if (cancelled) return
        setError(e instanceof Error ? e.message : 'Failed to load runs')
      }
    }

    void fetchRuns()
    const interval = window.setInterval(() => {
      void fetchRuns()
    }, 5000)

    return () => {
      cancelled = true
      window.clearInterval(interval)
    }
  }, [])

  return (
    <aside className="flex h-screen w-[260px] shrink-0 flex-col bg-white/60 backdrop-blur-xl border-r border-white/40">
      <div className="px-4 py-5 space-y-3">
        <div className="flex items-center gap-2">
          <img src={compassLogo} alt="Compass" className="w-7 h-7 object-contain" />
          <span className="text-base font-extrabold tracking-tight text-on-surface">Compass</span>
        </div>
        <button
          type="button"
          onClick={() => onSelect(null)}
          className="w-full bg-gradient-to-r from-[#003fb5] to-[#2563eb] text-white rounded-full px-4 py-2 text-sm font-bold shadow-lg shadow-blue-500/20 hover:opacity-90 active:scale-95 transition-all flex items-center justify-center gap-1.5"
        >
          <Plus className="size-3.5" />
          New Research
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-3 py-3">
        {error && (
          <div className="px-3 py-3 text-xs text-destructive">{error}</div>
        )}

        {!error && runs.length === 0 && (
          <div className="px-3 py-6 text-xs text-on-surface-variant text-center leading-relaxed">
            No runs yet. Start a new research on the right.
          </div>
        )}

        {!error && runs.length > 0 && (
          <div className="px-1 mb-2 text-[10px] font-extrabold uppercase tracking-widest text-on-surface-variant">Recent</div>
        )}

        <ul className="flex flex-col gap-1">
          {runs.map((run) => {
            const isActive = run.run_id === currentRunId
            const promptLine =
              run.prompt.trim().length === 0
                ? '(no prompt)'
                : truncate(run.prompt.trim(), 44)

            return (
              <li key={run.run_id}>
                <button
                  type="button"
                  onClick={() => onSelect(run.run_id)}
                  className={cn(
                    isActive
                      ? 'flex w-full flex-col gap-1 rounded-xl px-3 py-2.5 text-left transition-colors bg-surface-container-highest border border-primary/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
                      : 'flex w-full flex-col gap-1 rounded-xl px-3 py-2.5 text-left transition-colors hover:bg-surface-container border-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                  )}
                >
                  <div className="flex items-center gap-2">
                    <span
                      className={cn(
                        'size-1.5 shrink-0 rounded-full',
                        STATUS_DOT[run.status],
                      )}
                      style={{ width: '6px', height: '6px' }}
                      aria-label={run.status}
                    />
                    <span className="truncate text-sm font-medium leading-tight text-on-surface">
                      {promptLine}
                    </span>
                  </div>
                  <div className="text-[11px] text-on-surface-variant font-label">
                    {relativeTime(run.created_at)}
                  </div>
                  {run.outputs.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1 mt-0.5">
                      {run.outputs.map((outId) => {
                        const fmt = OUTPUT_FORMAT_BY_ID[outId]
                        if (!fmt) return null
                        const Icon = fmt.icon
                        return (
                          <Icon
                            key={outId}
                            className="size-3.5 text-muted-foreground"
                            aria-label={fmt.label}
                          />
                        )
                      })}
                    </div>
                  )}
                </button>
              </li>
            )
          })}
        </ul>
      </div>
    </aside>
  )
}

export default RunSidebar
