interface Props {
  message?: string
}

export default function LoadingState({ message = 'Loading…' }: Props) {
  return (
    <div className="flex items-center gap-3 py-8 text-on-surface-variant">
      <span className="material-symbols-outlined animate-spin text-primary-dim">refresh</span>
      <span className="text-sm">{message}</span>
    </div>
  )
}
