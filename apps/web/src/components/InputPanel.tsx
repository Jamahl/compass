import { useEffect, useState } from 'react'
import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { Textarea } from '@/components/ui/textarea'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
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
  const [selectedContexts, setSelectedContexts] = useState<Set<string>>(
    new Set(),
  )

  useEffect(() => {
    getContexts().then(setContexts).catch(console.error)
  }, [])

  const currentDepth = DEPTH_LEVELS[depthIdx]
  const selectedTemplate = TEMPLATES.find((t) => t.id === template)

  const promptTrimmedEmpty = prompt.trim().length === 0
  const submitDisabled =
    disabled || promptTrimmedEmpty || selectedOutputs.length === 0

  const toggleContext = (filename: string) => {
    setSelectedContexts((prev) => {
      const next = new Set(prev)
      if (next.has(filename)) {
        next.delete(filename)
      } else {
        next.add(filename)
      }
      return next
    })
  }

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
    <Card>
      <CardHeader>
        <CardTitle>Research Input</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <label
            htmlFor="research-prompt"
            className="text-sm font-medium"
          >
            Prompt
          </label>
          <p className="text-xs text-muted-foreground mt-1 mb-2">
            What do you want to research? The more specific the better. Example:{' '}
            <em>
              'What are the top 5 pricing strategies SaaS startups used in 2025
              to cross $10M ARR?'
            </em>
          </p>
          <Textarea
            id="research-prompt"
            rows={4}
            required
            placeholder="What do you want to research?"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={disabled}
          />
        </div>

        <div className="flex flex-col gap-2">
          <label htmlFor="research-urls" className="text-sm font-medium">
            URLs (optional)
          </label>
          <p className="text-xs text-muted-foreground mt-1 mb-2">
            Paste one URL per line. The research agent will prioritise these
            sources when relevant. Useful when you already have a reading list,
            company pages, or competitor docs. Leave empty to search the open
            web.
          </p>
          <Textarea
            id="research-urls"
            rows={3}
            placeholder={'https://example.com\nhttps://another.com'}
            value={urlsText}
            onChange={(e) => setUrlsText(e.target.value)}
            disabled={disabled}
          />
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Context files</label>
          <p className="text-xs text-muted-foreground mt-1 mb-2">
            Tick any internal documents to feed as background material into the
            research. The agent will reference them when generating outputs.
            Drop new .md files into the <code>Context/</code> folder to expand
            this list.
          </p>
          {contexts.length === 0 ? (
            <p className="text-xs text-muted-foreground italic">
              No files in Context/. Drop .md files there to enable.
            </p>
          ) : (
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {contexts.map((ctx) => {
                const isSelected = selectedContexts.has(ctx.filename)
                return (
                  <button
                    key={ctx.filename}
                    type="button"
                    onClick={() => toggleContext(ctx.filename)}
                    disabled={disabled}
                    className={cn(
                      'rounded-lg border p-2 text-left hover:bg-accent/60',
                      isSelected
                        ? 'border-primary bg-accent'
                        : 'border-border',
                    )}
                  >
                    <div className="text-sm font-medium">{ctx.name}</div>
                    <p className="text-[11px] text-muted-foreground line-clamp-2 mt-0.5">
                      {ctx.preview}
                    </p>
                  </button>
                )
              })}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Template</label>
          <Select
            value={template}
            onValueChange={(v) => setTemplate(v as Template)}
            disabled={disabled}
          >
            <SelectTrigger className="w-full">
              <SelectValue placeholder="Select a template" />
            </SelectTrigger>
            <SelectContent>
              {TEMPLATES.map((t) => (
                <SelectItem key={t.id} value={t.id}>
                  {t.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {selectedTemplate ? (
            <div className="flex items-start gap-2 mt-1">
              <span className="text-[10px] uppercase font-semibold px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 shrink-0">
                {selectedTemplate.scope}
              </span>
              <p className="text-xs text-muted-foreground">
                {selectedTemplate.description}
              </p>
            </div>
          ) : null}
        </div>

        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium">Depth</label>
          <Slider
            min={0}
            max={3}
            step={1}
            value={[depthIdx]}
            onValueChange={(v) => {
              const arr = v as number[]
              setDepthIdx(arr[0])
            }}
            disabled={disabled}
          />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span className="font-medium text-foreground">
              {currentDepth.label}
            </span>
            <span>{currentDepth.approxTime}</span>
          </div>
          <p className="text-xs text-muted-foreground">
            Higher depth = more web browsing, more sources, longer runtime.
          </p>
        </div>

        <Button
          type="button"
          onClick={handleSubmit}
          disabled={submitDisabled}
          className="w-full"
        >
          Run Research
        </Button>
      </CardContent>
    </Card>
  )
}

export default InputPanel
