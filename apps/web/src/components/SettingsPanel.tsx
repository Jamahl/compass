import { useEffect, useMemo, useState } from 'react'
import { RotateCcw, Save } from 'lucide-react'
import { Textarea } from '@/components/ui/textarea'
import {
  getPrompts,
  savePrompts,
  resetPrompts,
  type PromptsConfig,
  type PromptsEnvelope,
} from '@/api/client'
import { cn } from '@/lib/utils'

const REPORT_LABELS: Record<string, { label: string; description: string }> = {
  report_1pg: { label: 'One-page Report', description: 'Short executive brief (150–250 words).' },
  report_5pg: { label: 'In-depth Report', description: 'Structured 5-page report (600–900 words).' },
  competitor_doc: { label: 'Competitor Analysis', description: 'Landscape doc with a comparison table.' },
}

const MEDIA_LABELS: Record<string, string> = {
  podcast: 'Podcast',
  video: 'Video',
  slides: 'Slides (narrated)',
  infographic: 'Infographic',
  briefing_doc: 'Briefing Doc',
  text: 'Plain Text',
  faq: 'FAQ',
  study_guide: 'Study Guide',
  timeline: 'Timeline',
  quiz: 'Quiz',
  datatable: 'Data Table',
}

function isDirty(a: PromptsConfig, b: PromptsConfig): boolean {
  return JSON.stringify(a) !== JSON.stringify(b)
}

