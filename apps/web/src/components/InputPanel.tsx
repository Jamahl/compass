import { useEffect, useState } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Slider } from '@/components/ui/slider'
import {
  DEPTH_LEVELS,
  TEMPLATES,
  type Depth,
  type OutputType,
  type Template,
} from '@/lib/formats'
import { getContexts, type ContextFile } from '@/api/client'
import { cn } from '@/lib/utils'

export interface InputPanelProps {
  selectedOutputs: OutputType[]
  onSubmit: (req: {
    prompt: string
    urls: string[]
    template: Template
    depth: Depth
    outputs: OutputType[]
    context_files: string[]
  }) => void
  disabled?: boolean
}

export function InputPanel({
  selectedOutputs,
  onSubmit,
  disabled = false,
}: InputPanelProps) {
  const [prompt, setPrompt] = useState<string>('')
  const [urlsText, setUrlsText] = useState<string>('')
  const [template, setTemplate] = useState<Template>('custom')
  const [depthIdx, setDepthIdx] = useState<number>(1)
  const [contexts, setContexts] = useState<ContextFile[]>([])
  const [selectedContexts, setSelectedContexts] = useState<Set<string>>(new Set())

  useEffect(() => {
    getContexts().then(setContexts).catch(console.error)
  }, [])

  const toggleContext = (filename: string) => {
    setSelectedContexts((prev) => {
      const next = new Set(prev)
      if (next.has(filename)) next.delete(filename)
      else next.add(filename)
      return next
    })
  }

  // Guard against base-ui's Slider ever emitting out-of-range / non-integer
  // values (e.g. when the user clicks the track). Falls back to index 0.
  const safeDepthIdx = Number.isInteger(depthIdx)
    ? Math.max(0, Math.min(DEPTH_LEVELS.length - 1, depthIdx))
    : 0
  const currentDepth = DEPTH_LEVELS[safeDepthIdx] ?? DEPTH_LEVELS[0]
  const selectedTemplate = TEMPLATES.find((t) => t.id === template)

  const promptTrimmedEmpty = prompt.trim().length === 0
  const submitDisabled =
    disabled || promptTrimmedEmpty || selectedOutputs.length === 0

  const handleSubmit = () => {
    if (submitDisabled) return
    const urls = urlsText
      .split('\n')
      .map((l) => l.trim())
      .filter(Boolean)
    onSubmit({
      prompt: prompt.trim(),
      urls,
      template,
      depth: currentDepth.id,
      outputs: selectedOutputs,
      context_files: Array.from(selectedContexts),
    })
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2 mb-2">
        <h1 className="text-4xl font-extrabold tracking-tight text-on-surface leading-[1.1]">
          What are we <span className="text-primary">researching</span> today?
        </h1>
      </div>

      <div className="flex flex-col gap-2">
        {/* Gradient border wrapper */}
        <div className="p-[2px] rounded-2xl bg-gradient-to-br from-primary via-[#6c9fff] to-[#a5b4fc] overflow-hidden">
          <div className="group relative flex items-start gap-3 bg-white rounded-[calc(1.35rem-2px)] px-5 py-5 transition-all duration-300 focus-within:shadow-xl focus-within:shadow-primary/10">
            <Textarea
              id="research-prompt"
              rows={5}
              required
              placeholder="Describe your research objective…"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={disabled}
              className="bg-transparent border-none focus:ring-0 w-full text-lg font-medium placeholder:text-on-surface-variant/40 text-on-surface resize-none focus-visible:ring-0 focus-visible:outline-none shadow-none p-0"
            />
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-2">
        <label htmlFor="research-urls" className="text-xs font-semibold text-on-surface-variant">
          URLs <span className="font-normal normal-case">(optional, one per line)</span>
        </label>
        <Textarea
          id="research-urls"
          rows={3}
          placeholder={'https://example.com\nhttps://another.com'}
          value={urlsText}
          onChange={(e) => setUrlsText(e.target.value)}
          disabled={disabled}
          className="bg-surface-container-high border-none rounded-xl px-4 py-3 text-sm placeholder:text-on-surface-variant/50 focus-visible:ring-1 focus-visible:ring-primary/20 focus-visible:bg-surface-container-lowest transition-all"
        />
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant">Context Files</label>
        {contexts.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {contexts.map((ctx) => {
              const isSelected = selectedContexts.has(ctx.filename)
              return (
                <button
                  key={ctx.filename}
                  type="button"
                  onClick={() => toggleContext(ctx.filename)}
                  disabled={disabled}
                  className={cn(
                    'rounded-full px-3 py-1.5 text-xs font-semibold transition-all',
                    isSelected
                      ? 'bg-primary text-white shadow-sm'
                      : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest',
                  )}
                >
                  {ctx.name}
                </button>
              )
            })}
          </div>
        )}
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant">Template</label>
        <div className="flex flex-wrap gap-2">
          {TEMPLATES.map((t) => (
            <button
              key={t.id}
              type="button"
              onClick={() => setTemplate(t.id as Template)}
              disabled={disabled}
              className={cn(
                'px-3 py-1.5 rounded-full text-xs font-semibold transition-all',
                template === t.id
                  ? 'bg-primary text-white shadow-sm'
                  : 'bg-surface-container-high text-on-surface-variant hover:bg-surface-container-highest'
              )}
            >
              {t.label}
            </button>
          ))}
        </div>
        {selectedTemplate ? (
          <div className="flex items-start gap-2 mt-1">
            <span className="text-[10px] uppercase font-semibold px-2 py-0.5 rounded-full bg-surface-container-high text-on-surface-variant shrink-0">
              {selectedTemplate.scope}
            </span>
            <p className="text-xs text-on-surface-variant">
              {selectedTemplate.description}
            </p>
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-2">
        <label className="text-xs font-semibold text-on-surface-variant">Depth</label>
        <Slider
          min={0}
          max={3}
          step={1}
          value={[safeDepthIdx]}
          onValueChange={(v) => {
            // base-ui emits either number or number[] depending on
            // internal state. Normalise + clamp + round defensively.
            const raw = Array.isArray(v) ? v[0] : (v as number)
            if (typeof raw !== 'number' || Number.isNaN(raw)) return
            const rounded = Math.round(raw)
            const clamped = Math.max(
              0,
              Math.min(DEPTH_LEVELS.length - 1, rounded),
            )
            setDepthIdx(clamped)
          }}
          disabled={disabled}
        />
        <div className="flex items-center justify-between text-xs">
          <span className="font-semibold text-on-surface">{currentDepth.label}</span>
          <span className="text-on-surface-variant">{currentDepth.approxTime}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={handleSubmit}
        disabled={submitDisabled}
        className={cn(
          'w-full py-3 rounded-full font-bold text-sm transition-all',
          submitDisabled
            ? 'bg-surface-container-high text-on-surface-variant cursor-not-allowed opacity-60'
            : 'bg-white/25 backdrop-blur-md border border-white/50 text-primary shadow-sm hover:bg-white/35 hover:scale-[1.02] active:scale-[0.98]'
        )}
      >
        Run Research →
      </button>
    </div>
  )
}

export default InputPanel
