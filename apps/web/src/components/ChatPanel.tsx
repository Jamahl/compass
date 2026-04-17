import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Loader2, Send } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { cn } from '@/lib/utils'
import { postChat, type ChatMessage } from '@/api/client'
import { db } from '@/db/dexie'

interface ChatPanelProps {
  runId: string
  researchReady: boolean
}

export function ChatPanel({ runId, researchReady }: ChatPanelProps) {
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
    <div className="relative flex h-full flex-col">
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4"
      >
        <div className="flex flex-col gap-2">
          {messages.length === 0 && researchReady && (
            <div className="text-center text-xs text-muted-foreground">
              Ask a question about the research.
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
                  'max-w-[80%] whitespace-pre-wrap rounded-lg px-3 py-2 text-sm',
                  m.role === 'user'
                    ? 'bg-primary text-primary-foreground'
                    : 'bg-muted',
                )}
              >
                {m.content}
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

      {!researchReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-background/70 backdrop-blur-sm">
          <div className="rounded-md border bg-card px-4 py-2 text-sm text-muted-foreground shadow-sm">
            Waiting for research to complete…
          </div>
        </div>
      )}
    </div>
  )
}

export default ChatPanel
