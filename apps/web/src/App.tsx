import { useState } from 'react'
import InputPanel from '@/components/InputPanel'
import OutputSelector from '@/components/OutputSelector'
import RunDashboard from '@/components/RunDashboard'
import ChatPanel from '@/components/ChatPanel'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { postRun } from '@/api/client'
import type { RunRequest } from '@/api/client'
import type { OutputType } from '@/lib/formats'
import { useStore } from '@/state/store'

function App() {
  const { currentRunId, runState, setCurrentRun, reset } = useStore()
  const [selectedOutputs, setSelectedOutputs] = useState<Set<OutputType>>(
    new Set(['report_1pg']),
  )
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (req: RunRequest) => {
    setSubmitting(true)
    try {
      const { run_id } = await postRun(req)
      setCurrentRun(run_id)
    } catch (e) {
      // eslint-disable-next-line no-console
      console.error('Failed to start run', e)
      alert('Failed to start run — check backend logs.')
    } finally {
      setSubmitting(false)
    }
  }

  const researchReady =
    !!runState &&
    (runState.status === 'research_done' || runState.status === 'completed')

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold">BetterLabs Research Studio</h1>
          {currentRunId && (
            <Button variant="outline" size="sm" onClick={reset}>
              New Run
            </Button>
          )}
        </div>
      </header>

      <main className="max-w-7xl mx-auto p-6 grid gap-6 lg:grid-cols-2">
        {/* LEFT column */}
        <div className="space-y-6">
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
        <div className="space-y-6">
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
                <p>
                  1. Pick one or more output formats on the left.
                </p>
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
