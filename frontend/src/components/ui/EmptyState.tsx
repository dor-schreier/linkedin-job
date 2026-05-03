interface Props {
  icon?: string
  title: string
  description?: string
  action?: React.ReactNode
}

export default function EmptyState({ icon = 'inbox', title, description, action }: Props) {
  return (
    <div className="text-center py-16 space-y-3">
      <span className="material-symbols-outlined text-outline" style={{ fontSize: 48 }}>{icon}</span>
      <p className="text-xl font-extrabold font-headline">{title}</p>
      {description && <p className="text-sm text-on-surface-variant">{description}</p>}
      {action && <div className="flex justify-center pt-2">{action}</div>}
    </div>
  )
}
