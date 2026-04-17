import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import { cn } from '@/lib/utils'

interface MarkdownProps {
  children: string
  id?: string
  className?: string
}

export function Markdown({ children, id, className }: MarkdownProps) {
  return (
    <div id={id} className={cn(className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkBreaks]}>
        {children}
      </ReactMarkdown>
    </div>
  )
}

export default Markdown
