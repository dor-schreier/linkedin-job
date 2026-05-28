import { useState } from 'react'
import Layout from '../components/Layout'
import { useHistory } from '../api/queries'

interface ScrapeLog {
  id: number
  started_at: string
  finished_at: string | null
  jobs_found: number | null
  jobs_new: number | null
  status: string
  error: string | null
  trigger: string | null
  linkedin_count: number | null
  indeed_count: number | null
  glassdoor_count: number | null
  comeet_count: number | null
  filter_blocked: number | null
  filter_keywords: number | null
  filter_salary: number | null
  filter_remote: number | null
  jobs_scored: number | null
  score_failed: number | null
}

function durationStr(started: string, finished: string | null): string {
  if (!finished) return '—'
  const ms = new Date(finished).getTime() - new Date(started).getTime()
  const s = Math.round(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return rem > 0 ? `${m}m ${rem}s` : `${m}m`
}

function fmt(n: number | null | undefined): string {
  return n == null ? '—' : String(n)
}

function TriggerBadge({ trigger }: { trigger: string | null }) {
  if (trigger === 'manual') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-primary/15 text-primary">
        <span className="material-symbols-outlined" style={{ fontSize: 12 }}>person</span>
        Manual
      </span>
    )
  }
  if (trigger === 'scheduled') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-surface-container-high text-on-surface-variant">
        <span className="material-symbols-outlined" style={{ fontSize: 12 }}>schedule</span>
        Scheduled
      </span>
    )
  }
  return <span className="text-on-surface-variant text-xs">—</span>
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'success') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-500/15 text-green-700 dark:text-green-400">
        <span className="material-symbols-outlined" style={{ fontSize: 12 }}>check_circle</span>
        Success
      </span>
    )
  }
  if (status === 'error') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-error/15 text-error">
        <span className="material-symbols-outlined" style={{ fontSize: 12 }}>error</span>
        Error
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-500/15 text-yellow-700 dark:text-yellow-400">
      <span className="material-symbols-outlined" style={{ fontSize: 12 }}>hourglass_top</span>
      Running
    </span>
  )
}

function SourceCounts({ log }: { log: ScrapeLog }) {
  const parts: string[] = []
  if (log.linkedin_count != null) parts.push(`LI ${log.linkedin_count}`)
  if (log.indeed_count != null) parts.push(`In ${log.indeed_count}`)
  if (log.glassdoor_count != null) parts.push(`GD ${log.glassdoor_count}`)
  if (log.comeet_count != null) parts.push(`CM ${log.comeet_count}`)
  if (parts.length === 0) return <span className="text-on-surface-variant">—</span>
  return <span className="font-mono text-xs">{parts.join(' · ')}</span>
}

function ExpandedRow({ log }: { log: ScrapeLog }) {
  return (
    <tr className="bg-surface-container-low/50">
      <td colSpan={9} className="px-6 py-3">
        <div className="flex flex-wrap gap-6 text-sm text-on-surface-variant">
          <div>
            <span className="font-semibold text-on-surface">Filter breakdown</span>
            <div className="mt-1 space-y-0.5 font-mono text-xs">
              <div>Blocked companies: {fmt(log.filter_blocked)}</div>
              <div>Exclude keywords: {fmt(log.filter_keywords)}</div>
              <div>Min salary: {fmt(log.filter_salary)}</div>
              <div>Remote filtered: {fmt(log.filter_remote)}</div>
            </div>
          </div>
          <div>
            <span className="font-semibold text-on-surface">Scoring</span>
            <div className="mt-1 space-y-0.5 font-mono text-xs">
              <div>Scored: {fmt(log.jobs_scored)}</div>
              <div>Score failed: {fmt(log.score_failed)}</div>
            </div>
          </div>
          {log.error && (
            <div className="flex-1 min-w-0">
              <span className="font-semibold text-error">Error</span>
              <div className="mt-1 font-mono text-xs text-error/80 break-all line-clamp-4">
                {log.error}
              </div>
            </div>
          )}
        </div>
      </td>
    </tr>
  )
}

const PAGE_SIZE = 25

