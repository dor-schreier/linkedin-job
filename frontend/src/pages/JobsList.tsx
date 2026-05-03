import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'

import Layout from '../components/Layout'
import Badge from '../components/ui/Badge'
import Button from '../components/ui/Button'
import client from '../api/client'

// ── Types ─────────────────────────────────────────────────────────────────────

interface Job {
  id: number
  title: string
  company: string
  location?: string
  source: string
  apply_url?: string
  salary_min?: number
  salary_max?: number
  salary_currency?: string
  status: string
  fit_score?: number
  fit_summary?: string
  date_posted?: string
  user_rating?: number
  is_active: boolean
  is_rejected: boolean
  scraped_at: string
  sector?: string
  company_type?: string
}

interface Stats {
  total_jobs: number
  new_since_last_visit: number
  high_match_count: number
  unscored_count: number
  scraper_running: boolean
  last_scrape_at?: string
  last_scrape_inserted?: number
  last_scrape_skipped?: number
}

interface Filters {
  status: string
  company: string
  location: string
  sector: string
  source: string
  sort: string
  fresh_only: boolean
  hide_rated: boolean
  show_inactive: boolean
  include_rejected: boolean
  q: string
}

const DEFAULT_FILTERS: Filters = {
  status: '',
  company: '',
  location: '',
  sector: '',
  source: '',
  sort: 'fit_desc',
  fresh_only: false,
  hide_rated: false,
  show_inactive: false,
  include_rejected: false,
  q: '',
}

// ── Queries ───────────────────────────────────────────────────────────────────

function useJobs(filters: Filters, page: number) {
  const params = new URLSearchParams()
  if (filters.status) params.set('status', filters.status)
  if (filters.company) params.set('company', filters.company)
  if (filters.location) params.set('location', filters.location)
  if (filters.sector) params.set('sector', filters.sector)
  if (filters.source) params.set('source', filters.source)
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.fresh_only) params.set('fresh_only', '1')
  if (filters.hide_rated) params.set('hide_rated', '1')
  if (filters.show_inactive) params.set('show_inactive', '1')
  if (filters.include_rejected) params.set('include_rejected', '1')
  if (filters.q) params.set('q', filters.q)
  params.set('page', String(page))

  return useQuery({
    queryKey: ['jobs', filters, page],
    queryFn: async () => {
      const res = await fetch(`/api/jobs?${params}`, { headers: { Accept: 'application/json' } })
      if (!res.ok) throw new Error('Failed to load jobs')
      return res.json() as Promise<{ jobs: Job[]; total: number; page: number; has_more: boolean; stats: Stats }>
    },
  })
}

function useUpdateStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ jobId, status }: { jobId: number; status: string }) => {
      const res = await fetch(`/api/jobs/${jobId}/status`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ status }),
      })
      if (!res.ok) throw new Error(`Failed: ${res.status}`)
      return res.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })
}

function useRateJob() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ jobId, rating }: { jobId: number; rating: number | null }) => {
      await client.PATCH('/api/jobs/{job_id}/rate', {
        params: { path: { job_id: jobId } },
        body: { rating } as never,
      })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })
}

// ── Components ────────────────────────────────────────────────────────────────

function FitPill({ score }: { score?: number }) {
  if (score == null) return <span className="text-xs text-outline">—</span>
  const color = score >= 80 ? 'bg-success/15 text-success' : score >= 60 ? 'bg-warning/15 text-warning' : score >= 40 ? 'bg-warning/10 text-warning/70' : 'bg-error/15 text-error'
  return <span className={`px-2 py-0.5 rounded-full text-[11px] font-bold ${color}`}>{score}</span>
}

