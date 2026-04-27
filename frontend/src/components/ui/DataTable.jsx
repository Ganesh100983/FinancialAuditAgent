import { useState } from 'react'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react'
import clsx from 'clsx'

export default function DataTable({ columns, data, pageSize = 10, loading, emptyText = 'No data' }) {
  const [page, setPage] = useState(0)

  if (loading) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-100 dark:border-gray-800">
              {columns.map(c => (
                <th key={c.key} className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide">
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {Array.from({ length: 5 }).map((_, i) => (
              <tr key={i} className="border-b border-gray-50 dark:border-gray-800/50">
                {columns.map(c => (
                  <td key={c.key} className="px-3 py-2.5">
                    <div className="h-3 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  if (!data?.length) {
    return (
      <div className="text-center py-12 text-sm text-gray-400 dark:text-gray-500">{emptyText}</div>
    )
  }

  const totalPages = Math.ceil(data.length / pageSize)
  const rows = data.slice(page * pageSize, (page + 1) * pageSize)

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-lg border border-gray-100 dark:border-gray-800">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-50 dark:bg-gray-800/50 border-b border-gray-100 dark:border-gray-800">
              {columns.map(c => (
                <th
                  key={c.key}
                  className={clsx(
                    'px-3 py-2.5 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wide whitespace-nowrap',
                    c.align === 'right' ? 'text-right' : 'text-left'
                  )}
                >
                  {c.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-50 dark:divide-gray-800/50">
            {rows.map((row, i) => (
              <tr key={i} className="hover:bg-gray-50/50 dark:hover:bg-gray-800/30 transition-colors">
                {columns.map(c => (
                  <td
                    key={c.key}
                    className={clsx(
                      'px-3 py-2.5 text-gray-700 dark:text-gray-300 whitespace-nowrap',
                      c.align === 'right' ? 'text-right' : 'text-left'
                    )}
                  >
                    {c.render ? c.render(row[c.key], row) : (row[c.key] ?? '—')}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {totalPages > 1 && (
        <div className="flex items-center justify-between text-sm text-gray-500 dark:text-gray-400">
          <span>
            {page * pageSize + 1}–{Math.min((page + 1) * pageSize, data.length)} of {data.length}
          </span>
          <div className="flex items-center gap-1">
            <button onClick={() => setPage(0)} disabled={page === 0}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30">
              <ChevronsLeft className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(p => p - 1)} disabled={page === 0}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30">
              <ChevronLeft className="w-4 h-4" />
            </button>
            <span className="px-2">Page {page + 1} / {totalPages}</span>
            <button onClick={() => setPage(p => p + 1)} disabled={page === totalPages - 1}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30">
              <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(totalPages - 1)} disabled={page === totalPages - 1}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-30">
              <ChevronsRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
