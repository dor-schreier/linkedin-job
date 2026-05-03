/* eslint-disable react-refresh/only-export-components */
import { createContext, useContext, useState, useCallback, type ReactNode } from 'react'

type ToastType = 'success' | 'error' | 'info'

interface Toast {
  id: number
  message: string
  type: ToastType
}

interface ToastContextValue {
  toast: (message: string, type?: ToastType) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

let _id = 0

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([])

  const dismiss = useCallback((id: number) => {
    setToasts((prev) => prev.filter((t) => t.id !== id))
  }, [])

  const toast = useCallback((message: string, type: ToastType = 'info') => {
    const id = ++_id
    setToasts((prev) => [...prev, { id, message, type }])
    setTimeout(() => dismiss(id), 4000)
  }, [dismiss])

  const iconMap: Record<ToastType, string> = {
    success: 'check_circle',
    error: 'error',
    info: 'info',
  }

  const colorMap: Record<ToastType, string> = {
    success: 'bg-surface-container-highest border-success/30 text-success',
    error: 'bg-surface-container-highest border-error/30 text-error',
    info: 'bg-surface-container-highest border-primary/30 text-on-surface',
  }

  return (
    <ToastContext.Provider value={{ toast }}>
      {children}
      <div className="fixed bottom-6 right-6 flex flex-col gap-2 z-[9999] pointer-events-none">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`flex items-center gap-3 px-4 py-3 rounded-xl border shadow-lg text-sm font-medium pointer-events-auto animate-in fade-in slide-in-from-bottom-2 ${colorMap[t.type]}`}
          >
            <span className="material-symbols-outlined text-[18px] shrink-0">{iconMap[t.type]}</span>
            <span className="flex-1">{t.message}</span>
            <button
              onClick={() => dismiss(t.id)}
              className="shrink-0 opacity-60 hover:opacity-100 transition-opacity"
              aria-label="Dismiss"
            >
              <span className="material-symbols-outlined text-[16px]">close</span>
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside ToastProvider')
  return ctx.toast
}
