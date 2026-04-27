import { useState, useCallback, useRef } from 'react'

/**
 * Hook for consuming SSE streams from the FastAPI /chat/stream endpoint.
 * Uses fetch + ReadableStream so it works with Authorization headers
 * (EventSource doesn't support custom headers).
 */
export default function useSSE() {
  const [output, setOutput]       = useState('')
  const [isStreaming, setStreaming]= useState(false)
  const [toolCalls, setToolCalls] = useState([])
  const [error, setError]         = useState(null)
  const abortRef                  = useRef(null)

  const stream = useCallback(async (url, body) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setOutput('')
    setToolCalls([])
    setError(null)
    setStreaming(true)

    try {
      const token = localStorage.getItem('fa_token')
      const res = await fetch(url, {
        method:  'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body:   JSON.stringify(body),
        signal: controller.signal,
      })

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: res.statusText }))
        throw new Error(err.detail || 'Stream request failed')
      }

      const reader  = res.body.getReader()
      const decoder = new TextDecoder()
      let   buf     = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()            // keep incomplete line in buffer

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const evt = JSON.parse(line.slice(6))
            if (evt.type === 'token') {
              setOutput(prev => prev + evt.content)
            } else if (evt.type === 'tool_start') {
              setToolCalls(prev => [...prev, { name: evt.tool, status: 'running' }])
            } else if (evt.type === 'tool_end') {
              setToolCalls(prev =>
                prev.map(t => t.name === evt.tool && t.status === 'running'
                  ? { ...t, status: 'done' } : t)
              )
            } else if (evt.type === 'error') {
              setError(evt.content)
            } else if (evt.type === 'done') {
              setStreaming(false)
            }
          } catch { /* ignore malformed lines */ }
        }
      }
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    } finally {
      setStreaming(false)
    }
  }, [])

  const cancel = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
  }, [])

  return { output, isStreaming, toolCalls, error, stream, cancel }
}
