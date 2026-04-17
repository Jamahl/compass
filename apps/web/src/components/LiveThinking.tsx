/**
 * LiveThinking — append-only stream of orchestrator + tool events.
 *
 * Polls GET /api/runs/{runId}/events?since=<lastSeenId> on a tight interval
 * while the run is active, slows down once it's terminal. Renders a virtualised-
 * free scrollable log with color-coded source badges, timestamps, message,
 * and an expand/collapse toggle for the optional `data` JSON blob.
 *
 * Designed for the waiting/dashboard view so the user can watch the agent
 * "think" — tool calls, status transitions, errors, timings, token usage.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { Brain, ChevronDown, ChevronRight, Pause, Play } from 'lucide-react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { listEvents, type RunEvent } from '@/api/client'

interface LiveThinkingProps {
  runId: string
  /** When true the run is finished — slow polling and stop after one final fetch. */
  isTerminal: boolean
}

const SOURCE_BADGE: Record<string, string> = {
  runner: 'bg-purple-100 text-purple-700',
  parallel: 'bg-indigo-100 text-indigo-700',
  llm: 'bg-emerald-100 text-emerald-700',
  writer: 'bg-amber-100 text-amber-700',
  autocontent: 'bg-rose-100 text-rose-700',
}

const LEVEL_TEXT: Record<string, string> = {
  debug: 'text-gray-500',
  info: 'text-gray-800',
  warn: 'text-amber-700',
  error: 'text-red-700',
}

function sourceBadgeClass(source: string): string {
  return SOURCE_BADGE[source] ?? 'bg-gray-100 text-gray-700'
}

function formatTime(iso: string): string {
  // HH:MM:SS in the viewer's locale — easier to scan than full ISO.
  try {
    const d = new Date(iso)
    return d.toLocaleTimeString([], {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return iso
  }
}

function EventRow({ event }: { event: RunEvent }) {
  const [open, setOpen] = useState(false)
  const hasData = event.data && Object.keys(event.data).length > 0
  return (
    <li className="border-b border-gray-100 px-3 py-2 last:border-b-0">
      <div className="flex items-start gap-2 text-xs">
        <span className="font-mono text-gray-400 tabular-nums">
          {formatTime(event.ts)}
        </span>
        <span
          className={cn(
            'inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide',
            sourceBadgeClass(event.source),
          )}
        >
          {event.source}
        </span>
        <span className="font-mono text-[10px] text-gray-400">
          {event.type}
        </span>
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          className={cn(
            'flex flex-1 items-start gap-1 text-left',
            LEVEL_TEXT[event.level] ?? 'text-gray-800',
            !hasData && 'cursor-default',
          )}
          disabled={!hasData}
        >
          {hasData ? (
            open ? (
              <ChevronDown className="mt-0.5 h-3 w-3 flex-shrink-0" />
            ) : (
              <ChevronRight className="mt-0.5 h-3 w-3 flex-shrink-0" />
            )
          ) : (
            <span className="w-3" />
          )}
          <span className="break-words">{event.message}</span>
        </button>
      </div>
      {open && hasData && (
        <pre className="mt-1 ml-12 max-h-64 overflow-auto rounded bg-gray-900 p-2 text-[11px] text-gray-100">
          {JSON.stringify(event.data, null, 2)}
        </pre>
      )}
    </li>
  )
}

export function LiveThinking({ runId, isTerminal }: LiveThinkingProps) {
  const [events, setEvents] = useState<RunEvent[]>([])
  const [autoScroll, setAutoScroll] = useState(true)
  const [paused, setPaused] = useState(false)
  const sinceRef = useRef(0)
  const lastRunIdRef = useRef<string | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  // Polling loop — fast (1s) while running, slow (5s) while terminal,
  // stop entirely a few seconds after terminal once we've drained.
  useEffect(() => {
    // Reset the cursor + buffer synchronously when the run changes, BEFORE
    // the first tick fires. A separate useEffect would race with this one.
    if (lastRunIdRef.current !== runId) {
      sinceRef.current = 0
      setEvents([])
      lastRunIdRef.current = runId
    }

    let cancelled = false
    let timer: ReturnType<typeof setTimeout> | null = null
    let terminalDrains = 0

    const tick = async (): Promise<void> => {
      if (cancelled) return
      if (paused) {
        timer = setTimeout(tick, 1000)
        return
      }
      try {
        const next = await listEvents(runId, sinceRef.current, 1000)
        if (cancelled) return
        if (next.length > 0) {
          sinceRef.current = next[next.length - 1].id
          setEvents((prev) => [...prev, ...next])
        }
        if (isTerminal) {
          terminalDrains += 1
          // Two empty drains after terminal → stop polling.
          if (next.length === 0 && terminalDrains >= 2) return
        }
      } catch (err) {
        console.error('LiveThinking fetch failed', err)
      }
      const interval = isTerminal ? 5000 : 1000
      timer = setTimeout(tick, interval)
    }

    void tick()

    return () => {
      cancelled = true
      if (timer !== null) clearTimeout(timer)
    }
  }, [runId, isTerminal, paused])

  // Auto-scroll to bottom on new events when autoScroll is on.
  useEffect(() => {
    if (!autoScroll) return
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [events, autoScroll])

  // If the user scrolls up away from bottom, suspend auto-scroll until
  // they return to the bottom.
  const onScroll = (): void => {
    const el = scrollRef.current
    if (!el) return
    const atBottom =
      el.scrollHeight - el.scrollTop - el.clientHeight < 24
    setAutoScroll(atBottom)
  }

  const counts = useMemo(() => {
    let errors = 0
    let warns = 0
    for (const e of events) {
      if (e.level === 'error') errors += 1
      else if (e.level === 'warn') warns += 1
    }
    return { errors, warns }
  }, [events])

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 py-3">
        <CardTitle className="flex items-center gap-2 text-sm font-medium">
          <Brain className="h-4 w-4 text-purple-600" />
          Live thinking
          <span className="text-xs font-normal text-muted-foreground">
            {events.length} event{events.length === 1 ? '' : 's'}
            {counts.errors > 0 && (
              <span className="ml-2 text-red-600">{counts.errors} error{counts.errors === 1 ? '' : 's'}</span>
            )}
            {counts.warns > 0 && (
              <span className="ml-2 text-amber-600">{counts.warns} warning{counts.warns === 1 ? '' : 's'}</span>
            )}
          </span>
        </CardTitle>
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 px-2"
            onClick={() => setPaused((p) => !p)}
            title={paused ? 'Resume polling' : 'Pause polling'}
          >
            {paused ? (
              <Play className="h-3.5 w-3.5" />
            ) : (
              <Pause className="h-3.5 w-3.5" />
            )}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="px-0 pb-0">
        <div
          ref={scrollRef}
          onScroll={onScroll}
          className="max-h-96 overflow-y-auto border-t border-gray-100"
        >
          {events.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-muted-foreground">
              {isTerminal
                ? 'No events were recorded for this run.'
                : 'Waiting for the agent to start…'}
            </div>
          ) : (
            <ul>
              {events.map((e) => (
                <EventRow key={e.id} event={e} />
              ))}
            </ul>
          )}
        </div>
        {!autoScroll && events.length > 0 && (
          <button
            type="button"
            onClick={() => {
              setAutoScroll(true)
              const el = scrollRef.current
              if (el) el.scrollTop = el.scrollHeight
            }}
            className="w-full border-t border-gray-100 py-1.5 text-xs text-blue-600 hover:bg-blue-50"
          >
            Jump to latest ↓
          </button>
        )}
      </CardContent>
    </Card>
  )
}

export default LiveThinking