function StarRating({ value, onRate }: { value?: number | null; onRate: (r: number | null) => void }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((s) => (
        <button
          key={s}
          onClick={(e) => { e.stopPropagation(); onRate(value === s ? null : s) }}
          className={`material-symbols-outlined transition-colors ${s <= (value ?? 0) ? 'text-yellow-400' : 'text-outline hover:text-yellow-300'}`}
          style={{ fontSize: 16, fontVariationSettings: `'FILL' ${s <= (value ?? 0) ? 1 : 0}` }}
        >
          star
        </button>
      ))}
    </div>
  )
}

function StatPill({ icon, value, label, highlight }: { icon: string; value: string | number; label: string; highlight?: boolean }) {
  return (
    <div className={`flex items-center gap-2 px-4 py-2 rounded-xl ${highlight ? 'bg-primary-container' : 'bg-surface-container-lowest'}`}>
      <span className={`material-symbols-outlined text-[18px] ${highlight ? 'text-on-primary-container' : 'text-primary-dim'}`}>{icon}</span>
      <div>
        <div className={`text-lg font-extrabold font-headline leading-none ${highlight ? 'text-on-primary-container' : 'text-on-surface'}`}>{value}</div>
        <div className={`text-[10px] font-bold uppercase tracking-tight mt-0.5 ${highlight ? 'text-on-primary-container/60' : 'text-outline'}`}>{label}</div>
      </div>
    </div>
  )
}

