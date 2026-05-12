import { useState, useEffect } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import { useScrapeState, useScrapeRun, useScrapeStop, useSearchConfig, useSaveSearchConfig } from '../api/queries'
import { useForm } from '../lib/forms'

const ALL_SOURCES = ['linkedin', 'indeed', 'comeet'] as const
type Source = typeof ALL_SOURCES[number]

const SOURCE_LABELS: Record<Source, string> = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  comeet: 'Comeet',
}

type ScrapeProgressData = {
  phase?: string | null
  fetch_sources?: Record<string, number> | null
  rows_total?: number | null
  rows_done?: number | null
  inserted?: number | null
  skipped?: number | null
  scored?: number | null
  score_failed?: number | null
}

function ScrapeProgressPanel({ progress }: { progress: ScrapeProgressData }) {
  const { phase, fetch_sources, rows_total, rows_done, inserted, skipped, scored, score_failed } = progress
  const isProcessing = phase === 'processing'
  const isDone = phase === 'done'
  const pct = rows_total && rows_done != null ? Math.round((rows_done / rows_total) * 100) : 0
  const phaseLabel = phase === 'fetching' || phase === 'fetching_done' ? 'Fetching'
    : isProcessing ? 'Processing'
    : isDone ? 'Done'
    : 'Running'
  const hasSources = fetch_sources && Object.keys(fetch_sources).length > 0

  return (
    <div className="mt-3 space-y-2">
      <div className="flex items-center gap-2">
        {!isDone && (
          <svg className="animate-spin h-4 w-4 text-primary" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        <span className="text-sm font-medium text-on-surface">{phaseLabel}</span>
      </div>

      {hasSources && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(fetch_sources!).map(([src, count]) => (
            <span key={src} className="px-2 py-0.5 rounded-full text-xs bg-surface-variant text-on-surface-variant">
              {src.charAt(0).toUpperCase() + src.slice(1)} {count}
            </span>
          ))}
        </div>
      )}

      {isProcessing && rows_total != null && rows_done != null && (
        <div>
          <div className="h-1.5 bg-surface-variant rounded-full overflow-hidden">
            <div
              className="h-full bg-primary transition-all duration-300 rounded-full"
              style={{ width: `${pct}%` }}
            />
          </div>
          <p className="text-xs text-on-surface-variant mt-1">{rows_done} / {rows_total} rows</p>
        </div>
      )}

      {(inserted != null || skipped != null) && (
        <p className="text-xs text-on-surface-variant">
          {inserted ?? 0} new · {skipped ?? 0} skipped
        </p>
      )}

      {((scored ?? 0) > 0 || (score_failed ?? 0) > 0) && (
        <p className="text-xs text-on-surface-variant">
          {scored ?? 0} scored · {score_failed ?? 0} failed
        </p>
      )}
    </div>
  )
}

const initial = {
  keywords: '',
  location: '',
  experience_level: '',
  work_mode: '',
  role_level: '',
  country: '',
  max_age_hours: 72 as number | string,
  include_remote: false as boolean,
  include_comeet: false as boolean,
  exclude_keywords: '',
  blocked_companies: '',
  results_wanted: 50 as number | string,
  min_salary: '' as number | string,
}

