/**
 * Run state polling utility.
 * See project_overview.md section 5 + tasks.md T35.
 */

import { getRun, type RunState } from './client'

export function pollRun(
  runId: string,
  onUpdate: (state: RunState) => void,
  intervalMs = 2000,
): () => void {
  let intervalId: ReturnType<typeof setInterval> | null = null
  let stopped = false

  const clear = (): void => {
    if (intervalId !== null) {
      clearInterval(intervalId)
      intervalId = null
    }
  }

  const tick = async (): Promise<void> => {
    if (stopped) return
    try {
      const state = await getRun(runId)
      if (stopped) return
      onUpdate(state)
      if (state.status === 'completed' || state.status === 'failed') {
        stopped = true
        clear()
      }
    } catch (err) {
      console.error('pollRun fetch failed', err)
    }
  }

  // Fire immediately, then on interval.
  void tick()
  intervalId = setInterval(() => {
    void tick()
  }, intervalMs)

  return () => {
    stopped = true
    clear()
  }
}
