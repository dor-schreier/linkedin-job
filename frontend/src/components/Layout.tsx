import { type ReactNode, useEffect, useRef } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useUnreadCount } from '../api/queries'

interface Props {
  children: ReactNode
  title: string
  active?: string
  headerRight?: ReactNode
}

const navItems = [
  { key: 'jobs', href: '/jobs', icon: 'dashboard', label: 'Jobs' },
  { key: 'profile', href: '/profile', icon: 'person_search', label: 'Profile' },
  { key: 'profile-optimizer', href: '/profile/optimizer', icon: 'auto_awesome', label: 'Profile Optimizer' },
  { key: 'cv-export', href: '/cv/export', icon: 'description', label: 'Export CV', external: true },
  { key: 'search-config', href: '/search-config', icon: 'tune', label: 'Search Config' },
  { key: 'watch-rules', href: '/watch-rules', icon: 'rule', label: 'Watch Rules' },
  { key: 'reject-rules', href: '/reject-rules', icon: 'block', label: 'Reject Rules' },
  { key: 'scheduler', href: '/scheduler', icon: 'schedule', label: 'Scheduler' },
  { key: 'health', href: '/health', icon: 'monitor_heart', label: 'Health' },
]

const STORAGE_KEY = 'sidebar_state'
const DEFAULT_W = 256
const ICON_W = 68
const MIN_W = 60
const MAX_W = 400

function loadState(): { collapsed?: boolean; width?: number } {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '{}') }
  catch { return {} }
}
function saveState(s: { collapsed?: boolean; width?: number }) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(s)) } catch { /* storage unavailable */ }
}