export default function Scrape() {
  const { data: status } = useScrapeState()
  const { data: configData, isLoading: configLoading } = useSearchConfig()
  const run = useScrapeRun()
  const stop = useScrapeStop()
  const save = useSaveSearchConfig()
  const form = useForm(initial)
  const [selected, setSelected] = useState<Set<Source>>(new Set(ALL_SOURCES))

  useEffect(() => {
    if (configData) {
      const d = configData as any
      form.setValues({
        keywords: d.keywords ?? '',
        location: d.location ?? '',
        experience_level: d.experience_level ?? '',
        work_mode: d.work_mode ?? '',
        role_level: d.role_level ?? '',
        country: d.country ?? '',
        max_age_hours: d.max_age_hours ?? 72,
        include_remote: d.include_remote ?? false,
        include_comeet: d.include_comeet ?? false,
        exclude_keywords: d.exclude_keywords ?? '',
        blocked_companies: d.blocked_companies ?? '',
        results_wanted: d.results_wanted ?? 50,
        min_salary: d.min_salary ?? '',
      })
    }
  }, [configData])

  const st = status as any
  const isRunning = st?.running ?? false
  const stopRequested = st?.stop_requested ?? false
  const progress: ScrapeProgressData | null = st?.progress ?? null

  function toggleSource(src: Source) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(src) ? next.delete(src) : next.add(src)
      return next
    })
  }

  function handleRun() {
    run.mutate({ configId: (configData as any)?.id, sites: [...selected] })
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault()
    const v = form.values
    await save.mutateAsync({
      keywords: v.keywords || null,
      location: v.location || null,
      experience_level: v.experience_level || null,
      work_mode: v.work_mode || null,
      role_level: v.role_level || null,
      country: v.country || null,
      max_age_hours: v.max_age_hours ? Number(v.max_age_hours) : null,
      include_remote: v.include_remote,
      include_comeet: v.include_comeet,
      exclude_keywords: v.exclude_keywords || null,
      blocked_companies: v.blocked_companies || null,
      results_wanted: v.results_wanted ? Number(v.results_wanted) : 50,
      min_salary: v.min_salary ? Number(v.min_salary) : null,
    })
  }

  return (
    <Layout title="Find New Jobs" active="scrape">
      <div className="max-w-2xl space-y-6">

        {/* Config form */}
        {configLoading ? (
          <p className="text-sm text-on-surface-variant">Loading…</p>
        ) : (
          <form onSubmit={handleSave} className="space-y-6">
            <Card title="Search Parameters">
              <div className="space-y-4">
                <Input label="Keywords" id="keywords" placeholder="e.g. software engineer" {...form.bind('keywords')} />
                <div className="grid grid-cols-2 gap-4">
                  <Input label="Location" id="location" placeholder="e.g. New York" {...form.bind('location')} />
                  <Input label="Country" id="country" placeholder="e.g. USA" {...form.bind('country')} />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <Input label="Experience Level" id="experience_level" placeholder="e.g. mid-senior" {...form.bind('experience_level')} />
                  <Input label="Work Mode" id="work_mode" placeholder="e.g. remote, hybrid" {...form.bind('work_mode')} />
                </div>
                <Input label="Role Level" id="role_level" placeholder="e.g. senior, staff" {...form.bind('role_level')} />
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="include_remote"
                    checked={form.values.include_remote as boolean}
                    onChange={(e) => form.set('include_remote', e.target.checked as any)}
                    className="w-4 h-4 rounded"
                  />
                  <label htmlFor="include_remote" className="text-sm text-on-surface">Include remote jobs</label>
                </div>
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    id="include_comeet"
                    checked={form.values.include_comeet as boolean}
                    onChange={(e) => form.set('include_comeet', e.target.checked as any)}
                    className="w-4 h-4 rounded"
                  />
                  <label htmlFor="include_comeet" className="text-sm text-on-surface">Include Comeet jobs</label>
                </div>
              </div>
            </Card>

            <Card title="Filters">
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <Input label="Max age (hours)" id="max_age_hours" type="number" {...form.bind('max_age_hours')} />
                  <Input label="Results wanted" id="results_wanted" type="number" {...form.bind('results_wanted')} />
                </div>
                <Input label="Min salary" id="min_salary" type="number" placeholder="e.g. 80000" {...form.bind('min_salary')} />
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Exclude keywords</label>
                  <textarea
                    rows={2}
                    className="w-full px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="One per line"
                    value={form.values.exclude_keywords as string}
                    onChange={(e) => form.set('exclude_keywords', e.target.value as any)}
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Blocked companies</label>
                  <textarea
                    rows={2}
                    className="w-full px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="One per line"
                    value={form.values.blocked_companies as string}
                    onChange={(e) => form.set('blocked_companies', e.target.value as any)}
                  />
                </div>
              </div>
            </Card>

            <div className="flex items-center gap-4">
              <Button type="submit" loading={save.isPending} icon="save">Save Config</Button>
              {save.isSuccess && <span className="text-sm text-success">Saved.</span>}
              {save.isError && <span className="text-sm text-error">{(save.error as Error).message}</span>}
            </div>
          </form>
        )}

        {/* Status */}
        <Card title="Scrape Status">
          <div className="flex items-center gap-4">
            <Badge color={isRunning ? 'blue' : 'default'}>
              {isRunning ? (stopRequested ? 'Stopping…' : 'Running…') : 'Idle'}
            </Badge>
            {st?.error && (
              <span className="text-xs text-error">{st.error}</span>
            )}
          </div>
          {isRunning && progress ? (
            <ScrapeProgressPanel progress={progress} />
          ) : st?.last_result && (
            <div className="mt-3 text-sm text-on-surface-variant space-y-1">
              <p>{st.last_result.total_scraped} scraped · {st.last_result.inserted} new · {st.last_result.skipped} skipped</p>
            </div>
          )}
        </Card>

        {/* Run */}
        <Card title="Manual Scrape">
          <p className="text-sm text-on-surface-variant mb-3">
            Select sources and start an immediate scrape.
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {ALL_SOURCES.map(src => (
              <button
                key={src}
                type="button"
                onClick={() => toggleSource(src)}
                disabled={isRunning}
                className={[
                  'px-3 py-1.5 rounded-full text-sm font-medium border transition-colors disabled:opacity-50 disabled:cursor-not-allowed',
                  selected.has(src)
                    ? 'bg-primary text-on-primary border-primary'
                    : 'bg-transparent text-on-surface-variant border-outline-variant hover:border-outline',
                ].join(' ')}
              >
                {SOURCE_LABELS[src]}
              </button>
            ))}
          </div>
          <div className="flex items-center gap-4">
            <Button
              type="button"
              icon={isRunning ? undefined : 'search'}
              loading={isRunning || run.isPending}
              onClick={handleRun}
              disabled={isRunning || selected.size === 0}
            >
              {isRunning ? 'Scraping…' : 'Start Scrape'}
            </Button>
            {isRunning && (
              <Button
                type="button"
                variant="danger"
                icon="stop"
                loading={stop.isPending}
                onClick={() => stop.mutate()}
                disabled={stopRequested}
              >
                {stopRequested ? 'Stopping…' : 'Stop Scrape'}
              </Button>
            )}
            {run.isSuccess && !isRunning && (
              <span className="text-sm text-success">Started!</span>
            )}
          </div>
        </Card>

      </div>
    </Layout>
  )
}
