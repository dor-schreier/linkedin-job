import { useEffect } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useProfile, useSaveProfile, useAnalyzeProfile, useKeywordGaps } from '../api/queries'
import { useForm } from '../lib/forms'

const initial = {
  linkedin_url: '',
  skills: '',
  current_title: '',
  target_title: '',
  years_experience: '' as number | string,
}

export default function Profile() {
  const { data, isLoading } = useProfile()
  const save = useSaveProfile()
  const analyze = useAnalyzeProfile()
  const { data: gapsData } = useKeywordGaps()
  const form = useForm(initial)

  useEffect(() => {
    if (data) {
      const d = data as any
      form.setValues({
        linkedin_url: d.linkedin_url ?? '',
        skills: d.skills ?? '',
        current_title: d.current_title ?? '',
        target_title: d.target_title ?? '',
        years_experience: d.years_experience ?? '',
      })
    }
  }, [data])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const v = form.values
    await save.mutateAsync({
      linkedin_url: v.linkedin_url as string,
      skills: v.skills as string,
      current_title: v.current_title as string,
      target_title: v.target_title as string,
      years_experience: v.years_experience ? Number(v.years_experience) : undefined,
    })
  }

  const profile = data as any
  const gaps = (gapsData as any)?.gaps ?? []
  const gapRec = (gapsData as any)?.recommendation

  return (
    <Layout title="Profile" active="profile">
      <div className="max-w-2xl space-y-6">
        {isLoading ? (
          <p className="text-sm text-on-surface-variant">Loading…</p>
        ) : (
          <>
            <form onSubmit={handleSubmit} className="space-y-6">
              <Card title="Your Profile">
                <div className="space-y-4">
                  <Input label="LinkedIn URL" id="linkedin_url" placeholder="https://linkedin.com/in/..." {...form.bind('linkedin_url')} />
                  <div className="grid grid-cols-2 gap-4">
                    <Input label="Current Title" id="current_title" placeholder="e.g. Senior Engineer" {...form.bind('current_title')} />
                    <Input label="Target Title" id="target_title" placeholder="e.g. Staff Engineer" {...form.bind('target_title')} />
                  </div>
                  <Input label="Years Experience" id="years_experience" type="number" min={0} placeholder="e.g. 5" {...form.bind('years_experience')} />
                  <div>
                    <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Skills</label>
                    <textarea
                      rows={4}
                      className="w-full px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="Python, React, AWS, …"
                      value={form.values.skills as string}
                      onChange={(e) => form.set('skills', e.target.value as any)}
                    />
                  </div>
                </div>
              </Card>

              <div className="flex items-center gap-4">
                <Button type="submit" loading={save.isPending} icon="save">Save Profile</Button>
                {save.isSuccess && <span className="text-sm text-success">Saved.</span>}
                {save.isError && <span className="text-sm text-error">{(save.error as Error).message}</span>}
              </div>
            </form>

            {/* AI Recommendations */}
            <Card title="AI Recommendations">
              {profile?.ai_recommendations ? (
                <div className="space-y-2">
                  {profile.ai_recommendations.split('\n').filter(Boolean).map((line: string, i: number) => (
                    <p key={i} className="text-sm text-on-surface-variant flex gap-2">
                      <span className="text-primary shrink-0">•</span> {line}
                    </p>
                  ))}
                  <Button
                    variant="secondary"
                    size="sm"
                    icon="auto_awesome"
                    onClick={() => analyze.mutate()}
                    loading={analyze.isPending}
                    className="mt-4"
                  >
                    Refresh
                  </Button>
                </div>
              ) : (
                <div className="space-y-3">
                  <p className="text-sm text-on-surface-variant">No recommendations yet. Save your profile first.</p>
                  <Button
                    variant="secondary"
                    icon="auto_awesome"
                    onClick={() => analyze.mutate()}
                    loading={analyze.isPending}
                  >
                    Get AI Recommendations
                  </Button>
                  {analyze.isError && <p className="text-xs text-error">{(analyze.error as Error).message}</p>}
                </div>
              )}
            </Card>

            {/* Keyword gaps */}
            {gaps.length > 0 && (
              <Card title="Keyword Gaps">
                {gapRec && <p className="text-sm text-on-surface-variant mb-4">{gapRec}</p>}
                <div className="flex flex-wrap gap-2">
                  {gaps.slice(0, 20).map((g: any) => (
                    <span
                      key={g.keyword}
                      className="px-2 py-1 bg-surface-container rounded text-xs text-on-surface-variant"
                    >
                      {g.keyword}
                      <span className="ml-1 text-outline">×{g.count}</span>
                    </span>
                  ))}
                </div>
              </Card>
            )}
          </>
        )}
      </div>
    </Layout>
  )
}
