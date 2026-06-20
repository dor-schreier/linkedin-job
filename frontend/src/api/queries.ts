import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import client from './client'

async function apiFetch(path: string, opts?: RequestInit) {
  const res = await fetch(path, { headers: { 'Content-Type': 'application/json', ...opts?.headers }, ...opts })
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body?.detail ?? `Request failed: ${res.status}`)
  }
  if (res.status === 204) return null
  return res.json()
}

// ── Health ──────────────────────────────────────────────────────────────────

export function useHealth() {
  return useQuery({
    queryKey: ['health'],
    queryFn: () => apiFetch('/api/health'),
  })
}

// ── Scheduler ────────────────────────────────────────────────────────────────

export function useScheduler() {
  return useQuery({
    queryKey: ['scheduler'],
    queryFn: () => apiFetch('/api/scheduler'),
    refetchInterval: 10_000,
  })
}

export function useSchedulerToggle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/scheduler/toggle', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

export function useSchedulerRunNow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/scheduler/run-now', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

export function useSchedulerConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (interval_hours: number) => {
      const form = new FormData()
      form.append('interval_hours', String(interval_hours))
      return apiFetch('/api/scheduler/config', { method: 'POST', headers: {}, body: form })
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

export function useReenrichCompanies() {
  return useMutation({
    mutationFn: (limit = 20) =>
      apiFetch('/api/companies/re-enrich', {
        method: 'POST',
        body: JSON.stringify({ limit }),
      }) as Promise<{ enriched: number; failed: number }>,
  })
}

export function useCleanupRunNow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/cleanup/run', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

export function useCleanupSources() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (sources: string[]) =>
      apiFetch('/api/cleanup/sources', {
        method: 'POST',
        body: JSON.stringify({ sources }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

export function useCleanupLimit() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (limit: number) =>
      apiFetch('/api/cleanup/limit', {
        method: 'POST',
        body: JSON.stringify({ limit }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

export function useCleanupSkipValidated() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (hours: number) =>
      apiFetch('/api/cleanup/skip-validated', {
        method: 'POST',
        body: JSON.stringify({ hours }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
  })
}

// ── Scrape History ───────────────────────────────────────────────────────────

export function useHistory(page: number = 1, pageSize: number = 25) {
  return useQuery({
    queryKey: ['scrape-history', page, pageSize],
    queryFn: () => apiFetch(`/api/scrape/history?page=${page}&page_size=${pageSize}`),
  })
}

// ── Reject Rules ─────────────────────────────────────────────────────────────

export function useRejectRules() {
  return useQuery({
    queryKey: ['reject-rules'],
    queryFn: async () => {
      const { data, error } = await client.GET('/api/reject-rules')
      if (error) throw new Error(JSON.stringify(error))
      return data ?? []
    },
  })
}

export function useCreateRejectRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (body: { rule_type: string; property_name?: string; value: string }) => {
      const { data, error } = await client.POST('/api/reject-rules', { body } as never)
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reject-rules'] }),
  })
}

export function useToggleRejectRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ruleId: number) => {
      const { data, error } = await client.PATCH('/api/reject-rules/{rule_id}', {
        params: { path: { rule_id: ruleId } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reject-rules'] }),
  })
}

export function useDeleteRejectRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (ruleId: number) => {
      const { data, error } = await client.DELETE('/api/reject-rules/{rule_id}', {
        params: { path: { rule_id: ruleId } },
      })
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['reject-rules'] }),
  })
}

export function usePropertyValues(property: string) {
  return useQuery({
    queryKey: ['reject-rules', 'property-values', property],
    queryFn: () =>
      apiFetch(`/api/reject-rules/property-values?property=${encodeURIComponent(property)}`).then(
        (d) => d?.values ?? []
      ),
    enabled: !!property,
  })
}

export function useRejectLocations() {
  return useQuery({
    queryKey: ['reject-rules', 'locations'],
    queryFn: () => apiFetch('/api/reject-rules/locations').then((d) => d?.values ?? []),
  })
}

// ── Watch Rules ───────────────────────────────────────────────────────────────
// Actual routes: GET/POST /api/watch-rules, PATCH/DELETE /api/watch-rules/{id}

export function useWatchRules() {
  return useQuery({
    queryKey: ['watch-rules'],
    queryFn: () => apiFetch('/api/watch-rules'),
  })
}

export function useCreateWatchRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { rule_type: string; value: string }) =>
      apiFetch('/api/watch-rules', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watch-rules'] }),
  })
}

export function useToggleWatchRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ruleId: number) => apiFetch(`/api/watch-rules/${ruleId}`, { method: 'PATCH' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watch-rules'] }),
  })
}

