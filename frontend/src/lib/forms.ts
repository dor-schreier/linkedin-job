import { useState, type ChangeEvent } from 'react'

export function useForm<T extends Record<string, unknown>>(initial: T) {
  const [values, setValues] = useState<T>(initial)

  function set(field: keyof T, value: T[keyof T]) {
    setValues((prev) => ({ ...prev, [field]: value }))
  }

  function bind(field: keyof T) {
    return {
      value: values[field] as string | number | undefined,
      onChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        const raw = e.target.value
        const prev = initial[field]
        set(field, (typeof prev === 'number' ? (raw === '' ? '' : Number(raw)) : raw) as T[keyof T])
      },
    }
  }

  function reset() { setValues(initial) }

  return { values, set, bind, reset, setValues }
}
