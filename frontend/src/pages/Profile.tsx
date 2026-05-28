import { useEffect, useRef, useState } from 'react'
import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import Input from '../components/ui/Input'
import { useProfile, useSaveProfile, useAnalyzeProfile, useKeywordGaps, useUploadCv, useUploadedCvStatus, useDeleteUploadedCvById, useExtractFromUploadedCv, useReenrichCompanies, type ProfileExperienceItem, type ProfileEducationItem } from '../api/queries'
import { useForm } from '../lib/forms'

const initial = {
  linkedin_url: '',
  skills: '',
  current_title: '',
  target_title: '',
  years_experience: '' as number | string,
}

type FieldKey = 'linkedin_url' | 'current_title' | 'skills' | 'years_experience'
type ListKey = 'experiences' | 'educations'
type Choice = 'keep' | 'merged' | `file-${number}` | 'skip'

const CONFLICT_FIELDS: { key: FieldKey; label: string }[] = [
  { key: 'linkedin_url', label: 'LinkedIn URL' },
  { key: 'current_title', label: 'Current Title' },
  { key: 'skills', label: 'Skills' },
  { key: 'years_experience', label: 'Years Experience' },
]

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n) + '…' : s
}

function summarizeExperiences(items?: ProfileExperienceItem[] | null) {
  if (!items?.length) return null
  const first = items[0]
  const label = [first.title, first.company].filter(Boolean).join(' @ ')
  return `${items.length} role${items.length !== 1 ? 's' : ''}${label ? ` · latest: ${label}` : ''}`
}

function summarizeEducations(items?: ProfileEducationItem[] | null) {
  if (!items?.length) return null
  const first = items[0]
  const label = [first.degree, first.school].filter(Boolean).join(' · ')
  return `${items.length} degree${items.length !== 1 ? 's' : ''}${label ? ` · ${label}` : ''}`
}

const defaultChoices: Record<FieldKey, Choice> = {
  linkedin_url: 'keep',
  current_title: 'keep',
  skills: 'keep',
  years_experience: 'keep',
}

const defaultListChoices: Record<ListKey, Choice> = {
  experiences: 'keep',
  educations: 'keep',
}

