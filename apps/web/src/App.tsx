import { useState } from 'react'
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
      <RunSidebar
        currentRunId={currentRunId}
        onSelect={handleSelectRun}
      />

      <main className="flex min-h-screen flex-1 gap-6 p-6">
        {/* MIDDLE column */}
        <div className="flex-1 space-y-6">
          {!currentRunId ? (
            <>
              <OutputSelector
                selected={selectedOutputs}
                onChange={setSelectedOutputs}
              />
              <InputPanel
                selectedOutputs={Array.from(selectedOutputs)}
                onSubmit={handleSubmit}
                disabled={submitting}
              />
            </>
          ) : (
            <Card>
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
          )}
        </div>

        {/* RIGHT column */}
        <div className="flex-1 space-y-6 lg:w-[420px] lg:max-w-[420px] lg:flex-none">
          {currentRunId ? (
            <>
              <RunDashboard runId={currentRunId} />
              <ChatPanel runId={currentRunId} researchReady={researchReady} />
            </>
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>How it works</CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-muted-foreground space-y-2">
                <p>1. Pick one or more output formats on the left.</p>
                <p>
                  2. Enter a research prompt, optional URLs, a template, and
                  depth.
                </p>
                <p>
                  3. Click <b>Run Research</b>. Stages stream on the right.
                </p>
                <p>
                  4. Download artifacts as they complete. Chat with the research
                  context once research is done.
                </p>
              </CardContent>
            </Card>
          )}
        </div>
      </main>
    </div>
  )
}

export default App