export default function Layout({ children, title, active, headerRight }: Props) {
  const sidebarRef = useRef<HTMLElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const navigate = useNavigate()

  const { data: unreadData } = useUnreadCount()

  function applyState(width: number, collapsed: boolean) {
    const sidebar = sidebarRef.current
    const content = contentRef.current
    if (!sidebar) return
    const w = collapsed ? ICON_W : Math.max(MIN_W, Math.min(MAX_W, width))
    sidebar.style.width = `${w}px`
    if (content) content.style.marginLeft = `${w}px`

    const labels = sidebar.querySelectorAll<HTMLElement>('.nav-label')
    labels.forEach((el) => { el.style.display = collapsed ? 'none' : '' })

    const iconEl = sidebar.querySelector<HTMLElement>('#sidebar-toggle-icon')
    if (iconEl) iconEl.textContent = collapsed ? 'chevron_right' : 'chevron_left'

    const links = sidebar.querySelectorAll<HTMLElement>('.nav-link, .nav-cta')
    links.forEach((el) => {
      el.style.paddingLeft = collapsed ? '0' : ''
      el.style.paddingRight = collapsed ? '0' : ''
      el.style.justifyContent = collapsed ? 'center' : ''
    })
  }

  useEffect(() => {
    const sidebar = sidebarRef.current
    if (!sidebar) return
    const state = loadState()
    sidebar.style.transition = 'none'
    applyState(state.width || DEFAULT_W, !!state.collapsed)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { sidebar.style.transition = 'width 0.15s ease' })
    })

    const toggle = document.getElementById('sidebar-toggle')
    function onToggle() {
      const s = loadState()
      s.collapsed = !s.collapsed
      saveState(s)
      applyState(s.width || DEFAULT_W, !!s.collapsed)
    }
    toggle?.addEventListener('click', onToggle)

    const handle = document.getElementById('sidebar-resize-handle')
    function onMousedown(e: MouseEvent) {
      e.preventDefault()
      const startX = e.clientX
      const startW = sidebar!.getBoundingClientRect().width
      sidebar!.style.transition = 'none'
      document.body.style.userSelect = 'none'
      document.body.style.cursor = 'col-resize'

      function onMove(e: MouseEvent) {
        const newW = Math.max(MIN_W, Math.min(MAX_W, startW + (e.clientX - startX)))
        const nowCollapsed = newW < 90
        const s = loadState()
        if (!nowCollapsed) s.width = newW
        s.collapsed = nowCollapsed
        saveState(s)
        applyState(newW, nowCollapsed)
      }
      function onUp() {
        document.body.style.userSelect = ''
        document.body.style.cursor = ''
        sidebar!.style.transition = 'width 0.15s ease'
        document.removeEventListener('mousemove', onMove)
        document.removeEventListener('mouseup', onUp)
      }
      document.addEventListener('mousemove', onMove)
      document.addEventListener('mouseup', onUp)
    }
    handle?.addEventListener('mousedown', onMousedown)

    return () => {
      toggle?.removeEventListener('click', onToggle)
      handle?.removeEventListener('mousedown', onMousedown)
    }
  }, [])

  const unreadCount = (unreadData as any)?.count ?? 0

  return (
    <div className="min-h-screen bg-background text-on-surface">
      {/* Sidebar */}
      <aside
        ref={sidebarRef}
        id="app-sidebar"
        className="h-screen fixed left-0 top-0 bg-surface-container-low flex flex-col z-40 overflow-hidden"
        style={{ width: DEFAULT_W, transition: 'width 0.15s ease' }}
      >
        <div
          id="sidebar-resize-handle"
          className="absolute right-0 top-0 w-1.5 h-full cursor-col-resize hover:bg-primary/40 active:bg-primary/60 transition-colors z-40"
        />
        <div className="flex flex-col flex-1 p-4 min-w-0">
          <div className="mb-8 flex items-center gap-3 overflow-hidden min-w-0">
            <span className="material-symbols-outlined text-primary-dim shrink-0" style={{ fontSize: 22 }}>work</span>
            <h1 className="nav-label text-lg font-extrabold font-headline text-on-surface whitespace-nowrap overflow-hidden flex-1">Job Finder</h1>
            <button
              id="sidebar-toggle"
              className="shrink-0 w-8 h-8 bg-surface-container-high border border-outline-variant rounded-full flex items-center justify-center text-on-surface hover:bg-primary hover:text-on-primary hover:border-primary transition-colors shadow-md"
            >
              <span id="sidebar-toggle-icon" className="material-symbols-outlined" style={{ fontSize: 18 }}>chevron_left</span>
            </button>
          </div>

          <nav className="flex-1 space-y-1 text-sm">
            {navItems.map(({ key, href, icon, label, external }) =>
              external ? (
                <a
                  key={key}
                  href={href}
                  className={`nav-link flex items-center gap-3 px-4 py-3 rounded-lg transition-colors overflow-hidden ${
                    active === key
                      ? 'font-semibold text-on-surface bg-surface-container border-r-2 border-primary'
                      : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                  }`}
                >
                  <span className="material-symbols-outlined shrink-0" style={{ fontSize: 20 }}>{icon}</span>
                  <span className="nav-label whitespace-nowrap overflow-hidden">{label}</span>
                </a>
              ) : (
                <NavLink
                  key={key}
                  to={href}
                  className={({ isActive }) =>
                    `nav-link flex items-center gap-3 px-4 py-3 rounded-lg transition-colors overflow-hidden ${
                      isActive || active === key
                        ? 'font-semibold text-on-surface bg-surface-container border-r-2 border-primary'
                        : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                    }`
                  }
                >
                  <span className="material-symbols-outlined shrink-0" style={{ fontSize: 20 }}>{icon}</span>
                  <span className="nav-label whitespace-nowrap overflow-hidden">{label}</span>
                </NavLink>
              )
            )}

            {/* Watch matches with badge */}
            <NavLink
              to="/watch-matches"
              className={({ isActive }) =>
                `nav-link flex items-center gap-3 px-4 py-3 rounded-lg transition-colors overflow-hidden ${
                  isActive || active === 'watch-matches'
                    ? 'font-semibold text-on-surface bg-surface-container border-r-2 border-primary'
                    : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                }`
              }
            >
              <span className="material-symbols-outlined shrink-0" style={{ fontSize: 20 }}>notifications_active</span>
              <span className="nav-label whitespace-nowrap overflow-hidden">Matches</span>
              {unreadCount > 0 && (
                <span className="nav-label ml-auto inline-flex items-center justify-center text-xs font-bold text-on-error bg-error rounded-full px-1.5 py-0.5 min-w-[1.25rem] shrink-0">
                  {unreadCount}
                </span>
              )}
            </NavLink>
          </nav>

          <div className="mt-auto pt-4">
            <button
              onClick={() => navigate('/scrape')}
              className="nav-cta w-full flex items-center justify-center gap-2 py-3 bg-primary text-on-primary rounded-lg font-bold text-sm hover:opacity-90 transition-opacity overflow-hidden"
            >
              <span className="material-symbols-outlined shrink-0">add_task</span>
              <span className="nav-label whitespace-nowrap overflow-hidden">Find New Jobs</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div
        ref={contentRef}
        id="app-content"
        className="min-h-screen"
        style={{ marginLeft: DEFAULT_W }}
      >
        <header className="sticky top-0 z-50 bg-surface/80 backdrop-blur-md px-8 py-4 border-b border-outline-variant/15 flex items-center justify-between">
          <h2 className="text-xl font-bold font-headline">{title}</h2>
          {headerRight && <div>{headerRight}</div>}
        </header>
        <div className="px-8 py-6">{children}</div>
      </div>
    </div>
  )
}
