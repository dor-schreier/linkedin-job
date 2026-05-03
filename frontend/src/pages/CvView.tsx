import Layout from '../components/Layout'
import Card from '../components/ui/Card'
import Button from '../components/ui/Button'
import { useQuery } from '@tanstack/react-query'

function useCvList() {
  return useQuery({
    queryKey: ['cv', 'list'],
    queryFn: async () => {
      const res = await fetch('/cv/list')
      if (!res.ok) throw new Error('Failed to load CVs')
      return res.json()
    },
  })
}

export default function CvView() {
  const { data: cvs = [], isLoading } = useCvList()

  return (
    <Layout title="CV Export" active="cv-export">
      <div className="max-w-4xl space-y-6">

        {/* Import / build */}
        <Card title="Build CV from LinkedIn">
          <p className="text-sm text-on-surface-variant mb-4">
            Upload your LinkedIn data export ZIP to generate a structured CV.
          </p>
          <form
            method="post"
            action="/cv/import-zip"
            encType="multipart/form-data"
            className="flex items-end gap-4"
          >
            <div className="flex-1">
              <label className="text-[11px] font-bold uppercase tracking-wider text-outline block mb-1.5">
                LinkedIn ZIP
              </label>
              <input
                name="zip_file"
                type="file"
                accept=".zip"
                className="w-full text-sm text-on-surface-variant file:mr-3 file:px-3 file:py-1.5 file:rounded-lg file:border-0 file:bg-primary-container file:text-on-primary-container file:text-xs file:font-bold cursor-pointer"
              />
            </div>
            <Button type="submit" icon="upload">Import & Build</Button>
          </form>
        </Card>

        {/* CV list */}
        <Card title="Generated CVs">
          {isLoading && <p className="text-sm text-on-surface-variant">Loading…</p>}
          {!isLoading && (cvs as any[]).length === 0 && (
            <p className="text-sm text-outline">No CVs generated yet. Import your LinkedIn data above.</p>
          )}
          <div className="space-y-3">
            {(cvs as any[]).map((cv: any) => (
              <div key={cv.id} className="flex items-center gap-4 p-4 bg-surface-container rounded-xl">
                <div className="flex-1">
                  <p className="text-sm font-semibold text-on-surface">{cv.full_name}</p>
                  {cv.headline && (
                    <p className="text-xs text-on-surface-variant mt-0.5">{cv.headline}</p>
                  )}
                  {cv.created_at && (
                    <p className="text-xs text-outline mt-1">
                      {new Date(cv.created_at).toLocaleDateString()}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <a
                    href={`/cv/view?profile_url=${encodeURIComponent(cv.profile_url)}`}
                    className="text-xs text-primary hover:underline"
                  >
                    View
                  </a>
                  <a
                    href={`/cv/download/pdf?profile_url=${encodeURIComponent(cv.profile_url)}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-primary text-on-primary rounded-lg text-xs font-bold hover:opacity-90 transition-opacity"
                  >
                    <span className="material-symbols-outlined" style={{ fontSize: 14 }}>picture_as_pdf</span>
                    PDF
                  </a>
                  <a
                    href={`/cv/download/json?profile_url=${encodeURIComponent(cv.profile_url)}`}
                    className="inline-flex items-center gap-1 px-3 py-1.5 bg-surface-container-high text-on-surface-variant rounded-lg text-xs hover:text-on-surface transition-colors"
                  >
                    JSON
                  </a>
                </div>
              </div>
            ))}
          </div>
        </Card>

      </div>
    </Layout>
  )
}
