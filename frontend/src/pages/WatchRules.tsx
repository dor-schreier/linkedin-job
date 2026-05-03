import { useState } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import { useWatchRules, useCreateWatchRule, useToggleWatchRule, useDeleteWatchRule } from '../api/queries'

const RULE_TYPES = ['company', 'keyword', 'sector'] as const

export default function WatchRules() {
  const { data: rules = [], isLoading } = useWatchRules()
  const create = useCreateWatchRule()
  const toggle = useToggleWatchRule()
  const del = useDeleteWatchRule()

  const [type, setType] = useState<string>('keyword')
  const [value, setValue] = useState('')

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!value.trim()) return
    await create.mutateAsync({ rule_type: type, value })
    setValue('')
  }

  return (
    <Layout
      title="Watch Rules"
      active="watch-rules"
      headerRight={
        <Button icon="add" onClick={() => {}}>Create New Rule</Button>
      }
    >
      <div className="max-w-4xl space-y-6">

        {/* Create */}
        <Card title="Add Watch Rule">
          <form onSubmit={handleCreate} className="flex gap-4 items-end">
            <div>
              <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Type</label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value)}
                className="px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20"
              >
                {RULE_TYPES.map((t) => (
                  <option key={t} value={t}>{t}</option>
                ))}
              </select>
            </div>
            <div className="flex-1">
              <Input
                label="Value"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                placeholder="e.g. Google, machine learning"
              />
            </div>
            <Button type="submit" loading={create.isPending} icon="add">Add</Button>
          </form>
        </Card>

        {/* Rules list */}
        <Card>
          <div className="flex items-center justify-between mb-4">
            <span className="text-xs font-bold uppercase tracking-wider text-outline">Active Automations</span>
            <Badge color="primary">{(rules as any[]).length} Rules</Badge>
          </div>
          {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}
          {!isLoading && (rules as any[]).length === 0 && (
            <p className="text-sm text-outline">No watch rules yet.</p>
          )}
          <div className="space-y-3">
            {(rules as any[]).map((rule: any) => (
              <div
                key={rule.id}
                className="flex items-center gap-3 p-4 bg-surface-container rounded-xl"
              >
                <Badge color="blue">{rule.rule_type}</Badge>
                <span className="flex-1 text-sm text-on-surface font-medium">{rule.value}</span>
                <Badge color={rule.is_active ? 'green' : 'default'}>
                  {rule.is_active ? 'active' : 'paused'}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggle.mutate(rule.id)}
                  loading={toggle.isPending}
                >
                  {rule.is_active ? 'Pause' : 'Resume'}
                </Button>
                <Button
                  variant="danger"
                  size="sm"
                  icon="delete"
                  onClick={() => del.mutate(rule.id)}
                  loading={del.isPending}
                />
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Layout>
  )
}
