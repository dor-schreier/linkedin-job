import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import { useProfileOptimizer, useProfileOptimizerAnalyze } from '../api/queries'
import { useNavigate } from 'react-router-dom'

export default function ProfileOptimizer() {
  const { data, isLoading } = useProfileOptimizer()
  const analyze = useProfileOptimizerAnalyze()
  const navigate = useNavigate()

  const d = data as any
  const analysis = d?.analysis
  const analyzedAt = d?.analyzed_at

  return (
    <Layout title="Profile Optimizer" active="profile-optimizer">
      <div className="max-w-3xl space-y-6">

        {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}

        {!d?.linkedin_url && !isLoading && (
          <Card>
            <p className="text-sm text-on-surface-variant mb-4">
              Save your LinkedIn URL on the Profile page before analyzing.
            </p>
            <Button variant="secondary" onClick={() => navigate('/profile')}>
              Go to Profile
            </Button>
          </Card>
        )}

        {d?.linkedin_url && (
          <Card title="LinkedIn Profile">
            <div className="flex items-center justify-between">
              <a
                href={d.linkedin_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-primary hover:underline"
              >
                {d.linkedin_url}
              </a>
              {analyzedAt && (
                <span className="text-xs text-outline">
                  Analyzed {new Date(analyzedAt).toLocaleDateString()}
                </span>
              )}
            </div>
            <div className="mt-4">
              <Button
                icon="auto_awesome"
                onClick={() => analyze.mutate()}
                loading={analyze.isPending}
              >
                {analysis ? 'Re-analyze' : 'Analyze Profile'}
              </Button>
              {analyze.isError && (
                <p className="text-xs text-error mt-2">{(analyze.error as Error).message}</p>
              )}
            </div>
          </Card>
        )}

        {analysis && (analysis.overall_score != null || analysis.top_priority) && (
          <Card title="Summary">
            {analysis.overall_score != null && (
              <div className="flex items-center gap-2 mb-3">
                <Badge color={analysis.overall_score >= 80 ? 'green' : analysis.overall_score >= 50 ? 'yellow' : 'red'}>
                  Overall: {analysis.overall_score}/100
                </Badge>
              </div>
            )}
            {analysis.top_priority && (
              <p className="text-sm text-on-surface">
                <span className="font-semibold text-primary">Top priority: </span>
                {analysis.top_priority}
              </p>
            )}
          </Card>
        )}

        {analysis?.sections && (
          <div className="space-y-4">
            {(analysis.sections as any[]).map((section: any, i: number) => (
              <Card key={i} title={section.name ?? section.title}>
                <div className="flex items-center gap-2 mb-3">
                  <Badge
                    color={
                      section.score >= 80 ? 'green' :
                      section.score >= 50 ? 'yellow' : 'red'
                    }
                  >
                    Score: {section.score}/100
                  </Badge>
                </div>
                {section.tasks?.length > 0 && (
                  <div>
                    <p className="text-xs font-bold uppercase tracking-wider text-outline mb-2">Action Items</p>
                    <ul className="space-y-1">
                      {(section.tasks as string[]).map((task, j) => (
                        <li key={j} className="text-sm text-on-surface flex gap-2">
                          <span className="text-success shrink-0">→</span> {task}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </Layout>
  )
}
