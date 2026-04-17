import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from 'react'
import { CheckCircle2, Loader2, MessageSquare, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Markdown } from '@/components/ui/markdown'
import { cn } from '@/lib/utils'
import { postChat, type ChatMessage } from '@/api/client'
import { db } from '@/db/dexie'
import { useStore } from '@/state/store'

interface ChatPanelProps {
  runId: string
  researchReady: boolean
}

const SUGGESTED_PROMPTS = [
  'Summarise the key findings in 5 bullets.',
  'What are the biggest risks or gaps in the research?',
  'Give me 3 recommended next steps based on the outputs.',
]

function outputLabel(type: string): string {
  return type.replace(/_/g, ' ')
}

export function ChatPanel({ runId, researchReady }: ChatPanelProps) {
  const runState = useStore((s) => s.runState)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      const rows = await db.messages
        .where('runId')
        .equals(runId)
        .sortBy('ts')
      if (cancelled) return
      const mapped: ChatMessage[] = rows
        .filter(
          (r): r is typeof r & { role: 'user' | 'assistant' } =>
            r.role === 'user' || r.role === 'assistant',
        )
        .map((r) => ({ role: r.role, content: r.content }))
      setMessages(mapped)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [runId])

  useEffect(() => {
    const el = scrollRef.current
    if (el) {
      el.scrollTop = el.scrollHeight
    }
  }, [messages])

  const canSend =
    researchReady && !sending && input.trim().length > 0

  const artifactSummary = useMemo(() => {
    const all = runState?.artifacts ?? []
    const done = all.filter((a) => a.status === 'done')
    const running = all.filter(
      (a) => a.status === 'running' || a.status === 'pending',
    )
    return {
      doneTypes: done.map((a) => a.type),
      doneCount: done.length,
      runningCount: running.length,
      total: all.length,
    }
  }, [runState])

  const handleSuggestion = (text: string) => {
    if (!researchReady || sending) return
    setInput(text)
  }

  const handleSend = async () => {
    const content = input.trim()
    if (!content || sending || !researchReady) return

    const userMsg: ChatMessage = { role: 'user', content }
    const history = messages.slice()

    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setSending(true)

    try {
      await db.messages.add({
        runId,
        role: 'user',
        content,
        ts: Date.now(),
      })

      const { reply } = await postChat(runId, content, history)
      const assistantMsg: ChatMessage = {
        role: 'assistant',
        content: reply,
      }

      setMessages((prev) => [...prev, assistantMsg])
      await db.messages.add({
        runId,
        role: 'assistant',
        content: reply,
        ts: Date.now(),
      })
    } catch (err) {
      const errText =
        err instanceof Error ? err.message : 'Chat request failed.'
      const errMsg: ChatMessage = {
        role: 'assistant',
        content: `Error: ${errText}`,
      }
      setMessages((prev) => [...prev, errMsg])
    } finally {
      setSending(false)
    }
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (canSend) {
        void handleSend()
      }
    }
  }

  return (
    <Card className="relative flex h-[640px] flex-col overflow-hidden py-0 gap-0">
      <CardHeader className="flex flex-row items-center gap-2 border-b px-4 py-3 space-y-0">
        <MessageSquare className="h-4 w-4 text-muted-foreground" />
        <CardTitle className="text-sm font-medium">
          Chat with research
        </CardTitle>
        <span
          className={cn(
            'ml-auto inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
            researchReady
              ? 'bg-green-100 text-green-700'
              : 'bg-gray-100 text-gray-700',
          )}
        >
          {researchReady ? (
            <>
              <CheckCircle2 className="h-3 w-3" />
              Research ready
              {artifactSummary.total > 0 && (
                <span className="opacity-75">
                  · {artifactSummary.doneCount}/{artifactSummary.total} outputs
                </span>
              )}
            </>
          ) : (
            <>
              <Loader2 className="h-3 w-3 animate-spin" />
              Waiting for research
            </>
          )}
        </span>
      </CardHeader>
      <CardContent className="flex min-h-0 flex-1 flex-col p-0">
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-4 py-3"
        >
          <div className="flex flex-col gap-3">
            {messages.length === 0 && researchReady && (
              <div className="flex flex-col gap-3 py-2">
                <div className="rounded-md border bg-muted/40 p-3 text-xs">
                  <div className="mb-1 font-medium text-foreground">
                    Chat context loaded
                  </div>
                  <ul className="space-y-0.5 text-muted-foreground">
                    <li>• Parallel deep-research payload</li>
                    {artifactSummary.doneCount > 0 && (
                      <li>
                        • {artifactSummary.doneCount} generated artifact
                        {artifactSummary.doneCount === 1 ? '' : 's'}:{' '}
                        <span className="text-foreground">
                          {artifactSummary.doneTypes
                            .map(outputLabel)
                            .join(', ')}
                        </span>
                      </li>
                    )}
                    {artifactSummary.runningCount > 0 && (
                      <li className="italic">
                        • {artifactSummary.runningCount} artifact
                        {artifactSummary.runningCount === 1 ? '' : 's'} still
                        generating — will be folded in automatically
                      </li>
                    )}
                  </ul>
                </div>
                <div className="flex flex-wrap gap-2">
                  {SUGGESTED_PROMPTS.map((p) => (
                    <button
                      key={p}
                      type="button"
                      onClick={() => handleSuggestion(p)}
                      disabled={sending}
                      className="rounded-full border bg-background px-3 py-1 text-xs text-muted-foreground hover:bg-muted hover:text-foreground disabled:opacity-50"
                    >
                      {p}
                    </button>
                  ))}
                </div>
              </div>
            )}
            {messages.map((m, i) => (
              <div
                key={i}
                className={cn(
                  'flex w-full',
                  m.role === 'user' ? 'justify-end' : 'justify-start',
                )}
              >
                <div
                  className={cn(
                    'max-w-[85%] rounded-lg px-3 py-2 text-sm',
                    m.role === 'user'
                      ? 'bg-primary text-primary-foreground whitespace-pre-wrap'
                      : 'bg-muted',
                  )}
                >
                  {m.role === 'assistant' ? (
                    <Markdown
                      id={`msg-${i}`}
                      className="prose prose-sm max-w-none dark:prose-invert prose-p:my-1 prose-headings:my-2 prose-ul:my-1 prose-ol:my-1 prose-li:my-0"
                    >
                      {m.content}
                    </Markdown>
                  ) : (
                    m.content
                  )}
                </div>
              </div>
            ))}
            {sending && (
              <div className="flex w-full justify-start">
                <div className="flex items-center gap-2 rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  <span>Thinking…</span>
                </div>
              </div>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2 border-t p-3">
          <Input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              researchReady
                ? 'Ask about the research…'
                : 'Waiting for research…'
            }
            disabled={!researchReady || sending}
          />
          <Button
            onClick={() => void handleSend()}
            disabled={!canSend}
            size="sm"
          >
            {sending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </Button>
        </div>
      </CardContent>

      {!researchReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/70 backdrop-blur-sm">
          <div className="rounded-md border bg-card px-4 py-2 text-sm text-muted-foreground shadow-sm">
            Waiting for research to complete…
          </div>
        </div>
      )}
    </Card>
  )
}

export default ChatPanel
