import { useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import InterviewModal, { type InterviewData, type InterviewModalState } from '../components/InterviewModal'
import { useJobInterviews } from '../api/queries'
import client from '../api/client'

function useJob(id: number) {
  return useQuery({
    queryKey: ['jobs', id],
    queryFn: async () => {
      const { data, error } = await client.GET('/api/jobs/{job_id}', {
        params: { path: { job_id: id } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    enabled: id > 0,
  })
}

function useScoreJob(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await client.POST('/api/jobs/{job_id}/score', {
        params: { path: { job_id: id } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs', id] }),
  })
}

function useReextract(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const { data, error } = await client.POST('/api/jobs/{job_id}/reextract', {
        params: { path: { job_id: id } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs', id] }),
  })
}

function useRefreshJob(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/jobs/${id}/refresh`, { method: 'POST' })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail || `Failed: ${res.status}`)
      }
      return res.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs', id] }),
  })
}

function useRateJob(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (rating: number | null) => {
      const { data, error } = await client.PATCH('/api/jobs/{job_id}/rate', {
        params: { path: { job_id: id } },
        body: { rating } as never,
      })
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs', id] }),
  })
}

type TailoredCV = {
  job_id: number
  generated_at: string
  pdf_url: string
  docx_url: string
  model_used?: string | null
  cv: unknown
}

function useTailoredCv(id: number) {
  return useQuery<TailoredCV | null>({
    queryKey: ['tailored-cv', id],
    queryFn: async () => {
      const res = await fetch(`/api/jobs/${id}/cv`)
      if (res.status === 404) return null
      if (!res.ok) throw new Error(`Failed: ${res.status}`)
      return res.json()
    },
    enabled: id > 0,
  })
}

function useGenerateTailoredCv(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async () => {
      const res = await fetch(`/api/jobs/${id}/cv/generate`, { method: 'POST' })
      if (!res.ok) {
        let detail = `Failed: ${res.status}`
        try {
          const body = await res.json()
          if (body?.detail) detail = body.detail
        } catch {
          // ignore
        }
        const err = new Error(detail) as Error & { status?: number }
        err.status = res.status
        throw err
      }
      return res.json() as Promise<TailoredCV>
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['tailored-cv', id] }),
  })
}

function relativeTime(iso: string): string {
  const then = new Date(iso).getTime()
  const diff = Math.max(0, Date.now() - then)
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min} min ago`
  const hrs = Math.floor(min / 60)
  if (hrs < 24) return `${hrs} hr ago`
  const days = Math.floor(hrs / 24)
  return `${days} day${days === 1 ? '' : 's'} ago`
}

function useUpdateStatus(id: number) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (status: string) => {
      const res = await fetch(`/api/jobs/${id}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (!res.ok) throw new Error(`Failed: ${res.status}`)
      return res.json()
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs', id] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

const STATUS_OPTIONS = [
  { value: 'new', label: 'NEW' },
  { value: 'saved', label: 'SAVED' },
  { value: 'applied', label: 'APPLIED' },
  { value: 'interviewing', label: 'INTERVIEWING' },
  { value: 'offer', label: 'OFFER' },
  { value: 'rejected', label: 'REJECTED' },
]

function FitBar({ score }: { score: number }) {
  const color = score >= 80 ? 'bg-success' : score >= 60 ? 'bg-warning' : score >= 40 ? 'bg-warning/60' : 'bg-error'
  const label = score >= 80 ? 'Excellent' : score >= 60 ? 'Good' : score >= 40 ? 'Fair' : 'Poor'
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-on-surface-variant">Fit Score</span>
        <span className="font-bold text-on-surface">{score}/100 — {label}</span>
      </div>
      <div className="h-2 bg-surface-container rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${score}%` }} />
      </div>
    </div>
  )
}

export default function JobDetail() {
  const { id } = useParams<{ id: string }>()
  const jobId = parseInt(id || '0')
  const navigate = useNavigate()
  const { data, isLoading, error } = useJob(jobId)
  const score = useScoreJob(jobId)
  const reextract = useReextract(jobId)
  const refresh = useRefreshJob(jobId)
  const rate = useRateJob(jobId)
  const updateStatus = useUpdateStatus(jobId)
  const tailored = useTailoredCv(jobId)
  const generateTailored = useGenerateTailoredCv(jobId)
  const [activeTab, setActiveTab] = useState<'overview' | 'intelligence' | 'score' | 'description'>('overview')
  const [ivModal, setIvModal] = useState<InterviewModalState>(null)
  const { data: interviews } = useJobInterviews(jobId)

  const job = data as any

  if (isLoading) {
    return (
      <Layout title="Job Detail">
        <p className="text-sm text-on-surface-variant">Loading…</p>
      </Layout>
    )
  }

  if (error || !job) {
    return (
      <Layout title="Job Detail">
        <p className="text-sm text-error">{error ? (error as Error).message : 'Job not found'}</p>
      </Layout>
    )
  }

  const intel = job.intelligence
  const breakdown = job.breakdown

  return (
    <Layout
      title={job.title}
      headerRight={
        <Button variant="ghost" size="sm" icon="arrow_back" onClick={() => navigate(-1)}>
          Back to Jobs
        </Button>
      }
    >
      <div className="max-w-4xl space-y-6">

        {/* Hero */}
        <Card>
          <div className="flex items-start justify-between gap-4">
            <div className="space-y-1">
              <h1 className="text-2xl font-extrabold font-headline text-on-surface">{job.title}</h1>
              <p className="text-base text-on-surface-variant">
                {job.company}
                {job.location && <span> · {job.location}</span>}
              </p>
              {(job.salary_min || job.salary_max) && (
                <p className="text-sm text-on-surface-variant">
                  {[job.salary_min, job.salary_max].filter(Boolean).map(Math.round).join('–')}
                  {job.salary_currency ? ` ${job.salary_currency}` : ''}
                </p>
              )}
              <div className="flex flex-wrap gap-2 pt-1">
                <Badge color={job.is_rejected ? 'red' : job.is_active ? 'green' : 'default'}>
                  {job.is_rejected ? 'Rejected' : job.is_active ? 'Active' : 'Inactive'}
                </Badge>
                <Badge>{job.source}</Badge>
                {job.sector && <Badge color="blue">{job.sector}</Badge>}
              </div>
            </div>
            <div className="shrink-0 space-y-2">
              {job.apply_url && (
                <a
                  href={job.apply_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold hover:opacity-90 transition-opacity"
                >
                  <span className="material-symbols-outlined" style={{ fontSize: 16 }}>open_in_new</span>
                  Apply
                </a>
              )}
            </div>
          </div>

          {/* Fit score bar */}
          {job.fit_score != null && (
            <div className="mt-4">
              <FitBar score={job.fit_score} />
              {job.fit_summary && <p className="text-sm text-on-surface-variant mt-2">{job.fit_summary}</p>}
            </div>
          )}

          {/* Status + rating */}
          <div className="mt-4 flex items-center gap-4 flex-wrap">
            <div className="flex items-center gap-2">
              <span className="text-xs text-outline uppercase tracking-wider font-bold">Status</span>
              <select
                value={job.status}
                onChange={(e) => updateStatus.mutate(e.target.value)}
                className="px-2 py-1 bg-surface-container-low border-none rounded-lg text-xs text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s.value} value={s.value}>{s.label}</option>
                ))}
              </select>
            </div>
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  onClick={() => rate.mutate(job.user_rating === star ? null : star)}
                  className={`material-symbols-outlined text-[20px] transition-colors ${
                    job.user_rating != null && star <= job.user_rating
                      ? 'text-yellow-400'
                      : 'text-outline hover:text-yellow-400'
                  }`}
                  style={{ fontVariationSettings: `'FILL' ${job.user_rating != null && star <= job.user_rating ? 1 : 0}` }}
                >
                  star
                </button>
              ))}
            </div>
          </div>
        </Card>

        {/* Tabs */}
        <div className="flex gap-1 bg-surface-container-lowest rounded-xl p-1">
          {(['overview', 'intelligence', 'score', 'description'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              className={`flex-1 py-2 px-3 rounded-lg text-xs font-bold capitalize transition-colors ${
                activeTab === tab
                  ? 'bg-primary text-on-primary'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {tab}
            </button>
          ))}
        </div>

        {/* Tab content */}
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <Card title="Quick Info">
              <div className="grid grid-cols-2 gap-3 text-sm">
                {job.date_posted && <InfoRow label="Posted" value={job.date_posted} />}
                {job.scraped_at && <InfoRow label="Scraped" value={new Date(job.scraped_at).toLocaleDateString()} />}
                {job.company_type && <InfoRow label="Company Type" value={job.company_type} />}
              </div>
            </Card>
            {job.company_summary && (
              <Card title="About the Company">
                <p className="text-sm text-on-surface-variant leading-relaxed">{job.company_summary}</p>
              </Card>
            )}
            <div className="flex gap-3 flex-wrap">
              <Button
                variant="secondary"
                icon="auto_awesome"
                onClick={() => score.mutate()}
                loading={score.isPending}
              >
                {job.fit_score != null ? 'Re-score' : 'Score Job'}
              </Button>
              <Button
                variant="secondary"
                icon="psychology"
                onClick={() => reextract.mutate(undefined, { onSuccess: () => setActiveTab('intelligence') })}
                loading={reextract.isPending}
              >
                {intel ? 'Re-extract' : 'Extract Intelligence'}
              </Button>
              <Button
                variant="secondary"
                icon="refresh"
                onClick={() => refresh.mutate()}
                loading={refresh.isPending}
                title="Re-fetch description from job URL, then re-extract and re-score"
              >
                Refresh Job
              </Button>
            </div>
            {(score.isError || reextract.isError || refresh.isError) && (
              <p className="text-xs text-error">
                {((score.error || reextract.error || refresh.error) as Error)?.message}
              </p>
            )}

            <Card title="Tailored CV">
              {tailored.isLoading ? (
                <p className="text-sm text-on-surface-variant">Loading…</p>
              ) : tailored.data ? (
                <div className="space-y-3">
                  <p className="text-xs text-on-surface-variant">
                    Generated {relativeTime(tailored.data.generated_at)}
                    {tailored.data.model_used ? ` · ${tailored.data.model_used}` : ''}
                  </p>
                  <div className="flex flex-wrap gap-3">
                    <a
                      href={tailored.data.pdf_url}
                      className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg text-sm font-bold hover:opacity-90 transition-opacity"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>picture_as_pdf</span>
                      Download PDF
                    </a>
                    <a
                      href={tailored.data.docx_url}
                      className="flex items-center gap-2 px-4 py-2 bg-surface-container text-on-surface rounded-lg text-sm font-bold hover:opacity-90 transition-opacity"
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>description</span>
                      Download DOCX
                    </a>
                    <Button
                      variant="ghost"
                      icon="refresh"
                      onClick={() => generateTailored.mutate()}
                      loading={generateTailored.isPending}
                    >
                      Regenerate
                    </Button>
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-on-surface-variant">
                    Generate a CV tailored to this job's requirements (PDF + DOCX).
                  </p>
                  <Button
                    icon="description"
                    onClick={() => generateTailored.mutate()}
                    loading={generateTailored.isPending}
                  >
                    Generate Tailored CV
                  </Button>
                </div>
              )}
              {generateTailored.isError && (
                <div className="mt-3">
                  <p className="text-xs text-error">
                    {(generateTailored.error as Error)?.message}
                  </p>
                  {(generateTailored.error as Error & { status?: number })?.status === 422 && (
                    <button
                      onClick={() => navigate('/profile')}
                      className="text-xs text-primary underline mt-1"
                    >
                      Go to Profile page
                    </button>
                  )}
                </div>
              )}
            </Card>
          </div>
        )}

        {activeTab === 'intelligence' && (
          <div className="space-y-4">
            {!intel ? (
              <Card>
                <p className="text-sm text-on-surface-variant mb-3">No intelligence extracted yet.</p>
                <Button
                  icon="psychology"
                  onClick={() => { reextract.mutate(); setActiveTab('intelligence') }}
                  loading={reextract.isPending}
                >
                  Extract Intelligence
                </Button>
              </Card>
            ) : (
              <>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {intel.required_skills?.length > 0 && (
                    <Card title="Required Skills">
                      <SkillList items={intel.required_skills} color="text-on-surface" />
                    </Card>
                  )}
                  {intel.preferred_skills?.length > 0 && (
                    <Card title="Preferred Skills">
                      <SkillList items={intel.preferred_skills} color="text-on-surface-variant" />
                    </Card>
                  )}
                  {intel.tech_stack?.length > 0 && (
                    <Card title="Tech Stack">
                      <div className="flex flex-wrap gap-2">
                        {intel.tech_stack.map((t: string) => (
                          <Badge key={t} color="blue">{t}</Badge>
                        ))}
                      </div>
                    </Card>
                  )}
                  {intel.red_flags?.length > 0 && (
                    <Card title="Red Flags">
                      <SkillList items={intel.red_flags} color="text-error" />
                    </Card>
                  )}
                </div>
                <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                  {intel.seniority_level && <InfoPill label="Seniority" value={intel.seniority_level} />}
                  {intel.remote_policy && <InfoPill label="Remote Policy" value={intel.remote_policy} />}
                  {intel.team_size_signals && <InfoPill label="Team Size" value={intel.team_size_signals} />}
                  {intel.salary_signals && <InfoPill label="Salary Signals" value={intel.salary_signals} />}
                </div>
              </>
            )}
          </div>
        )}

        {activeTab === 'score' && (
          <div className="space-y-4">
            {!breakdown ? (
              <Card>
                <p className="text-sm text-on-surface-variant mb-3">Not scored yet.</p>
                <Button
                  icon="auto_awesome"
                  onClick={() => { score.mutate(); setActiveTab('score') }}
                  loading={score.isPending}
                >
                  Score Job
                </Button>
              </Card>
            ) : (
              <>
                {job.fit_score != null && <FitBar score={job.fit_score} />}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {breakdown.matching_qualifications?.length > 0 && (
                    <Card title="Matching Qualifications">
                      <SkillList items={breakdown.matching_qualifications} color="text-success" icon="check" />
                    </Card>
                  )}
                  {breakdown.missing_qualifications?.length > 0 && (
                    <Card title="Missing Qualifications">
                      <SkillList items={breakdown.missing_qualifications} color="text-error" icon="close" />
                    </Card>
                  )}
                  {breakdown.red_flags?.length > 0 && (
                    <Card title="Red Flags">
                      <SkillList items={breakdown.red_flags} color="text-error" icon="warning" />
                    </Card>
                  )}
                </div>
                {(breakdown.experience_alignment || breakdown.application_priority) && (
                  <div className="grid grid-cols-2 gap-3">
                    {breakdown.experience_alignment && (
                      <InfoPill label="Experience Alignment" value={breakdown.experience_alignment} />
                    )}
                    {breakdown.application_priority && (
                      <InfoPill label="Priority" value={breakdown.application_priority} />
                    )}
                  </div>
                )}
                {breakdown.summary && (
                  <Card title="Recommendation">
                    <p className="text-sm text-on-surface-variant">{breakdown.summary}</p>
                  </Card>
                )}
              </>
            )}
          </div>
        )}

        {activeTab === 'description' && (
          <Card title="Job Description">
            {job.description ? (
              <pre className="text-sm text-on-surface-variant whitespace-pre-wrap font-sans leading-relaxed">
                {job.description}
              </pre>
            ) : (
              <p className="text-sm text-outline">No description available.</p>
            )}
          </Card>
        )}

        {/* Interviews section — always visible */}
        <InterviewsSection
          jobId={jobId}
          appliedAt={job.applied_at}
          interviews={(interviews as InterviewData[]) ?? []}
          onOpenModal={(state) => setIvModal(state)}
        />
      </div>

      {ivModal && <InterviewModal state={ivModal} onClose={() => setIvModal(null)} />}
    </Layout>
  )
}

const IV_TYPE_LABELS: Record<string, string> = {
  first_hr: 'First HR', initial: 'Initial', technical: 'Technical', final_hr: 'Final HR',
}
const MEDIUM_ICONS: Record<string, string> = {
  phone: 'call', zoom: 'videocam', in_person: 'location_on',
}

function relTimeFromNow(iso: string): string {
  const diff = new Date(iso).getTime() - Date.now()
  const absDiff = Math.abs(diff)
  const isPast = diff < 0
  const mins = Math.floor(absDiff / 60000)
  if (mins < 60) return isPast ? `${mins}m ago` : `in ${mins}m`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return isPast ? `${hrs}h ago` : `in ${hrs}h`
  const days = Math.floor(hrs / 24)
  return isPast ? `${days} day${days === 1 ? '' : 's'} ago` : `in ${days} day${days === 1 ? '' : 's'}`
}

function InterviewsSection({
  jobId,
  appliedAt,
  interviews,
  onOpenModal,
}: {
  jobId: number
  appliedAt?: string | null
  interviews: InterviewData[]
  onOpenModal: (state: InterviewModalState) => void
}) {
  const now = new Date()
  const upcoming = interviews.filter(iv => new Date(iv.scheduled_at) > now)
  const past = interviews.filter(iv => new Date(iv.scheduled_at) <= now)

  return (
    <Card>
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-base font-bold font-headline">Interviews</h3>
        <button
          onClick={() => onOpenModal({ mode: 'create', jobId })}
          className="flex items-center gap-1 text-xs text-primary hover:underline"
        >
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>add</span>
          Schedule interview
        </button>
      </div>
      {appliedAt && (
        <p className="text-xs text-on-surface-variant mb-4">
          Applied on {new Date(appliedAt).toLocaleDateString(undefined, { dateStyle: 'medium' })}{' '}
          <span className="text-outline">({relTimeFromNow(appliedAt)})</span>
        </p>
      )}

      {interviews.length === 0 ? (
        <p className="text-sm text-on-surface-variant">No interviews scheduled yet.</p>
      ) : (
        <div className="space-y-4">
          {upcoming.length > 0 && (
            <div>
              <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-2">Upcoming</p>
              <div className="space-y-2">
                {upcoming.map(iv => (
                  <InterviewRow key={iv.id} iv={iv} jobId={jobId} onOpenModal={onOpenModal} />
                ))}
              </div>
            </div>
          )}
          {past.length > 0 && (
            <div>
              <p className="text-xs font-bold text-on-surface-variant uppercase tracking-wider mb-2">Past</p>
              <div className="space-y-2">
                {[...past].reverse().map(iv => (
                  <InterviewRow key={iv.id} iv={iv} jobId={jobId} onOpenModal={onOpenModal} isPast />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  )
}

function InterviewRow({
  iv,
  jobId,
  onOpenModal,
  isPast = false,
}: {
  iv: InterviewData
  jobId: number
  onOpenModal: (state: InterviewModalState) => void
  isPast?: boolean
}) {
  const dt = new Date(iv.scheduled_at)
  const absDate = dt.toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' })

  return (
    <div className={`flex items-start gap-3 p-3 rounded-lg border ${isPast ? 'border-outline-variant/30 opacity-60' : 'border-outline-variant/60 bg-surface-container-lowest'}`}>
      <div className="flex-1 min-w-0 space-y-1">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-bold text-primary tracking-wider">
            {IV_TYPE_LABELS[iv.interview_type] ?? iv.interview_type}
          </span>
          <span className="text-xs text-on-surface-variant">·</span>
          <span className="text-xs text-on-surface">{absDate}</span>
          <span className="text-xs text-on-surface-variant">({relTimeFromNow(iv.scheduled_at)})</span>
        </div>
        <div className="flex items-center gap-1.5 text-xs text-on-surface-variant">
          <span className="material-symbols-outlined" style={{ fontSize: 14 }}>{MEDIUM_ICONS[iv.medium] ?? 'event'}</span>
          <span className="capitalize">{iv.medium.replace('_', ' ')}</span>
          {iv.location && <><span>·</span><span className="truncate">{iv.location}</span></>}
        </div>
        {iv.notes && <p className="text-xs text-on-surface-variant italic truncate">{iv.notes}</p>}
      </div>
      <button
        onClick={() => onOpenModal({ mode: 'edit', jobId, interview: iv })}
        className="shrink-0 text-on-surface-variant hover:text-primary transition-colors"
        title="Edit"
      >
        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>edit</span>
      </button>
    </div>
  )
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-outline uppercase tracking-wider font-bold">{label}</p>
      <p className="text-on-surface mt-0.5">{value}</p>
    </div>
  )
}

function InfoPill({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-surface-container rounded-xl p-3">
      <p className="text-[10px] font-bold uppercase tracking-wider text-outline">{label}</p>
      <p className="text-sm text-on-surface mt-1">{value}</p>
    </div>
  )
}

function SkillList({ items, color, icon }: { items: string[]; color: string; icon?: string }) {
  return (
    <ul className="space-y-1.5">
      {items.map((item, i) => (
        <li key={i} className={`flex items-start gap-2 text-sm ${color}`}>
          {icon ? (
            <span className="material-symbols-outlined text-[14px] shrink-0 mt-0.5">{icon}</span>
          ) : (
            <span className="shrink-0 mt-1.5 w-1 h-1 rounded-full bg-current" />
          )}
          {item}
        </li>
      ))}
    </ul>
  )
}
