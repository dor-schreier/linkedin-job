import { type HTMLAttributes } from 'react'

type Color = 'default' | 'green' | 'red' | 'yellow' | 'blue' | 'primary'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  color?: Color
}

const colors: Record<Color, string> = {
  default: 'bg-surface-container text-outline',
  primary: 'bg-primary-container text-on-primary-container',
  green: 'bg-success/15 text-success',
  red: 'bg-error/15 text-error',
  yellow: 'bg-warning/15 text-warning',
  blue: 'bg-info/15 text-info',
}

export default function Badge({ color = 'default', children, className = '', ...rest }: Props) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${colors[color]} ${className}`}
      {...rest}
    >
      {children}
    </span>
  )
}
