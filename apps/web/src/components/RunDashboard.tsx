import { useEffect } from 'react'
import { CheckCircle2, Loader2, AlertCircle, Circle } from 'lucide-react'
import { cn } from '@/lib/utils'
import { pollRun } from '@/api/polling'
import type { Stage } from '@/api/client'
import { useStore } from '@/state/store'
import { ArtifactCard } from './ArtifactCard'
import { LiveThinking } from './LiveThinking'

interface RunDashboardProps {
  runId: string
}

type StageStatus = Stage['status']

const STATUS_BADGE: Record<StageStatus, string> = {
  pending: 'bg-surface-container-high text-on-surface-variant',
  running: 'bg-primary/10 text-primary',
  done: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-600',
}

function stageDisplayName(name: string): string {
  if (name === 'research') return 'Research'
  if (name === 'synthesize') return 'Synthesize'
  return name
}

function StatusBadge({ status }: { status: StageStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        STATUS_BADGE[status],
      )}
    >
      {status === 'pending' && <Circle className="h-3 w-3" />}
      {status === 'running' && <Loader2 className="h-3 w-3 animate-spin" />}
      {status === 'done' && <CheckCircle2 className="h-3 w-3" />}
      {status === 'error' && <AlertCircle className="h-3 w-3" />}
      <span className="capitalize">{status}</span>
    </span>
  )
}

export function RunDashboard({ runId }: RunDashboardProps) {
  const runState = useStore((s) => s.runState)
  const setRunState = useStore((s) => s.setRunState)

  useEffect(() => {
    const cleanup = pollRun(
      runId,
      (s) => {
        setRunState(s)
      },
      2000,
    )
    return cleanup
  }, [runId, setRunState])

  if (!runState) {
    return (
      <div className="flex items-center gap-2 py-8 px-4 bg-surface-container-lowest rounded-xl">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="text-sm text-on-surface-variant">Loading run…</span>
      </div>
    )
  }

  const stageErrors = runState.stages.filter((s) => s.error)
  const isFailed = runState.status === 'failed'

  return (
    <div className="flex flex-col gap-3">
      {isFailed && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4">
          <div className="flex items-start gap-2 text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <div className="font-semibold text-sm">Run failed</div>
              <div className="text-xs opacity-80 mt-0.5">The run encountered a fatal error and did not complete.</div>
            </div>
          </div>
        </div>
      )}

      {stageErrors.map((stage) => (
        <div
          key={`err-${stage.name}`}
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-4"
        >
          <div className="flex items-start gap-2 text-red-700">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <div className="font-semibold text-sm">
                {stageDisplayName(stage.name)} error
              </div>
              <div className="text-xs opacity-80 mt-0.5">
                {stage.error ?? 'Unknown error'}
              </div>
            </div>
          </div>
        </div>
      ))}

      <div className="flex flex-col gap-2">
        {runState.stages.map((stage) => (
          <div key={stage.name} className="flex items-center justify-between bg-surface-container-lowest rounded-xl px-4 py-3 border border-transparent">
            <span className="text-sm font-semibold text-on-surface">{stageDisplayName(stage.name)}</span>
            <StatusBadge status={stage.status} />
          </div>
        ))}
      </div>

      <LiveThinking
        runId={runId}
        isTerminal={
          runState.status === 'completed' || runState.status === 'failed'
        }
      />

      {runState.artifacts.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs font-extrabold uppercase tracking-widest text-primary px-1">Artifacts</p>
          <div className="flex flex-col gap-2">
            {runState.artifacts.map((artifact) => (
              <ArtifactCard key={artifact.id} artifact={artifact} />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default RunDashboard
