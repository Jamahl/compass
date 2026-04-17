/**
 * Frontend shared metadata.
 *
 * Enum values MUST match apps/api/src/models.py exactly.
 * See project_overview.md section 4 for canonical contract.
 */

import type { LucideIcon } from 'lucide-react'
import {
  BarChart3,
  BookOpen,
  Clock,
  FileSpreadsheet,
  FileText,
  HelpCircle,
  Image as ImageIcon,
  Film,
  Headphones,
  ListChecks,
  MessageSquare,
  Mic,
  Presentation,
  Scale,
  Video,
} from 'lucide-react'

export type Template =
  | 'market_sizing'
  | 'competitor_scan'
  | 'customer_pain'
  | 'company_deep_dive'
  | 'product_teardown'
  | 'custom'

export type Depth = 'quick' | 'standard' | 'deep' | 'exhaustive'

export type OutputType =
  // OpenAI PDF reports
  | 'report_1pg'
  | 'report_5pg'
  | 'competitor_doc'
  // AutoContent media
  | 'podcast'
  | 'slides'
  | 'video'
  | 'infographic'
  // AutoContent PDF
  | 'briefing_doc'
  // AutoContent text/structured
  | 'faq'
  | 'study_guide'
  | 'timeline'
  | 'quiz'
  | 'datatable'
  | 'text'
  // ElevenLabs
  | 'elevenlabs_audio'
  | 'elevenlabs_video'

export type PreviewKind = 'pdf' | 'audio' | 'video' | 'image' | 'markdown'

export interface OutputFormat {
  id: OutputType
  label: string
  description: string
  icon: LucideIcon
  /** File extension the backend will write. Drives mime + preview kind. */
  ext: 'pdf' | 'mp3' | 'mp4' | 'png' | 'md'
  /** How the UI renders this artifact in the preview modal. */
  preview: PreviewKind
  /** Group label for the OutputSelector grid. */
  group: 'Reports' | 'Media' | 'Structured' | 'ElevenLabs'
  /**
   * Whether this output is gated behind an AutoContent Pro plan. When true
   * the UI shows "Coming soon" and disables the tile. Flip these once known.
   */
  pro?: boolean
}

export const OUTPUT_FORMATS: OutputFormat[] = [
  // ---- Reports (OpenAI + fpdf2) -----------------------------------------
  {
    id: 'report_1pg',
    label: '1-page Report',
    description: 'Exec-ready single-page brief (PDF)',
    icon: FileText,
    ext: 'pdf',
    preview: 'pdf',
    group: 'Reports',
  },
  {
    id: 'report_5pg',
    label: '5-page Report',
    description: 'In-depth analysis with findings + sources (PDF)',
    icon: FileText,
    ext: 'pdf',
    preview: 'pdf',
    group: 'Reports',
  },
  {
    id: 'competitor_doc',
    label: 'Competitor Analysis',
    description: 'Table-heavy competitor landscape (PDF)',
    icon: Scale,
    ext: 'pdf',
    preview: 'pdf',
    group: 'Reports',
  },
  {
    id: 'briefing_doc',
    label: 'Briefing Doc',
    description: 'AutoContent-generated briefing (PDF)',
    icon: FileText,
    ext: 'pdf',
    preview: 'pdf',
    group: 'Reports',
  },
  // ---- Media (AutoContent) ----------------------------------------------
  {
    id: 'podcast',
    label: 'Podcast',
    description: 'Audio summary (MP3) — plays inline',
    icon: Headphones,
    ext: 'mp3',
    preview: 'audio',
    group: 'Media',
  },
  {
    id: 'slides',
    label: 'Slides (narrated)',
    description: 'AI-narrated slide deck video',
    icon: Presentation,
    ext: 'mp4',
    preview: 'video',
    group: 'Media',
  },
  {
    id: 'video',
    label: 'Video Overview',
    description: 'Short explainer video (MP4)',
    icon: Video,
    ext: 'mp4',
    preview: 'video',
    group: 'Media',
    pro: true,
  },
  {
    id: 'infographic',
    label: 'Infographic',
    description: 'Single-image visual summary (PNG)',
    icon: ImageIcon,
    ext: 'png',
    preview: 'image',
    group: 'Media',
  },
  // ---- Structured text (AutoContent) ------------------------------------
  {
    id: 'faq',
    label: 'FAQ',
    description: 'Q&A summary of findings',
    icon: HelpCircle,
    ext: 'md',
    preview: 'markdown',
    group: 'Structured',
  },
  {
    id: 'study_guide',
    label: 'Study Guide',
    description: 'Explainer-style study guide',
    icon: BookOpen,
    ext: 'md',
    preview: 'markdown',
    group: 'Structured',
  },
  {
    id: 'timeline',
    label: 'Timeline',
    description: 'Chronological event breakdown',
    icon: Clock,
    ext: 'md',
    preview: 'markdown',
    group: 'Structured',
  },
  {
    id: 'quiz',
    label: 'Quiz',
    description: 'Knowledge-check questions',
    icon: ListChecks,
    ext: 'md',
    preview: 'markdown',
    group: 'Structured',
  },
  {
    id: 'datatable',
    label: 'Data Table',
    description: 'Structured data extracted from research',
    icon: FileSpreadsheet,
    ext: 'md',
    preview: 'markdown',
    group: 'Structured',
  },
  {
    id: 'text',
    label: 'Plain Text',
    description: 'Free-form text summary',
    icon: MessageSquare,
    ext: 'md',
    preview: 'markdown',
    group: 'Structured',
  },
  // ---- ElevenLabs ----------------------------------------------------------
  {
    id: 'elevenlabs_audio',
    label: 'Narration (ElevenLabs)',
    description: 'High-quality TTS narration of the brief (MP3)',
    icon: Mic,
    ext: 'mp3',
    preview: 'audio',
    group: 'ElevenLabs',
  },
  {
    id: 'elevenlabs_video',
    label: 'Narrated Video (ElevenLabs)',
    description: 'ElevenLabs TTS over generated title card (MP4)',
    icon: Film,
    ext: 'mp4',
    preview: 'video',
    group: 'ElevenLabs',
  },
]