export function SettingsPanel() {
  const [envelope, setEnvelope] = useState<PromptsEnvelope | null>(null)
  const [draft, setDraft] = useState<PromptsConfig | null>(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [savedAt, setSavedAt] = useState<number | null>(null)

  const load = async () => {
    try {
      const env = await getPrompts()
      setEnvelope(env)
      setDraft(structuredClone(env.config))
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load prompts.')
    }
  }

  useEffect(() => { void load() }, [])

  const dirty = useMemo(
    () => (envelope && draft ? isDirty(envelope.config, draft) : false),
    [envelope, draft],
  )

  const handleSave = async () => {
    if (!draft) return
    setSaving(true)
    setError(null)
    try {
      const env = await savePrompts(draft)
      setEnvelope(env)
      setDraft(structuredClone(env.config))
      setSavedAt(Date.now())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Save failed.')
    } finally {
      setSaving(false)
    }
  }

  const handleDiscard = () => {
    if (!envelope) return
    setSavedAt(null)
    setDraft(structuredClone(envelope.config))
  }

  const handleResetAll = async () => {
    if (!confirm('Reset every prompt to its shipped default? Unsaved edits will also be lost.')) return
    setSaving(true)
    try {
      const env = await resetPrompts()
      setEnvelope(env)
      setDraft(structuredClone(env.config))
      setSavedAt(Date.now())
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reset failed.')
    } finally {
      setSaving(false)
    }
  }

  if (!envelope || !draft) {
    return (
      <div className="mx-auto max-w-3xl p-8 text-sm text-on-surface-variant">
        {error ? <span className="text-destructive">{error}</span> : 'Loading prompt settings…'}
      </div>
    )
  }

  const defaults = envelope.defaults

  const resetSynthesize = () => { setSavedAt(null); setDraft({ ...draft, synthesize: defaults.synthesize }) }
  const resetChat = () => { setSavedAt(null); setDraft({ ...draft, chat: defaults.chat }) }
  const resetReport = (key: string) => { setSavedAt(null); setDraft({ ...draft, reports: { ...draft.reports, [key]: defaults.reports[key] ?? '' } }) }
  const resetMedia = (key: string) => { setSavedAt(null); setDraft({ ...draft, media_guidance: { ...draft.media_guidance, [key]: defaults.media_guidance[key] ?? '' } }) }

  return (
    <div className="mx-auto max-w-3xl space-y-8 pb-24">
      {/* Sticky save bar */}
      <div className="sticky top-0 z-10 -mx-6 flex items-center justify-between border-b border-outline-variant/20 bg-background/80 px-6 py-3 backdrop-blur-xl">
        <div>
          <h1 className="text-lg font-bold text-on-surface leading-tight">
            Prompt Settings
            {dirty && <span className="ml-2 inline-block size-1.5 rounded-full bg-amber-500 align-middle" aria-label="unsaved" />}
          </h1>
          <p className="text-xs text-on-surface-variant">
            Edit the system prompts that shape every research output.
            {savedAt && !dirty && <span className="ml-2 text-green-600">Saved.</span>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={handleDiscard}
            disabled={!dirty || saving}
            className="px-3 py-1.5 rounded-full text-xs font-semibold text-on-surface-variant hover:bg-surface-container-high disabled:opacity-40 transition-all"
          >
            Discard
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={!dirty || saving}
            className="flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-bold bg-primary text-white shadow-sm disabled:opacity-40 hover:bg-primary/90 transition-all"
          >
            <Save className="size-3" />
            {saving ? 'Saving…' : 'Save changes'}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-xl border border-destructive/30 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Brief synthesis */}
      <SettingsCard
        title="Brief Synthesis"
        description="Turns raw research into the brief that feeds every downstream output — PDF reports and every media job."
        onReset={resetSynthesize}
        resetDisabled={draft.synthesize === defaults.synthesize}
      >
        <Textarea
          value={draft.synthesize}
          onChange={(e) => setDraft({ ...draft, synthesize: e.target.value })}
          className="min-h-56 font-mono text-xs leading-relaxed bg-surface-container-lowest border-outline-variant/20 focus-visible:ring-primary/20"
          spellCheck={false}
        />
        <div className="mt-1 text-right text-[10px] text-on-surface-variant">{draft.synthesize.length.toLocaleString()} chars</div>
      </SettingsCard>

      {/* Chat */}
      <SettingsCard
        title="Chat"
        description={<>System prompt for post-research chat. Use <code className="rounded bg-surface-container-high px-1 py-0.5 text-[11px]">{'{context}'}</code> to mark where the brief is injected.</>}
        onReset={resetChat}
        resetDisabled={draft.chat === defaults.chat}
      >
        <Textarea
          value={draft.chat}
          onChange={(e) => setDraft({ ...draft, chat: e.target.value })}
          className="min-h-40 font-mono text-xs leading-relaxed bg-surface-container-lowest border-outline-variant/20 focus-visible:ring-primary/20"
          spellCheck={false}
        />
        <div className="mt-1 flex items-center justify-between text-[10px] text-on-surface-variant">
          <span>
            {draft.chat.includes('{context}')
              ? <span className="text-green-600">✓ {'{context}'} placeholder present</span>
              : <span className="text-amber-600">No {'{context}'} — brief will be appended</span>}
          </span>
          <span>{draft.chat.length.toLocaleString()} chars</span>
        </div>
      </SettingsCard>

      {/* Report writers */}
      <SettingsCard title="Report Writers" description="System prompts for each PDF report type.">
        <div className="space-y-3">
          {Object.keys(defaults.reports).map((key) => {
            const meta = REPORT_LABELS[key] ?? { label: key, description: '' }
            const val = draft.reports[key] ?? ''
            return (
              <details key={key} className="group rounded-xl border border-outline-variant/20 bg-surface-container-lowest open:bg-white">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-4 py-3 text-sm">
                  <div>
                    <span className="font-semibold text-on-surface">{meta.label}</span>
                    <p className="text-[11px] text-on-surface-variant">{meta.description}</p>
                  </div>
                  <span className="text-xs text-on-surface-variant group-open:hidden">expand</span>
                  <span className="hidden text-xs text-on-surface-variant group-open:inline">collapse</span>
                </summary>
                <div className="space-y-2 border-t border-outline-variant/20 p-3">
                  <Textarea
                    value={val}
                    onChange={(e) => setDraft({ ...draft, reports: { ...draft.reports, [key]: e.target.value } })}
                    className="min-h-40 font-mono text-xs leading-relaxed"
                    spellCheck={false}
                  />
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-on-surface-variant">{val.length.toLocaleString()} chars</span>
                    <ResetButton onClick={() => resetReport(key)} disabled={val === defaults.reports[key]} />
                  </div>
                </div>
              </details>
            )
          })}
        </div>
      </SettingsCard>

      {/* Media guidance */}
      <SettingsCard title="Media Output Guidance" description="Short instructions appended to each AutoContent job.">
        <div className="grid gap-3 sm:grid-cols-2">
          {Object.keys(defaults.media_guidance).map((key) => {
            const label = MEDIA_LABELS[key] ?? key
            const val = draft.media_guidance[key] ?? ''
            return (
              <div key={key} className="flex flex-col gap-1.5 rounded-xl border border-outline-variant/20 p-3 bg-surface-container-lowest">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-on-surface">{label}</span>
                  <ResetButton onClick={() => resetMedia(key)} disabled={val === defaults.media_guidance[key]} />
                </div>
                <Textarea
                  value={val}
                  onChange={(e) => setDraft({ ...draft, media_guidance: { ...draft.media_guidance, [key]: e.target.value } })}
                  className="min-h-20 text-xs leading-relaxed"
                  spellCheck={false}
                />
              </div>
            )
          })}
        </div>
      </SettingsCard>

      {/* Reset everything */}
      <div className="flex justify-end pt-2">
        <button
          type="button"
          onClick={handleResetAll}
          disabled={saving}
          className="flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold text-white bg-destructive hover:bg-destructive/90 disabled:opacity-40 transition-all"
        >
          <RotateCcw className="size-3.5" />
          Reset everything to defaults
        </button>
      </div>
    </div>
  )
}

function SettingsCard({
  title,
  description,
  children,
  onReset,
  resetDisabled,
}: {
  title: string
  description: React.ReactNode
  children: React.ReactNode
  onReset?: () => void
  resetDisabled?: boolean
}) {
  return (
    <div className="rounded-2xl border border-outline-variant/20 bg-white/60 backdrop-blur-sm p-6 space-y-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-bold text-on-surface">{title}</h2>
          <p className="mt-0.5 text-xs text-on-surface-variant">{description}</p>
        </div>
        {onReset && <ResetButton onClick={onReset} disabled={resetDisabled ?? false} />}
      </div>
      {children}
    </div>
  )
}

function ResetButton({ onClick, disabled }: { onClick: () => void; disabled: boolean }) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title="Reset to default"
      className={cn(
        'flex items-center gap-1 px-2 py-1 rounded-full text-[10px] font-semibold transition-all',
        disabled
          ? 'text-on-surface-variant/40 cursor-not-allowed'
          : 'text-on-surface-variant hover:bg-surface-container-high'
      )}
    >
      <RotateCcw className="size-2.5" />
      Reset
    </button>
  )
}

export default SettingsPanel
