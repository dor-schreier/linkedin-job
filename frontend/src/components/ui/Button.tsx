import { type ButtonHTMLAttributes } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'
type Size = 'sm' | 'md'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  icon?: string
}

const base =
  'inline-flex items-center gap-2 font-bold rounded-lg transition-colors focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed'

const variants: Record<Variant, string> = {
  primary: 'bg-primary text-on-primary hover:opacity-90',
  secondary:
    'bg-surface-container-high text-on-surface border border-outline-variant/30 hover:bg-surface-container-highest',
  ghost: 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface',
  danger: 'bg-error/20 text-error border border-error/30 hover:bg-error/30',
}

const sizes: Record<Size, string> = {
  sm: 'px-3 py-1.5 text-xs',
  md: 'px-4 py-2 text-sm',
}

export default function Button({
  variant = 'primary',
  size = 'md',
  loading = false,
  icon,
  children,
  className = '',
  disabled,
  ...rest
}: Props) {
  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]} ${className}`}
      disabled={disabled || loading}
      {...rest}
    >
      {loading ? (
        <span className="material-symbols-outlined text-[16px] animate-spin">refresh</span>
      ) : icon ? (
        <span className="material-symbols-outlined text-[16px]">{icon}</span>
      ) : null}
      {children}
    </button>
  )
}