export const OUTPUT_FORMAT_BY_ID: Record<OutputType, OutputFormat> =
  Object.fromEntries(OUTPUT_FORMATS.map((f) => [f.id, f])) as Record<
    OutputType,
    OutputFormat
  >

export interface TemplateMeta {
  id: Template
  label: string
  /** One-line helper shown under the select. */
  description: string
  /** How comprehensive the research is for this template. */
  scope: 'Narrow' | 'Balanced' | 'Broad' | 'Exhaustive'
}

export const TEMPLATES: TemplateMeta[] = [
  {
    id: 'market_sizing',
    label: 'Market Sizing',
    description:
      'TAM / SAM / SOM estimates with sources. Focused on numbers, growth rates, and segments.',
    scope: 'Balanced',
  },
  {
    id: 'competitor_scan',
    label: 'Competitor Scan',
    description:
      'Lists direct + indirect competitors, positioning, pricing, and moats. Broad landscape sweep.',
    scope: 'Broad',
  },
  {
    id: 'customer_pain',
    label: 'Customer Pain',
    description:
      'Synthesises pain points, jobs-to-be-done, quotes, and workarounds from user-facing sources.',
    scope: 'Balanced',
  },
  {
    id: 'company_deep_dive',
    label: 'Company Deep-Dive',
    description:
      'History, team, funding, product, strategy, metrics. Most comprehensive single-entity research.',
    scope: 'Exhaustive',
  },
  {
    id: 'product_teardown',
    label: 'Product Teardown',
    description:
      'Features, UX, tech choices, strengths/weaknesses of one product. Narrow but deep.',
    scope: 'Narrow',
  },
  {
    id: 'custom',
    label: 'Custom (prompt only)',
    description:
      'No template guidance — the research agent follows only your prompt. Use when your ask is specific.',
    scope: 'Narrow',
  },
]

export interface DepthMeta {
  id: Depth
  label: string
  approxTime: string
}

export const DEPTH_LEVELS: DepthMeta[] = [
  { id: 'quick', label: 'Quick', approxTime: '~30s' },
  { id: 'standard', label: 'Standard', approxTime: '~2min' },
  { id: 'deep', label: 'Deep', approxTime: '~5min' },
  { id: 'exhaustive', label: 'Exhaustive', approxTime: '~10min+' },
]

export { BarChart3 }
