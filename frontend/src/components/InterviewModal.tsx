import { useState } from 'react'
import { useCreateInterview, useUpdateInterview, useDeleteInterview } from '../api/queries'

export type InterviewData = {
  id: number
  scheduled_at: string
  interview_type: string
  medium: string
  location?: string | null
  notes?: string | null
}

export type InterviewModalState =
  | { mode: 'create'; jobId: number }
  | { mode: 'edit'; jobId: number; interview: InterviewData }
  | null

const MEDIUM_ICONS: Record<string, string> = {
  phone: 'call', zoom: 'videocam', in_person: 'location_on',
}

function toLocalDatetime(iso: string): string {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

export default function InterviewModal({
  state,
  onClose,
}: {
  state: InterviewModalState
  onClose: () => void
}) {
  const createInterview = useCreateInterview()
  const updateInterview = useUpdateInterview()
  const deleteInterview = useDeleteInterview()
  const [error, setError] = useState('')

  const existing = state?.mode === 'edit' ? state.interview : null

  const [form, setForm] = useState({
    scheduled_at: existing ? toLocalDatetime(existing.scheduled_at) : '',
    interview_type: existing?.interview_type ?? 'technical',
    medium: existing?.medium ?? 'zoom',
    location: existing?.location ?? '',
    notes: existing?.notes ?? '',
  })

  if (!state) return null

  const jobId = state.jobId

  function set(key: string, value: string) {
    setForm(f => ({ ...f, [key]: value }))
    setError('')
  }

  async function handleSave() {
    if (!form.scheduled_at) { setError('Date & time is required'); return }
    if (form.medium === 'in_person' && !form.location.trim()) {
      setError('Location is required for in-person interviews'); return
    }
    const body = {
      scheduled_at: new Date(form.scheduled_at).toISOString(),
      interview_type: form.interview_type,
      medium: form.medium,
      location: form.location || undefined,
      notes: form.notes || undefined,
    }
    try {
      if (state.mode === 'create') {
        await createInterview.mutateAsync({ jobId, body })
      } else {
        await updateInterview.mutateAsync({ interviewId: state.interview.id, jobId, body })
      }
      onClose()
    } catch (e: any) {
      setError(e.message ?? 'Failed to save')
    }
  }

  async function handleDelete() {
    if (!existing) return
    try {
      await deleteInterview.mutateAsync({ interviewId: existing.id, jobId })
      onClose()
    } catch (e: any) {
      setError(e.message ?? 'Failed to delete')
    }
  }

  const busy = createInterview.isPending || updateInterview.isPending || deleteInterview.isPending

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="bg-surface-container border border-outline-variant rounded-xl shadow-2xl w-full max-w-md p-6 flex flex-col gap-4"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-bold font-headline">
            {state.mode === 'create' ? 'Schedule Interview' : 'Edit Interview'}
          </h3>
          <button onClick={onClose} className="text-on-surface-variant hover:text-on-surface">
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">Date & Time</label>
          <input
            type="datetime-local"
            value={form.scheduled_at}
            onChange={e => set('scheduled_at', e.target.value)}
            className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">Interview Type</label>
          <select
            value={form.interview_type}
            onChange={e => set('interview_type', e.target.value)}
            className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary"
          >
            <option value="first_hr">First HR</option>
            <option value="initial">Initial</option>
            <option value="technical">Technical</option>
            <option value="final_hr">Final HR</option>
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">Medium</label>
          <div className="flex gap-2">
            {(['phone', 'zoom', 'in_person'] as const).map(m => (
              <button
                key={m}
                onClick={() => set('medium', m)}
                className={`flex-1 flex items-center justify-center gap-1.5 py-2 rounded-lg border text-xs font-medium transition-colors ${
                  form.medium === m
                    ? 'border-primary bg-primary/10 text-primary'
                    : 'border-outline-variant text-on-surface-variant hover:border-outline'
                }`}
              >
                <span className="material-symbols-outlined" style={{ fontSize: 16 }}>{MEDIUM_ICONS[m]}</span>
                {m === 'in_person' ? 'In Person' : m.charAt(0).toUpperCase() + m.slice(1)}
              </button>
            ))}
          </div>
        </div>

        {form.medium !== 'phone' && (
          <div className="flex flex-col gap-1">
            <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">
              {form.medium === 'zoom' ? 'Zoom Link' : 'Address'}
              {form.medium === 'in_person' && <span className="text-error ml-1">*</span>}
            </label>
            <input
              type="text"
              value={form.location}
              onChange={e => set('location', e.target.value)}
              placeholder={form.medium === 'zoom' ? 'https://zoom.us/j/...' : '123 Main St'}
              className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary"
            />
          </div>
        )}

        <div className="flex flex-col gap-1">
          <label className="text-xs font-medium text-on-surface-variant uppercase tracking-wider">Notes</label>
          <textarea
            value={form.notes}
            onChange={e => set('notes', e.target.value)}
            rows={2}
            className="bg-surface-container-high border border-outline-variant rounded-lg px-3 py-2 text-sm text-on-surface focus:outline-none focus:border-primary resize-none"
          />
        </div>

        {error && <p className="text-xs text-error">{error}</p>}

        <div className="flex gap-2 pt-1">
          {state.mode === 'edit' && (
            <button
              onClick={handleDelete}
              disabled={busy}
              className="px-3 py-2 rounded-lg text-sm font-medium text-error border border-error/30 hover:bg-error/10 transition-colors disabled:opacity-50"
            >
              Delete
            </button>
          )}
          <div className="flex-1" />
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-on-surface-variant hover:text-on-surface transition-colors">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={busy}
            className="px-5 py-2 rounded-lg text-sm font-bold bg-primary text-on-primary hover:opacity-90 transition-opacity disabled:opacity-50"
          >
            {busy ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
