import { useState, useRef, useEffect } from 'react'
import { Link } from 'react-router-dom'
import Layout from '../components/Layout'
import InterviewModal, { type InterviewData, type InterviewModalState } from '../components/InterviewModal'
import {
  useApplications,
  useUpdateJobStatus,
} from '../api/queries'

// ── Types ────────────────────────────────────────────────────────────────────

type NextInterview = InterviewData

type TrackerJob = {
  id: number
  title: string
  company: string
  location?: string | null
  status: string
  applied_at?: string | null
  next_interview?: NextInterview | null
}

// ── Constants ────────────────────────────────────────────────────────────────

const COLUMNS: { key: string; label: string; dot: string; ring: string }[] = [
  { key: 'saved',        label: 'Saved',        dot: 'bg-blue-400',    ring: 'hover:ring-blue-400/40' },
  { key: 'applied',      label: 'Applied',      dot: 'bg-emerald-400', ring: 'hover:ring-emerald-400/40' },
  { key: 'interviewing', label: 'Interviewing', dot: 'bg-primary',     ring: 'hover:ring-primary/40' },
  { key: 'offer',        label: 'Offer',        dot: 'bg-yellow-400',  ring: 'hover:ring-yellow-400/40' },
  { key: 'rejected',     label: 'Rejected',     dot: 'bg-error',       ring: 'hover:ring-error/40' },
]

const STATUS_LABELS: Record<string, string> = {
  new: 'New', saved: 'Saved', applied: 'Applied',
  interviewing: 'Interviewing', offer: 'Offer', rejected: 'Rejected',
}

const IV_TYPE_LABELS: Record<string, string> = {
  first_hr: 'FIRST HR', initial: 'INITIAL', technical: 'TECHNICAL', final_hr: 'FINAL HR',
}

const MEDIUM_ICONS: Record<string, string> = {
  phone: 'call', zoom: 'videocam', in_person: 'location_on',
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 2) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  const days = Math.floor(hrs / 24)
  if (days === 1) return '1 day ago'
  return `${days} days ago`
}

function countdownLabel(iso: string): string {
  const now = new Date()
  const target = new Date(iso)
  const diffMs = target.getTime() - now.getTime()
  if (diffMs < 0) return 'Past'
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 60) return `in ${diffMins}m`
  const diffHrs = Math.floor(diffMins / 60)
  if (diffHrs < 24) {
    const today = now.toDateString() === target.toDateString()
    if (today) {
      return `Today ${target.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
    }
    return `in ${diffHrs}h`
  }
  const diffDays = Math.floor(diffHrs / 24)
  const tomorrow = new Date(now); tomorrow.setDate(tomorrow.getDate() + 1)
  if (target.toDateString() === tomorrow.toDateString()) {
    return `Tomorrow ${target.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
  }
  return `in ${diffDays} days`
}

function initials(company: string): string {
  return company.trim().slice(0, 2).toUpperCase()
}

type ModalState = InterviewModalState

// ── Status Pill Dropdown ──────────────────────────────────────────────────────

const ALL_STATUSES = ['saved', 'applied', 'interviewing', 'offer', 'rejected']

function StatusDropdown({
  jobId,
  current,
  onClose,
}: {
  jobId: number
  current: string
  onClose: () => void
}) {
  const updateStatus = useUpdateJobStatus()
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [onClose])

  async function pick(s: string) {
    if (s === current) { onClose(); return }
    await updateStatus.mutateAsync({ jobId, status: s })
    onClose()
  }

  return (
    <div
      ref={ref}
      className="absolute top-full left-0 mt-1 z-30 bg-surface-container-high border border-outline-variant rounded-lg shadow-lg overflow-hidden min-w-[140px]"
    >
      {ALL_STATUSES.filter(s => s !== current).map(s => (
        <button
          key={s}
          onClick={() => pick(s)}
          className="w-full text-left px-3 py-2 text-xs hover:bg-surface-container text-on-surface-variant hover:text-on-surface transition-colors"
        >
          {STATUS_LABELS[s]}
        </button>
      ))}
    </div>
  )
}

// ── Application Card ──────────────────────────────────────────────────────────

