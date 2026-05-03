import { useState, useRef, useEffect } from 'react'
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
  required_skills: string[]
  tech_stack: string[]
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
  company: string[]
  location: string[]
  sector: string[]
  source: string
  company_type: string
  sort: string
  fresh_only: boolean
  hide_rated: boolean
  show_inactive: boolean
  include_rejected: boolean
  q: string
}

const DEFAULT_FILTERS: Filters = {
  status: '',
  company: [],
  location: [],
  sector: [],
  source: '',
  company_type: '',
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
  if (filters.company.length) params.set('company', filters.company.join(','))
  if (filters.location.length) params.set('location', filters.location.join(','))
  if (filters.sector.length) params.set('sector', filters.sector.join(','))
  if (filters.source) params.set('source', filters.source)
  if (filters.company_type) params.set('company_type', filters.company_type)
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

function useFilterOptions() {
  const fetchValues = async (url: string): Promise<string[]> => {
    const res = await fetch(url, { headers: { Accept: 'application/json' } })
    if (!res.ok) return []
    const data = await res.json()
    return (data.values as string[]).filter(Boolean).sort()
  }
  const companies = useQuery({ queryKey: ['filter-options', 'company'], queryFn: () => fetchValues('/api/reject-rules/property-values?property=company'), staleTime: 60_000 })
  const locations = useQuery({ queryKey: ['filter-options', 'location'], queryFn: () => fetchValues('/api/reject-rules/locations'), staleTime: 60_000 })
  const sectors = useQuery({ queryKey: ['filter-options', 'sector'], queryFn: () => fetchValues('/api/reject-rules/property-values?property=sector'), staleTime: 60_000 })
  return { companies: companies.data ?? [], locations: locations.data ?? [], sectors: sectors.data ?? [] }
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

function daysAgo(dateStr?: string): string {
  if (!dateStr) return '—'
  const diff = Math.floor((Date.now() - new Date(dateStr).getTime()) / 86_400_000)
  if (diff < 0) return dateStr
  if (diff === 0) return 'today'
  if (diff === 1) return '1d ago'
  if (diff < 7) return `${diff}d ago`
  if (diff < 30) return `${Math.floor(diff / 7)}w ago`
  return `${Math.floor(diff / 30)}mo ago`
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

function MultiSelectDropdown({
  label,
  options,
  selected,
  onChange,
}: {
  label: string
  options: string[]
  selected: string[]
  onChange: (values: string[]) => void
}) {
  const [open, setOpen] = useState(false)
  const [search, setSearch] = useState('')
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    if (open) document.addEventListener('mousedown', onClickOutside)
    return () => document.removeEventListener('mousedown', onClickOutside)
  }, [open])

  const filtered = options.filter((o) => o.toLowerCase().includes(search.toLowerCase()))

  function toggle(val: string) {
    onChange(selected.includes(val) ? selected.filter((v) => v !== val) : [...selected, val])
  }

  const buttonLabel = selected.length === 0 ? `All ${label}s` : selected.length === 1 ? selected[0] : `${selected.length} ${label}s`

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen((o) => !o)}
        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-primary/20 transition-colors ${
          selected.length > 0 ? 'bg-primary/15 text-primary font-medium' : 'bg-surface-container-low text-on-surface'
        }`}
      >
        <span className="truncate max-w-[120px]">{buttonLabel}</span>
        <span className="material-symbols-outlined text-[14px]">{open ? 'expand_less' : 'expand_more'}</span>
      </button>
      {open && (
        <div className="absolute z-50 top-full mt-1 left-0 min-w-[200px] bg-surface-container-low rounded-xl shadow-lg border border-outline-variant/20 overflow-hidden">
          {options.length > 8 && (
            <div className="p-2 border-b border-outline-variant/20">
              <input
                autoFocus
                type="text"
                placeholder="Search…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full px-2 py-1 bg-surface-container border-none rounded text-sm text-on-surface placeholder:text-outline focus:outline-none"
              />
            </div>
          )}
          <div className="max-h-56 overflow-y-auto py-1">
            {filtered.length === 0 && <p className="px-3 py-2 text-xs text-outline">No results</p>}
            {filtered.map((opt) => (
              <label key={opt} className="flex items-center gap-2 px-3 py-1.5 text-sm text-on-surface hover:bg-surface-container cursor-pointer">
                <input
                  type="checkbox"
                  checked={selected.includes(opt)}
                  onChange={() => toggle(opt)}
                  className="w-3.5 h-3.5 rounded accent-primary"
                />
                <span className="truncate">{opt}</span>
              </label>
            ))}
          </div>
          {selected.length > 0 && (
            <div className="border-t border-outline-variant/20 p-2">
              <button onClick={() => onChange([])} className="text-xs text-outline hover:text-error transition-colors w-full text-left px-1">
                Clear selection
              </button>
            </div>
          )}
        </div>
      )}
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
const COMPANY_TYPE_OPTIONS = ['', 'corporate', 'startup', 'scaleup', 'agency', 'non-profit', 'government', 'unknown']
const SOURCE_OPTIONS = ['', 'linkedin', 'indeed', 'glassdoor', 'zip_recruiter']

// ── Main Page ─────────────────────────────────────────────────────────────────

const STORAGE_KEY = 'jobsListFilters'

function loadFilters(): Filters {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY)
    if (raw) return { ...DEFAULT_FILTERS, ...JSON.parse(raw) }
  } catch { /* ignore */ }
  return DEFAULT_FILTERS
}

export default function JobsList() {
  const [filters, setFilters] = useState<Filters>(loadFilters)
  const [page, setPage] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set())
  const [bulkStatus, setBulkStatus] = useState('')
  const navigate = useNavigate()
  const { data, isLoading, error } = useJobs(filters, page)
  const updateStatus = useUpdateStatus()
  const rateJob = useRateJob()
  const filterOptions = useFilterOptions()

  useEffect(() => {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(filters))
  }, [filters])

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
          {/* Search + sort + status row */}
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
          {/* Detailed filters row */}
          <div className="flex gap-3 flex-wrap">
            <MultiSelectDropdown label="Company" options={filterOptions.companies} selected={filters.company} onChange={(v) => setFilter('company', v)} />
            <MultiSelectDropdown label="Location" options={filterOptions.locations} selected={filters.location} onChange={(v) => setFilter('location', v)} />
            <MultiSelectDropdown label="Sector" options={filterOptions.sectors} selected={filters.sector} onChange={(v) => setFilter('sector', v)} />
            <select
              value={filters.source}
              onChange={(e) => setFilter('source', e.target.value)}
              className="px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {SOURCE_OPTIONS.map((s) => (
                <option key={s} value={s}>{s || 'All Sources'}</option>
              ))}
            </select>
            <select
              value={filters.company_type}
              onChange={(e) => setFilter('company_type', e.target.value)}
              className="px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
            >
              {COMPANY_TYPE_OPTIONS.map((t) => (
                <option key={t} value={t}>{t || 'All Types'}</option>
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
            {Object.entries(filters).some(([k, v]) => {
              if (k === 'sort') return false
              const def = DEFAULT_FILTERS[k as keyof Filters]
              if (Array.isArray(v)) return v.length > 0
              return v && v !== def
            }) && (
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
                  className={`grid grid-cols-[auto_1fr_auto_auto_auto_auto] gap-4 px-4 py-3 items-start cursor-pointer transition-colors ${
                    selectedIds.has(job.id) ? 'bg-primary-container/30' : 'hover:bg-surface-container'
                  } ${job.is_rejected ? 'opacity-50' : ''}`}
                  onClick={() => navigate(`/jobs/${job.id}`)}
                >
                  {/* Checkbox */}
                  <div onClick={(e) => e.stopPropagation()} className="pt-0.5">
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
                    {((job.required_skills?.length ?? 0) > 0 || (job.tech_stack?.length ?? 0) > 0) && (
                      <div className="flex gap-1 mt-1.5 flex-wrap">
                        {(job.required_skills ?? []).slice(0, 5).map((s) => (
                          <span key={s} className="px-1.5 py-0.5 rounded text-[10px] bg-primary/10 text-primary font-medium">{s}</span>
                        ))}
                        {(job.tech_stack ?? []).slice(0, 4).map((s) => (
                          <span key={s} className="px-1.5 py-0.5 rounded text-[10px] bg-surface-container text-on-surface-variant">{s}</span>
                        ))}
                      </div>
                    )}
                    {job.fit_summary && (
                      <p className="text-[11px] text-on-surface-variant mt-1.5 leading-relaxed">{job.fit_summary}</p>
                    )}
                  </div>

                  {/* Fit score */}
                  <div className="text-right pt-0.5">
                    <FitPill score={job.fit_score} />
                  </div>

                  {/* Status */}
                  <div onClick={(e) => e.stopPropagation()} className="pt-0.5">
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
                  <div onClick={(e) => e.stopPropagation()} className="pt-0.5">
                    <StarRating
                      value={job.user_rating}
                      onRate={(r) => rateJob.mutate({ jobId: job.id, rating: r })}
                    />
                  </div>

                  {/* Date */}
                  <div className="text-[11px] text-outline whitespace-nowrap text-right pt-0.5" title={job.date_posted ?? ''}>
                    {daysAgo(job.date_posted)}
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
