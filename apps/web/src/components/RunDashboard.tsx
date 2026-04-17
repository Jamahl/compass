import { useEffect } from 'react'
import { CheckCircle2, Loader2, AlertCircle, Circle } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { pollRun } from '@/api/polling'
import type { Stage } from '@/api/client'
import { useStore } from '@/state/store'
import { ArtifactCard } from './ArtifactCard'

interface RunDashboardProps {
  runId: string
}

type StageStatus = Stage['status']

const STATUS_BADGE: Record<StageStatus, string> = {
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  done: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
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
      <Card>
        <CardContent className="flex items-center gap-2 py-6">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm text-muted-foreground">Loading run…</span>
        </CardContent>
      </Card>
    )
  }

  const stageErrors = runState.stages.filter((s) => s.error)
  const isFailed = runState.status === 'failed'

  return (
    <div className="flex flex-col gap-3">
      {isFailed && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="py-4">
            <div className="flex items-start gap-2 text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div>
                <div className="font-medium">Run failed</div>
                <div className="text-sm opacity-90">
                  The run encountered a fatal error and did not complete.
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {stageErrors.map((stage) => (
        <Card
          key={`err-${stage.name}`}
          className="border-red-200 bg-red-50"
        >
          <CardContent className="py-4">
            <div className="flex items-start gap-2 text-red-700">
              <AlertCircle className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <div>
                <div className="font-medium">
                  {stageDisplayName(stage.name)} error
                </div>
                <div className="text-sm opacity-90">
                  {stage.error ?? 'Unknown error'}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      ))}

      <div className="flex flex-col gap-2">
        {runState.stages.map((stage) => (
          <Card key={stage.name}>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 py-3">
              <CardTitle className="text-sm font-medium">
                {stageDisplayName(stage.name)}
              </CardTitle>
              <StatusBadge status={stage.status} />
            </CardHeader>
          </Card>
        ))}
      </div>

      {runState.artifacts.length > 0 && (
        <div className="flex flex-col gap-2">
          {runState.artifacts.map((artifact) => (
            <ArtifactCard key={artifact.id} artifact={artifact} />
          ))}
        </div>
      )}
    </div>
  )
}

export default RunDashboard
