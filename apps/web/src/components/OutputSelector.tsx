import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import { cn } from '@/lib/utils'
import { OUTPUT_FORMATS, type OutputFormat, type OutputType } from '@/lib/formats'

export interface OutputSelectorProps {
  selected: Set<OutputType>
  onChange: (next: Set<OutputType>) => void
}

const GROUP_ORDER: OutputFormat['group'][] = ['Reports', 'Media', 'Structured']

export function OutputSelector({ selected, onChange }: OutputSelectorProps) {
  const toggle = (id: OutputType) => {
    const next = new Set(selected)
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }

  const selectedCount = selected.size

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle>Output Formats</CardTitle>
        <span className="text-xs text-muted-foreground">
          {selectedCount} selected
        </span>
      </CardHeader>
      <CardContent className="space-y-5">
        {GROUP_ORDER.map((group) => {
          const items = OUTPUT_FORMATS.filter((f) => f.group === group)
          if (items.length === 0) return null
          return (
            <div key={group}>
              <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground mb-2">
                {group}
              </div>
              <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
                {items.map((format) => {
                  const Icon = format.icon
                  const isSelected = selected.has(format.id)
                  return (
                    <button
                      key={format.id}
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => toggle(format.id)}
                      className={cn(
                        'flex flex-col items-start gap-1.5 rounded-lg border p-2.5 text-left transition-colors',
                        'hover:bg-accent/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                        isSelected
                          ? 'border-primary bg-accent'
                          : 'border-border bg-transparent',
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Icon
                          className={cn(
                            'size-4 shrink-0',
                            isSelected
                              ? 'text-primary'
                              : 'text-muted-foreground',
                          )}
                        />
                        <span className="text-sm font-medium leading-tight">
                          {format.label}
                        </span>
                      </div>
                      <p className="text-[11px] leading-snug text-muted-foreground">
                        {format.description}
                      </p>
                    </button>
                  )
                })}
              </div>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

export default OutputSelector
