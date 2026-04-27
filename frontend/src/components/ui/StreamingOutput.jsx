import { useEffect, useRef } from 'react'
import { Loader2, Wrench, CheckCircle } from 'lucide-react'
import clsx from 'clsx'
import Badge from './Badge'

function renderMarkdown(text) {
  return text
    .replace(/^### (.+)$/gm, '<h3>$1</h3>')
    .replace(/^## (.+)$/gm, '<h2>$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/^- (.+)$/gm, '<li>$1</li>')
    .replace(/(<li>[\s\S]*?<\/li>)/g, '<ul>$1</ul>')
    .replace(/\n\n/g, '</p><p>')
    .replace(/^(?!<[hul])(.+)$/gm, '<p>$1</p>')
}

export default function StreamingOutput({ output, isStreaming, toolCalls, error }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [output])

  if (!output && !isStreaming && !error && (!toolCalls || toolCalls.length === 0)) {
    return null
  }

  return (
    <div className="space-y-3">
      {toolCalls?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {toolCalls.map((t, i) => (
            <div key={i} className="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full bg-gray-100 dark:bg-gray-800">
              {t.status === 'running'
                ? <Loader2 className="w-3 h-3 animate-spin text-brand-500" />
                : <CheckCircle className="w-3 h-3 text-green-500" />
              }
              <Wrench className="w-3 h-3 text-gray-500" />
              <span className="text-gray-600 dark:text-gray-400 font-mono">{t.name}</span>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="px-4 py-3 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 text-sm text-red-700 dark:text-red-400">
          {error}
        </div>
      )}

      {output && (
        <div className={clsx(
          'prose-output bg-white dark:bg-gray-900 rounded-xl border border-gray-100 dark:border-gray-800 p-5 text-sm',
          isStreaming && 'streaming-cursor'
        )}>
          <div dangerouslySetInnerHTML={{ __html: renderMarkdown(output) }} />
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  )
}
