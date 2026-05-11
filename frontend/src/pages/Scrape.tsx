import { useState } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { useScrapeState, useScrapeRun, useScrapeStop, useScrapeConfig } from '../api/queries'
import { useNavigate } from 'react-router-dom'

const ALL_SOURCES = ['linkedin', 'indeed', 'comeet'] as const
type Source = typeof ALL_SOURCES[number]

const SOURCE_LABELS: Record<Source, string> = {
  linkedin: 'LinkedIn',
  indeed: 'Indeed',
  comeet: 'Comeet',
}

export default function Scrape() {
  const { data: status } = useScrapeState()
  const { data: page } = useScrapeConfig()
  const run = useScrapeRun()
  const stop = useScrapeStop()
  const navigate = useNavigate()
  const [selected, setSelected] = useState<Set<Source>>(new Set(ALL_SOURCES))

  const st = status as any
  const cfg = (page as any)?.latest_config
  const isRunning = st?.running ?? false
  const stopRequested = st?.stop_requested ?? false

  function toggleSource(src: Source) {
    setSelected(prev => {
      const next = new Set(prev)
      next.has(src) ? next.delete(src) : next.add(src)
      return next
    })
  }

  function handleRun() {
    run.mutate({ configId: cfg?.id, sites: [...selected] })
  }

  return (
    <Layout title="Find New Jobs" active="scrape">
      <div className="max-w-2xl space-y-6">

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
          {st?.last_result && (
            <div className="mt-3 text-sm text-on-surface-variant space-y-1">
              <p>{st.last_result.total_scraped} scraped · {st.last_result.inserted} new · {st.last_result.skipped} skipped</p>
            </div>
          )}
        </Card>

        {/* Active config */}
        {cfg && (
          <Card title="Active Search Config">
            <div className="text-sm space-y-2">
              {cfg.keywords && <Row label="Keywords" value={cfg.keywords} />}
              {cfg.location && <Row label="Location" value={cfg.location} />}
              {cfg.work_mode && <Row label="Work Mode" value={cfg.work_mode} />}
              {cfg.experience_level && <Row label="Experience" value={cfg.experience_level} />}
              {cfg.results_wanted && <Row label="Results" value={String(cfg.results_wanted)} />}
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate('/search-config')}
              className="mt-4 !px-0 !py-0 text-xs"
            >
              Edit config →
            </Button>
          </Card>
        )}

        {/* Run */}
        <Card title="Manual Scrape">
          <p className="text-sm text-on-surface-variant mb-3">
            Select sources and start an immediate scrape.
          </p>
          <div className="flex flex-wrap gap-2 mb-4">
            {ALL_SOURCES.map(src => (
              <button
                key={src}
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
              icon={isRunning ? undefined : 'search'}
              loading={isRunning || run.isPending}
              onClick={handleRun}
              disabled={isRunning || selected.size === 0}
            >
              {isRunning ? 'Scraping…' : 'Start Scrape'}
            </Button>
            {isRunning && (
              <Button
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <p>
      <span className="text-on-surface-variant">{label}: </span>
      <span className="text-on-surface font-medium">{value}</span>
    </p>
  )
}
