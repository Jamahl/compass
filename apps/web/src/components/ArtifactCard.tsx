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
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  pending: 'bg-gray-100 text-gray-700',
  running: 'bg-blue-100 text-blue-700',
  done: 'bg-green-100 text-green-700',
  error: 'bg-red-100 text-red-700',
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
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 py-3">
          <div className="flex items-center gap-2">
            {Icon ? <Icon className="h-4 w-4 text-muted-foreground" /> : null}
            <CardTitle className="text-sm font-medium">{label}</CardTitle>
          </div>
          <StatusBadge status={artifact.status} />
        </CardHeader>
        <CardContent className="flex flex-col gap-3 pb-4">
          {description && (
            <p className="text-xs text-muted-foreground">{description}</p>
          )}

          {artifact.status === 'done' && (
            <div className="flex gap-2">
              <Button size="sm" onClick={() => setOpen(true)}>
                <Eye className="h-3.5 w-3.5 mr-1" /> {verb}
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => downloadArtifact(artifact.id)}
              >
                <Download className="h-3.5 w-3.5 mr-1" /> Download
              </Button>
            </div>
          )}

          {(artifact.status === 'pending' || artifact.status === 'running') && (
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" />
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
        </CardContent>
      </Card>

      {open && (
        <ArtifactModal artifact={artifact} onClose={() => setOpen(false)} />
      )}
    </>
  )
}

export default ArtifactCard