export default function Profile() {
  const { data, isLoading } = useProfile()
  const save = useSaveProfile()
  const analyze = useAnalyzeProfile()
  const { data: gapsData } = useKeywordGaps()
  const { data: cvStatus, refetch: refetchCvStatus } = useUploadedCvStatus()
  const uploadCv = useUploadCv()
  const deleteUploadedCvById = useDeleteUploadedCvById()
  const extractFromUploadedCv = useExtractFromUploadedCv()
  const reenrich = useReenrichCompanies()
  const [reenrichResult, setReenrichResult] = useState<{ enriched: number; failed: number } | null>(null)
  const form = useForm(initial)
  const fileRef = useRef<HTMLInputElement>(null)

  const [experiences, setExperiences] = useState<ProfileExperienceItem[]>([])
  const [educations, setEducations] = useState<ProfileEducationItem[]>([])
  const [uploadResult, setUploadResult] = useState<any | null>(null)
  const [fieldChoices, setFieldChoices] = useState<Record<FieldKey, Choice>>(defaultChoices)
  const [listChoices, setListChoices] = useState<Record<ListKey, Choice>>(defaultListChoices)

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
      setExperiences(d.experiences ?? [])
      setEducations(d.educations ?? [])
    }
  }, [data])

  useEffect(() => {
    if (!uploadResult) return
    const merged = uploadResult.merged as Record<FieldKey, any>
    const cur = form.values
    const choices = {} as Record<FieldKey, Choice>
    for (const { key } of CONFLICT_FIELDS) {
      const prop = merged?.[key]
      const hasMerged = prop !== null && prop !== undefined && prop !== ''
      if (!hasMerged) {
        choices[key] = 'keep'
      } else if (!cur[key]) {
        choices[key] = 'merged'
      } else {
        choices[key] = 'keep'
      }
    }
    setFieldChoices(choices)
    setListChoices({
      experiences: (uploadResult.merged?.experiences?.length ?? 0) > 0 ? 'merged' : 'keep',
      educations: (uploadResult.merged?.educations?.length ?? 0) > 0 ? 'merged' : 'keep',
    })
  }, [uploadResult])

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const v = form.values
    await save.mutateAsync({
      linkedin_url: v.linkedin_url as string,
      skills: v.skills as string,
      current_title: v.current_title as string,
      target_title: v.target_title as string,
      years_experience: v.years_experience ? Number(v.years_experience) : undefined,
      experiences,
      educations,
    })
  }

  async function handleUpload() {
    const files = Array.from(fileRef.current?.files ?? [])
    if (!files.length) return
    try {
      const result = await uploadCv.mutateAsync(files)
      setUploadResult(result)
      refetchCvStatus()
      if (fileRef.current) fileRef.current.value = ''
    } catch {
      // error shown via uploadCv.error
    }
  }

  async function handleExtract() {
    try {
      const result = await extractFromUploadedCv.mutateAsync()
      setUploadResult(result)
    } catch {
      // error shown via extractFromUploadedCv.error
    }
  }

  async function handleDeleteFile(id: number) {
    await deleteUploadedCvById.mutateAsync(id)
    const newStatus = await refetchCvStatus()
    const status = (newStatus.data as any)
    if (status?.files?.length > 0) {
      setUploadResult({ files: status.files, merged: status.merged, errors: [] })
    } else {
      setUploadResult(null)
    }
  }

  async function handleApply() {
    const mergedProposed = uploadResult.merged as Record<FieldKey, any>
    const files = uploadResult.files as any[]
    const v = { ...form.values }
    for (const { key } of CONFLICT_FIELDS) {
      const choice = fieldChoices[key]
      if (choice === 'keep') continue
      if (choice === 'skip') {
        ;(v as any)[key] = ''
      } else if (choice === 'merged') {
        ;(v as any)[key] = mergedProposed[key]
      } else if (typeof choice === 'string' && choice.startsWith('file-')) {
        const idx = parseInt(choice.replace('file-', '')) - 1
        ;(v as any)[key] = files[idx]?.proposed[key] ?? ''
      }
    }

    let newExperiences = experiences
    let newEducations = educations

    const expChoice = listChoices.experiences
    if (expChoice === 'skip') {
      newExperiences = []
    } else if (expChoice === 'merged') {
      newExperiences = uploadResult.merged?.experiences ?? experiences
    } else if (typeof expChoice === 'string' && expChoice.startsWith('file-')) {
      const idx = parseInt(expChoice.replace('file-', '')) - 1
      newExperiences = files[idx]?.proposed?.experiences ?? experiences
    }

    const eduChoice = listChoices.educations
    if (eduChoice === 'skip') {
      newEducations = []
    } else if (eduChoice === 'merged') {
      newEducations = uploadResult.merged?.educations ?? educations
    } else if (typeof eduChoice === 'string' && eduChoice.startsWith('file-')) {
      const idx = parseInt(eduChoice.replace('file-', '')) - 1
      newEducations = files[idx]?.proposed?.educations ?? educations
    }

    await save.mutateAsync({
      linkedin_url: v.linkedin_url as string,
      skills: v.skills as string,
      current_title: v.current_title as string,
      target_title: v.target_title as string,
      years_experience: v.years_experience ? Number(v.years_experience) : undefined,
      experiences: newExperiences,
      educations: newEducations,
    })
    setUploadResult(null)
  }

  const profile = data as any
  const gaps = (gapsData as any)?.gaps ?? []
  const gapRec = (gapsData as any)?.recommendation
  const existingFiles: any[] = (cvStatus as any)?.files ?? []

  const uploadFiles: any[] = uploadResult?.files ?? []
  const numUploadFiles = uploadFiles.length
  const tableGridCols = `120px 1fr ${Array(numUploadFiles).fill('minmax(0,1fr)').join(' ')} minmax(0,1fr) 180px`

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

              <Card title="Experience">
                <div className="space-y-4">
                  {experiences.map((exp, i) => (
                    <div key={i} className="space-y-3 pb-4 border-b border-outline-variant/20 last:border-0 last:pb-0">
                      <div className="grid grid-cols-2 gap-3">
                        <Input label="Title" id={`exp-title-${i}`} placeholder="e.g. Senior Engineer" value={exp.title ?? ''} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, title: e.target.value } : x))} />
                        <Input label="Company" id={`exp-company-${i}`} placeholder="e.g. Acme Corp" value={exp.company ?? ''} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, company: e.target.value } : x))} />
                      </div>
                      <Input label="Location" id={`exp-location-${i}`} placeholder="e.g. Tel Aviv" value={exp.location ?? ''} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, location: e.target.value } : x))} />
                      <div className="grid grid-cols-2 gap-3">
                        <Input label="Start Date" id={`exp-start-${i}`} placeholder="e.g. 2021-03" value={exp.start_date ?? ''} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, start_date: e.target.value } : x))} />
                        <Input label="End Date" id={`exp-end-${i}`} placeholder="e.g. 2023-06" disabled={!!exp.is_current} value={exp.is_current ? '' : (exp.end_date ?? '')} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, end_date: e.target.value } : x))} />
                      </div>
                      <label className="flex items-center gap-2 text-sm cursor-pointer">
                        <input type="checkbox" checked={!!exp.is_current} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, is_current: e.target.checked, end_date: e.target.checked ? undefined : x.end_date } : x))} className="accent-primary" />
                        <span className="text-on-surface-variant">Current role</span>
                      </label>
                      <div>
                        <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Description</label>
                        <textarea rows={3} className="w-full px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="Key responsibilities and achievements…" value={exp.description ?? ''} onChange={e => setExperiences(prev => prev.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} />
                      </div>
                      <Button variant="danger" size="sm" icon="delete" type="button" onClick={() => setExperiences(prev => prev.filter((_, j) => j !== i))}>Remove</Button>
                    </div>
                  ))}
                  <Button variant="secondary" size="sm" icon="add" type="button" onClick={() => setExperiences(prev => [...prev, { title: '', company: '', is_current: false }])}>Add Experience</Button>
                </div>
              </Card>

              <Card title="Education">
                <div className="space-y-4">
                  {educations.map((edu, i) => (
                    <div key={i} className="space-y-3 pb-4 border-b border-outline-variant/20 last:border-0 last:pb-0">
                      <Input label="School" id={`edu-school-${i}`} placeholder="e.g. Tel Aviv University" value={edu.school ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, school: e.target.value } : x))} />
                      <div className="grid grid-cols-2 gap-3">
                        <Input label="Degree" id={`edu-degree-${i}`} placeholder="e.g. B.Sc." value={edu.degree ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, degree: e.target.value } : x))} />
                        <Input label="Field of Study" id={`edu-field-${i}`} placeholder="e.g. Computer Science" value={edu.field_of_study ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, field_of_study: e.target.value } : x))} />
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        <Input label="Start Year" id={`edu-start-${i}`} type="number" placeholder="e.g. 2016" value={edu.start_year ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, start_year: e.target.value ? Number(e.target.value) : undefined } : x))} />
                        <Input label="End Year" id={`edu-end-${i}`} type="number" placeholder="e.g. 2020" value={edu.end_year ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, end_year: e.target.value ? Number(e.target.value) : undefined } : x))} />
                        <Input label="Grade" id={`edu-grade-${i}`} placeholder="e.g. 89" value={edu.grade ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, grade: e.target.value } : x))} />
                      </div>
                      <div>
                        <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">Description</label>
                        <textarea rows={2} className="w-full px-3 py-2 bg-surface-container-low border-none rounded-lg text-sm text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20" placeholder="Relevant coursework, thesis, activities…" value={edu.description ?? ''} onChange={e => setEducations(prev => prev.map((x, j) => j === i ? { ...x, description: e.target.value } : x))} />
                      </div>
                      <Button variant="danger" size="sm" icon="delete" type="button" onClick={() => setEducations(prev => prev.filter((_, j) => j !== i))}>Remove</Button>
                    </div>
                  ))}
                  <Button variant="secondary" size="sm" icon="add" type="button" onClick={() => setEducations(prev => [...prev, { school: '' }])}>Add Education</Button>
                </div>
              </Card>

              <div className="flex items-center gap-4">
                <Button type="submit" loading={save.isPending} icon="save">Save Profile</Button>
                {save.isSuccess && <span className="text-sm text-success">Saved.</span>}
                {save.isError && <span className="text-sm text-error">{(save.error as Error).message}</span>}
              </div>
            </form>

            {/* Upload Profile PDF */}
            <Card title="Upload CV or LinkedIn PDF">
              <div className="space-y-3">
                <p className="text-xs text-on-surface-variant">
                  Upload one or more CVs or LinkedIn profile exports (LinkedIn → Me → Save to PDF). You can upload files together or in separate sessions — all are stored and merged.
                </p>
                <div className="flex gap-2 items-center flex-wrap">
                  <input
                    ref={fileRef}
                    type="file"
                    accept="application/pdf"
                    multiple
                    className="text-sm text-on-surface-variant file:mr-3 file:px-3 file:py-1.5 file:text-xs file:font-bold file:rounded-lg file:border-0 file:bg-surface-container-high file:text-on-surface cursor-pointer"
                  />
                  <Button
                    type="button"
                    icon="upload"
                    loading={uploadCv.isPending}
                    onClick={handleUpload}
                  >
                    Upload
                  </Button>
                </div>
                {uploadCv.isError && (
                  <p className="text-sm text-error">{(uploadCv.error as Error).message}</p>
                )}
                {extractFromUploadedCv.isError && (
                  <p className="text-sm text-error">{(extractFromUploadedCv.error as Error).message}</p>
                )}
                {existingFiles.length > 0 && (
                  <Button
                    type="button"
                    icon="download"
                    variant="secondary"
                    loading={extractFromUploadedCv.isPending}
                    onClick={handleExtract}
                  >
                    Extract from uploaded CV/LinkedIn
                  </Button>
                )}
                {existingFiles.length > 0 && (
                  <div className="border-t border-outline-variant/20 pt-3 mt-1 space-y-2">
                    {existingFiles.map((f: any) => (
                      <div key={f.id} className="flex items-center justify-between gap-4">
                        <span className="text-xs text-on-surface-variant">
                          <strong>{f.original_filename}</strong>{' '}
                          <span className="text-outline">· {new Date(f.uploaded_at).toLocaleDateString()}</span>
                        </span>
                        <Button
                          variant="danger"
                          size="sm"
                          icon="delete"
                          loading={deleteUploadedCvById.isPending}
                          onClick={() => handleDeleteFile(f.id)}
                        >
                          Remove
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </Card>

            {/* Conflict resolution */}
            {uploadResult && uploadFiles.length > 0 && (
              <Card title="Apply parsed fields to your profile">
                <div className="space-y-4">
                  <p className="text-xs text-on-surface-variant">
                    Choose which value to use for each field. The "Merged" column combines all uploaded files.
                  </p>
                  <div className="overflow-x-auto">
                    {/* Header */}
                    <div
                      className="grid gap-2 pb-2 border-b border-outline-variant/20 text-[10px] font-bold uppercase tracking-wider text-outline"
                      style={{ gridTemplateColumns: tableGridCols }}
                    >
                      <span>Field</span>
                      <span>Current</span>
                      {uploadFiles.map((f: any, i: number) => (
                        <span key={f.id} title={f.original_filename}>{truncate(f.original_filename, 14)}</span>
                      ))}
                      <span>Merged</span>
                      <span>Choose</span>
                    </div>

                    {/* Rows */}
                    <div className="divide-y divide-outline-variant/20">
                      {CONFLICT_FIELDS.map(({ key, label }) => {
                        const mergedVal = uploadResult.merged?.[key]
                        const current = (form.values as any)[key]
                        const hasMerged = mergedVal !== null && mergedVal !== undefined && mergedVal !== ''

                        return (
                          <div
                            key={key}
                            className="py-3 grid gap-2 items-start text-sm"
                            style={{ gridTemplateColumns: tableGridCols }}
                          >
                            <span className="font-medium text-on-surface pt-0.5 text-xs">{label}</span>
                            <span className="text-on-surface-variant text-xs break-words">{current || <em className="opacity-50">empty</em>}</span>
                            {uploadFiles.map((f: any, i: number) => {
                              const fileVal = f.proposed?.[key]
                              const hasFileVal = fileVal !== null && fileVal !== undefined && fileVal !== ''
                              return (
                                <span key={f.id} className={`text-xs break-words ${hasFileVal ? 'text-secondary' : 'opacity-40'}`}>
                                  {hasFileVal ? String(fileVal) : <em>—</em>}
                                </span>
                              )
                            })}
                            <span className={`text-xs break-words ${hasMerged ? 'text-primary' : 'opacity-40'}`}>
                              {hasMerged ? String(mergedVal) : <em>—</em>}
                            </span>
                            <div className="flex flex-col gap-1">
                              <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input
                                  type="radio"
                                  name={key}
                                  value="keep"
                                  checked={fieldChoices[key] === 'keep'}
                                  onChange={() => setFieldChoices(prev => ({ ...prev, [key]: 'keep' }))}
                                  className="accent-primary"
                                />
                                Keep current
                              </label>
                              <label className={`flex items-center gap-1.5 text-xs cursor-pointer ${!hasMerged ? 'opacity-30 pointer-events-none' : ''}`}>
                                <input
                                  type="radio"
                                  name={key}
                                  value="merged"
                                  checked={fieldChoices[key] === 'merged'}
                                  disabled={!hasMerged}
                                  onChange={() => setFieldChoices(prev => ({ ...prev, [key]: 'merged' }))}
                                  className="accent-primary"
                                />
                                Use merged
                              </label>
                              {uploadFiles.map((f: any, i: number) => {
                                const fileVal = f.proposed?.[key]
                                const hasFileVal = fileVal !== null && fileVal !== undefined && fileVal !== ''
                                const choiceKey = `file-${i + 1}` as Choice
                                return (
                                  <label key={f.id} className={`flex items-center gap-1.5 text-xs cursor-pointer ${!hasFileVal ? 'opacity-30 pointer-events-none' : ''}`}>
                                    <input
                                      type="radio"
                                      name={key}
                                      value={choiceKey}
                                      checked={fieldChoices[key] === choiceKey}
                                      disabled={!hasFileVal}
                                      onChange={() => setFieldChoices(prev => ({ ...prev, [key]: choiceKey }))}
                                      className="accent-primary"
                                    />
                                    {truncate(f.original_filename, 14)}
                                  </label>
                                )
                              })}
                              <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input
                                  type="radio"
                                  name={key}
                                  value="skip"
                                  checked={fieldChoices[key] === 'skip'}
                                  onChange={() => setFieldChoices(prev => ({ ...prev, [key]: 'skip' }))}
                                  className="accent-primary"
                                />
                                Skip (leave blank)
                              </label>
                            </div>
                          </div>
                        )
                      })}

                      {/* Experience row */}
                      {(() => {
                        const listKey: ListKey = 'experiences'
                        const mergedItems = uploadResult.merged?.experiences
                        const hasMerged = (mergedItems?.length ?? 0) > 0
                        const currentSummary = summarizeExperiences(experiences)
                        const mergedSummary = summarizeExperiences(mergedItems)
                        return (
                          <div className="py-3 grid gap-2 items-start text-sm" style={{ gridTemplateColumns: tableGridCols }}>
                            <span className="font-medium text-on-surface pt-0.5 text-xs">Experience</span>
                            <span className="text-on-surface-variant text-xs break-words">{currentSummary || <em className="opacity-50">empty</em>}</span>
                            {uploadFiles.map((f: any, i: number) => {
                              const s = summarizeExperiences(f.proposed?.experiences)
                              return (
                                <span key={f.id} className={`text-xs break-words ${s ? 'text-secondary' : 'opacity-40'}`}>
                                  {s || <em>—</em>}
                                </span>
                              )
                            })}
                            <span className={`text-xs break-words ${hasMerged ? 'text-primary' : 'opacity-40'}`}>
                              {mergedSummary || <em>—</em>}
                            </span>
                            <div className="flex flex-col gap-1">
                              <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input type="radio" name={listKey} value="keep" checked={listChoices[listKey] === 'keep'} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: 'keep' }))} className="accent-primary" />
                                Keep current
                              </label>
                              <label className={`flex items-center gap-1.5 text-xs cursor-pointer ${!hasMerged ? 'opacity-30 pointer-events-none' : ''}`}>
                                <input type="radio" name={listKey} value="merged" checked={listChoices[listKey] === 'merged'} disabled={!hasMerged} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: 'merged' }))} className="accent-primary" />
                                Use merged
                              </label>
                              {uploadFiles.map((f: any, i: number) => {
                                const hasFileVal = (f.proposed?.experiences?.length ?? 0) > 0
                                const choiceKey = `file-${i + 1}` as Choice
                                return (
                                  <label key={f.id} className={`flex items-center gap-1.5 text-xs cursor-pointer ${!hasFileVal ? 'opacity-30 pointer-events-none' : ''}`}>
                                    <input type="radio" name={listKey} value={choiceKey} checked={listChoices[listKey] === choiceKey} disabled={!hasFileVal} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: choiceKey }))} className="accent-primary" />
                                    {truncate(f.original_filename, 14)}
                                  </label>
                                )
                              })}
                              <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input type="radio" name={listKey} value="skip" checked={listChoices[listKey] === 'skip'} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: 'skip' }))} className="accent-primary" />
                                Skip (leave blank)
                              </label>
                            </div>
                          </div>
                        )
                      })()}

                      {/* Education row */}
                      {(() => {
                        const listKey: ListKey = 'educations'
                        const mergedItems = uploadResult.merged?.educations
                        const hasMerged = (mergedItems?.length ?? 0) > 0
                        const currentSummary = summarizeEducations(educations)
                        const mergedSummary = summarizeEducations(mergedItems)
                        return (
                          <div className="py-3 grid gap-2 items-start text-sm" style={{ gridTemplateColumns: tableGridCols }}>
                            <span className="font-medium text-on-surface pt-0.5 text-xs">Education</span>
                            <span className="text-on-surface-variant text-xs break-words">{currentSummary || <em className="opacity-50">empty</em>}</span>
                            {uploadFiles.map((f: any, i: number) => {
                              const s = summarizeEducations(f.proposed?.educations)
                              return (
                                <span key={f.id} className={`text-xs break-words ${s ? 'text-secondary' : 'opacity-40'}`}>
                                  {s || <em>—</em>}
                                </span>
                              )
                            })}
                            <span className={`text-xs break-words ${hasMerged ? 'text-primary' : 'opacity-40'}`}>
                              {mergedSummary || <em>—</em>}
                            </span>
                            <div className="flex flex-col gap-1">
                              <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input type="radio" name={listKey} value="keep" checked={listChoices[listKey] === 'keep'} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: 'keep' }))} className="accent-primary" />
                                Keep current
                              </label>
                              <label className={`flex items-center gap-1.5 text-xs cursor-pointer ${!hasMerged ? 'opacity-30 pointer-events-none' : ''}`}>
                                <input type="radio" name={listKey} value="merged" checked={listChoices[listKey] === 'merged'} disabled={!hasMerged} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: 'merged' }))} className="accent-primary" />
                                Use merged
                              </label>
                              {uploadFiles.map((f: any, i: number) => {
                                const hasFileVal = (f.proposed?.educations?.length ?? 0) > 0
                                const choiceKey = `file-${i + 1}` as Choice
                                return (
                                  <label key={f.id} className={`flex items-center gap-1.5 text-xs cursor-pointer ${!hasFileVal ? 'opacity-30 pointer-events-none' : ''}`}>
                                    <input type="radio" name={listKey} value={choiceKey} checked={listChoices[listKey] === choiceKey} disabled={!hasFileVal} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: choiceKey }))} className="accent-primary" />
                                    {truncate(f.original_filename, 14)}
                                  </label>
                                )
                              })}
                              <label className="flex items-center gap-1.5 text-xs cursor-pointer">
                                <input type="radio" name={listKey} value="skip" checked={listChoices[listKey] === 'skip'} onChange={() => setListChoices(prev => ({ ...prev, [listKey]: 'skip' }))} className="accent-primary" />
                                Skip (leave blank)
                              </label>
                            </div>
                          </div>
                        )
                      })()}
                    </div>
                  </div>

                  {uploadResult.errors?.length > 0 && (
                    <div className="text-xs text-error space-y-1">
                      {uploadResult.errors.map((e: any, i: number) => (
                        <p key={i}>{e.filename}: {e.message}</p>
                      ))}
                    </div>
                  )}

                  <div className="flex gap-3 pt-2">
                    <Button icon="check" loading={save.isPending} onClick={handleApply}>Apply</Button>
                    <Button variant="secondary" onClick={() => setUploadResult(null)}>Cancel</Button>
                    {save.isError && <span className="text-sm text-error self-center">{(save.error as Error).message}</span>}
                  </div>
                </div>
              </Card>
            )}

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

            {/* Company re-enrichment */}
            <Card title="Company Data">
              <div className="space-y-3">
                <p className="text-xs text-on-surface-variant">
                  Re-enrich stale company records using live web snippets. Updates sector, type, and description for the oldest entries first.
                </p>
                <div className="flex items-center gap-4">
                  <Button
                    type="button"
                    variant="secondary"
                    icon="travel_explore"
                    loading={reenrich.isPending}
                    onClick={async () => {
                      setReenrichResult(null)
                      const result = await reenrich.mutateAsync(20)
                      setReenrichResult(result)
                    }}
                  >
                    Re-enrich Companies
                  </Button>
                  {reenrichResult && (
                    <span className="text-sm text-on-surface-variant">
                      Enriched <strong>{reenrichResult.enriched}</strong>
                      {reenrichResult.failed > 0 && <>, failed <strong>{reenrichResult.failed}</strong></>}
                    </span>
                  )}
                  {reenrich.isError && (
                    <span className="text-sm text-error">{(reenrich.error as Error).message}</span>
                  )}
                </div>
              </div>
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
