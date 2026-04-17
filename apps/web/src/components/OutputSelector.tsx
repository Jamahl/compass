import { cn } from '@/lib/utils'
import { OUTPUT_FORMATS, type OutputFormat, type OutputType } from '@/lib/formats'

export interface OutputSelectorProps {
  selected: Set<OutputType>
  onChange: (next: Set<OutputType>) => void
}

const GROUP_ORDER: OutputFormat['group'][] = ['Reports', 'Media', 'Structured']

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
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <p className="text-xs font-extrabold uppercase tracking-widest text-primary mb-1">Output Blueprints</p>
          <h2 className="text-xl font-bold text-on-surface">Choose your delivery formats.</h2>
        </div>
        <span className="text-xs font-semibold text-on-surface-variant">{selectedCount} selected</span>
      </div>
      {GROUP_ORDER.map((group) => {
        const items = OUTPUT_FORMATS.filter((f) => f.group === group)
        if (items.length === 0) return null
        return (
          <div key={group}>
            <div className="text-xs font-extrabold uppercase tracking-widest text-on-surface-variant mb-3">
              {group}
            </div>
            <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
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
                      isPro
                        ? 'group relative flex flex-col items-start gap-2 rounded-xl border border-transparent bg-surface-container-lowest p-4 text-left opacity-50 cursor-not-allowed'
                        : isSelected
                          ? 'group relative flex flex-col items-start gap-2 rounded-xl border border-primary/30 bg-accent/40 p-4 text-left transition-all duration-200 shadow-sm cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring'
                          : 'group relative flex flex-col items-start gap-2 rounded-xl border border-transparent bg-surface-container-lowest p-4 text-left transition-all duration-200 hover:border-primary/10 hover:shadow-lg cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
                    )}
                  >
                    {isPro && (
                      <span className="absolute top-2 right-2 text-[9px] uppercase font-bold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-700">
                        Coming soon
                      </span>
                    )}
                    <div className={cn(
                      "w-9 h-9 rounded-lg flex items-center justify-center mb-1",
                      group === 'Reports' ? 'bg-primary-fixed' : group === 'Media' ? 'bg-secondary-fixed-dim' : 'bg-tertiary-fixed'
                    )}>
                      <Icon
                        className={cn(
                          'size-4 shrink-0',
                          isSelected
                            ? 'text-primary'
                            : 'text-on-surface-variant',
                        )}
                      />
                    </div>
                    <span className="text-sm font-bold text-on-surface leading-tight">
                      {format.label}
                    </span>
                    <p className="text-[11px] leading-snug text-on-surface-variant">
                      {format.description}
                    </p>
                  </button>
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default OutputSelector
