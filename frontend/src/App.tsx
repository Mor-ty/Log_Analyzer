import { BrowserRouter as Router, Routes, Route, Link, useLocation } from 'react-router-dom';
import { Upload, Activity, FileText, BarChart3, Loader2, CheckCircle2 } from 'lucide-react';
import './index.css';

import { AnalysisProvider, useAnalysis, TrackedJob } from './context/AnalysisContext';
import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import ClusterBrowserPage from './pages/ClusterBrowserPage';

// ─── Live analysis status bar ─────────────────────────────────────────────────
// Shows a slim banner below the nav while any job is running, and briefly flashes
// green when a job finishes. Clicking a label navigates to the page that owns it.

const SOURCE_PATH: Record<string, string> = {
  upload: '/',
  dashboard: '/dashboard',
  cluster: '/cluster',
};

function AnalysisStatusBar() {
  const { jobs } = useAnalysis();
  const allJobs = Object.values(jobs);
  const activeJobs = allJobs.filter(j => j.status === 'pending' || j.status === 'running');
  const recentlyDone = allJobs.filter(
    j => j.status === 'completed' && Date.now() - j.startedAt < 30_000,
  );

  if (activeJobs.length === 0 && recentlyDone.length === 0) return null;

  const renderJob = (job: TrackedJob) => {
    const isDone = job.status === 'completed';
    return (
      <Link
        key={job.jobId}
        to={SOURCE_PATH[job.source] ?? '/'}
        className={`flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium border transition-colors
          ${isDone
            ? 'bg-green-900/40 border-green-700/50 text-green-300 hover:bg-green-900/60'
            : 'bg-indigo-900/40 border-indigo-700/50 text-indigo-200 hover:bg-indigo-900/60'
          }`}
      >
        {isDone
          ? <CheckCircle2 className="h-3.5 w-3.5 text-green-400 shrink-0" />
          : <Loader2 className="h-3.5 w-3.5 text-indigo-400 animate-spin shrink-0" />
        }
        <span className="max-w-[18ch] truncate" title={job.label}>{job.label}</span>
        {!isDone && (
          <span className="text-indigo-400 font-normal shrink-0">{job.elapsedSeconds}s</span>
        )}
        {isDone && <span className="text-green-500 font-normal shrink-0">done</span>}
      </Link>
    );
  };

  return (
    <div className="bg-gray-900/80 border-b border-gray-700/60 backdrop-blur-sm">
      <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10 py-2 flex items-center gap-3 flex-wrap">
        <span className="text-xs text-gray-500 shrink-0 font-semibold uppercase tracking-wide">
          AI Analysis
        </span>
        <div className="flex flex-wrap gap-2">
          {activeJobs.map(renderJob)}
          {recentlyDone.map(renderJob)}
        </div>
        {activeJobs.length > 0 && (
          <span className="ml-auto text-xs text-indigo-500 shrink-0 hidden sm:block">
            {activeJobs.length} running · navigate freely
          </span>
        )}
      </div>
    </div>
  );
}

// ─── Nav link (highlights active route) ──────────────────────────────────────
function NavLink({ to, icon, label }: { to: string; icon: React.ReactNode; label: string }) {
  const location = useLocation();
  const active = location.pathname === to;
  return (
    <Link
      to={to}
      className={`flex items-center px-3 py-2 rounded-md text-sm font-medium transition
        ${active ? 'bg-gray-700 text-white' : 'text-gray-300 hover:bg-gray-700 hover:text-white'}`}
    >
      {icon}
      {label}
    </Link>
  );
}

// ─── App shell ────────────────────────────────────────────────────────────────
function AppShell() {
  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <nav className="bg-gray-800 border-b border-gray-700 sticky top-0 z-40">
        <div className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <Activity className="h-8 w-8 text-blue-400" />
              <span className="text-xl font-bold text-white">K8s Log Analytics</span>
            </div>
            <div className="flex items-center gap-1">
              <NavLink to="/"         icon={<Upload  className="h-4 w-4 mr-2" />} label="Upload"    />
              <NavLink to="/cluster"  icon={<FileText className="h-4 w-4 mr-2" />} label="Cluster"   />
              <NavLink to="/dashboard" icon={<BarChart3 className="h-4 w-4 mr-2" />} label="Dashboard" />
            </div>
          </div>
        </div>
      </nav>

      {/* Live analysis status bar — visible from any page */}
      <AnalysisStatusBar />

      <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10 py-8">
        <Routes>
          <Route path="/"         element={<UploadPage />} />
          <Route path="/cluster"  element={<ClusterBrowserPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </main>
    </div>
  );
}

function App() {
  return (
    <Router>
      <AnalysisProvider>
        <AppShell />
      </AnalysisProvider>
    </Router>
  );
}

export default App;
