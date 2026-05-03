interface Props {
  message: string
  onRetry?: () => void
}

export default function ErrorState({ message, onRetry }: Props) {
  return (
    <div className="flex items-start gap-3 p-4 bg-error/10 rounded-xl text-error">
      <span className="material-symbols-outlined shrink-0">error</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium">{message}</p>
        {onRetry && (
          <button onClick={onRetry} className="mt-2 text-xs underline hover:no-underline">
            Try again
          </button>
        )}
      </div>
    </div>
  )
}