function AppCard({
  job,
  colKey,
  onSchedule,
}: {
  job: TrackerJob
  colKey: string
  onSchedule: (jobId: number, interview?: NextInterview) => void
}) {
  const [showDrop, setShowDrop] = useState(false)
  const col = COLUMNS.find(c => c.key === colKey)!

  return (
    <div className={`relative bg-surface-container border border-outline-variant/60 rounded-xl p-4 flex flex-col gap-3 ring-2 ring-transparent ${col.ring} transition-all hover:border-outline`}>
      {/* Header */}
      <div className="flex items-start gap-3">
        <div className="shrink-0 w-8 h-8 rounded-lg bg-surface-container-high border border-outline-variant flex items-center justify-center text-xs font-bold text-on-surface-variant">
          {initials(job.company)}
        </div>
        <div className="flex-1 min-w-0">
          <Link
            to={`/jobs/${job.id}`}
            className="text-sm font-semibold text-on-surface hover:text-primary transition-colors line-clamp-2 leading-tight"
          >
            {job.title}
          </Link>
          <p className="text-xs text-on-surface-variant mt-0.5 truncate">
            {job.company}{job.location ? ` · ${job.location}` : ''}
          </p>
        </div>
      </div>

      {/* Column-specific content */}
      {colKey === 'applied' && job.applied_at && (
        <p className="text-xs text-emerald-400 font-medium">Applied {relativeTime(job.applied_at)}</p>
      )}

      {colKey === 'interviewing' && (
        <div className="flex flex-col gap-2">
          {job.next_interview ? (
            <button
              onClick={() => onSchedule(job.id, job.next_interview!)}
              className="flex flex-col gap-1.5 bg-primary/5 border border-primary/20 rounded-lg p-2.5 text-left hover:bg-primary/10 transition-colors w-full"
            >
              <div className="flex items-center gap-2">
                <span className="text-xs font-bold text-primary tracking-wider">
                  {IV_TYPE_LABELS[job.next_interview.interview_type] ?? job.next_interview.interview_type.toUpperCase()}
                </span>
                <span className="text-xs text-on-surface-variant">·</span>
                <span className="text-xs text-on-surface-variant font-medium">
                  {countdownLabel(job.next_interview.scheduled_at)}
                </span>
              </div>
              <div className="flex items-center gap-1.5 text-xs text-on-surface-variant">
                <span className="material-symbols-outlined" style={{ fontSize: 14 }}>
                  {MEDIUM_ICONS[job.next_interview.medium] ?? 'event'}
                </span>
                {job.next_interview.location && (
                  <span className="truncate">{job.next_interview.location}</span>
                )}
              </div>
            </button>
          ) : (
            <p className="text-xs text-on-surface-variant italic">No upcoming interviews</p>
          )}
          <button
            onClick={() => onSchedule(job.id)}
            className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-primary transition-colors"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 14 }}>add</span>
            Schedule interview
          </button>
        </div>
      )}

      {colKey === 'applied' && (
        <button
          onClick={() => onSchedule(job.id)}
          className="flex items-center gap-1 text-xs text-on-surface-variant hover:text-primary transition-colors"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>event</span>
          Schedule interview
        </button>
      )}

      {(colKey === 'offer' || colKey === 'rejected') && job.applied_at && (
        <p className="text-xs text-on-surface-variant">Applied {relativeTime(job.applied_at)}</p>
      )}

      {/* Footer: status pill */}
      <div className="relative">
        <button
          onClick={() => setShowDrop(v => !v)}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium border transition-colors ${
            colKey === 'applied'      ? 'border-emerald-400/40 text-emerald-400 bg-emerald-400/10 hover:bg-emerald-400/20' :
            colKey === 'interviewing' ? 'border-primary/40 text-primary bg-primary/10 hover:bg-primary/20' :
            colKey === 'offer'        ? 'border-yellow-400/40 text-yellow-400 bg-yellow-400/10 hover:bg-yellow-400/20' :
            colKey === 'rejected'     ? 'border-error/40 text-error bg-error/10 hover:bg-error/20' :
                                        'border-blue-400/40 text-blue-400 bg-blue-400/10 hover:bg-blue-400/20'
          }`}
        >
          {STATUS_LABELS[colKey]}
          <span className="material-symbols-outlined" style={{ fontSize: 12 }}>expand_more</span>
        </button>
        {showDrop && (
          <StatusDropdown jobId={job.id} current={colKey} onClose={() => setShowDrop(false)} />
        )}
      </div>
    </div>
  )
}

// ── Column ────────────────────────────────────────────────────────────────────

function KanbanColumn({
  col,
  jobs,
  onSchedule,
}: {
  col: typeof COLUMNS[0]
  jobs: TrackerJob[]
  onSchedule: (jobId: number, interview?: NextInterview) => void
}) {
  return (
    <div className="flex flex-col gap-3 w-72 shrink-0 h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-1 shrink-0">
        <span className={`w-2 h-2 rounded-full shrink-0 ${col.dot}`} />
        <span className="text-sm font-semibold text-on-surface">{col.label}</span>
        <span className="ml-auto inline-flex items-center justify-center text-xs font-bold bg-surface-container-high text-on-surface-variant rounded-full w-5 h-5">
          {jobs.length}
        </span>
      </div>

      {/* Cards */}
      <div className="flex flex-col gap-3 overflow-y-auto flex-1 min-h-0">
        {jobs.length === 0 ? (
          <div className="border border-dashed border-outline-variant/40 rounded-xl p-6 text-center text-xs text-on-surface-variant">
            {col.key === 'interviewing' ? 'No interviews scheduled' : 'No applications yet'}
          </div>
        ) : (
          jobs.map(job => (
            <AppCard key={job.id} job={job} colKey={col.key} onSchedule={onSchedule} />
          ))
        )}
      </div>
    </div>
  )
}

// ── Skeleton ──────────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-surface-container border border-outline-variant/60 rounded-xl p-4 flex flex-col gap-3 animate-pulse">
      <div className="flex items-start gap-3">
        <div className="w-8 h-8 rounded-lg bg-surface-container-high" />
        <div className="flex-1 flex flex-col gap-2">
          <div className="h-3 bg-surface-container-high rounded w-3/4" />
          <div className="h-2.5 bg-surface-container-high rounded w-1/2" />
        </div>
      </div>
      <div className="h-2 bg-surface-container-high rounded w-1/3" />
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function ApplicationTracker() {
  const { data: jobs, isLoading } = useApplications()
  const [search, setSearch] = useState('')
  const [modal, setModal] = useState<ModalState>(null)

  const allJobs: TrackerJob[] = (jobs as TrackerJob[]) ?? []

  const filtered = search.trim()
    ? allJobs.filter(j =>
        j.title.toLowerCase().includes(search.toLowerCase()) ||
        j.company.toLowerCase().includes(search.toLowerCase())
      )
    : allJobs

  const byStatus = (status: string) => filtered.filter(j => j.status === status)

  function openSchedule(jobId: number, interview?: NextInterview) {
    if (interview) {
      setModal({ mode: 'edit', jobId, interview })
    } else {
      setModal({ mode: 'create', jobId })
    }
  }

  return (
    <Layout
      title="Application Tracker"
      active="applications"
      headerRight={
        <div className="relative">
          <span className="material-symbols-outlined absolute left-2.5 top-1/2 -translate-y-1/2 text-on-surface-variant" style={{ fontSize: 18 }}>search</span>
          <input
            type="text"
            placeholder="Search jobs…"
            value={search}
            onChange={e => setSearch(e.target.value)}
            className="pl-8 pr-3 py-1.5 text-sm bg-surface-container border border-outline-variant rounded-lg text-on-surface placeholder:text-on-surface-variant focus:outline-none focus:border-primary w-56"
          />
        </div>
      }
    >
      <p className="text-sm text-on-surface-variant mb-4 shrink-0">
        Manage your recruitment pipeline and active interviews
      </p>

      <div className="flex-1 overflow-x-auto min-h-0">
        <div className="flex gap-5 min-w-max h-full">
          {isLoading
            ? COLUMNS.map(col => (
                <div key={col.key} className="flex flex-col gap-3 w-72 shrink-0">
                  <div className="flex items-center gap-2 px-1">
                    <span className={`w-2 h-2 rounded-full ${col.dot}`} />
                    <span className="text-sm font-semibold text-on-surface">{col.label}</span>
                  </div>
                  {[1, 2].map(i => <SkeletonCard key={i} />)}
                </div>
              ))
            : COLUMNS.map(col => (
                <KanbanColumn
                  key={col.key}
                  col={col}
                  jobs={byStatus(col.key)}
                  onSchedule={openSchedule}
                />
              ))
          }
        </div>
      </div>

      {modal && (
        <InterviewModal state={modal} onClose={() => setModal(null)} />
      )}
    </Layout>
  )
}
