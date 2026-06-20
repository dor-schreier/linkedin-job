import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import SimilarityRadar from '../components/SimilarityRadar'
import {
  useSimilarityWeights,
  useUpdateSimilarityWeights,
  useTargetJobs,
  useToggleJobTarget,
  useRecomputeSimilarity,
} from '../api/queries'

type WeightKey = 'weight_title' | 'weight_skills' | 'weight_seniority' | 'weight_sector'

const DEFAULT_WEIGHTS: Record<WeightKey, number> = {
  weight_title: 1,
  weight_skills: 1,
  weight_seniority: 1,
  weight_sector: 1,
}

export default function SimilarSearch() {
  const navigate = useNavigate()
  const { data: weightsData, isLoading: weightsLoading } = useSimilarityWeights()
  const { data: targetJobs, isLoading: targetsLoading } = useTargetJobs()
  const updateWeights = useUpdateSimilarityWeights()
  const removeTarget = useToggleJobTarget()
  const recompute = useRecomputeSimilarity()

  const [weights, setWeights] = useState<Record<WeightKey, number>>(DEFAULT_WEIGHTS)
  const [isEnabled, setIsEnabled] = useState(true)
  const [minThreshold, setMinThreshold] = useState<string>('')
  const [dirty, setDirty] = useState(false)
  const [recomputeResult, setRecomputeResult] = useState<number | null>(null)

  useEffect(() => {
    if (weightsData) {
      setWeights({
        weight_title: weightsData.weight_title ?? 1,
        weight_skills: weightsData.weight_skills ?? 1,
        weight_seniority: weightsData.weight_seniority ?? 1,
        weight_sector: weightsData.weight_sector ?? 1,
      })
      setIsEnabled(weightsData.is_enabled ?? true)
      setMinThreshold(weightsData.min_score_threshold != null ? String(weightsData.min_score_threshold) : '')
      setDirty(false)
    }
  }, [weightsData])

  function handleWeightChange(key: WeightKey, value: number) {
    setWeights((w) => ({ ...w, [key]: value }))
    setDirty(true)
  }

  async function handleSave() {
    const threshold = minThreshold !== '' ? parseInt(minThreshold) : null
    await updateWeights.mutateAsync({
      ...weights,
      is_enabled: isEnabled,
      ...(threshold !== null ? { min_score_threshold: threshold } : {}),
    })
    setDirty(false)
  }

  async function handleRecompute() {
    const result = await recompute.mutateAsync()
    setRecomputeResult(result?.updated ?? 0)
    setTimeout(() => setRecomputeResult(null), 4000)
  }

  const jobs = (targetJobs as any[]) ?? []

  return (
    <Layout title="Similar Job Search" active="similar">
      <div className="max-w-2xl space-y-6">

        {/* Enable toggle */}
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-base font-bold text-on-surface">Similarity Matching</h2>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Score every job by how closely it matches your target roles.
              </p>
            </div>
            <button
              onClick={() => { setIsEnabled((v) => !v); setDirty(true) }}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${isEnabled ? 'bg-primary' : 'bg-surface-container'}`}
              aria-checked={isEnabled}
              role="switch"
            >
              <span className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform ${isEnabled ? 'translate-x-6' : 'translate-x-1'}`} />
            </button>
          </div>
        </Card>

        {/* Radar weight editor */}
        <Card title="Weight Dimensions">
          <p className="text-xs text-on-surface-variant mb-4">
            Drag the sliders to adjust how much each dimension contributes to the similarity score.
          </p>
          {weightsLoading ? (
            <p className="text-sm text-on-surface-variant">Loading…</p>
          ) : (
            <SimilarityRadar weights={weights} onChange={handleWeightChange} />
          )}

          <div className="mt-4 flex items-center gap-2">
            <label className="text-xs text-on-surface-variant whitespace-nowrap">Min score threshold</label>
            <input
              type="number"
              min="0"
              max="100"
              placeholder="None"
              value={minThreshold}
              onChange={(e) => { setMinThreshold(e.target.value); setDirty(true) }}
              className="w-20 px-2 py-1.5 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
            />
            <span className="text-xs text-outline">/ 100 — scrape logs will count jobs below this</span>
          </div>

          <div className="mt-4 flex gap-2 items-center">
            <Button
              onClick={handleSave}
              loading={updateWeights.isPending}
              disabled={!dirty}
            >
              Save Weights
            </Button>
            <Button
              variant="secondary"
              icon="refresh"
              onClick={handleRecompute}
              loading={recompute.isPending}
            >
              Recompute Scores
            </Button>
            {recomputeResult !== null && (
              <span className="text-xs text-success font-semibold">
                ✓ Updated {recomputeResult} jobs
              </span>
            )}
            {updateWeights.isError && (
              <span className="text-xs text-error">{(updateWeights.error as Error)?.message}</span>
            )}
          </div>
        </Card>

        {/* Target jobs list */}
        <Card title={`Target Jobs (${jobs.length})`}>
          {targetsLoading ? (
            <p className="text-sm text-on-surface-variant">Loading…</p>
          ) : jobs.length === 0 ? (
            <div className="py-6 text-center space-y-2">
              <span className="material-symbols-outlined text-outline text-4xl block">my_location</span>
              <p className="text-sm text-on-surface-variant">No target jobs yet.</p>
              <p className="text-xs text-outline">Mark jobs as targets from the job list or detail page.</p>
              <Button variant="ghost" icon="dashboard" onClick={() => navigate('/jobs')}>
                Browse Jobs
              </Button>
            </div>
          ) : (
            <div className="divide-y divide-outline-variant/15">
              {jobs.map((job: any) => (
                <div key={job.id} className="flex items-start gap-3 py-3">
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => navigate(`/jobs/${job.id}`)}>
                    <p className="text-sm font-semibold text-on-surface truncate">{job.title}</p>
                    <p className="text-xs text-on-surface-variant">{job.company}{job.location ? ` · ${job.location}` : ''}</p>
                    {job.sector && (
                      <span className="inline-block mt-1 px-1.5 py-0.5 rounded text-[10px] bg-primary/10 text-primary font-medium">{job.sector}</span>
                    )}
                  </div>
                  <button
                    onClick={() => removeTarget.mutate({ jobId: job.id, isTarget: false })}
                    className="shrink-0 p-1 text-outline hover:text-error transition-colors"
                    title="Remove from targets"
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 18 }}>close</span>
                  </button>
                </div>
              ))}
            </div>
          )}
        </Card>

      </div>
    </Layout>
  )
}
