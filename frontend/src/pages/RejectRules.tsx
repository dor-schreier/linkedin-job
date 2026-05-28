import { useState } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Badge from '../components/ui/Badge'
import Input from '../components/ui/Input'
import {
  useRejectRules,
  useCreateRejectRule,
  useToggleRejectRule,
  useDeleteRejectRule,
  usePropertyValues,
  useRejectLocations,
} from '../api/queries'

const RULE_TYPES = ['title_keyword', 'location', 'property'] as const
const SUPPORTED_PROPERTIES = ['company', 'source', 'sector', 'company_type'] as const

const SELECT_CLS =
  'px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface focus:outline-none focus:ring-2 focus:ring-primary/20'

export default function RejectRules() {
  const { data: rules = [], isLoading } = useRejectRules()
  const create = useCreateRejectRule()
  const toggle = useToggleRejectRule()
  const del = useDeleteRejectRule()

  const [type, setType] = useState<string>('title_keyword')
  const [value, setValue] = useState('')
  const [propName, setPropName] = useState<string>('company')

  const { data: locations = [] } = useRejectLocations()
  const { data: propertyValues = [] } = usePropertyValues(type === 'property' ? propName : '')

  const rulesList = rules as any[]
  const existingLocations = new Set(
    rulesList.filter((r) => r.rule_type === 'location').map((r) => r.value),
  )
  const existingPropertyValues = new Set(
    rulesList
      .filter((r) => r.rule_type === 'property' && r.property_name === propName)
      .map((r) => r.value),
  )

  const availableLocations = (locations as string[]).filter((v) => !existingLocations.has(v))
  const availablePropertyValues = (propertyValues as string[]).filter(
    (v) => !existingPropertyValues.has(v),
  )

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!value.trim()) return
    await create.mutateAsync({ rule_type: type, value, property_name: type === 'property' ? propName : undefined })
    setValue('')
  }

  return (
    <Layout title="Reject Rules" active="reject-rules">
      <div className="max-w-4xl space-y-6">

        {/* Create new rule */}
        <Card title="Add Rule">
          <form onSubmit={handleCreate} className="space-y-4">
            <div className="flex gap-4">
              <div>
                <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Type</label>
                <select
                  value={type}
                  onChange={(e) => {
                    setType(e.target.value)
                    setValue('')
                  }}
                  className={SELECT_CLS}
                >
                  {RULE_TYPES.map((t) => (
                    <option key={t} value={t}>{t}</option>
                  ))}
                </select>
              </div>
              {type === 'property' && (
                <div>
                  <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Property Name</label>
                  <select
                    value={propName}
                    onChange={(e) => {
                      setPropName(e.target.value)
                      setValue('')
                    }}
                    className={SELECT_CLS}
                  >
                    {SUPPORTED_PROPERTIES.map((p) => (
                      <option key={p} value={p}>{p}</option>
                    ))}
                  </select>
                </div>
              )}
              <div className="flex-1">
                {type === 'title_keyword' ? (
                  <Input
                    label="Value"
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                    placeholder="e.g. intern, contract"
                  />
                ) : (
                  <>
                    <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Value</label>
                    <select
                      value={value}
                      onChange={(e) => setValue(e.target.value)}
                      className={`${SELECT_CLS} w-full`}
                    >
                      <option value="">— select —</option>
                      {(type === 'location' ? availableLocations : availablePropertyValues).map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  </>
                )}
              </div>
              <div className="flex items-end">
                <Button type="submit" loading={create.isPending} icon="add">Add</Button>
              </div>
            </div>
            {create.isError && (
              <p className="text-xs text-error">{(create.error as Error).message}</p>
            )}
          </form>
        </Card>

        {/* Rules list */}
        <Card title={`Rules (${(rules as any[]).length})`}>
          {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}
          {!isLoading && (rules as any[]).length === 0 && (
            <p className="text-sm text-outline">No reject rules yet.</p>
          )}
          <div className="space-y-2">
            {(rules as any[]).map((rule: any) => (
              <div
                key={rule.id}
                className="flex items-center gap-3 p-3 bg-surface-container rounded-lg"
              >
                <Badge color="default">{rule.rule_type}</Badge>
                {rule.property_name && (
                  <span className="text-xs text-on-surface-variant">{rule.property_name}:</span>
                )}
                <span className="flex-1 text-sm text-on-surface font-medium">{rule.value}</span>
                {rule.attributed_count > 0 && (
                  <span className="text-xs text-on-surface-variant">{rule.attributed_count} jobs</span>
                )}
                <Badge color={rule.is_enabled ? 'green' : 'default'}>
                  {rule.is_enabled ? 'active' : 'disabled'}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => toggle.mutate(rule.id)}
                  loading={toggle.isPending}
                >
                  {rule.is_enabled ? 'Disable' : 'Enable'}
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