export function useDeleteWatchRule() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (ruleId: number) => apiFetch(`/api/watch-rules/${ruleId}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watch-rules'] }),
  })
}

// ── Watch Matches ─────────────────────────────────────────────────────────────

export function useWatchMatches() {
  return useQuery({
    queryKey: ['watch-matches'],
    queryFn: async () => {
      const data = await apiFetch('/api/watch-matches')
      return data?.rows ?? []
    },
    refetchInterval: 30_000,
  })
}

export function useMarkMatchesRead() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/notifications/mark-read', { method: 'POST' }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['watch-matches'] })
      qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

// ── Search Config ─────────────────────────────────────────────────────────────

export function useSearchConfig() {
  return useQuery({
    queryKey: ['search-config'],
    queryFn: () => apiFetch('/api/search-config'),
  })
}

export function useSaveSearchConfig() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Record<string, unknown>) =>
      apiFetch('/api/scrape/save-config', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['search-config'] }),
  })
}

// ── Scrape ────────────────────────────────────────────────────────────────────

export function useScrapeState() {
  return useQuery({
    queryKey: ['scrape', 'status'],
    queryFn: () => apiFetch('/api/scrape/status'),
    refetchInterval: 3_000,
  })
}

export function useScrapeRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ configId, sites }: { configId?: number; sites?: string[] } = {}) =>
      apiFetch('/api/scrape/run', {
        method: 'POST',
        body: JSON.stringify({
          ...(configId ? { config_id: configId } : {}),
          ...(sites ? { sites } : {}),
        }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scrape'] }),
  })
}

export function useScrapeStop() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/scrape/stop', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scrape'] }),
  })
}

export function useScrapeConfig() {
  return useQuery({
    queryKey: ['scrape', 'config'],
    queryFn: () => apiFetch('/api/scrape'),
  })
}

// ── Profile ───────────────────────────────────────────────────────────────────
// Actual routes: GET/PUT /api/profile, POST /api/profile/analyze, GET /api/profile/keyword-gaps

export function useProfile() {
  return useQuery({
    queryKey: ['profile'],
    queryFn: () => apiFetch('/api/profile'),
  })
}

export type ProfileExperienceItem = {
  title?: string
  company?: string
  location?: string
  start_date?: string
  end_date?: string
  is_current?: boolean
  description?: string
}

export type ProfileEducationItem = {
  school?: string
  degree?: string
  field_of_study?: string
  start_year?: number
  end_year?: number
  grade?: string
  description?: string
}

export function useSaveProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      linkedin_url: string
      skills: string
      current_title: string
      target_title: string
      years_experience?: number
      experiences?: ProfileExperienceItem[]
      educations?: ProfileEducationItem[]
    }) => apiFetch('/api/profile', { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile'] }),
  })
}

export function useAnalyzeProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/profile/analyze', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile'] }),
  })
}

export function useKeywordGaps() {
  return useQuery({
    queryKey: ['profile', 'keyword-gaps'],
    queryFn: () => apiFetch('/api/profile/keyword-gaps'),
  })
}

export function useUploadedCvStatus() {
  return useQuery({
    queryKey: ['profile', 'cv-upload'],
    queryFn: () => apiFetch('/api/profile/cv-upload'),
  })
}

export function useUploadCv() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (files: File[]) => {
      const form = new FormData()
      for (const file of files) {
        form.append('files', file)
      }
      const res = await fetch('/api/profile/cv-upload', { method: 'POST', body: form })
      if (!res.ok) {
        const body = await res.json().catch(() => ({}))
        throw new Error(body?.detail ?? `Upload failed: ${res.status}`)
      }
      return res.json()
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile', 'cv-upload'] }),
  })
}

export function useDeleteUploadedCv() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/profile/cv-upload', { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile', 'cv-upload'] }),
  })
}

export function useDeleteUploadedCvById() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: number) => apiFetch(`/api/profile/cv-upload/${id}`, { method: 'DELETE' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile', 'cv-upload'] }),
  })
}

export function useExtractFromUploadedCv() {
  return useMutation({
    mutationFn: () => apiFetch('/api/profile/cv-extract', { method: 'POST' }),
  })
}

// ── Profile Optimizer ─────────────────────────────────────────────────────────
// Actual routes: GET/POST /api/profile-optimizer, POST /api/profile-optimizer/analyze

export function useProfileOptimizer() {
  return useQuery({
    queryKey: ['profile-optimizer'],
    queryFn: () => apiFetch('/api/profile-optimizer'),
  })
}

export function useProfileOptimizerAnalyze() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/profile-optimizer/analyze', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['profile-optimizer'] }),
  })
}

// ── Notifications ─────────────────────────────────────────────────────────────

// ── Application Tracker ───────────────────────────────────────────────────────

export function useApplications() {
  return useQuery({
    queryKey: ['applications'],
    queryFn: () => apiFetch('/api/jobs/tracker'),
  })
}

export function useUpdateJobStatus() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, status }: { jobId: number; status: string }) =>
      apiFetch(`/api/jobs/${jobId}/status`, {
        method: 'PATCH',
        body: JSON.stringify({ status }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['jobs'] })
    },
  })
}

export function useJobInterviews(jobId: number) {
  return useQuery({
    queryKey: ['interviews', jobId],
    queryFn: () => apiFetch(`/api/jobs/${jobId}/interviews`),
    enabled: jobId > 0,
  })
}

export function useCreateInterview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      jobId,
      body,
    }: {
      jobId: number
      body: {
        scheduled_at: string
        interview_type: string
        medium: string
        location?: string
        notes?: string
      }
    }) =>
      apiFetch(`/api/jobs/${jobId}/interviews`, {
        method: 'POST',
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['interviews', variables.jobId] })
    },
  })
}

export function useUpdateInterview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      interviewId,
      jobId,
      body,
    }: {
      interviewId: number
      jobId: number
      body: {
        scheduled_at?: string
        interview_type?: string
        medium?: string
        location?: string
        notes?: string
      }
    }) =>
      apiFetch(`/api/interviews/${interviewId}`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['interviews', variables.jobId] })
    },
  })
}

export function useDeleteInterview() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ interviewId, jobId }: { interviewId: number; jobId: number }) =>
      apiFetch(`/api/interviews/${interviewId}`, { method: 'DELETE' }),
    onSuccess: (_data, variables) => {
      qc.invalidateQueries({ queryKey: ['applications'] })
      qc.invalidateQueries({ queryKey: ['interviews', variables.jobId] })
      qc.invalidateQueries({ queryKey: ['notifications'] })
    },
  })
}

// ── Similarity ────────────────────────────────────────────────────────────────

export function useSimilarityWeights() {
  return useQuery({
    queryKey: ['similarity', 'weights'],
    queryFn: () => apiFetch('/api/similarity/weights'),
  })
}

export function useUpdateSimilarityWeights() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      weight_title?: number
      weight_skills?: number
      weight_seniority?: number
      weight_sector?: number
      is_enabled?: boolean
      min_score_threshold?: number | null
    }) => apiFetch('/api/similarity/weights', { method: 'PUT', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['similarity'] }),
  })
}

export function useTargetJobs() {
  return useQuery({
    queryKey: ['similarity', 'targets'],
    queryFn: () => apiFetch('/api/similarity/targets'),
  })
}

export function useToggleJobTarget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, isTarget }: { jobId: number; isTarget: boolean }) =>
      apiFetch(`/api/jobs/${jobId}/target`, { method: 'POST', body: JSON.stringify({ is_target: isTarget }) }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['jobs'] })
      qc.invalidateQueries({ queryKey: ['similarity', 'targets'] })
    },
  })
}

export function useRecomputeSimilarity() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/similarity/recompute', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['jobs'] }),
  })
}

// ── Company Sector Options ────────────────────────────────────────────────────

export function useCompanySectorOptions() {
  return useQuery({
    queryKey: ['companies', 'sectors'],
    queryFn: () =>
      apiFetch('/api/companies/sectors') as Promise<{ sectors: string[]; subsectors: string[] }>,
    staleTime: 5 * 60 * 1000,
  })
}

export function useUpdateCompanySector() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({
      companyId,
      sector,
      subsector,
    }: {
      companyId: number
      sector: string | null
      subsector: string | null
    }) =>
      apiFetch(`/api/companies/${companyId}`, {
        method: 'PATCH',
        body: JSON.stringify({ sector, subsector }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['companies', 'overview'] })
      qc.invalidateQueries({ queryKey: ['companies', 'sectors'] })
    },
  })
}

// ── Companies Overview ────────────────────────────────────────────────────────

export type CompanyOverviewItem = {
  name_display: string
  company: string
  company_id: number | null
  sector: string | null
  subsector: string | null
  company_type: string | null
  what_they_do: string | null
  total_active_jobs: number
  last_scraped_at: string | null
  location_breakdown: { location: string; count: number }[]
}

export function useCompaniesOverview() {
  return useQuery({
    queryKey: ['companies', 'overview'],
    queryFn: () => apiFetch('/api/companies/overview') as Promise<CompanyOverviewItem[]>,
  })
}

export function useCompanyJobs(companyName: string | null, location?: string | null) {
  const params = new URLSearchParams()
  if (companyName) params.set('company', companyName)
  if (location) params.set('location', location)
  params.set('limit', '200')
  params.set('valid_only', '1')
  return useQuery({
    queryKey: ['jobs', 'by-company', companyName, location ?? null],
    queryFn: () =>
      apiFetch(`/api/jobs?${params}`) as Promise<{ jobs: any[]; total: number; has_more: boolean }>,
    enabled: !!companyName,
  })
}

export function useUnreadCount() {
  return useQuery({
    queryKey: ['notifications', 'unread-count'],
    queryFn: async () => {
      const { data, error } = await client.GET('/api/notifications/unread-count')
      if (error) throw new Error(JSON.stringify(error))
      return data
    },
    refetchInterval: 30_000,
  })
}
