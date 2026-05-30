import React, { useState, useEffect, useRef } from 'react';
import { BarChart3, PieChart, TrendingUp, Loader2, AlertCircle, Filter, Brain, Trash2, Server, FileText, History, ChevronDown, ChevronUp } from 'lucide-react';
import { useLocation } from 'react-router-dom';
import { logAPI, parseAnalysis } from '../services/api';
import { LogEntry, K8sResource, LogSession } from '../types';
import { useAnalysis } from '../context/AnalysisContext';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart as RechartsPieChart,
  Cell,
  Pie
} from 'recharts';

const DashboardPage: React.FC = () => {
  const location = useLocation();
  const { startTracking, getLatestJob, clearJob, jobs } = useAnalysis();
  /** Tracks which completed dashboard jobs we've already shown a popup for. */
  const handledJobsRef = useRef<Set<string>>(new Set());

  const [resources, setResources] = useState<K8sResource[]>([]);
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [selectedResource, setSelectedResource] = useState<number | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [showAnalysisPopup, setShowAnalysisPopup] = useState(false);
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<LogSession[]>([]);
  const [deletingSessionId, setDeletingSessionId] = useState<number | null>(null);
  const [confirmDeleteSessionId, setConfirmDeleteSessionId] = useState<number | null>(null);
  const [expandedGroupName, setExpandedGroupName] = useState<string | null>(null);
  const [confirmDeleteGroupName, setConfirmDeleteGroupName] = useState<string | null>(null);

  // ── Watch for dashboard jobs that complete — show popup automatically ──────
  useEffect(() => {
    const completedJobs = Object.values(jobs).filter(
      j =>
        j.source === 'dashboard' &&
        j.status === 'completed' &&
        j.result &&
        !handledJobsRef.current.has(j.jobId),
    );
    if (completedJobs.length === 0) return;
    const latest = completedJobs.sort((a, b) => b.startedAt - a.startedAt)[0];
    handledJobsRef.current.add(latest.jobId);
    setAnalysis(parseAnalysis(latest.result!));
    setShowAnalysisPopup(true);
    loadSessions();
    clearJob(latest.jobId);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs]);

  // Show popup if redirected from Cluster page with analysis in state
  useEffect(() => {
    const navState = location.state as any;
    if (navState?.analysis) {
      setAnalysis(navState.analysis);
      setShowAnalysisPopup(true);
      // Clear navigation state so popup doesn't re-appear on manual refresh
      window.history.replaceState({}, document.title);
    }
  }, [location.state]);

  useEffect(() => {
    loadResources();
    loadSessions();
  }, []);

  useEffect(() => {
    loadEntries();
  }, [selectedResource, selectedLevel]);

  const loadResources = async () => {
    setLoading(true);
    setError(null);
    try {
      const resourcesData = await logAPI.getResources();
      setResources(resourcesData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load resources');
    } finally {
      setLoading(false);
    }
  };

  const loadSessions = async () => {
    try {
      const data = await logAPI.getSessions();
      setSessions(data);
    } catch { /* non-critical */ }
  };

  const loadEntries = async () => {
    setLoading(true);
    setError(null);
    try {
      const entries = await logAPI.getEntries(selectedResource || undefined, selectedLevel || undefined, 1000);
      setEntries(entries);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load entries');
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyze = async (resourceId: number) => {
    setError(null);
    try {
      const resource = resources.find(r => r.id === resourceId);
      const label = resource ? `${resource.namespace}/${resource.pod_name}` : `Resource #${resourceId}`;
      const job = await logAPI.analyzeLogs(resourceId, undefined, 'general');
      startTracking(job.job_id, 'dashboard', label, resourceId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis');
    }
  };

  const handleDeleteResource = async (resourceId: number) => {
    setDeletingId(resourceId);
    setError(null);
    try {
      await logAPI.deleteResource(resourceId);
      if (selectedResource === resourceId) setSelectedResource(null);
      await loadResources();
      await loadEntries();
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete resource');
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const handleRestoreSession = (session: LogSession) => {
    if (!session.analysis) return;
    const parsed = parseAnalysis(session.analysis);
    setAnalysis(parsed);
    setShowAnalysisPopup(true);
  };

  const handleDeleteSession = async (sessionId: number) => {
    setDeletingSessionId(sessionId);
    try {
      await logAPI.deleteSession(sessionId);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete session');
    } finally {
      setDeletingSessionId(null);
      setConfirmDeleteSessionId(null);
    }
  };

  const handleDeleteGroup = async (name: string) => {
    const group = sessions.filter(s => s.name === name);
    for (const s of group) {
      try { await logAPI.deleteSession(s.id); } catch { /* best effort */ }
    }
    setSessions(prev => prev.filter(s => s.name !== name));
    setConfirmDeleteGroupName(null);
    if (expandedGroupName === name) setExpandedGroupName(null);
  };

  // Prepare data for charts
  const LEVEL_COLORS: Record<string, string> = {
    DEBUG:    '#8B5CF6',
    INFO:     '#3B82F6',
    WARNING:  '#F59E0B',
    ERROR:    '#EF4444',
    CRITICAL: '#DC2626',
    UNKNOWN:  '#6B7280',
  };

  const levelData = entries.reduce((acc, entry) => {
    const level = (entry.level || 'UNKNOWN').toUpperCase();
    acc[level] = (acc[level] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const levelChartData = Object.entries(levelData)
    .map(([level, count]) => ({ level, count, fill: LEVEL_COLORS[level] ?? '#6B7280' }))
    .sort((a, b) => {
      const order = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL', 'UNKNOWN'];
      return order.indexOf(a.level) - order.indexOf(b.level);
    });

  const resourceChartData = resources
    .map(r => ({
      name: r.pod_name.length > 18 ? r.pod_name.substring(0, 18) + '…' : r.pod_name,
      fullName: `${r.namespace}/${r.pod_name}`,
      count: entries.filter(e => e.resource_id === r.id).length,
    }))
    .filter(r => r.count > 0)
    .sort((a, b) => b.count - a.count);

  const getLevelColor = (level: string) => LEVEL_COLORS[(level || 'UNKNOWN').toUpperCase()] ?? '#6B7280';

  const getSeverityStyle = (severity?: string) => {
    switch ((severity || '').toLowerCase()) {
      case 'critical': return 'bg-red-900/60 text-red-300 border-red-700';
      case 'high':     return 'bg-orange-900/60 text-orange-300 border-orange-700';
      case 'warning':  return 'bg-yellow-900/60 text-yellow-300 border-yellow-700';
      case 'low':
      case 'normal':   return 'bg-green-900/60 text-green-300 border-green-700';
      default:         return 'bg-gray-700 text-gray-300 border-gray-600';
    }
  };

  // Custom pie label renderer — only shown when slice is large enough
  const renderPieLabel = ({ cx, cy, midAngle, innerRadius, outerRadius, percent, level }: any) => {
    if (percent < 0.06) return null;
    const RADIAN = Math.PI / 180;
    const r = innerRadius + (outerRadius - innerRadius) * 0.6;
    const x = cx + r * Math.cos(-midAngle * RADIAN);
    const y = cy + r * Math.sin(-midAngle * RADIAN);
    return (
      <text x={x} y={y} fill="#fff" textAnchor="middle" dominantBaseline="central" fontSize={11} fontWeight={600}>
        {level}
      </text>
    );
  };

  const CustomBarTooltip = ({ active, payload }: any) => {
    if (active && payload?.length) {
      return (
        <div className="bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm">
          <p className="text-white font-medium">{payload[0].payload.fullName}</p>
          <p className="text-blue-400">{payload[0].value} entries</p>
        </div>
      );
    }
    return null;
  };

  const CustomPieTooltip = ({ active, payload }: any) => {
    if (active && payload?.length) {
      const total = levelChartData.reduce((s, d) => s + d.count, 0);
      return (
        <div className="bg-gray-900 border border-gray-600 rounded px-3 py-2 text-sm">
          <p style={{ color: payload[0].payload.fill }} className="font-semibold">{payload[0].name}</p>
          <p className="text-white">{payload[0].value} entries ({((payload[0].value / total) * 100).toFixed(1)}%)</p>
        </div>
      );
    }
    return null;
  };

  if (loading && resources.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin h-8 w-8 text-blue-400" />
      </div>
    );
  }

  // Group sessions by name (newest-first within each group), groups sorted by most recent
  const groupedSessions: Record<string, LogSession[]> = {};
  sessions.forEach(s => {
    if (!groupedSessions[s.name]) groupedSessions[s.name] = [];
    groupedSessions[s.name].push(s);
  });
  const sortedGroupNames = Object.keys(groupedSessions).sort((a, b) =>
    new Date(groupedSessions[b][0].created_at).getTime() - new Date(groupedSessions[a][0].created_at).getTime()
  );
  const uniqueCount = sortedGroupNames.length;

  return (
    <div className="flex gap-6 items-start w-full">

      {/* ── LEFT SIDEBAR: Session History ── */}
      <aside className="w-72 shrink-0 self-start sticky top-6 rounded-xl border border-gray-700/80 overflow-hidden flex flex-col shadow-lg" style={{ background: '#0b1120', maxHeight: 'calc(100vh - 6rem)' }}>
        <div className="px-4 py-4 border-b border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <History className="h-4 w-4 text-purple-400" />
            <span className="text-sm font-semibold text-gray-200 uppercase tracking-wide">Sessions</span>
          </div>
          {uniqueCount > 0 && (
            <span className="bg-purple-600/30 text-purple-300 text-xs font-semibold px-2 py-0.5 rounded-full border border-purple-700/50">
              {uniqueCount}
            </span>
          )}
        </div>

        <div className="overflow-y-auto" style={{ maxHeight: 'calc(100vh - 10rem)' }}>
          {uniqueCount === 0 ? (
            <div className="flex flex-col items-center justify-center py-16 px-4 text-center">
              <History className="h-10 w-10 text-gray-700 mb-3" />
              <p className="text-gray-500 text-sm">No sessions yet</p>
              <p className="text-gray-600 text-xs mt-1">Analyze a resource or upload a log file</p>
            </div>
          ) : (
            <div className="divide-y divide-gray-700/50">
              {sortedGroupNames.map((name) => {
                const group = groupedSessions[name];
                const latest = group[0];
                const count = group.length;
                const isExpanded = expandedGroupName === name;

                return (
                  <div key={name} className={`transition-colors ${isExpanded ? 'bg-gray-800/60' : 'hover:bg-gray-800/30'}`}>
                    {/* Group header */}
                    <div className="px-3 py-3 flex items-start gap-2">
                      <div className="mt-0.5 shrink-0">
                        {latest.source_type === 'pod'
                          ? <Server className="h-4 w-4 text-blue-400" />
                          : <FileText className="h-4 w-4 text-green-400" />}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-100 truncate leading-tight" title={name}>{name}</p>
                        <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                          {latest.severity && (
                            <span className={`text-xs px-1.5 py-0.5 rounded border font-medium ${getSeverityStyle(latest.severity)}`}>
                              {latest.severity}
                            </span>
                          )}
                          <span className="text-xs text-gray-500">{latest.entry_count} entries</span>
                        </div>
                        <div className="flex items-center gap-1 mt-1">
                          <span className="text-xs text-purple-400 font-semibold">{count}&times; analysed</span>
                        </div>
                      </div>
                      <div className="flex flex-col gap-1 shrink-0 items-end">
                        {/* Expand toggle */}
                        <button
                          onClick={() => setExpandedGroupName(isExpanded ? null : name)}
                          className="p-1 text-gray-400 hover:text-purple-300 hover:bg-purple-900/30 rounded transition-colors"
                          title="Show executions"
                        >
                          {isExpanded ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
                        </button>
                        {/* Group delete */}
                        {confirmDeleteGroupName === name ? (
                          <div className="flex gap-0.5 mt-0.5">
                            <button onClick={() => handleDeleteGroup(name)}
                              className="text-xs bg-red-600 hover:bg-red-700 text-white px-1.5 py-0.5 rounded">All</button>
                            <button onClick={() => setConfirmDeleteGroupName(null)}
                              className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-1.5 py-0.5 rounded">✕</button>
                          </div>
                        ) : (
                          <button onClick={() => setConfirmDeleteGroupName(name)}
                            className="p-1 text-gray-700 hover:text-red-400 rounded transition-colors" title="Delete all runs">
                            <Trash2 className="h-3 w-3" />
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Executions list */}
                    {isExpanded && (
                      <div className="border-t border-gray-700/60 bg-gray-900/50 divide-y divide-gray-800/60">
                        {group.map((session, idx) => (
                          <div key={session.id} className="px-3 py-2 flex items-center gap-2 hover:bg-gray-800/40 transition-colors">
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="text-xs font-semibold text-gray-400">#{count - idx}</span>
                                <span className="text-xs text-gray-500">
                                  {new Date(session.created_at).toLocaleString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                                </span>
                              </div>
                              {session.severity && (
                                <span className={`text-xs px-1 py-0.5 rounded border font-medium mt-0.5 inline-block ${getSeverityStyle(session.severity)}`}>
                                  {session.severity}
                                </span>
                              )}
                            </div>
                            <div className="flex items-center gap-1 shrink-0">
                              <button
                                onClick={() => handleRestoreSession(session)}
                                disabled={!session.analysis}
                                title={session.analysis ? 'View analysis' : 'No analysis stored'}
                                className={`p-1 rounded transition-colors text-xs ${
                                  session.analysis
                                    ? 'text-purple-400 hover:text-purple-300 hover:bg-purple-900/30'
                                    : 'text-gray-700 cursor-not-allowed'
                                }`}
                              >
                                <Brain className="h-3.5 w-3.5" />
                              </button>
                              {confirmDeleteSessionId === session.id ? (
                                <div className="flex gap-0.5">
                                  <button onClick={() => handleDeleteSession(session.id)} disabled={deletingSessionId === session.id}
                                    className="text-xs bg-red-600 hover:bg-red-700 text-white px-1 py-0.5 rounded">
                                    {deletingSessionId === session.id ? '…' : 'Y'}
                                  </button>
                                  <button onClick={() => setConfirmDeleteSessionId(null)}
                                    className="text-xs bg-gray-600 text-white px-1 py-0.5 rounded">N</button>
                                </div>
                              ) : (
                                <button onClick={() => setConfirmDeleteSessionId(session.id)}
                                  className="p-1 text-gray-800 hover:text-red-400 rounded transition-colors">
                                  <Trash2 className="h-3 w-3" />
                                </button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>

      {/* ── MAIN CONTENT ── */}
      <main className="flex-1 min-w-0 space-y-6">
        <div className="flex flex-col gap-1.5 pb-5 border-b border-gray-700/50">
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Analytics Dashboard</h1>
          <p className="text-gray-400 text-sm">Monitor log analytics, anomalies and resource health metrics</p>
        </div>

        {error && (
          <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 flex items-start gap-3">
            <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
            <p className="text-red-300 text-sm">{error}</p>
          </div>
        )}

        {/* Filters & Resources */}
        <div className="bg-gray-800/70 rounded-xl border border-gray-700 overflow-hidden shadow-md">
          <div className="px-6 py-3.5 border-b border-gray-700 flex items-center gap-2 bg-gray-800">
            <Filter className="h-4 w-4 text-blue-400" />
            <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Filters &amp; Resources</h2>
          </div>
          <div className="p-6 grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Scrollable resource list */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Resource</label>
              <div className="border border-gray-600 rounded-lg bg-gray-900 overflow-y-auto" style={{ maxHeight: '11rem' }}>
                <div
                  className={`flex items-center gap-2 px-3 py-2 cursor-pointer border-b border-gray-700/60 transition-colors ${
                    selectedResource === null ? 'bg-blue-600/20 text-blue-300' : 'text-gray-400 hover:bg-gray-700/50 hover:text-gray-200'
                  }`}
                  onClick={() => setSelectedResource(null)}
                >
                  <Server className="h-3.5 w-3.5 shrink-0" />
                  <span className="text-sm font-medium">All Resources</span>
                </div>
                {resources.map((resource) => (
                  <div
                    key={resource.id}
                    className={`group flex items-center justify-between px-3 py-2 border-b border-gray-700/40 last:border-0 transition-colors ${
                      selectedResource === resource.id ? 'bg-blue-600/20' : 'hover:bg-gray-700/50'
                    }`}
                  >
                    <div className="flex-1 min-w-0 cursor-pointer" onClick={() => setSelectedResource(resource.id)}>
                      <p className={`text-sm font-medium truncate leading-tight ${selectedResource === resource.id ? 'text-blue-300' : 'text-gray-200'}`}>
                        {resource.pod_name}
                      </p>
                      <p className="text-xs text-gray-500 truncate">{resource.namespace}</p>
                    </div>
                    {confirmDeleteId === resource.id ? (
                      <div className="flex items-center gap-1 ml-2 shrink-0">
                        <button onClick={() => handleDeleteResource(resource.id)} disabled={deletingId === resource.id}
                          className="text-xs bg-red-600 hover:bg-red-700 text-white px-2 py-0.5 rounded font-medium">
                          {deletingId === resource.id ? '…' : 'Yes'}
                        </button>
                        <button onClick={() => setConfirmDeleteId(null)}
                          className="text-xs bg-gray-600 hover:bg-gray-500 text-white px-2 py-0.5 rounded font-medium">
                          No
                        </button>
                      </div>
                    ) : (
                      <button onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(resource.id); }}
                        className="ml-2 shrink-0 opacity-0 group-hover:opacity-100 text-gray-500 hover:text-red-400 transition-opacity"
                        title="Delete resource">
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                ))}
                {resources.length === 0 && (
                  <p className="text-gray-500 text-xs px-3 py-4 text-center">No resources yet</p>
                )}
              </div>
            </div>
            {/* Log Level */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Log Level</label>
              <select
                value={selectedLevel || ''}
                onChange={(e) => setSelectedLevel(e.target.value || null)}
                className="w-full bg-gray-900 text-gray-200 rounded-lg px-3 py-2 border border-gray-600 focus:outline-none focus:border-blue-500 text-sm h-9"
              >
                <option value="">All Levels</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
              <div className="grid grid-cols-2 gap-2 mt-1">
                {[
                  { label: 'Errors', count: entries.filter(e => e.level === 'ERROR' || e.level === 'CRITICAL').length, color: 'text-red-400' },
                  { label: 'Warnings', count: entries.filter(e => e.level === 'WARNING').length, color: 'text-yellow-400' },
                ].map(({ label, count, color }) => (
                  <div key={label} className="bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-center">
                    <p className={`text-lg font-bold ${color}`}>{count}</p>
                    <p className="text-xs text-gray-500">{label}</p>
                  </div>
                ))}
              </div>
            </div>
            {/* Actions */}
            <div className="flex flex-col gap-1.5">
              <label className="text-xs font-semibold text-gray-400 uppercase tracking-wide">Actions</label>
              {(() => {
                const rJob = selectedResource ? getLatestJob('dashboard', selectedResource) : undefined;
                const isAnalyzing = rJob?.status === 'pending' || rJob?.status === 'running';
                return (
                  <>
                    <button
                      onClick={() => selectedResource && handleAnalyze(selectedResource)}
                      disabled={!selectedResource || isAnalyzing}
                      className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-700 disabled:text-gray-500 text-white font-medium py-2 px-4 rounded-lg transition-colors flex items-center justify-center gap-2 text-sm h-9"
                    >
                      {isAnalyzing ? (
                        <><Loader2 className="animate-spin h-4 w-4" />Analyzing…</>
                      ) : (
                        <><Brain className="h-4 w-4" />Analyze with AI</>
                      )}
                    </button>
                    {!selectedResource && (
                      <p className="text-xs text-gray-500 text-center">Select a resource above to analyze</p>
                    )}
                    {isAnalyzing && rJob && (
                      <p className="text-xs text-indigo-400 text-center animate-pulse">
                        AI processing… {rJob.elapsedSeconds}s elapsed
                      </p>
                    )}
                  </>
                );
              })()}
            </div>
          </div>
        </div>

        {/* Summary Cards */}
      <div className="grid grid-cols-2 xl:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 flex items-center gap-4 shadow-sm hover:border-blue-600/50 transition-colors">
          <div className="rounded-lg p-3 bg-blue-500/10 border border-blue-500/20 shrink-0">
            <BarChart3 className="h-6 w-6 text-blue-400" />
          </div>
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wide">Total Entries</p>
            <p className="text-3xl font-bold text-white leading-none mt-1">{entries.length}</p>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 flex items-center gap-4 shadow-sm hover:border-red-600/50 transition-colors">
          <div className="rounded-lg p-3 bg-red-500/10 border border-red-500/20 shrink-0">
            <AlertCircle className="h-6 w-6 text-red-400" />
          </div>
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wide">Errors</p>
            <p className="text-3xl font-bold text-red-400 leading-none mt-1">
              {entries.filter(e => e.level === 'ERROR' || e.level === 'CRITICAL').length}
            </p>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 flex items-center gap-4 shadow-sm hover:border-yellow-600/50 transition-colors">
          <div className="rounded-lg p-3 bg-yellow-500/10 border border-yellow-500/20 shrink-0">
            <TrendingUp className="h-6 w-6 text-yellow-400" />
          </div>
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wide">Warnings</p>
            <p className="text-3xl font-bold text-yellow-400 leading-none mt-1">
              {entries.filter(e => e.level === 'WARNING').length}
            </p>
          </div>
        </div>
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 flex items-center gap-4 shadow-sm hover:border-green-600/50 transition-colors">
          <div className="rounded-lg p-3 bg-green-500/10 border border-green-500/20 shrink-0">
            <PieChart className="h-6 w-6 text-green-400" />
          </div>
          <div>
            <p className="text-gray-400 text-xs font-medium uppercase tracking-wide">Resources</p>
            <p className="text-3xl font-bold text-white leading-none mt-1">{resources.length}</p>
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Log Level Distribution - Donut chart with legend */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 shadow-sm">
          <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2"><PieChart className="h-4 w-4 text-purple-400" />Log Level Distribution</h2>
          {levelChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={360}>
              <RechartsPieChart>
                <Pie
                  data={levelChartData}
                  cx="50%"
                  cy="45%"
                  innerRadius={65}
                  outerRadius={110}
                  dataKey="count"
                  nameKey="level"
                  labelLine={false}
                  label={renderPieLabel}
                  paddingAngle={2}
                >
                  {levelChartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.fill} stroke="transparent" />
                  ))}
                </Pie>
                <Tooltip content={<CustomPieTooltip />} />
                <Legend
                  formatter={(value) => <span style={{ color: LEVEL_COLORS[value] ?? '#6B7280', fontSize: 12 }}>{value}</span>}
                  iconType="circle"
                  iconSize={8}
                  wrapperStyle={{ paddingTop: 8 }}
                />
              </RechartsPieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-12">No data available</p>
          )}
        </div>

        {/* Log Entries per Resource - horizontal or vertical bar with angled labels */}
        <div className="bg-gray-800 rounded-xl border border-gray-700 p-5 shadow-sm">
          <h2 className="text-base font-semibold text-white mb-4 flex items-center gap-2"><BarChart3 className="h-4 w-4 text-blue-400" />Log Entries per Resource</h2>
          {resourceChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={360}>
              <BarChart
                data={resourceChartData}
                margin={{ top: 8, right: 16, left: 0, bottom: resourceChartData.length > 4 ? 60 : 20 }}
                barCategoryGap="30%"
              >
                <defs>
                  <linearGradient id="barGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#60A5FA" stopOpacity={1} />
                    <stop offset="100%" stopColor="#2563EB" stopOpacity={0.9} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" vertical={false} />
                <XAxis
                  dataKey="name"
                  stroke="#9CA3AF"
                  tick={{ fill: '#9CA3AF', fontSize: 11 }}
                  angle={resourceChartData.length > 4 ? -35 : 0}
                  textAnchor={resourceChartData.length > 4 ? 'end' : 'middle'}
                  interval={0}
                />
                <YAxis
                  stroke="#9CA3AF"
                  tick={{ fill: '#9CA3AF', fontSize: 11 }}
                  allowDecimals={false}
                  width={40}
                />
                <Tooltip content={<CustomBarTooltip />} cursor={{ fill: 'rgba(255,255,255,0.05)' }} />
                <Bar dataKey="count" fill="url(#barGradient)" radius={[4, 4, 0, 0]} name="Entries" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-12">No data available</p>
          )}
        </div>
      </div>

      {/* Recent Logs Table */}
      <div className="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden shadow-sm">
        <div className="px-6 py-4 border-b border-gray-700 flex items-center gap-2 bg-gray-800">
          <FileText className="h-4 w-4 text-green-400" />
          <h2 className="text-sm font-semibold text-gray-200 uppercase tracking-wider">Recent Log Entries</h2>
          {entries.length > 0 && (
            <span className="ml-auto text-xs text-gray-500">Showing {Math.min(entries.length, 20)} of {entries.length}</span>
          )}
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-900/50">
                <th className="text-left text-gray-500 font-medium py-3 px-5 text-xs uppercase tracking-wide w-44">Timestamp</th>
                <th className="text-left text-gray-500 font-medium py-3 px-4 text-xs uppercase tracking-wide w-24">Level</th>
                <th className="text-left text-gray-500 font-medium py-3 px-4 text-xs uppercase tracking-wide">Message</th>
                <th className="text-left text-gray-500 font-medium py-3 px-5 text-xs uppercase tracking-wide w-48">Source</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-700/50">
              {entries.slice(0, 20).map((entry, idx) => (
                <tr key={entry.id} className={`hover:bg-gray-700/40 transition-colors ${idx % 2 === 0 ? '' : 'bg-gray-900/20'}`}>
                  <td className="py-3 px-5 text-gray-400 text-xs tabular-nums">
                    {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '-'}
                  </td>
                  <td className="py-3 px-4">
                    <span
                      className="px-2 py-0.5 rounded-md text-xs font-semibold border"
                      style={{
                        backgroundColor: getLevelColor(entry.level || 'INFO') + '18',
                        color: getLevelColor(entry.level || 'INFO'),
                        borderColor: getLevelColor(entry.level || 'INFO') + '40',
                      }}
                    >
                      {entry.level || 'INFO'}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-gray-300 max-w-xl">
                    <p className="truncate">{entry.message}</p>
                  </td>
                  <td className="py-3 px-5 text-gray-500 text-xs truncate max-w-[12rem]">
                    {entry.source_file || `Resource ${entry.resource_id}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {entries.length === 0 && (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <FileText className="h-10 w-10 text-gray-700 mb-3" />
              <p className="text-gray-500">No log entries found</p>
              <p className="text-gray-600 text-xs mt-1">Upload a file or collect logs from a pod</p>
            </div>
          )}
        </div>
      </div>

      {/* Analysis Results Popup */}
      {showAnalysisPopup && analysis && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 max-w-2xl w-full mx-4 border border-purple-700 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-2xl font-bold text-white flex items-center">
                <Brain className="h-6 w-6 mr-2 text-purple-400" />
                AI Analysis Results
              </h2>
              <button
                onClick={() => setShowAnalysisPopup(false)}
                className="text-gray-400 hover:text-white"
              >
                ✕
              </button>
            </div>

            {/* Severity */}
            <div className={`p-4 rounded-lg mb-4 ${
              analysis.severity === 'Critical' ? 'bg-red-900/50 border border-red-700' :
              analysis.severity === 'Warning' ? 'bg-yellow-900/50 border border-yellow-700' :
              'bg-green-900/50 border border-green-700'
            }`}>
              <p className={`font-semibold ${
                analysis.severity === 'Critical' ? 'text-red-300' :
                analysis.severity === 'Warning' ? 'text-yellow-300' :
                'text-green-300'
              }`}>
                Severity: {analysis.severity}
              </p>
              <p className="text-sm text-gray-400">Confidence: {(analysis.confidence_score * 100).toFixed(1)}%</p>
            </div>

            {/* Health Assessment */}
            {analysis.health_assessment && (
              <div className="mb-4">
                <h3 className="font-semibold text-white mb-2">Health Assessment</h3>
                <p className="text-gray-300 bg-gray-700 rounded p-3">{analysis.health_assessment}</p>
              </div>
            )}

            {/* Anomalies */}
            {analysis.anomalies && analysis.anomalies.length > 0 && (
              <div className="mb-4">
                <h3 className="font-semibold text-white mb-2">Anomalies Detected</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-300 bg-gray-700 rounded p-3">
                  {analysis.anomalies.map((anomaly: string, idx: number) => (
                    <li key={idx}>{anomaly}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Configuration Issues */}
            {analysis.config_issues && analysis.config_issues.length > 0 && (
              <div className="mb-4">
                <h3 className="font-semibold text-white mb-2">Configuration Issues</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-300 bg-gray-700 rounded p-3">
                  {analysis.config_issues.map((issue: string, idx: number) => (
                    <li key={idx}>{issue}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Performance Insights */}
            {analysis.performance_insights && analysis.performance_insights.length > 0 && (
              <div className="mb-4">
                <h3 className="font-semibold text-white mb-2">Performance Insights</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-300 bg-gray-700 rounded p-3">
                  {analysis.performance_insights.map((insight: string, idx: number) => (
                    <li key={idx}>{insight}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Root Causes */}
            {analysis.root_causes && analysis.root_causes.length > 0 && (
              <div className="mb-4">
                <h3 className="font-semibold text-white mb-2">Potential Root Causes</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-300 bg-gray-700 rounded p-3">
                  {analysis.root_causes.map((cause: string, idx: number) => (
                    <li key={idx}>{cause}</li>
                  ))}
                </ul>
              </div>
            )}

            {/* Resolutions */}
            {analysis.resolutions && analysis.resolutions.length > 0 && (
              <div>
                <h3 className="font-semibold text-white mb-2">Suggested Resolutions</h3>
                <ul className="list-disc list-inside space-y-1 text-gray-300 bg-gray-700 rounded p-3">
                  {analysis.resolutions.map((resolution: string, idx: number) => (
                    <li key={idx}>{resolution}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
      </main>
    </div>
  );
};

export default DashboardPage;
