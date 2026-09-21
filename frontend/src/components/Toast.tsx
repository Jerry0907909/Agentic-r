import { AlertCircle, CheckCircle2, X } from 'lucide-react'
import { useEffect } from 'react'
import { cn } from '@/lib/utils'

export type ToastState = { id: number; message: string; tone?: 'error' | 'success' | 'info' }

export function Toast({ toast, onClose }: { toast: ToastState | null; onClose: () => void }) {
  useEffect(() => {
    if (!toast) return
    const timer = window.setTimeout(onClose, 3600)
    return () => window.clearTimeout(timer)
  }, [toast, onClose])

  if (!toast) return null
  const success = toast.tone === 'success'
  return (
    <div
      role="status"
      className={cn(
        'fixed right-4 top-24 z-50 flex max-w-[calc(100vw-2rem)] items-start gap-3 rounded-2xl border bg-card px-4 py-3 text-sm shadow-lifted sm:max-w-sm',
        toast.tone === 'error' ? 'border-red-200 dark:border-red-900' : 'border-border',
      )}
    >
      {success ? (
        <CheckCircle2 aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0 text-success" />
      ) : (
        <AlertCircle aria-hidden="true" className={cn('mt-0.5 h-4 w-4 shrink-0', toast.tone === 'error' ? 'text-danger' : 'text-primary')} />
      )}
      <span className="leading-5">{toast.message}</span>
      <button className="-m-2 ml-0 grid h-11 w-11 shrink-0 place-items-center rounded-xl text-muted-foreground hover:bg-muted hover:text-foreground" onClick={onClose} aria-label="关闭提示">
        <X aria-hidden="true" className="h-4 w-4" />
      </button>
    </div>
  )
}
