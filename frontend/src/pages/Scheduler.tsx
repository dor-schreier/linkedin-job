import { useState } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import { useScheduler, useSchedulerToggle, useSchedulerRunNow, useSchedulerConfig, useCleanupRunNow, useCleanupSources, useCleanupLimit, useCleanupSkipValidated } from '../api/queries'

export default function Scheduler() {
  const { data, isLoading } = useScheduler()
  const toggle = useSchedulerToggle()
  const runNow = useSchedulerRunNow()
  const saveConfig = useSchedulerConfig()
  const cleanupRun = useCleanupRunNow()
  const cleanupSources = useCleanupSources()
  const cleanupLimit = useCleanupLimit()
  const cleanupSkipValidated = useCleanupSkipValidated()
  const [intervalHours, setIntervalHours] = useState<string>('')
  const [limitInput, setLimitInput] = useState<string>('')
  const [skipHoursInput, setSkipHoursInput] = useState<string>('')

  const cfg = (data as any)?.config
  const logs: any[] = (data as any)?.scrape_logs ?? []
  const cleanupLastRun = (data as any)?.cleanup_last_run_at
  const cleanupResult = (data as any)?.cleanup_last_result

  // null cleanup_sources means "all sources"; reflect that as every box checked.
  const availableSources: string[] = (data as any)?.available_sources ?? []
  const selectedSources: string[] | null = (data as any)?.cleanup_sources ?? null
  const isSourceSelected = (s: string) => (selectedSources === null ? true : selectedSources.includes(s))
  const savedLimit: number | null = (data as any)?.cleanup_limit ?? null
  const savedSkipHours: number | null = (data as any)?.cleanup_skip_validated_hours ?? null

  function toggleSource(s: string) {
    const current = selectedSources === null ? [...availableSources] : [...selectedSources]
    const next = current.includes(s) ? current.filter((x) => x !== s) : [...current, s]
    cleanupSources.mutate(next)
  }

  function handleSaveLimit(e: React.FormEvent) {
    e.preventDefault()
    const n = parseInt(limitInput)
    cleanupLimit.mutate(Number.isFinite(n) && n > 0 ? n : 0)
  }

  function handleSaveSkipHours(e: React.FormEvent) {
    e.preventDefault()
    const n = parseInt(skipHoursInput)
    cleanupSkipValidated.mutate(Number.isFinite(n) && n > 0 ? n : 0)
  }

  function handleSaveConfig(e: React.FormEvent) {
    e.preventDefault()
    const h = parseInt(intervalHours)
    if (h >= 1) saveConfig.mutate(h)
  }

  return (
    <Layout title="Scheduler">
      <div className="max-w-3xl space-y-6">

        {/* Status card */}
        <Card title="Scheduler Status">
          {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}
          {cfg && (
            <div className="space-y-4">
              <div className="flex items-center gap-4">
                <Badge color={cfg.is_enabled ? 'green' : 'default'}>
                  {cfg.is_enabled ? 'Enabled' : 'Disabled'}
                </Badge>
                {cfg.is_running && <Badge color="blue">Running</Badge>}
                <span className="text-sm text-on-surface-variant">Every {cfg.interval_hours}h</span>
                {cfg.next_run && (
                  <span className="text-sm text-on-surface-variant">
                    Next: {new Date(cfg.next_run).toLocaleString()}
                  </span>
                )}
              </div>
              <Button
                variant="secondary"
                onClick={() => toggle.mutate()}
                loading={toggle.isPending}
              >
                {cfg.is_enabled ? 'Disable' : 'Enable'} Scheduler
              </Button>
            </div>
          )}
        </Card>

        {/* Interval config */}
        <Card title="Configure Interval">
          <form onSubmit={handleSaveConfig} className="flex items-end gap-4">
            <div className="flex-1">
              <Input
                label="Run every N hours"
                type="number"
                min={1}
                max={168}
                placeholder={cfg ? String(cfg.interval_hours) : '6'}
                value={intervalHours}
                onChange={(e) => setIntervalHours(e.target.value)}
              />
            </div>
            <Button type="submit" loading={saveConfig.isPending}>Save</Button>
          </form>
        </Card>

        {/* Manual run */}
        <Card title="Manual Run">
          <p className="text-sm text-on-surface-variant mb-4">
            Trigger an immediate scrape across all active search configs.
          </p>
          <div className="flex items-center gap-4">
            <Button
              variant="secondary"
              icon="play_circle"
              onClick={() => runNow.mutate()}
              loading={runNow.isPending}
            >
              Run Now
            </Button>
            {runNow.isSuccess && (
              <span className="text-sm text-on-surface-variant">Started.</span>
            )}
          </div>
        </Card>

        {/* Cleanup */}
        <Card title="Cleanup Inactive Jobs">
          <p className="text-sm text-on-surface-variant mb-4">
            Re-checks each job's source URL and marks posts inactive when gone or closed.
            Runs automatically every 24 hours.
          </p>
          {cleanupLastRun && (
            <p className="text-xs text-outline mb-4">
              Last run: <span className="text-on-surface-variant">{new Date(cleanupLastRun).toLocaleString()}</span>
            </p>
          )}
          {availableSources.length > 0 && (
            <div className="mb-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-outline mb-2">Sources to check</p>
              <div className="flex flex-wrap gap-2">
                {availableSources.map((s) => {
                  const on = isSourceSelected(s)
                  return (
                    <button
                      key={s}
                      type="button"
                      onClick={() => toggleSource(s)}
                      disabled={cleanupSources.isPending}
                      className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-sm capitalize transition-colors disabled:opacity-50 ${
                        on
                          ? 'border-primary/40 bg-primary/10 text-primary'
                          : 'border-outline-variant/40 bg-transparent text-on-surface-variant'
                      }`}
                    >
                      <span className="material-symbols-outlined" style={{ fontSize: 16 }}>
                        {on ? 'check_circle' : 'radio_button_unchecked'}
                      </span>
                      {s}
                    </button>
                  )
                })}
              </div>
              <p className="mt-2 text-xs text-outline">
                Applies to both manual and scheduled runs. Tip: unchecking LinkedIn avoids automated checks against your logged-in account.
              </p>
            </div>
          )}
          <div className="mb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-outline mb-2">Jobs per run</p>
            <form onSubmit={handleSaveLimit} className="flex items-end gap-3">
              <div className="w-40">
                <Input
                  label="Max jobs to check"
                  type="number"
                  min={0}
                  placeholder={savedLimit ? String(savedLimit) : 'No limit'}
                  value={limitInput}
                  onChange={(e) => setLimitInput(e.target.value)}
                />
              </div>
              <Button type="submit" variant="secondary" loading={cleanupLimit.isPending}>Save</Button>
            </form>
            <p className="mt-2 text-xs text-outline">
              Checks the oldest jobs first (by scrape date). Currently:{' '}
              <span className="text-on-surface-variant">{savedLimit ? `${savedLimit} per run` : 'no limit (all jobs)'}</span>. Set 0 for no limit.
            </p>
          </div>
          <div className="mb-4">
            <p className="text-xs font-semibold uppercase tracking-wider text-outline mb-2">Skip recently validated</p>
            <form onSubmit={handleSaveSkipHours} className="flex items-end gap-3">
              <div className="w-40">
                <Input
                  label="Skip if checked within (hours)"
                  type="number"
                  min={0}
                  placeholder={savedSkipHours ? String(savedSkipHours) : 'Off'}
                  value={skipHoursInput}
                  onChange={(e) => setSkipHoursInput(e.target.value)}
                />
              </div>
              <Button type="submit" variant="secondary" loading={cleanupSkipValidated.isPending}>Save</Button>
            </form>
            <p className="mt-2 text-xs text-outline">
              Jobs with a confirmed active/inactive result in this window are skipped, so limited
              batches rotate through the backlog. Blocked checks are always retried. Currently:{' '}
              <span className="text-on-surface-variant">{savedSkipHours ? `skipping if validated in last ${savedSkipHours}h` : 'off (re-check every run)'}</span>. Set 0 to disable.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <Button
              variant="secondary"
              icon="cleaning_services"
              onClick={() => cleanupRun.mutate()}
              loading={cleanupRun.isPending}
            >
              Run Cleanup Now
            </Button>
            {cleanupResult && (
              <span className="text-sm text-on-surface-variant">
                {cleanupResult.checked} checked · {cleanupResult.marked_inactive} marked inactive
              </span>
            )}
          </div>
          {cleanupResult?.linkedin_auth_invalid && (
            <div className="mt-4 flex items-start gap-2 rounded-lg border border-warning/40 bg-warning/10 p-3 text-sm text-warning">
              <span className="material-symbols-outlined" style={{ fontSize: 18 }}>warning</span>
              <span>
                Your LinkedIn session cookie is missing or expired, so LinkedIn jobs couldn't be checked.
                Update <code className="font-mono text-xs">LINKEDIN_SESSION_COOKIE</code> in your <code className="font-mono text-xs">.env</code> and restart the app.
              </span>
            </div>
          )}
        </Card>

        {/* Scrape log */}
        <Card title="Recent Runs">
          {logs.length === 0 ? (
            <p className="text-sm text-outline">No scrape runs recorded yet.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-outline uppercase tracking-wider border-b border-outline-variant/20">
                    <th className="text-left pb-2 font-semibold">Started</th>
                    <th className="text-left pb-2 font-semibold">Duration</th>
                    <th className="text-right pb-2 font-semibold">Found</th>
                    <th className="text-right pb-2 font-semibold">New</th>
                    <th className="text-left pb-2 font-semibold pl-4">Status</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-outline-variant/10">
                  {logs.map((log: any) => {
                    const dur =
                      log.started_at && log.finished_at
                        ? Math.round(
                            (new Date(log.finished_at).getTime() - new Date(log.started_at).getTime()) / 1000
                          )
                        : null
                    return (
                      <tr key={log.id}>
                        <td className="py-2 text-on-surface-variant">
                          {log.started_at ? new Date(log.started_at).toLocaleString('en', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}
                        </td>
                        <td className="py-2 text-on-surface-variant">
                          {dur !== null
                            ? dur < 60 ? `${dur}s` : `${Math.floor(dur / 60)}m ${dur % 60}s`
                            : log.status === 'running'
                            ? <span className="text-primary animate-pulse">Running…</span>
                            : '—'}
                        </td>
                        <td className="py-2 text-right text-on-surface">{log.jobs_found ?? '—'}</td>
                        <td className="py-2 text-right text-on-surface">{log.jobs_new ?? '—'}</td>
                        <td className="py-2 pl-4">
                          <Badge color={log.status === 'success' ? 'green' : log.status === 'error' ? 'red' : 'default'}>
                            {log.status === 'success' ? 'OK' : log.status === 'error' ? 'Error' : 'Running'}
                          </Badge>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </Layout>
  )
}
