import { useEffect, useRef, useState, type KeyboardEvent } from 'react'
import { Loader2, Send } from 'lucide-react'
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
    <div className="relative flex flex-col bg-surface-container-lowest rounded-xl overflow-hidden" style={{minHeight: '320px'}}>
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4 min-h-[240px]"
      >
        <div className="flex flex-col gap-2">
          {messages.length === 0 && researchReady && (
            <div className="text-center text-xs text-on-surface-variant">
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
                  m.role === 'user'
                    ? 'max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm bg-gradient-brand text-white shadow-sm'
                    : 'max-w-[80%] whitespace-pre-wrap rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm bg-surface-container-high text-on-surface',
                )}
              >
                {m.content}
              </div>
            </div>
          ))}
          {sending && (
            <div className="flex w-full justify-start">
              <div className="flex items-center gap-2 rounded-2xl rounded-tl-sm bg-surface-container-high px-4 py-2.5 text-sm text-on-surface-variant">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span>Thinking…</span>
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="flex items-center gap-2 border-t border-outline-variant/30 bg-surface-container-low px-4 py-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={
            researchReady
              ? 'Ask about the research…'
              : 'Waiting for research…'
          }
          disabled={!researchReady || sending}
          className="flex-1 bg-transparent border-none text-sm placeholder:text-on-surface-variant/60 focus:outline-none text-on-surface"
        />
        <button
          onClick={() => void handleSend()}
          disabled={!canSend}
          className={cn(
            'flex items-center justify-center w-8 h-8 rounded-full transition-all',
            canSend ? 'bg-gradient-brand text-white shadow-sm hover:opacity-90' : 'bg-surface-container-high text-on-surface-variant cursor-not-allowed'
          )}
        >
          {sending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
        </button>
      </div>

      {!researchReady && (
        <div className="absolute inset-0 flex items-center justify-center bg-surface-container-lowest/80 backdrop-blur-sm">
          <div className="rounded-full border border-outline-variant/30 bg-white px-5 py-2 text-sm font-medium text-on-surface-variant shadow-sm">
            Complete research to unlock chat
          </div>
        </div>
      )}
    </div>
  )
}

export default ChatPanel
