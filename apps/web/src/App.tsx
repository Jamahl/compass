import { useState } from 'react'
import GradientBackground from '@/components/GradientBackground'
import InputPanel from '@/components/InputPanel'
import OutputSelector from '@/components/OutputSelector'
import RunDashboard from '@/components/RunDashboard'
import ChatPanel from '@/components/ChatPanel'
import RunSidebar from '@/components/RunSidebar'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { postRun } from '@/api/client'
import type { RunRequest } from '@/api/client'
import type { OutputType } from '@/lib/formats'
import { useStore } from '@/state/store'

function App() {
  const { currentRunId, runState, setCurrentRun, setRunState, reset } =
    useStore()
  const [selectedOutputs, setSelectedOutputs] = useState<Set<OutputType>>(
    new Set(['report_1pg']),
  )
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (req: RunRequest) => {
    setSubmitting(true)
    try {
      const { run_id } = await postRun({
        ...req,
        context_files: req.context_files ?? [],
      })
      setCurrentRun(run_id)
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to start run', e)
      alert('Failed to start run — check backend logs.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSelectRun = (runId: string | null) => {
    if (runId === null) {
      reset()
      return
    }
    setCurrentRun(runId)
    setRunState(null)
  }

  const researchReady =
    !!runState &&
    (runState.status === 'research_done' || runState.status === 'completed')

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <GradientBackground />
      <RunSidebar
        currentRunId={currentRunId}
        onSelect={handleSelectRun}
      />

      <main className="flex min-h-screen flex-1 gap-8 px-8 py-8 overflow-hidden">
        {!currentRunId ? (
          <div className="flex h-full w-full gap-8 items-start">
            {/* Left: search + options */}
            <div className="flex-1 min-w-0">
              <InputPanel
                selectedOutputs={Array.from(selectedOutputs)}
                onSubmit={handleSubmit}
                disabled={submitting}
              />
            </div>
            {/* Right: output blueprints */}
            <div className="w-[340px] shrink-0">
              <OutputSelector
                selected={selectedOutputs}
                onChange={setSelectedOutputs}
              />
            </div>
          </div>
        ) : (
          <div className="flex h-full w-full gap-8 items-start">
            <div className="flex-1 min-w-0">
              <Card className="bg-surface-container-lowest">
                <CardHeader>
                  <CardTitle>Current Run</CardTitle>
                </CardHeader>
                <CardContent className="space-y-1 text-sm">
                  <div>
                    <span className="text-muted-foreground">Run ID:</span>{' '}
                    <code className="text-xs">{currentRunId}</code>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Status:</span>{' '}
                    {runState?.status ?? 'loading…'}
                  </div>
                  <div>
                    <span className="text-muted-foreground">Outputs:</span>{' '}
                    {runState?.artifacts.map((a) => a.type).join(', ') || '—'}
                  </div>
                </CardContent>
              </Card>
            </div>
            <div className="w-[420px] shrink-0 space-y-6">
              <RunDashboard runId={currentRunId} />
              <ChatPanel runId={currentRunId} researchReady={researchReady} />
            </div>
          </div>
        )}
      </main>
    </div>
  )
}

export default App
