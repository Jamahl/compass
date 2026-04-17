import { cn } from '@/lib/utils'
import { OUTPUT_FORMATS, type OutputFormat, type OutputType } from '@/lib/formats'

export interface OutputSelectorProps {
  selected: Set<OutputType>
  onChange: (next: Set<OutputType>) => void
}

const GROUP_ORDER: OutputFormat['group'][] = ['Reports', 'Media', 'Structured', 'ElevenLabs']

export function OutputSelector({ selected, onChange }: OutputSelectorProps) {
  const toggle = (id: OutputType) => {
    const format = OUTPUT_FORMATS.find((f) => f.id === id)
    const next = new Set(selected)
    if (format?.pro === true) {
      // Defensive: Pro tiles should never be selected; strip if present.
      next.delete(id)
      onChange(next)
      return
    }
    if (next.has(id)) next.delete(id)
    else next.add(id)
    onChange(next)
  }

  const selectedCount = selected.size

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-on-surface-variant">Outputs</span>
        <span className="text-xs font-semibold text-on-surface-variant bg-surface-container-high px-2 py-0.5 rounded-full">{selectedCount} selected</span>
      </div>

      <div className="flex flex-col gap-4">
        {GROUP_ORDER.map((group) => {
          const items = OUTPUT_FORMATS.filter((f) => f.group === group)
          if (items.length === 0) return null
          return (
            <div key={group} className="flex flex-col gap-1.5">
              <div className="text-[10px] font-semibold text-on-surface-variant/60 mb-0.5">{group}</div>
              {items.map((format) => {
                const Icon = format.icon
                const isPro = format.pro === true
                const isSelected = selected.has(format.id) && !isPro
                return (
                  <button
                    key={format.id}
                    type="button"
                    aria-pressed={isSelected}
                    disabled={isPro}
                    onClick={() => toggle(format.id)}
                    className={cn(
                      'relative flex items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm transition-all w-full',
                      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                      isPro
                        ? 'opacity-40 cursor-not-allowed bg-surface-container-lowest'
                        : isSelected
                          ? 'bg-accent border border-primary/30 shadow-sm'
                          : 'bg-surface-container-lowest border border-transparent hover:border-primary/10 hover:shadow-sm'
                    )}
                  >
                    {isPro && (
                      <span className="absolute top-1 right-1 text-[8px] font-semibold px-1.5 py-0.5 rounded-full bg-black/5 text-on-surface-variant">Pro</span>
                    )}
                    <Icon className={cn('size-3.5 shrink-0', isSelected ? 'text-primary' : 'text-on-surface-variant')} />
                    <span className={cn('text-xs font-semibold leading-tight', isSelected ? 'text-primary' : 'text-on-surface')}>{format.label}</span>
                  </button>
                )
              })}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default OutputSelector
