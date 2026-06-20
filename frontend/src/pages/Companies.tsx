import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'
import Layout from '../components/Layout'
import Badge from '../components/ui/Badge'
import { useCompaniesOverview, useCompanyJobs, useUpdateJobStatus, useCompanySectorOptions, useUpdateCompanySector, type CompanyOverviewItem } from '../api/queries'

// ── Types ─────────────────────────────────────────────────────────────────────

type GroupBy = 'type' | 'sector' | 'location'

interface PanelState {
  company: CompanyOverviewItem
  locationContext: string | null
  locationCount: number
}

// ── Constants ─────────────────────────────────────────────────────────────────

const GROUP_LABELS: Record<GroupBy, string> = { type: 'Type', sector: 'Sector', location: 'Location' }
const ALL_GROUPS: GroupBy[] = ['type', 'sector', 'location']
const UNKNOWN = 'Unknown / Unspecified'

// Scraped-within-last-N-days filter options (0 = all time)
const DAYS_OPTIONS: { value: number; label: string }[] = [
  { value: 0, label: 'Any time' },
  { value: 1, label: 'Last 24h' },
  { value: 3, label: 'Last 3 days' },
  { value: 7, label: 'Last 7 days' },
  { value: 14, label: 'Last 14 days' },
  { value: 30, label: 'Last 30 days' },
]

// ── Helpers ───────────────────────────────────────────────────────────────────

function loadGroupBy(): GroupBy {
  try {
    const v = localStorage.getItem('companiesGroupBy')
    if (v === 'type' || v === 'sector' || v === 'location') return v
  } catch { /* ignore */ }
  return 'type'
}

function saveGroupBy(v: GroupBy) {
  try { localStorage.setItem('companiesGroupBy', v) } catch { /* ignore */ }
}

function loadFlatMode(): boolean {
  try {
    const v = localStorage.getItem('companiesFlatMode')
    if (v === 'false') return false
  } catch { /* ignore */ }
  return true
}

function saveFlatMode(v: boolean) {
  try { localStorage.setItem('companiesFlatMode', String(v)) } catch { /* ignore */ }
}

// Session state — persists across same-tab navigation (back button)
const SESSION_KEY = 'companies_session'

interface SessionState {
  search: string
  typeFilter: string
  daysFilter: number
  subGroupBy: GroupBy | null
  scrollTop: number
}

function loadSession(): Partial<SessionState> {
  try { return JSON.parse(sessionStorage.getItem(SESSION_KEY) || '{}') } catch { return {} }
}

function saveSession(patch: Partial<SessionState>) {
  try {
    const prev = loadSession()
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ ...prev, ...patch }))
  } catch { /* ignore */ }
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

function fitColor(score?: number) {
  if (score == null) return 'bg-surface-container text-outline'
  if (score >= 80) return 'bg-success/15 text-success'
  if (score >= 60) return 'bg-warning/15 text-warning'
  if (score >= 40) return 'bg-warning/10 text-warning/70'
  return 'bg-error/15 text-error'
}

function getItemKey(item: CompanyOverviewItem, groupBy: GroupBy): string {
  if (groupBy === 'type') return item.company_type || UNKNOWN
  if (groupBy === 'sector') return item.sector || UNKNOWN
  return UNKNOWN
}

function locationCountFor(item: CompanyOverviewItem, loc: string): number {
  return item.location_breakdown.find(
    (l) => l.location === loc || (!l.location && loc === UNKNOWN)
  )?.count ?? 0
}

function buildGroups(items: CompanyOverviewItem[], groupBy: GroupBy): Map<string, CompanyOverviewItem[]> {
  const map = new Map<string, CompanyOverviewItem[]>()
  for (const item of items) {
    if (groupBy === 'location') {
      const locs = item.location_breakdown.length > 0
        ? item.location_breakdown.map((l) => l.location || UNKNOWN)
        : [UNKNOWN]
      for (const loc of [...new Set(locs)]) {
        if (!map.has(loc)) map.set(loc, [])
        map.get(loc)!.push(item)
      }
    } else {
      const key = getItemKey(item, groupBy)
      if (!map.has(key)) map.set(key, [])
      map.get(key)!.push(item)
    }
  }
  return new Map(
    [...map.entries()].sort(([ka, a], [kb, b]) => {
      if (ka === UNKNOWN && kb !== UNKNOWN) return 1
      if (kb === UNKNOWN && ka !== UNKNOWN) return -1
      return b.length - a.length
    })
  )
}

