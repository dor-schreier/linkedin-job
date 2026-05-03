import { useEffect } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useSearchConfig, useSaveSearchConfig } from '../api/queries'
import { useForm } from '../lib/forms'

const initial = {
  keywords: '',
  location: '',
  experience_level: '',
  work_mode: '',
  role_level: '',
  country: '',
  max_age_hours: 72 as number | string,
  include_remote: false as boolean,
  exclude_keywords: '',
  blocked_companies: '',
  results_wanted: 50 as number | string,
  min_salary: '' as number | string,
}

export default function SearchConfig() {
  const { data, isLoading } = useSearchConfig()
  const save = useSaveSearchConfig()
  const form = useForm(initial)

  useEffect(() => {
    if (data) {
      const d = data as any
      form.setValues({
        keywords: d.keywords ?? '',
        location: d.location ?? '',
        experience_level: d.experience_level ?? '',
        work_mode: d.work_mode ?? '',
        role_level: d.role_level ?? '',
        country: d.country ?? '',
        max_age_hours: d.max_age_hours ?? 72,
        include_remote: d.include_remote ?? false,
        exclude_keywords: d.exclude_keywords ?? '',
        blocked_companies: d.blocked_companies ?? '',
        results_wanted: d.results_wanted ?? 50,
        min_salary: d.min_salary ?? '',
      })
    }
  }, [data])

  async function handleSubmit(e: React.FormEvent) {
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
      exclude_keywords: v.exclude_keywords || null,
      blocked_companies: v.blocked_companies || null,
      results_wanted: v.results_wanted ? Number(v.results_wanted) : 50,
      min_salary: v.min_salary ? Number(v.min_salary) : null,
    })
  }

  return (
    <Layout title="Search Config" active="search-config">
      <div className="max-w-2xl">
        {isLoading ? (
          <p className="text-sm text-on-surface-variant">Loading…</p>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-6">
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
      </div>
    </Layout>
  )
}
