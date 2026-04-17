import { useState } from 'react'
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

export interface InputPanelProps {
  selectedOutputs: OutputType[]
  onSubmit: (req: {
    prompt: string
    urls: string[]
    template: Template
    depth: Depth
    outputs: OutputType[]
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

  const currentDepth = DEPTH_LEVELS[depthIdx]

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
          <Textarea
            id="research-urls"
            rows={3}
            placeholder={'https://example.com\nhttps://another.com'}
            value={urlsText}
            onChange={(e) => setUrlsText(e.target.value)}
            disabled={disabled}
          />
          <p className="text-xs text-muted-foreground">One URL per line.</p>
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
