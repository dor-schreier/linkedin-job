import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { useWatchMatches, useMarkMatchesRead } from '../api/queries'
import { useNavigate } from 'react-router-dom'

export default function WatchMatches() {
  const { data: rows = [], isLoading } = useWatchMatches()
  const markRead = useMarkMatchesRead()
  const navigate = useNavigate()

  const unread = (rows as any[]).filter((r: any) => !r.is_read).length

  return (
    <Layout
      title="Watch Matches"
      active="watch-matches"
      headerRight={
        unread > 0 ? (
          <Button
            variant="secondary"
            icon="done_all"
            onClick={() => markRead.mutate()}
            loading={markRead.isPending}
          >
            Mark {unread} read
          </Button>
        ) : undefined
      }
    >
      <div className="max-w-4xl">
        <Card>
          {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}
          {!isLoading && (rows as any[]).length === 0 && (
            <p className="text-sm text-outline">No matches yet. Add watch rules to get notified.</p>
          )}
          <div className="space-y-3">
            {(rows as any[]).map((row: any) => (
              <div
                key={row.notification_id}
                onClick={() => navigate(`/jobs/${row.job_id}`)}
                className={`p-4 rounded-xl cursor-pointer transition-colors ${
                  row.is_read
                    ? 'bg-surface-container hover:bg-surface-container-high'
                    : 'bg-primary-container hover:bg-primary-container/80 border-l-2 border-primary'
                }`}
              >
                <div className="flex items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-on-surface">{row.job_title}</p>
                    <p className="text-xs text-on-surface-variant mt-0.5">{row.company}{row.location ? ` · ${row.location}` : ''}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge color="blue">{row.rule_type}: {row.rule_value}</Badge>
                    {!row.is_read && <Badge color="primary">new</Badge>}
                  </div>
                </div>
                <p className="text-xs text-outline mt-2">
                  {new Date(row.created_at).toLocaleString()}
                </p>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Layout>
  )
}
