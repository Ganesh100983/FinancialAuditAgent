import { useCallback, useState } from 'react'
import { useDropzone } from 'react-dropzone'
import { Upload, CheckCircle, AlertCircle, Loader2, FileDown } from 'lucide-react'
import clsx from 'clsx'

export default function FileUpload({ label, accept, onUpload, status, disabled, sampleUrl }) {
  const [uploading, setUploading] = useState(false)

  const onDrop = useCallback(async ([file]) => {
    if (!file || uploading) return
    setUploading(true)
    try {
      await onUpload(file)
    } finally {
      setUploading(false)
    }
  }, [onUpload, uploading])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: accept ?? { 'text/csv': ['.csv'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'] },
    maxFiles: 1,
    disabled: disabled || uploading,
  })

  const isSuccess = status?.status === 'ok'
  const isError   = status?.status === 'error'

  return (
    <div className="space-y-2">
      {label && (
        <div className="flex items-center justify-between">
          <p className="label">{label}</p>
          {sampleUrl && (
            <a
              href={sampleUrl}
              download
              onClick={e => e.stopPropagation()}
              className="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 font-medium"
            >
              <FileDown className="w-3.5 h-3.5" />
              Download sample
            </a>
          )}
        </div>
      )}

      <div
        {...getRootProps()}
        className={clsx(
          'relative border-2 border-dashed rounded-xl p-5 text-center cursor-pointer transition-all',
          isDragActive
            ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/10'
            : isSuccess
              ? 'border-green-300 bg-green-50 dark:border-green-700 dark:bg-green-900/10'
              : isError
                ? 'border-red-300 bg-red-50 dark:border-red-700 dark:bg-red-900/10'
                : 'border-gray-200 hover:border-brand-400 hover:bg-brand-50/50 dark:border-gray-700 dark:hover:border-brand-600',
          (disabled || uploading) && 'opacity-60 cursor-not-allowed'
        )}
      >
        <input {...getInputProps()} />

        {uploading ? (
          <Loader2 className="mx-auto w-8 h-8 text-brand-500 animate-spin mb-2" />
        ) : isSuccess ? (
          <CheckCircle className="mx-auto w-8 h-8 text-green-500 mb-2" />
        ) : isError ? (
          <AlertCircle className="mx-auto w-8 h-8 text-red-500 mb-2" />
        ) : (
          <Upload className="mx-auto w-8 h-8 text-gray-400 mb-2" />
        )}

        {uploading ? (
          <p className="text-sm text-brand-600 dark:text-brand-400">Uploading…</p>
        ) : isSuccess ? (
          <>
            <p className="text-sm font-medium text-green-700 dark:text-green-400">
              {status.filename}
            </p>
            <p className="text-xs text-green-600 dark:text-green-500 mt-0.5">
              {status.rows?.toLocaleString()} rows · Click to replace
            </p>
          </>
        ) : isError ? (
          <p className="text-sm text-red-600 dark:text-red-400">{status.message ?? 'Upload failed'}</p>
        ) : (
          <>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              {isDragActive ? 'Drop file here' : 'Drop CSV / XLSX here'}
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">or click to browse</p>
          </>
        )}
      </div>
    </div>
  )
}
