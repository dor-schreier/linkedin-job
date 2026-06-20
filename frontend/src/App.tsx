import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import Health from './pages/Health'
import Scheduler from './pages/Scheduler'
import RejectRules from './pages/RejectRules'
import WatchRules from './pages/WatchRules'
import WatchMatches from './pages/WatchMatches'
import Scrape from './pages/Scrape'
import Profile from './pages/Profile'
import ProfileOptimizer from './pages/ProfileOptimizer'
import JobDetail from './pages/JobDetail'
import JobsList from './pages/JobsList'
import History from './pages/History'
import ApplicationTracker from './pages/ApplicationTracker'
import SimilarSearch from './pages/SimilarSearch'
import Companies from './pages/Companies'

function App() {
  return (
    <BrowserRouter basename="/">
      <Routes>
        <Route path="/" element={<Navigate to="/jobs" replace />} />
        <Route path="/applications" element={<ApplicationTracker />} />
        <Route path="/health" element={<Health />} />
        <Route path="/scheduler" element={<Scheduler />} />
        <Route path="/history" element={<History />} />
        <Route path="/reject-rules" element={<RejectRules />} />
        <Route path="/watch-rules" element={<WatchRules />} />
        <Route path="/watch-matches" element={<WatchMatches />} />
        <Route path="/scrape" element={<Scrape />} />
        <Route path="/profile" element={<Profile />} />
        <Route path="/profile/optimizer" element={<ProfileOptimizer />} />
        <Route path="/jobs" element={<JobsList />} />
        <Route path="/jobs/:id" element={<JobDetail />} />
        <Route path="/similar" element={<SimilarSearch />} />
        <Route path="/companies" element={<Companies />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App
