import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { Button } from '@/components/ui/button'
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
    <aside className="flex h-screen w-[260px] shrink-0 flex-col border-r bg-background">
      <div className="flex flex-col gap-3 border-b px-4 py-4">
        <div className="text-sm font-semibold">Research Studio</div>
        <Button
          type="button"
          size="sm"
          onClick={() => onSelect(null)}
          className="w-full"
        >
          <Plus className="size-3.5" />
          New Research
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-2">
        {error && (
          <div className="px-2 py-3 text-xs text-red-600">{error}</div>
        )}

        {!error && runs.length === 0 && (
          <div className="px-2 py-6 text-xs text-muted-foreground">
            No runs yet. Start a new research on the right.
          </div>
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
                    'flex w-full flex-col gap-1.5 rounded-lg border px-2.5 py-2 text-left transition-colors',
                    'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    isActive
                      ? 'border-primary bg-accent'
                      : 'border-transparent hover:bg-accent/60',
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
                    <span className="truncate text-sm font-medium leading-tight">
                      {promptLine}
                    </span>
                  </div>
                  <div className="text-[11px] text-muted-foreground">
                    {relativeTime(run.created_at)}
                  </div>
                  {run.outputs.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1">
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
