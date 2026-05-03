import { type HTMLAttributes } from 'react'

interface Props extends HTMLAttributes<HTMLDivElement> {
  title?: string
}

export default function Card({ title, children, className = '', ...rest }: Props) {
  return (
    <div
      className={`bg-surface-container-lowest rounded-xl p-6 ${className}`}
      {...rest}
    >
      {title && (
        <h3 className="text-base font-bold font-headline mb-4">{title}</h3>
      )}
      {children}
    </div>
  )
}