function groupJobCount(items: CompanyOverviewItem[], groupKey: string, groupBy: GroupBy): number {
  if (groupBy === 'location') {
    return items.reduce((sum, item) => sum + locationCountFor(item, groupKey), 0)
  }
  return items.reduce((sum, item) => sum + item.total_active_jobs, 0)
}

// Deterministic initials avatar color from company name
function hashStr(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0
  return Math.abs(h)
}

function getLogoHue(name: string): number {
  // Spread across hues but avoid yellow-green range (hard to read)
  const raw = hashStr(name) % 300
  return raw < 60 ? raw : raw + 60
}

// ── Company Logo ──────────────────────────────────────────────────────────────

function CompanyLogo({ name, size = 'md' }: { name: string; size?: 'sm' | 'md' | 'lg' }) {
  const initials = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0].toUpperCase())
    .join('')

  const hue = getLogoHue(name)
  const sizeClass =
    size === 'sm' ? 'w-8 h-8 text-xs rounded-lg' :
    size === 'lg' ? 'w-14 h-14 text-lg rounded-2xl' :
    'w-10 h-10 text-sm rounded-xl'

  return (
    <div
      className={`${sizeClass} flex items-center justify-center font-bold shrink-0`}
      style={{ background: `hsl(${hue}, 55%, 38%)`, color: `hsl(${hue}, 80%, 92%)` }}
    >
      {initials}
    </div>
  )
}

// ── Company Card ──────────────────────────────────────────────────────────────

function CompanyCard({
  item,
  locationContext,
  locationCount,
  onClick,
}: {
  item: CompanyOverviewItem
  locationContext: string | null
  locationCount: number
  onClick: () => void
}) {
  const jobCount = locationContext != null ? locationCount : item.total_active_jobs

  return (
    <button
      onClick={onClick}
      className="group w-full text-left bg-surface-container border border-outline-variant/20 hover:border-primary/30 rounded-2xl p-5 flex flex-col gap-4 transition-all duration-150 hover:bg-surface-container-high"
    >
      {/* Top row: logo + roles pill */}
      <div className="flex items-start justify-between gap-3">
        <CompanyLogo name={item.name_display} size="md" />
        <span className="flex items-center gap-1 px-2.5 py-1 rounded-full text-[11px] font-bold bg-primary/10 text-primary whitespace-nowrap shrink-0">
          <span className="material-symbols-outlined" style={{ fontSize: 11 }}>work</span>
          {jobCount} {jobCount === 1 ? 'Role' : 'Roles'}
        </span>
      </div>

      {/* Company name */}
      <p className="font-semibold text-base text-on-surface leading-snug group-hover:text-primary transition-colors">
        {item.name_display}
      </p>

      {/* Type / sector tags */}
      {(item.company_type || item.sector || item.subsector) && (
        <div className="flex flex-wrap gap-1.5">
          {item.company_type && <Badge color="primary">{item.company_type}</Badge>}
          {item.sector && <Badge color="default">{item.sector}</Badge>}
          {item.subsector && <Badge color="blue">{item.subsector}</Badge>}
        </div>
      )}

      {/* Description */}
      {item.what_they_do && (
        <p className="text-xs text-on-surface-variant leading-relaxed line-clamp-3 flex-1">
          {item.what_they_do}
        </p>
      )}

      {/* View Details footer */}
      <div className="mt-auto pt-3 border-t border-outline-variant/20 text-xs font-semibold text-on-surface-variant group-hover:text-primary transition-colors flex items-center justify-center gap-1">
        View Details
        <span className="material-symbols-outlined" style={{ fontSize: 14 }}>chevron_right</span>
      </div>
    </button>
  )
}