export default function History() {
  const [page, setPage] = useState(1)
  const [expanded, setExpanded] = useState<Set<number>>(new Set())

  const { data, isLoading, isError } = useHistory(page, PAGE_SIZE)

  const items: ScrapeLog[] = (data as any)?.items ?? []
  const total: number = (data as any)?.total ?? 0
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE))

  function toggleRow(id: number) {
    setExpanded((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  return (
    <Layout title="Scrape History" active="history">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <p className="text-sm text-on-surface-variant">{total} run{total !== 1 ? 's' : ''} total</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg text-sm bg-surface-container border border-outline-variant disabled:opacity-40 hover:bg-surface-container-high transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>chevron_left</span>
            </button>
            <span className="text-sm text-on-surface-variant px-1">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg text-sm bg-surface-container border border-outline-variant disabled:opacity-40 hover:bg-surface-container-high transition-colors"
            >
              <span className="material-symbols-outlined" style={{ fontSize: 16 }}>chevron_right</span>
            </button>
          </div>
        </div>

        {isLoading && (
          <div className="text-on-surface-variant text-sm py-12 text-center">Loading...</div>
        )}
        {isError && (
          <div className="text-error text-sm py-12 text-center">Failed to load scrape history.</div>
        )}
        {!isLoading && !isError && items.length === 0 && (
          <div className="text-on-surface-variant text-sm py-12 text-center">No scrape runs recorded yet.</div>
        )}

        {items.length > 0 && (
          <div className="rounded-xl border border-outline-variant overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-surface-container text-on-surface-variant text-xs uppercase tracking-wide">
                <tr>
                  <th className="px-4 py-3 text-left">Started</th>
                  <th className="px-4 py-3 text-left">Trigger</th>
                  <th className="px-4 py-3 text-left">Duration</th>
                  <th className="px-4 py-3 text-left">Sources</th>
                  <th className="px-4 py-3 text-right">Found</th>
                  <th className="px-4 py-3 text-right">New</th>
                  <th className="px-4 py-3 text-right">Filtered</th>
                  <th className="px-4 py-3 text-right">Scored</th>
                  <th className="px-4 py-3 text-left">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant/30">
                {items.map((log) => {
                  const isExpanded = expanded.has(log.id)
                  const totalFiltered =
                    (log.filter_blocked ?? 0) +
                    (log.filter_keywords ?? 0) +
                    (log.filter_salary ?? 0) +
                    (log.filter_remote ?? 0)
                  const hasDetail = log.error || log.filter_blocked != null || log.jobs_scored != null
                  return (
                    <>
                      <tr
                        key={log.id}
                        onClick={() => hasDetail && toggleRow(log.id)}
                        className={`transition-colors ${hasDetail ? 'cursor-pointer hover:bg-surface-container/60' : ''}`}
                      >
                        <td className="px-4 py-3 whitespace-nowrap text-on-surface-variant font-mono text-xs">
                          {new Date(log.started_at).toLocaleString()}
                        </td>
                        <td className="px-4 py-3">
                          <TriggerBadge trigger={log.trigger} />
                        </td>
                        <td className="px-4 py-3 font-mono text-xs text-on-surface-variant">
                          {durationStr(log.started_at, log.finished_at)}
                        </td>
                        <td className="px-4 py-3">
                          <SourceCounts log={log} />
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">{fmt(log.jobs_found)}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-primary">{fmt(log.jobs_new)}</td>
                        <td className="px-4 py-3 text-right font-mono text-xs text-on-surface-variant">
                          {totalFiltered > 0 ? totalFiltered : '—'}
                        </td>
                        <td className="px-4 py-3 text-right font-mono text-xs">{fmt(log.jobs_scored)}</td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5">
                            <StatusBadge status={log.status} />
                            {hasDetail && (
                              <span className="material-symbols-outlined text-on-surface-variant" style={{ fontSize: 16 }}>
                                {isExpanded ? 'expand_less' : 'expand_more'}
                              </span>
                            )}
                          </div>
                        </td>
                      </tr>
                      {isExpanded && <ExpandedRow key={`${log.id}-expanded`} log={log} />}
                    </>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        {totalPages > 1 && (
          <div className="flex items-center justify-center gap-2 pt-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1.5 rounded-lg text-sm bg-surface-container border border-outline-variant disabled:opacity-40 hover:bg-surface-container-high transition-colors"
            >
              Previous
            </button>
            <span className="text-sm text-on-surface-variant">Page {page} of {totalPages}</span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1.5 rounded-lg text-sm bg-surface-container border border-outline-variant disabled:opacity-40 hover:bg-surface-container-high transition-colors"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </Layout>
  )
}
