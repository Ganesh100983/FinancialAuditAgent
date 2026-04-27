import { useState, useRef, useEffect } from 'react'
import { Bot, Send, Square, Trash2, Lightbulb } from 'lucide-react'
import { chatApi } from '../api/client'
import useSSE from '../hooks/useSSE'
import StreamingOutput from '../components/ui/StreamingOutput'
import useAppStore from '../store/useAppStore'
import clsx from 'clsx'

const SUGGESTIONS = [
  'Summarise the ledger and highlight any anomalies',
  'What is the net profit for the current period?',
  'Generate a GST liability report for all tax rates',
  'Compare old vs new tax regime for all employees',
  'List the top 10 transactions by value',
  'What is the total IGST liability for this period?',
  'Show employees whose TDS deducted differs significantly from calculated tax',
  'Calculate GSTR-3B for the current period',
]

const AGENT_TYPES = [
  { value: 'ledger', label: 'Ledger' },
  { value: 'form16', label: 'Form 16' },
  { value: 'gst',    label: 'GST' },
]

export default function AIAssistant() {
  const [query,     setQuery]     = useState('')
  const [agentType, setAgentType] = useState('ledger')
  const [history,   setHistory]   = useState([])
  const [showTips,  setShowTips]  = useState(true)
  const { output, isStreaming, toolCalls, error, stream, cancel } = useSSE()
  const textareaRef = useRef(null)
  const bottomRef   = useRef(null)
  const uploads = useAppStore(s => s.uploads)

  const hasData = uploads.ledger?.status === 'ok' || uploads.gst?.status === 'ok' || uploads.employee?.status === 'ok'

  useEffect(() => {
    if (output || isStreaming) {
      bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [output, isStreaming])

  // Capture completed response into history
  useEffect(() => {
    if (!isStreaming && output && history[history.length - 1]?.role !== 'assistant') {
      setHistory(h => [...h, { role: 'assistant', content: output, toolCalls }])
    }
  }, [isStreaming]) // eslint-disable-line

  function handleSend() {
    if (!query.trim() || isStreaming) return
    const q = query.trim()
    setQuery('')
    setHistory(h => [...h, { role: 'user', content: q }])
    setShowTips(false)
    stream(chatApi.streamUrl(), { message: q, agent_type: agentType })
    textareaRef.current?.focus()
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSuggestion(s) {
    setQuery(s)
    textareaRef.current?.focus()
  }

  function clearHistory() {
    setHistory([])
    setShowTips(true)
  }

  return (
    <div className="flex flex-col h-full max-w-4xl mx-auto" style={{ minHeight: 'calc(100vh - 6rem)' }}>
      <div className="flex items-center justify-between mb-5">
        <div>
          <h1 className="text-xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Bot className="w-5 h-5 text-brand-600" /> AI Assistant
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400">Ask anything about your financial data — powered by GPT-4o mini</p>
        </div>
        <div className="flex items-center gap-2">
          {/* Agent selector */}
          <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-lg p-1">
            {AGENT_TYPES.map(a => (
              <button
                key={a.value}
                onClick={() => setAgentType(a.value)}
                className={`px-3 py-1 rounded-md text-xs font-medium transition-all ${
                  agentType === a.value
                    ? 'bg-white dark:bg-gray-700 text-brand-700 dark:text-brand-300 shadow-sm'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-200'
                }`}
              >
                {a.label}
              </button>
            ))}
          </div>
          {history.length > 0 && (
            <button onClick={clearHistory} className="btn-secondary text-xs">
              <Trash2 className="w-3.5 h-3.5" /> Clear
            </button>
          )}
        </div>
      </div>

      {!hasData && (
        <div className="mb-4 px-4 py-3 rounded-xl bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 text-sm text-yellow-700 dark:text-yellow-400">
          No data uploaded yet. Upload ledger, GST or employee files to get meaningful answers.
        </div>
      )}

      {/* Chat history */}
      <div className="flex-1 overflow-y-auto space-y-4 pb-4">
        {/* Suggestions */}
        {showTips && history.length === 0 && (
          <div className="space-y-3">
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Lightbulb className="w-4 h-4 text-yellow-500" />
              <span>Try asking…</span>
            </div>
            <div className="grid sm:grid-cols-2 gap-2">
              {SUGGESTIONS.map(s => (
                <button
                  key={s}
                  onClick={() => handleSuggestion(s)}
                  className="text-left text-sm px-3 py-2.5 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-brand-400 hover:bg-brand-50 dark:hover:bg-brand-900/20 dark:hover:border-brand-600 text-gray-600 dark:text-gray-400 hover:text-brand-700 dark:hover:text-brand-300 transition-all"
                >
                  {s}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Messages */}
        {history.map((msg, i) => (
          <div key={i} className={clsx('flex', msg.role === 'user' ? 'justify-end' : 'justify-start')}>
            {msg.role === 'user' ? (
              <div className="max-w-[75%] px-4 py-2.5 rounded-2xl rounded-tr-sm bg-brand-600 text-white text-sm">
                {msg.content}
              </div>
            ) : (
              <div className="max-w-[90%] w-full">
                <StreamingOutput
                  output={msg.content}
                  isStreaming={false}
                  toolCalls={msg.toolCalls}
                  error={null}
                />
              </div>
            )}
          </div>
        ))}

        {/* Live streaming output */}
        {(isStreaming || (output && !history.find(h => h.content === output && h.role === 'assistant'))) && (
          <div className="flex justify-start">
            <div className="max-w-[90%] w-full">
              <StreamingOutput
                output={output}
                isStreaming={isStreaming}
                toolCalls={toolCalls}
                error={error}
              />
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div className="sticky bottom-0 bg-gray-50 dark:bg-gray-950 pt-3 pb-1">
        <div className="flex gap-2 items-end card p-2 shadow-md">
          <textarea
            ref={textareaRef}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isStreaming ? 'AI is responding…' : 'Ask about your financial data… (Enter to send, Shift+Enter for newline)'}
            disabled={isStreaming}
            rows={1}
            className="flex-1 resize-none bg-transparent outline-none text-sm text-gray-800 dark:text-gray-200 placeholder-gray-400 dark:placeholder-gray-500 py-2 px-2 min-h-[2.5rem] max-h-[8rem] overflow-y-auto"
            style={{ fieldSizing: 'content' }}
          />
          {isStreaming ? (
            <button onClick={cancel} className="btn-danger shrink-0 p-2.5 rounded-lg">
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <button
              onClick={handleSend}
              disabled={!query.trim()}
              className="btn-primary shrink-0 p-2.5 rounded-lg disabled:opacity-50"
            >
              <Send className="w-4 h-4" />
            </button>
          )}
        </div>
        <p className="text-xs text-gray-400 dark:text-gray-600 text-center mt-1.5">
          AI may make mistakes. Verify important figures independently.
        </p>
      </div>
    </div>
  )
}
