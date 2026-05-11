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

export function useCleanupRunNow() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => apiFetch('/api/cleanup/run', { method: 'POST' }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['scheduler'] }),
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

export function useSaveProfile() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: {
      linkedin_url: string
      skills: string
      current_title: string
      target_title: string
      years_experience?: number
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