const STATUS_OPTIONS = ['', 'NEW', 'SAVED', 'APPLIED', 'INTERVIEWING', 'OFFER', 'REJECTED', 'rated']
const SORT_OPTIONS = [
  { value: 'fit_desc', label: 'Best Fit First' },
  { value: 'freshest', label: 'Freshest First' },
  { value: 'date_posted_asc', label: 'Date Posted ↑' },
  { value: 'rating_desc', label: 'Top Rated' },
  { value: 'fit_asc', label: 'Worst Fit First' },
]

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function JobsList() {
  const [filters, setFilters] = useState<Filters>(DEFAULT_FILTERS)
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [bulkStatus, setBulkStatus] = useState('')
  const navigate = useNavigate()
  const { data, isLoading, error } = useJobs(filters, page)
  const updateStatus = useUpdateStatus()
  const rateJob = useRateJob()

  const jobs = data?.jobs ?? []
  const stats = data?.stats
  const hasMore = data?.has_more ?? false

  function setFilter<K extends keyof Filters>(key: K, value: Filters[K]) {
    setFilters((f) => ({ ...f, [key]: value }))
    setPage(1)
    setSelectedIds(new Set())
  }

  function toggleSelect(id: number) {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  function toggleSelectAll() {
    if (selectedIds.size === jobs.length) {
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set(jobs.map((j) => j.id)))
    }
  }

  async function applyBulkStatus() {
    if (!bulkStatus || selectedIds.size === 0) return
    await Promise.all([...selectedIds].map((id) => updateStatus.mutateAsync({ jobId: id, status: bulkStatus })))
    setSelectedIds(new Set())
  }

  const selCount = selectedIds.size

  return (
    <Layout title="Jobs" active="jobs">
      <div className="space-y-6">

        {/* Stats hero */}
        {stats && (
          <div className="flex flex-wrap gap-3 items-start justify-between">
            <div className="flex flex-wrap gap-3">
              <StatPill icon="work" value={stats.total_jobs} label="Total Jobs" />
              <StatPill icon="new_releases" value={stats.new_since_last_visit} label="New Since Last Visit" />
              <StatPill icon="star" value={stats.high_match_count} label="High Match" highlight />
              {stats.unscored_count > 0 && (
                <StatPill icon="pending" value={stats.unscored_count} label="Unscored" />
              )}
            </div>
            {/* Scraper status */}
            <div className="shrink-0 bg-surface-container-lowest rounded-xl p-4 flex flex-col gap-3 min-w-[220px]">
              {stats.scraper_running ? (
                <div className="flex items-center gap-2 text-xs font-bold text-on-primary-container bg-primary-container px-3 py-1.5 rounded-full w-fit">
                  <span className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                  Scraper Active
                </div>
              ) : stats.last_scrape_at ? (
                <p className="text-xs text-outline">
                  Last scraped <span className="text-on-surface-variant font-medium">
                    {new Date(stats.last_scrape_at).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                  </span>
                </p>
              ) : (
                <p className="text-xs text-outline">No scrape run yet.</p>
              )}
              {stats.last_scrape_inserted != null && (
                <p className="text-xs text-on-surface-variant">
                  Added <span className="font-semibold text-on-surface">{stats.last_scrape_inserted}</span> jobs
                  ({stats.last_scrape_skipped} dupes skipped)
                </p>
              )}
              <Button icon="add_task" onClick={() => navigate('/scrape')} disabled={stats.scraper_running}>
                Find New Jobs
              </Button>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-surface-container-lowest rounded-xl p-4 space-y-3">
          {/* Search + sort row */}
          <div className="flex gap-3 flex-wrap">
            <div className="flex-1 min-w-[180px] relative">
              <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline" style={{ fontSize: 16 }}>search</span>
              <input
                type="text"
                placeholder="Search title, company, location…"
                value={filters.q}
                onChange={(e) => setFilter('q', e.target.value)}
                className="w-full pl-9 pr-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20"
              />
            </div>
            <select
              value={filters.sort}
              onChange={(e) => setFilter('sort', e.target.value)}
              className="px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {SORT_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
            <select
              value={filters.status}
              onChange={(e) => setFilter('status', e.target.value)}
              className="px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {STATUS_OPTIONS.map((s) => (
                <option key={s} value={s}>{s || 'All Statuses'}</option>
              ))}
            </select>
          </div>
          {/* Toggle filters */}
          <div className="flex flex-wrap gap-2 text-xs">
            {([
              ['fresh_only', 'Fresh Only'],
              ['hide_rated', 'Hide Rated'],
              ['show_inactive', 'Show Inactive'],
              ['include_rejected', 'Include Rejected'],
            ] as const).map(([key, label]) => (
              <button
                key={key}
                onClick={() => setFilter(key, !filters[key])}
                className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
                  filters[key]
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container text-on-surface-variant hover:text-on-surface'
                }`}
              >
                {label}
              </button>
            ))}
            {(filters.q || filters.status || filters.sector || filters.source || Object.entries(filters).some(([k, v]) => k !== 'sort' && v && v !== DEFAULT_FILTERS[k as keyof Filters])) && (
              <button
                onClick={() => { setFilters(DEFAULT_FILTERS); setPage(1) }}
                className="px-3 py-1.5 rounded-lg text-on-surface-variant hover:text-error transition-colors"
              >
                Clear filters
              </button>
            )}
          </div>
        </div>

        {/* Bulk actions */}
        {selCount > 0 && (
          <div className="flex items-center gap-3 p-3 bg-primary-container rounded-xl">
            <span className="text-sm font-bold text-on-primary-container">{selCount} selected</span>
            <select
              value={bulkStatus}
              onChange={(e) => setBulkStatus(e.target.value)}
              className="px-2 py-1.5 bg-surface-container rounded-lg text-xs text-on-surface border-none focus:outline-none"
            >
              <option value="">Set status…</option>
              {['SAVED', 'APPLIED', 'INTERVIEWING', 'OFFER', 'REJECTED'].map((s) => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
            <Button size="sm" onClick={applyBulkStatus} loading={updateStatus.isPending} disabled={!bulkStatus}>
              Apply
            </Button>
            <Button variant="ghost" size="sm" onClick={() => setSelectedIds(new Set())} className="ml-auto !text-on-primary-container/70 hover:!text-on-primary-container">
              Cancel
            </Button>
          </div>
        )}

        {/* Jobs table */}
        {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}
        {error && <p className="text-sm text-error">{(error as Error).message}</p>}

        {!isLoading && jobs.length === 0 && (
          <div className="text-center py-16 space-y-3">
            <p className="text-xl font-extrabold font-headline">No jobs found</p>
            <p className="text-sm text-on-surface-variant">Try adjusting your filters or run a scrape.</p>
            <Button icon="add_task" onClick={() => navigate('/scrape')}>Find New Jobs</Button>
          </div>
        )}

        {jobs.length > 0 && (
          <div className="bg-surface-container-lowest rounded-xl overflow-hidden">
            {/* Table header */}
            <div className="grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-4 px-4 py-2.5 border-b border-outline-variant/20 text-[10px] font-bold uppercase tracking-wider text-outline">
              <div>
                <input
                  type="checkbox"
                  checked={selCount === jobs.length && jobs.length > 0}
                  onChange={toggleSelectAll}
                  className="w-3.5 h-3.5 rounded"
                />
              </div>
              <div>Job</div>
              <div className="text-right">Fit</div>
              <div>Status</div>
              <div>Rating</div>
              <div>Posted</div>
            </div>

            {/* Rows */}
            <div className="divide-y divide-outline-variant/10">
              {jobs.map((job) => (
                <div
                  key={job.id}
                  className={`grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-4 px-4 py-3 items-center cursor-pointer transition-colors ${
                    selectedIds.has(job.id) ? 'bg-primary-container/30' : 'hover:bg-surface-container'
                  } ${job.is_rejected ? 'opacity-50' : ''}`}
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  {/* Checkbox */}
                  <div onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(job.id)}
                      onChange={() => toggleSelect(job.id)}
                      className="w-3.5 h-3.5 rounded"
                    />
                  </div>

                  {/* Job info */}
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-on-surface truncate">{job.title}</p>
                    <p className="text-xs text-on-surface-variant truncate">
                      {job.company}
                      {job.location ? ` · ${job.location}` : ''}
                    </p>
                    <div className="flex gap-1.5 mt-1 flex-wrap">
                      <Badge>{job.source}</Badge>
                      {job.sector && <Badge color="blue">{job.sector}</Badge>}
                      {!job.is_active && <Badge color="default">Inactive</Badge>}
                    </div>
                  </div>

                  {/* Fit score */}
                  <div className="text-right">
                    <FitPill score={job.fit_score} />
                    {job.fit_summary && (
                      <p className="text-[10px] text-outline mt-0.5 max-w-[120px] truncate text-right">
                        {job.fit_summary}
                      </p>
                    )}
                  </div>

                  {/* Status */}
                  <div onClick={(e) => e.stopPropagation()}>
                    <select
                      value={job.status}
                      onChange={(e) => updateStatus.mutate({ jobId: job.id, status: e.target.value })}
                      className="px-2 py-1 bg-surface-container border-none rounded text-[11px] text-on-surface focus:outline-none focus:ring-1 focus:ring-primary/30"
                    >
                      {['NEW', 'SAVED', 'APPLIED', 'INTERVIEWING', 'OFFER', 'REJECTED'].map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </div>

                  {/* Rating */}
                  <div onClick={(e) => e.stopPropagation()}>
                    <StarRating
                      value={job.user_rating}
                      onRate={(r) => rateJob.mutate({ jobId: job.id, rating: r })}
                    />
                  </div>

                  {/* Date */}
                  <div className="text-[11px] text-outline whitespace-nowrap">
                    {job.date_posted || '—'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pagination */}
        {(page > 1 || hasMore) && (
          <div className="flex items-center gap-3 justify-center pt-2">
            <Button variant="secondary" size="sm" disabled={page === 1} onClick={() => setPage(page - 1)}>← Prev</Button>
            <span className="text-sm text-on-surface-variant">Page {page}</span>
            <Button variant="secondary" size="sm" disabled={!hasMore} onClick={() => setPage(page + 1)}>Next →</Button>
          </div>
        )}

      </div>
    </Layout>
  )
}