// ── Skeleton Card ─────────────────────────────────────────────────────────────

function SkeletonCard() {
  return (
    <div className="bg-surface-container border border-outline-variant/20 rounded-2xl p-5 flex flex-col gap-4 animate-pulse">
      <div className="flex justify-between gap-3">
        <div className="w-10 h-10 bg-surface-container-high rounded-xl" />
        <div className="h-6 bg-surface-container-high rounded-full w-16" />
      </div>
      <div className="h-4 bg-surface-container-high rounded w-3/4" />
      <div className="flex gap-1.5">
        <div className="h-4 bg-surface-container-high rounded w-20" />
        <div className="h-4 bg-surface-container-high rounded w-16" />
      </div>
      <div className="space-y-2">
        <div className="h-3 bg-surface-container-high rounded w-full" />
        <div className="h-3 bg-surface-container-high rounded w-4/5" />
        <div className="h-3 bg-surface-container-high rounded w-2/3" />
      </div>
      <div className="h-8 bg-surface-container-high rounded-lg" />
    </div>
  )
}

// ── Company Jobs Panel (Drawer) ────────────────────────────────────────────────

function CompanyJobsPanel({ state, onClose }: { state: PanelState; onClose: () => void }) {
  const navigate = useNavigate()
  const qc = useQueryClient()
  const { company, locationContext } = state

  const { data, isLoading } = useCompanyJobs(company.company, locationContext)
  const jobs = data?.jobs ?? []

  const updateStatus = useUpdateJobStatus()
  const { data: sectorOptions } = useCompanySectorOptions()
  const updateSector = useUpdateCompanySector()

  const canEditSector = company.company_id != null

  const [editSector, setEditSector] = useState(company.sector ?? '')
  const [editSubsector, setEditSubsector] = useState(company.subsector ?? '')
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null)

  // Reset local edit state when panel company changes
  useEffect(() => {
    setEditSector(company.sector ?? '')
    setEditSubsector(company.subsector ?? '')
  }, [company.company_id, company.sector, company.subsector])

  function showToast(msg: string, ok: boolean) {
    setToast({ msg, ok })
    setTimeout(() => setToast(null), 3000)
  }

  function handleSaveSector() {
    if (!canEditSector || company.company_id == null) return
    updateSector.mutate(
      {
        companyId: company.company_id,
        sector: editSector || null,
        subsector: editSubsector || null,
      },
      {
        onSuccess: () => showToast('Sector saved', true),
        onError: (e) => showToast((e as Error).message ?? 'Save failed', false),
      }
    )
  }

  function handleReject(jobId: number) {
    updateStatus.mutate(
      { jobId, status: 'rejected' },
      { onSuccess: () => qc.invalidateQueries({ queryKey: ['companies', 'overview'] }) }
    )
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  const subtitle = [
    company.company_type,
    locationContext && locationContext !== UNKNOWN ? locationContext : null,
  ].filter(Boolean).join(' • ')

  const sectors = sectorOptions?.sectors ?? []
  const subsectors = sectorOptions?.subsectors ?? []

  const sectorChanged = editSector !== (company.sector ?? '') || editSubsector !== (company.subsector ?? '')

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <div
        className="relative w-full max-w-[480px] h-full bg-surface-container-low flex flex-col shadow-2xl"
        style={{ animation: 'slideInRight 0.18s ease' }}
      >
        {/* Header */}
        <div className="shrink-0 px-6 pt-5 pb-4 border-b border-outline-variant/20">
          <div className="flex items-start gap-4">
            <CompanyLogo name={company.name_display} size="lg" />
            <div className="flex-1 min-w-0">
              <h2 className="font-bold text-lg text-on-surface leading-snug">{company.name_display}</h2>
              {subtitle && <p className="text-xs text-on-surface-variant mt-0.5">{subtitle}</p>}
            </div>
            <button
              onClick={onClose}
              className="shrink-0 w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
            </button>
          </div>
        </div>

        {/* Scrollable body */}
        <div className="flex-1 overflow-y-auto">
          {/* Sector editor */}
          <div className="px-6 py-4 border-b border-outline-variant/20">
            <p className="text-[10px] font-bold text-outline uppercase tracking-widest mb-3">Sector</p>
            {canEditSector ? (
              <div className="flex flex-col gap-2">
                <select
                  value={editSector}
                  onChange={(e) => setEditSector(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/40 text-sm text-on-surface focus:outline-none focus:border-primary"
                >
                  <option value="">— None —</option>
                  {sectors.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
                <input
                  list="subsector-suggestions"
                  value={editSubsector}
                  onChange={(e) => setEditSubsector(e.target.value)}
                  placeholder="Subsector (optional)"
                  className="w-full px-3 py-2 rounded-lg bg-surface-container border border-outline-variant/40 text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary"
                />
                <datalist id="subsector-suggestions">
                  {subsectors.map((s) => <option key={s} value={s} />)}
                </datalist>
                {sectorChanged && (
                  <button
                    onClick={handleSaveSector}
                    disabled={updateSector.isPending}
                    className="self-end px-4 py-1.5 rounded-lg bg-primary text-on-primary text-xs font-semibold hover:opacity-90 transition-opacity disabled:opacity-50"
                  >
                    {updateSector.isPending ? 'Saving…' : 'Save'}
                  </button>
                )}
              </div>
            ) : (
              <p className="text-xs text-outline italic">Company not yet enriched — sector editing unavailable.</p>
            )}
          </div>

          {/* About section */}
          {company.what_they_do && (
            <div className="px-6 py-4 border-b border-outline-variant/20">
              <p className="text-[10px] font-bold text-outline uppercase tracking-widest mb-2">About the Company</p>
              <p className="text-sm text-on-surface-variant leading-relaxed">{company.what_they_do}</p>
            </div>
          )}

          {/* Open positions header */}
          <div className="px-6 pt-4 pb-2 flex items-center gap-2">
            <p className="text-[10px] font-bold text-outline uppercase tracking-widest">Open Positions</p>
            {!isLoading && jobs.length > 0 && (
              <span className="px-2 py-0.5 rounded-full text-[10px] font-bold bg-success/15 text-success">
                {jobs.length} NEW
              </span>
            )}
          </div>

          {isLoading && (
            <div className="flex justify-center py-12">
              <span className="w-5 h-5 rounded-full border-2 border-primary border-t-transparent animate-spin" />
            </div>
          )}

          {!isLoading && jobs.length === 0 && (
            <div className="flex flex-col items-center justify-center py-12 gap-3 text-center px-6">
              <span className="material-symbols-outlined text-outline" style={{ fontSize: 36 }}>work_off</span>
              <p className="text-sm font-semibold text-on-surface">No open jobs</p>
              <p className="text-xs text-on-surface-variant">No active listings for this company right now.</p>
            </div>
          )}

          {!isLoading && jobs.length > 0 && (
            <div className="divide-y divide-outline-variant/10">
              {jobs.map((job: any) => {
                const rejecting = updateStatus.isPending && updateStatus.variables?.jobId === job.id
                return (
                  <div
                    key={job.id}
                    className={`group/row w-full px-6 py-3.5 hover:bg-surface-container transition-colors flex items-center gap-3 ${rejecting ? 'opacity-50 pointer-events-none' : ''}`}
                  >
                    <button
                      onClick={() => navigate(`/jobs/${job.id}`)}
                      className="flex-1 min-w-0 text-left"
                    >
                      <p className="text-sm font-medium text-on-surface truncate">{job.title}</p>
                      {job.location && (
                        <p className="text-[11px] text-on-surface-variant mt-0.5">{job.location}</p>
                      )}
                    </button>
                    <div className="shrink-0 flex items-center gap-2">
                      {job.fit_score != null && (
                        <span className={`px-1.5 py-0.5 rounded-full text-[11px] font-bold ${fitColor(job.fit_score)}`}>
                          {job.fit_score}
                        </span>
                      )}
                      <span className="text-[10px] text-outline">{daysAgo(job.date_posted)}</span>
                      <button
                        onClick={() => handleReject(job.id)}
                        disabled={rejecting}
                        title="Reject this job"
                        aria-label="Reject this job"
                        className="w-7 h-7 flex items-center justify-center rounded-full text-outline hover:text-error hover:bg-error/10 transition-colors"
                      >
                        <span className="material-symbols-outlined" style={{ fontSize: 16 }}>block</span>
                      </button>
                    </div>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Sticky footer */}
        <div className="shrink-0 px-6 py-4 border-t border-outline-variant/20 flex gap-2">
          <button
            onClick={() => navigate('/jobs')}
            className="flex-1 py-2.5 rounded-xl bg-primary text-on-primary font-semibold text-sm hover:opacity-90 transition-opacity"
          >
            View All Jobs
          </button>
          <button
            className="w-10 h-10 flex items-center justify-center rounded-xl bg-surface-container-high text-on-surface-variant hover:text-on-surface transition-colors"
            aria-label="Share"
            onClick={() => {
              if (navigator.share) navigator.share({ title: company.name_display, url: window.location.href })
            }}
          >
            <span className="material-symbols-outlined" style={{ fontSize: 18 }}>share</span>
          </button>
        </div>

        {/* Toast */}
        {toast && (
          <div
            className={`absolute bottom-20 left-1/2 -translate-x-1/2 px-4 py-2 rounded-xl text-sm font-semibold shadow-lg pointer-events-none transition-all ${
              toast.ok ? 'bg-success text-white' : 'bg-error text-white'
            }`}
          >
            {toast.msg}
          </div>
        )}
      </div>

      <style>{`
        @keyframes slideInRight {
          from { transform: translateX(100%); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
      `}</style>
    </div>
  )
}

// ── Section Header ────────────────────────────────────────────────────────────

function SectionHeader({
  title,
  companyCount,
  jobCount,
  collapsed,
  onToggle,
}: {
  title: string
  companyCount: number
  jobCount: number
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <button
      onClick={onToggle}
      className="group w-full flex items-center gap-3 hover:opacity-80 transition-opacity text-left"
    >
      <span
        className="material-symbols-outlined text-outline shrink-0 transition-transform duration-150"
        style={{ fontSize: 16, transform: collapsed ? 'rotate(-90deg)' : 'rotate(0deg)' }}
      >
        expand_more
      </span>
      <h3 className="font-headline font-bold text-sm text-on-surface capitalize whitespace-nowrap">{title}</h3>
      <span className="text-xs text-outline whitespace-nowrap">
        {companyCount} {companyCount === 1 ? 'co' : 'cos'} · {jobCount} {jobCount === 1 ? 'job' : 'jobs'}
      </span>
      <div className="flex-1 h-px bg-outline-variant/20" />
    </button>
  )
}

// ── Card Grid ─────────────────────────────────────────────────────────────────

function CardGrid({
  items,
  groupKey,
  groupBy,
  onCardClick,
}: {
  items: CompanyOverviewItem[]
  groupKey: string
  groupBy: GroupBy
  onCardClick: (item: CompanyOverviewItem, loc: string | null, count: number) => void
}) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
      {items.map((item) => {
        const loc = groupBy === 'location' ? groupKey : null
        const count = loc ? locationCountFor(item, loc) : item.total_active_jobs
        return (
          <CompanyCard
            key={`${item.company}-${groupKey}`}
            item={item}
            locationContext={loc}
            locationCount={count}
            onClick={() => onCardClick(item, loc, count)}
          />
        )
      })}
    </div>
  )
}

// ── Group Section ─────────────────────────────────────────────────────────────

function GroupSection({
  groupKey,
  items,
  groupBy,
  subGroupBy,
  onCardClick,
}: {
  groupKey: string
  items: CompanyOverviewItem[]
  groupBy: GroupBy
  subGroupBy: GroupBy | null
  onCardClick: (item: CompanyOverviewItem, loc: string | null, count: number) => void
}) {
  const [collapsed, setCollapsed] = useState(true)
  const jobCount = groupJobCount(items, groupKey, groupBy)

  const header = (
    <SectionHeader
      title={groupKey}
      companyCount={items.length}
      jobCount={jobCount}
      collapsed={collapsed}
      onToggle={() => setCollapsed((c) => !c)}
    />
  )

  if (!subGroupBy) {
    return (
      <div className="space-y-3">
        {header}
        {!collapsed && (
          <CardGrid items={items} groupKey={groupKey} groupBy={groupBy} onCardClick={onCardClick} />
        )}
      </div>
    )
  }

  const subGroups = buildGroups(items, subGroupBy)

  return (
    <div className="space-y-3">
      {header}
      {!collapsed && (
        <div className="pl-4 border-l-2 border-outline-variant/15 space-y-5">
          {[...subGroups.entries()].map(([subKey, subItems]) => {
            const subJobCount = groupJobCount(subItems, subKey, subGroupBy)
            return (
              <div key={subKey} className="space-y-2.5">
                <div className="flex items-center gap-2">
                  <p className="text-[11px] font-bold text-on-surface-variant uppercase tracking-wider">{subKey}</p>
                  <span className="text-[10px] text-outline">{subItems.length} cos · {subJobCount} jobs</span>
                  <div className="flex-1 h-px bg-outline-variant/10" />
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
                  {subItems.map((item) => {
                    const loc = subGroupBy === 'location' ? subKey : groupBy === 'location' ? groupKey : null
                    const count = loc ? locationCountFor(item, loc) : item.total_active_jobs
                    return (
                      <CompanyCard
                        key={`${item.company}-${groupKey}-${subKey}`}
                        item={item}
                        locationContext={loc}
                        locationCount={count}
                        onClick={() => onCardClick(item, loc, count)}
                      />
                    )
                  })}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

// ── Main Page ─────────────────────────────────────────────────────────────────

export default function Companies() {
  const session = useMemo(loadSession, [])
  const [search, setSearch] = useState(session.search ?? '')
  const [typeFilter, setTypeFilter] = useState(session.typeFilter ?? '')
  const [daysFilter, setDaysFilter] = useState<number>(session.daysFilter ?? 0)
  const [flatMode, setFlatMode] = useState<boolean>(loadFlatMode)
  const [groupBy, setGroupBy] = useState<GroupBy>(loadGroupBy)
  const [subGroupBy, setSubGroupBy] = useState<GroupBy | null>(session.subGroupBy ?? null)
  const [panel, setPanel] = useState<PanelState | null>(null)
  const scrollRestored = useRef(false)

  const { data, isLoading, error } = useCompaniesOverview()
  const companies = data ?? []

  // Persist transient filter state so the back button restores it
  useEffect(() => { saveSession({ search }) }, [search])
  useEffect(() => { saveSession({ typeFilter }) }, [typeFilter])
  useEffect(() => { saveSession({ daysFilter }) }, [daysFilter])
  useEffect(() => { saveSession({ subGroupBy }) }, [subGroupBy])

  // Save scroll position when leaving the page
  useEffect(() => {
    return () => {
      const el = document.getElementById('main-scroll')
      if (el) saveSession({ scrollTop: el.scrollTop })
    }
  }, [])

  // Restore scroll once data has loaded
  useEffect(() => {
    if (!isLoading && !scrollRestored.current) {
      scrollRestored.current = true
      const top = loadSession().scrollTop
      if (top) {
        const el = document.getElementById('main-scroll')
        if (el) el.scrollTop = top
      }
    }
  }, [isLoading])

  // Distinct company types for filter chips
  const allTypes = useMemo(() => {
    const set = new Set<string>()
    for (const c of companies) if (c.company_type) set.add(c.company_type)
    return Array.from(set).sort()
  }, [companies])

  // Filtered list (search + type chip)
  const filtered = useMemo(() => {
    const cutoff = daysFilter > 0 ? Date.now() - daysFilter * 86_400_000 : null
    return companies.filter((item) => {
      if (typeFilter && item.company_type !== typeFilter) return false
      if (cutoff != null) {
        if (!item.last_scraped_at) return false
        if (new Date(item.last_scraped_at).getTime() < cutoff) return false
      }
      if (search) {
        const q = search.toLowerCase()
        return (
          item.name_display.toLowerCase().includes(q) ||
          (item.sector || '').toLowerCase().includes(q) ||
          (item.company_type || '').toLowerCase().includes(q) ||
          item.location_breakdown.some((l) => (l.location || '').toLowerCase().includes(q))
        )
      }
      return true
    })
  }, [companies, search, typeFilter, daysFilter])

  // Groups for grouped mode — built from filtered list
  const groups = useMemo(() => buildGroups(filtered, groupBy), [filtered, groupBy])

  const totalJobs = filtered.reduce((sum, c) => sum + c.total_active_jobs, 0)

  function handleGroupByChange(g: GroupBy) {
    setGroupBy(g)
    saveGroupBy(g)
    if (subGroupBy === g) setSubGroupBy(null)
  }

  function handleFlatToggle(v: boolean) {
    setFlatMode(v)
    saveFlatMode(v)
  }

  return (
    <Layout title="Companies" active="companies">
      <div className="space-y-5">

        {/* Search + view-mode toggle row */}
        <div className="flex flex-wrap items-center gap-3">
          <div className="relative flex-1 min-w-[200px]">
            <span
              className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-outline pointer-events-none"
              style={{ fontSize: 16 }}
            >
              search
            </span>
            <input
              type="search"
              placeholder="Search companies, sectors, locations…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-8 pr-4 py-2 bg-surface-container-lowest border border-outline-variant/30 rounded-xl text-sm text-on-surface placeholder:text-outline focus:outline-none focus:border-primary/50 focus:ring-1 focus:ring-primary/20"
            />
          </div>

          {/* Scraped-within filter */}
          <div className="flex items-center bg-surface-container-low rounded-lg overflow-hidden shrink-0">
            <span className="pl-3 pr-1 material-symbols-outlined text-outline" style={{ fontSize: 16 }}>schedule</span>
            <select
              value={daysFilter}
              onChange={(e) => setDaysFilter(Number(e.target.value))}
              title="Show companies scraped within"
              className="pl-1 pr-3 py-2 bg-transparent border-none text-sm text-on-surface focus:outline-none cursor-pointer"
            >
              {DAYS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>{o.label}</option>
              ))}
            </select>
          </div>

          {/* Flat / Grouped toggle */}
          <div className="flex items-center bg-surface-container-low rounded-lg overflow-hidden shrink-0">
            <button
              onClick={() => handleFlatToggle(true)}
              title="Grid view"
              className={`px-3 py-2 flex items-center transition-colors ${
                flatMode ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
              }`}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>grid_view</span>
            </button>
            <button
              onClick={() => handleFlatToggle(false)}
              title="Grouped view"
              className={`px-3 py-2 flex items-center transition-colors ${
                !flatMode ? 'bg-primary text-on-primary' : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
              }`}
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>view_agenda</span>
            </button>
          </div>
        </div>

        {/* Type filter chips */}
        {!isLoading && allTypes.length > 0 && (
          <div className="flex gap-2 overflow-x-auto pb-1" style={{ scrollbarWidth: 'none' }}>
            <button
              onClick={() => setTypeFilter('')}
              className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors shrink-0 ${
                typeFilter === ''
                  ? 'bg-primary text-on-primary'
                  : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest'
              }`}
            >
              All Types
            </button>
            {allTypes.map((type) => (
              <button
                key={type}
                onClick={() => setTypeFilter(type === typeFilter ? '' : type)}
                className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap transition-colors shrink-0 ${
                  typeFilter === type
                    ? 'bg-primary text-on-primary'
                    : 'bg-surface-container-high text-on-surface-variant hover:text-on-surface hover:bg-surface-container-highest'
                }`}
              >
                {type}
              </button>
            ))}
          </div>
        )}

        {/* Group-by controls — only in grouped mode */}
        {!flatMode && (
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center bg-surface-container-low rounded-lg overflow-hidden shrink-0">
              <span className="pl-3 pr-2 text-[11px] font-bold text-outline uppercase tracking-wider">Group</span>
              {ALL_GROUPS.map((g) => (
                <button
                  key={g}
                  onClick={() => handleGroupByChange(g)}
                  className={`px-3 py-2 text-sm font-medium transition-colors ${
                    groupBy === g
                      ? 'bg-primary text-on-primary'
                      : 'text-on-surface-variant hover:text-on-surface hover:bg-surface-container'
                  }`}
                >
                  {GROUP_LABELS[g]}
                </button>
              ))}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] font-bold text-outline uppercase tracking-wider">Then by</span>
              <select
                value={subGroupBy ?? ''}
                onChange={(e) => setSubGroupBy((e.target.value as GroupBy) || null)}
                className="px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                <option value="">None</option>
                {ALL_GROUPS.filter((g) => g !== groupBy).map((g) => (
                  <option key={g} value={g}>{GROUP_LABELS[g]}</option>
                ))}
              </select>
            </div>
          </div>
        )}

        {/* Summary line */}
        {!isLoading && filtered.length > 0 && (
          <p className="text-xs text-outline">
            <span className="font-semibold text-on-surface-variant">{filtered.length}</span>{' '}
            {filtered.length === 1 ? 'company' : 'companies'}
            {companies.length !== filtered.length && ` of ${companies.length}`}
            {' · '}
            <span className="font-semibold text-on-surface-variant">{totalJobs}</span>{' '}
            active {totalJobs === 1 ? 'job' : 'jobs'}
          </p>
        )}

        {/* Loading skeletons */}
        {isLoading && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {[0, 1, 2, 3, 4, 5].map((i) => <SkeletonCard key={i} />)}
          </div>
        )}

        {/* Error */}
        {error && (
          <div className="flex items-center gap-2 px-4 py-3 bg-error/10 rounded-xl text-sm text-error">
            <span className="material-symbols-outlined shrink-0" style={{ fontSize: 18 }}>error</span>
            {(error as Error).message}
          </div>
        )}

        {/* Empty state — no companies at all */}
        {!isLoading && !error && companies.length === 0 && (
          <div className="flex flex-col items-center justify-center py-24 gap-4 text-center">
            <span className="material-symbols-outlined text-outline" style={{ fontSize: 48 }}>apartment</span>
            <p className="text-lg font-extrabold font-headline text-on-surface">No companies with valid job postings yet</p>
            <p className="text-sm text-on-surface-variant">Run a scrape to discover companies.</p>
          </div>
        )}

        {/* No results after filter */}
        {!isLoading && !error && companies.length > 0 && filtered.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 gap-3 text-center">
            <span className="material-symbols-outlined text-outline" style={{ fontSize: 40 }}>search_off</span>
            <p className="text-base font-semibold text-on-surface">No results found</p>
            <p className="text-sm text-on-surface-variant">Try a different search or filter.</p>
          </div>
        )}

        {/* Flat grid */}
        {!isLoading && !error && filtered.length > 0 && flatMode && (
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
            {filtered.map((item) => (
              <CompanyCard
                key={item.company}
                item={item}
                locationContext={null}
                locationCount={item.total_active_jobs}
                onClick={() => setPanel({ company: item, locationContext: null, locationCount: item.total_active_jobs })}
              />
            ))}
          </div>
        )}

        {/* Grouped view */}
        {!isLoading && !error && filtered.length > 0 && !flatMode && (
          <div className="space-y-8">
            {[...groups.entries()].map(([groupKey, groupItems]) => (
              <GroupSection
                key={groupKey}
                groupKey={groupKey}
                items={groupItems}
                groupBy={groupBy}
                subGroupBy={subGroupBy}
                onCardClick={(item, loc, count) => setPanel({ company: item, locationContext: loc, locationCount: count })}
              />
            ))}
          </div>
        )}
      </div>

      {/* Detail drawer */}
      {panel && (
        <CompanyJobsPanel state={panel} onClose={() => setPanel(null)} />
      )}
    </Layout>
  )
}
