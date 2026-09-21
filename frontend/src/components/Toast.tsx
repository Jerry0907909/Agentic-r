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
        'fixed right-4 top-20 z-50 flex max-w-sm items-start gap-3 rounded-xl border bg-card px-4 py-3 text-sm shadow-2xl',
        toast.tone === 'error' ? 'border-red-200 dark:border-red-900' : 'border-border',
      )}
    >
      {success ? (
        <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
      ) : (
        <AlertCircle className={cn('mt-0.5 h-4 w-4 shrink-0', toast.tone === 'error' ? 'text-red-500' : 'text-primary')} />
      )}
      <span className="leading-5">{toast.message}</span>
      <button className="ml-1 text-muted-foreground hover:text-foreground" onClick={onClose} aria-label="关闭提示">
        <X className="h-4 w-4" />
      </button>
    </div>
  )
}
