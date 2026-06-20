import { useEffect } from 'react'

interface Props {
  onClose: () => void
}

const sections = [
  {
    icon: 'dashboard',
    title: 'Jobs',
    body: 'Your main feed of scraped job listings. Each card shows fit score, salary, and AI-extracted intelligence. Filter by status, score, or keyword. Click a job to see the full detail, apply, save, or reject it.',
  },
  {
    icon: 'person_search',
    title: 'Profile',
    body: 'Enter your skills, title, and experience level. This drives the LLM fit-scoring engine — the more accurate your profile, the more relevant your scores.',
  },
  {
    icon: 'auto_awesome',
    title: 'Profile Optimizer',
    body: 'Upload your CV and let the AI suggest improvements based on the jobs you\'ve saved or applied to. Generates a tailored version of your CV for a target role.',
  },
  {
    icon: 'rule',
    title: 'Watch Rules',
    body: 'Define keyword or criteria-based rules. When a newly scraped job matches a rule, it appears in Watch Matches and you get a notification badge.',
  },
  {
    icon: 'block',
    title: 'Reject Rules',
    body: 'Set up automatic rejection criteria (e.g. salary too low, certain keywords). Jobs that match are auto-rejected and logged in the Reject Audit Log.',
  },
  {
    icon: 'my_location',
    title: 'Similar Search',
    body: 'Find jobs semantically similar to a role you describe. Uses vector similarity rather than exact keyword matching, surfacing roles you might otherwise miss.',
  },
  {
    icon: 'view_kanban',
    title: 'Applications',
    body: 'Kanban board tracking every job you\'ve applied to through the pipeline: Applied → Interviewing → Offer / Rejected. Log interview notes and follow-ups here.',
  },
  {
    icon: 'schedule',
    title: 'Scheduler',
    body: 'Configure how often the app automatically scrapes for new jobs (default every 6 hours). Shows the last run time and lets you trigger a manual scrape.',
  },
  {
    icon: 'history',
    title: 'History',
    body: 'Full log of every scrape run: how many jobs were found, added, rejected, and enriched. Useful for debugging why certain jobs did or didn\'t appear.',
  },
  {
    icon: 'monitor_heart',
    title: 'Health',
    body: 'System status dashboard — LLM provider connectivity, database stats, scheduler state, and recent error counts. Check here first if something seems off.',
  },
  {
    icon: 'notifications_active',
    title: 'Watch Matches',
    body: 'Jobs that triggered one of your Watch Rules. Unread matches show a badge on the sidebar. Mark them as read after reviewing.',
  },
]

export default function InfoModal({ onClose }: Props) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
      role="dialog"
      aria-modal="true"
      aria-label="App feature guide"
      onClick={onClose}
    >
      <div
        className="relative bg-surface rounded-2xl shadow-2xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-outline-variant/20 shrink-0">
          <div className="flex items-center gap-2">
            <span className="material-symbols-outlined text-primary" style={{ fontSize: 22 }}>info</span>
            <h2 className="text-lg font-bold font-headline">App Guide</h2>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors text-on-surface-variant hover:text-on-surface"
            aria-label="Close"
          >
            <span className="material-symbols-outlined" style={{ fontSize: 20 }}>close</span>
          </button>
        </div>

        {/* Content */}
        <div className="overflow-y-auto flex-1 px-6 py-4 space-y-4">
          {sections.map(({ icon, title, body }) => (
            <div key={title} className="flex gap-3">
              <span
                className="material-symbols-outlined text-primary shrink-0 mt-0.5"
                style={{ fontSize: 20 }}
              >
                {icon}
              </span>
              <div>
                <p className="font-semibold text-sm text-on-surface">{title}</p>
                <p className="text-sm text-on-surface-variant leading-relaxed">{body}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
