import { useState } from 'react'
import {
  AlertCircle,
  CheckCircle2,
  Circle,
  Clock,
  Download,
  Eye,
  Loader2,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import type { ArtifactMeta } from '@/api/client'
import { downloadArtifact } from '@/api/client'
import { OUTPUT_FORMAT_BY_ID, type OutputType } from '@/lib/formats'
import ArtifactModal from './ArtifactModal'

interface ArtifactCardProps {
  artifact: ArtifactMeta
}

type ArtifactStatus = ArtifactMeta['status']

const STATUS_BADGE: Record<ArtifactStatus, string> = {
  pending: 'bg-surface-container-high text-on-surface-variant',
  running: 'bg-primary/10 text-primary',
  done: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-600',
}

function StatusBadge({ status }: { status: ArtifactStatus }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
        STATUS_BADGE[status],
      )}
    >
      {status === 'pending' && <Circle className="h-3 w-3" />}
      {status === 'running' && <Loader2 className="h-3 w-3 animate-spin" />}
      {status === 'done' && <CheckCircle2 className="h-3 w-3" />}
      {status === 'error' && <AlertCircle className="h-3 w-3" />}
      <span className="capitalize">{status}</span>
    </span>
  )
}

export function ArtifactCard({ artifact }: ArtifactCardProps) {
  const [open, setOpen] = useState(false)
  const format = OUTPUT_FORMAT_BY_ID[artifact.type as OutputType]
  const Icon = format?.icon
  const label = format?.label ?? artifact.type
  const description = format?.description ?? ''
  const verb =
    format?.preview === 'audio' || format?.preview === 'video' ? 'Play' : 'View'

  return (
    <>
      <div className="bg-surface-container-lowest rounded-xl border border-transparent hover:border-primary/10 hover:shadow-md transition-all">
        {/* header row */}
        <div className="flex items-center justify-between px-4 py-3">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-primary-fixed flex items-center justify-center">
              {Icon ? <Icon className="h-4 w-4 text-primary" /> : null}
            </div>
            <span className="text-sm font-semibold text-on-surface">{label}</span>
          </div>
          <StatusBadge status={artifact.status} />
        </div>
        {/* body */}
        <div className="flex flex-col gap-3 px-4 pb-4">
          {description && (
            <p className="text-xs text-on-surface-variant">{description}</p>
          )}

          {artifact.status === 'done' && (
            <div className="flex gap-2">
              <button
                onClick={() => setOpen(true)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-full bg-gradient-brand text-white text-xs font-bold shadow-sm hover:opacity-90 transition-opacity"
              >
                <Eye className="h-3 w-3" /> {verb}
              </button>
              <button
                onClick={() => downloadArtifact(artifact.id)}
                className="flex items-center gap-1 px-3 py-1.5 rounded-full border border-outline-variant text-xs font-bold text-on-surface hover:bg-surface-container-high transition-colors"
              >
                <Download className="h-3 w-3" /> Download
              </button>
            </div>
          )}

          {(artifact.status === 'pending' || artifact.status === 'running') && (
            <div className="flex items-center gap-2 text-xs text-on-surface-variant">
              <Loader2 className="h-3 w-3 animate-spin text-primary" />
              <span>Generating…</span>
            </div>
          )}

          {artifact.status === 'error' &&
            (() => {
              const errorText = artifact.error ?? 'Generation failed.'
              const isComingSoon =
                errorText.includes('Coming soon') ||
                errorText.includes('AutoContent Pro')
              return (
                <div
                  className={cn(
                    'flex items-center gap-1 text-xs',
                    isComingSoon ? 'text-amber-700' : 'text-red-600',
                  )}
                >
                  {isComingSoon && (
                    <Clock className="h-3 w-3 shrink-0" />
                  )}
                  <span>{errorText}</span>
                </div>
              )
            })()}
        </div>
      </div>

      {open && (
        <ArtifactModal artifact={artifact} onClose={() => setOpen(false)} />
      )}
    </>
  )
}

export default ArtifactCard
