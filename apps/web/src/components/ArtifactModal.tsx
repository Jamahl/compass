import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Download, Loader2 } from 'lucide-react'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Button } from '@/components/ui/button'
import { downloadArtifact } from '@/api/client'
import type { ArtifactMeta } from '@/api/client'
import { OUTPUT_FORMAT_BY_ID } from '@/lib/formats'
import { cn } from '@/lib/utils'

interface ArtifactModalProps {
  artifact: ArtifactMeta | null
  onClose: () => void
}

/**
 * Preview modal for every artifact type.
 * - pdf   -> iframe (browser PDF viewer)
 * - audio -> inline <audio controls>
 * - video -> inline <video controls>
 * - image -> <img>
 * - markdown -> react-markdown with gfm tables
 */
export default function ArtifactModal({
  artifact,
  onClose,
}: ArtifactModalProps) {
  const [mdContent, setMdContent] = useState<string | null>(null)
  const [mdError, setMdError] = useState<string | null>(null)

  const fmt = artifact ? OUTPUT_FORMAT_BY_ID[artifact.type] : null
  const src = artifact ? `/api/artifacts/${artifact.id}` : ''

  // Load markdown text for text-based artifacts
  useEffect(() => {
    if (!artifact || !fmt || fmt.preview !== 'markdown') {
      setMdContent(null)
      setMdError(null)
      return
    }
    let cancelled = false
    setMdContent(null)
    setMdError(null)
    fetch(src)
      .then(async (res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.text()
      })
      .then((txt) => {
        if (!cancelled) setMdContent(txt)
      })
      .catch((e) => {
        if (!cancelled) setMdError(String(e))
      })
    return () => {
      cancelled = true
    }
  }, [artifact, fmt, src])

  if (!artifact || !fmt) return null

  const Icon = fmt.icon

  return (
    <Dialog open onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent
        className={cn(
          // 90vw × 90vh — nearly fullscreen. Override the Dialog primitive's
          // default max-w-sm cap. flex flex-col so the body's flex-1 fills
          // the remaining height beneath the header.
          'p-0 overflow-hidden gap-0 flex flex-col',
          'w-[90vw] h-[90vh] max-w-[90vw] sm:max-w-[90vw]',
        )}
      >
        <DialogHeader className="px-5 py-3 border-b flex flex-row items-center justify-between space-y-0">
          <DialogTitle className="flex items-center gap-2 text-base">
            <Icon className="h-4 w-4" />
            {fmt.label}
          </DialogTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={() => downloadArtifact(artifact.id)}
            className="mr-8"
          >
            <Download className="h-4 w-4 mr-1" /> Download
          </Button>
        </DialogHeader>

        <div
          className={cn(
            // Fill remaining modal height (DialogContent uses grid with
            // header auto-rowed, so flex-1 + min-h-0 lets the body scroll
            // inside the 50vh frame instead of overflowing it).
            'flex-1 min-h-0 bg-muted/30',
            fmt.preview === 'pdf' || fmt.preview === 'video'
              ? ''
              : 'overflow-auto',
          )}
        >
          {fmt.preview === 'pdf' && (
            <iframe
              src={src}
              title={fmt.label}
              className="w-full h-full border-0 bg-white"
            />
          )}

          {fmt.preview === 'video' && (
            <div className="w-full h-full flex items-center justify-center bg-black">
              <video
                src={src}
                controls
                autoPlay={false}
                className="max-w-full max-h-full"
              />
            </div>
          )}

          {fmt.preview === 'audio' && (
            <div className="p-8 flex flex-col items-center gap-6">
              <div className="h-24 w-24 rounded-full bg-primary/10 flex items-center justify-center">
                <Icon className="h-10 w-10 text-primary" />
              </div>
              <audio src={src} controls className="w-full max-w-xl" />
              <p className="text-sm text-muted-foreground">{fmt.description}</p>
            </div>
          )}

          {fmt.preview === 'image' && (
            <div className="p-4 flex items-center justify-center">
              <img
                src={src}
                alt={fmt.label}
                className="max-w-full max-h-full object-contain rounded"
              />
            </div>
          )}

          {fmt.preview === 'markdown' && (
            <div className="p-6 h-full overflow-auto">
              {mdContent === null && !mdError && (
                <div className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" /> Loading…
                </div>
              )}
              {mdError && (
                <div className="text-sm text-red-600">
                  Failed to load: {mdError}
                </div>
              )}
              {mdContent && (
                <article className="prose prose-sm max-w-none dark:prose-invert">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {mdContent}
                  </ReactMarkdown>
                </article>
              )}
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
