import { useState } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import { useScheduler, useSchedulerToggle, useSchedulerRunNow, useSchedulerConfig, useCleanupRunNow } from '../api/queries'

export default function Scheduler() {
  const { data, isLoading } = useScheduler()
  const toggle = useSchedulerToggle()
  const runNow = useSchedulerRunNow()
  const saveConfig = useSchedulerConfig()
  const cleanupRun = useCleanupRunNow()
  const [intervalHours, setIntervalHours] = useState<string>('')

  const cfg = (data as any)?.config
  const logs: any[] = (data as any)?.scrape_logs ?? []
  const cleanupLastRun = (data as any)?.cleanup_last_run_at
  const cleanupResult = (data as any)?.cleanup_last_result

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
