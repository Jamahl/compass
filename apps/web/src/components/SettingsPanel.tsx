import { useEffect, useMemo, useState } from 'react'
import { RotateCcw, Save } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  getPrompts,
  savePrompts,
  resetPrompts,
  type PromptsConfig,
  type PromptsEnvelope,
} from '@/api/client'

// Friendly labels for sections that ship with cryptic keys (report_1pg, etc).
const REPORT_LABELS: Record<string, { label: string; description: string }> = {
  report_1pg: {
    label: 'One-page Report',
    description: 'Short executive brief (150–250 words).',
  },
  report_5pg: {
    label: 'In-depth Report',
    description: 'Structured 5-page report (600–900 words).',
  },
  competitor_doc: {
    label: 'Competitor Analysis',
    description: 'Landscape doc with a comparison table.',
  },
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

  useEffect(() => {
    void load()
  }, [])

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
    if (
      !confirm(
        'Reset every prompt to its shipped default? Unsaved edits will also be lost.',
      )
    ) {
      return
    }
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
      <div className="mx-auto max-w-3xl p-8 text-sm text-muted-foreground">
        {error ? (
          <span className="text-destructive">{error}</span>
        ) : (
          'Loading prompt settings…'
        )}
      </div>
    )
  }

  const defaults = envelope.defaults

  // ---- per-field reset handlers -------------------------------------------

  // Local resets are draft-only (no server call) — clear the "Saved." flag
  // so the user isn't misled by a stale success indicator after editing.
  const resetSynthesize = () => {
    setSavedAt(null)
    setDraft({ ...draft, synthesize: defaults.synthesize })
  }

  const resetChat = () => {
    setSavedAt(null)
    setDraft({ ...draft, chat: defaults.chat })
  }

  const resetReport = (key: string) => {
    setSavedAt(null)
    setDraft({
      ...draft,
      reports: { ...draft.reports, [key]: defaults.reports[key] ?? '' },
    })
  }

  const resetMedia = (key: string) => {
    setSavedAt(null)
    setDraft({
      ...draft,
      media_guidance: {
        ...draft.media_guidance,
        [key]: defaults.media_guidance[key] ?? '',
      },
    })
  }

  // ---- render --------------------------------------------------------------

  return (
    <div className="mx-auto max-w-3xl space-y-8 pb-24">
      {/* Sticky save bar */}
      <div className="sticky top-0 z-10 -mx-6 flex items-center justify-between border-b bg-background/90 px-6 py-3 backdrop-blur">
        <div>
          <h1 className="text-lg font-semibold leading-tight">
            Prompt Settings
            {dirty && (
              <span
                className="ml-2 inline-block size-1.5 rounded-full bg-amber-500 align-middle"
                aria-label="unsaved"
              />
            )}
          </h1>
          <p className="text-xs text-muted-foreground">
            Edit the system prompts that shape every research output.
            {savedAt && !dirty && (
              <span className="ml-2 text-green-600">Saved.</span>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={handleDiscard}
            disabled={!dirty || saving}
          >
            Discard
          </Button>
          <Button
            type="button"
            size="sm"
            onClick={handleSave}
            disabled={!dirty || saving}
          >
            <Save className="size-3.5" />
            {saving ? 'Saving…' : 'Save changes'}
          </Button>
        </div>
      </div>

      {error && (
        <div className="rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      )}

      {/* 1. Brief synthesis */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>Brief Synthesis</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              Turns raw research into the brief that feeds every downstream
              output — PDF reports <em>and</em> every AutoContent media job.
            </p>
          </div>
          <ResetButton
            onClick={resetSynthesize}
            disabled={draft.synthesize === defaults.synthesize}
          />
        </CardHeader>
        <CardContent>
          <Textarea
            value={draft.synthesize}
            onChange={(e) =>
              setDraft({ ...draft, synthesize: e.target.value })
            }
            className="min-h-56 font-mono text-xs leading-relaxed"
            spellCheck={false}
          />
          <div className="mt-1 text-right text-[10px] text-muted-foreground">
            {draft.synthesize.length.toLocaleString()} chars
          </div>
        </CardContent>
      </Card>

      {/* 1b. Chat */}
      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-3">
          <div>
            <CardTitle>Chat</CardTitle>
            <p className="mt-1 text-xs text-muted-foreground">
              System prompt for the post-research chat. Use{' '}
              <code className="rounded bg-muted px-1 py-0.5 text-[11px]">
                {'{context}'}
              </code>{' '}
              to mark where the research brief is injected. If omitted, the
              brief is appended at the end.
            </p>
          </div>
          <ResetButton
            onClick={resetChat}
            disabled={draft.chat === defaults.chat}
          />
        </CardHeader>
        <CardContent>
          <Textarea
            value={draft.chat}
            onChange={(e) => setDraft({ ...draft, chat: e.target.value })}
            className="min-h-40 font-mono text-xs leading-relaxed"
            spellCheck={false}
          />
          <div className="mt-1 flex items-center justify-between text-[10px] text-muted-foreground">
            <span>
              {draft.chat.includes('{context}') ? (
                <span className="text-green-600">
                  ✓ {'{context}'} placeholder present
                </span>
              ) : (
                <span className="text-amber-600">
                  No {'{context}'} placeholder — brief will be appended
                </span>
              )}
            </span>
            <span>{draft.chat.length.toLocaleString()} chars</span>
          </div>
        </CardContent>
      </Card>

      {/* 2. Report writers */}
      <Card>
        <CardHeader>
          <CardTitle>Report Writers</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            System prompts for each PDF report type. Only used when that
            report is selected on a run.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          {Object.keys(defaults.reports).map((key) => {
            const meta = REPORT_LABELS[key] ?? {
              label: key,
              description: '',
            }
            const val = draft.reports[key] ?? ''
            return (
              <details
                key={key}
                className="group rounded-lg border bg-muted/30 open:bg-background"
              >
                <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-sm">
                  <div className="flex flex-col">
                    <span className="font-medium">{meta.label}</span>
                    <span className="text-[11px] text-muted-foreground">
                      {meta.description}
                    </span>
                  </div>
                  <span className="text-xs text-muted-foreground group-open:hidden">
                    expand
                  </span>
                  <span className="hidden text-xs text-muted-foreground group-open:inline">
                    collapse
                  </span>
                </summary>
                <div className="space-y-2 border-t p-3">
                  <Textarea
                    value={val}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        reports: {
                          ...draft.reports,
                          [key]: e.target.value,
                        },
                      })
                    }
                    className="min-h-40 font-mono text-xs leading-relaxed"
                    spellCheck={false}
                  />
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] text-muted-foreground">
                      {val.length.toLocaleString()} chars
                    </span>
                    <ResetButton
                      onClick={() => resetReport(key)}
                      disabled={val === defaults.reports[key]}
                    />
                  </div>
                </div>
              </details>
            )
          })}
        </CardContent>
      </Card>

      {/* 3. Media guidance */}
      <Card>
        <CardHeader>
          <CardTitle>Media Output Guidance</CardTitle>
          <p className="mt-1 text-xs text-muted-foreground">
            Short instructions appended to each AutoContent job. Keep terse —
            AutoContent treats this as a user-level nudge, not a full prompt.
          </p>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.keys(defaults.media_guidance).map((key) => {
              const label = MEDIA_LABELS[key] ?? key
              const val = draft.media_guidance[key] ?? ''
              return (
                <div
                  key={key}
                  className="flex flex-col gap-1.5 rounded-lg border p-2.5"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-medium">{label}</span>
                    <ResetButton
                      onClick={() => resetMedia(key)}
                      disabled={val === defaults.media_guidance[key]}
                    />
                  </div>
                  <Textarea
                    value={val}
                    onChange={(e) =>
                      setDraft({
                        ...draft,
                        media_guidance: {
                          ...draft.media_guidance,
                          [key]: e.target.value,
                        },
                      })
                    }
                    className="min-h-20 text-xs leading-relaxed"
                    spellCheck={false}
                  />
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>

      {/* Reset everything */}
      <div className="flex justify-end pt-2">
        <Button
          type="button"
          variant="destructive"
          size="sm"
          onClick={handleResetAll}
          disabled={saving}
        >
          <RotateCcw className="size-3.5" />
          Reset everything to defaults
        </Button>
      </div>
    </div>
  )
}

function ResetButton({
  onClick,
  disabled,
}: {
  onClick: () => void
  disabled: boolean
}) {
  return (
    <Button
      type="button"
      variant="ghost"
      size="xs"
      onClick={onClick}
      disabled={disabled}
      title="Reset to default"
    >
      <RotateCcw className="size-3" />
      Reset
    </Button>
  )
}

export default SettingsPanel
