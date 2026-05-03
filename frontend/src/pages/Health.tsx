import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import { useHealth } from '../api/queries'

export default function Health() {
  const { data, isLoading, error } = useHealth()

  return (
    <Layout title="Health Check" active="health">
      <div className="max-w-xl">
        <Card>
          {isLoading && <p className="text-sm text-on-surface-variant">Checking…</p>}
          {error && <p className="text-sm text-error">{(error as Error).message}</p>}
          {data && (
            <div className="space-y-3">
              <Row label="Status" value={(data as any).status} />
              <Row label="Database" value={(data as any).db_exists ? 'OK' : 'MISSING'} />
              <Row label="Tables" value={String((data as any).table_count)} />
              <Row label="WAL Mode" value={(data as any).wal_mode ? 'ON' : 'OFF'} />
              <div className="flex gap-2 text-sm">
                <span className="text-on-surface-variant">LLM:</span>
                <span className={(data as any).llm_ok ? 'text-success font-medium' : 'text-error font-medium'}>
                  {(data as any).llm_ok ? 'OK' : 'UNAVAILABLE'}
                </span>
                <span className="text-on-surface-variant">({(data as any).llm_provider} / {(data as any).llm_model})</span>
                {(data as any).llm_error && (
                  <span className="text-error text-xs">— {(data as any).llm_error}</span>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>
    </Layout>
  )
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <p className="text-sm">
      <span className="text-on-surface-variant">{label}: </span>
      <span className="text-on-surface font-medium">{value}</span>
    </p>
  )
}
