import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Server, Activity, AlertCircle, Loader2, ChevronDown, ChevronRight, CheckCircle } from 'lucide-react';
import { k8sAPI, logAPI, parseAnalysis } from '../services/api';
import { K8sPodInfo, ClusterHealth, AnalysisResult } from '../types';
import { useAnalysis } from '../context/AnalysisContext';

const SESSION_KEY = 'clusterBrowserState';

const ClusterBrowserPage: React.FC = () => {
  const navigate = useNavigate();
  const { startTracking, jobs, clearJob } = useAnalysis();
  const handledClusterJobsRef = useRef<Set<string>>(new Set());

  const [health, setHealth] = useState<ClusterHealth | null>(null);
  const [namespaces, setNamespaces] = useState<string[]>([]);
  const [selectedNamespace, setSelectedNamespace] = useState<string>('');
  const [pods, setPods] = useState<K8sPodInfo[]>([]);
  const [selectedPod, setSelectedPod] = useState<K8sPodInfo | null>(null);
  const [logs, setLogs] = useState<any[]>([]);
  const [currentResourceId, setCurrentResourceId] = useState<number | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingLogs, setLoadingLogs] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [expandedPods, setExpandedPods] = useState<Set<string>>(new Set());

  // ── Derived: the active cluster analysis job (if any) ─────────────────────
  const clusterJob = Object.values(jobs)
    .filter(j => j.source === 'cluster')
    .sort((a, b) => b.startedAt - a.startedAt)[0];

  const isAnalyzing =
    clusterJob?.status === 'pending' || clusterJob?.status === 'running';

  // ── When a cluster job finishes, navigate to Dashboard ────────────────────
  useEffect(() => {
    const done = Object.values(jobs).find(
      j =>
        j.source === 'cluster' &&
        j.status === 'completed' &&
        j.result &&
        !handledClusterJobsRef.current.has(j.jobId),
    );
    if (!done) return;
    handledClusterJobsRef.current.add(done.jobId);
    const meta = done.metadata as { pod?: K8sPodInfo } | undefined;
    const parsed = parseAnalysis(done.result!);
    setAnalysis(parsed);
    setSuccessMessage(`Analysis complete for ${meta?.pod?.name ?? 'pod'}! Redirecting to Dashboard…`);
    clearJob(done.jobId);
    setTimeout(() => {
      navigate('/dashboard', {
        state: {
          analysis: parsed,
          sourcePod: meta?.pod?.name,
          sourceNamespace: meta?.pod?.namespace,
        },
      });
    }, 1200);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobs]);

  // Hold saved namespace in a ref so loadClusterData can use it after async fetch
  const savedNamespaceRef = React.useRef<string | null>(null);

  // On mount: restore session
  useEffect(() => {
    const saved = sessionStorage.getItem(SESSION_KEY);
    if (saved) {
      try {
        const s = JSON.parse(saved);
        if (s.selectedNamespace) savedNamespaceRef.current = s.selectedNamespace;
        if (s.logs?.length) setLogs(s.logs);
        if (s.selectedPod) setSelectedPod(s.selectedPod);
      } catch { /* ignore */ }
    }
    loadClusterData();
  }, []);

  // Persist only namespace + last viewed logs/pod
  useEffect(() => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({
      selectedNamespace,
      selectedPod,
      logs,
    }));
  }, [selectedNamespace, selectedPod, logs]);

  const loadClusterData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, namespacesData] = await Promise.all([
        k8sAPI.getHealth(),
        k8sAPI.getNamespaces(),
      ]);
      setHealth(healthData);
      setNamespaces(namespacesData.namespaces);
      // Use saved namespace if it still exists in the cluster, otherwise fall back to first
      const savedNs = savedNamespaceRef.current;
      if (savedNs && namespacesData.namespaces.includes(savedNs)) {
        setSelectedNamespace(savedNs);
      } else if (namespacesData.namespaces.length > 0) {
        setSelectedNamespace(namespacesData.namespaces[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load cluster data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (selectedNamespace) {
      loadPods(selectedNamespace);
    }
  }, [selectedNamespace]);

  const loadPods = async (namespace: string) => {
    setLoading(true);
    setError(null);
    try {
      const podsData = await k8sAPI.getPods(namespace);
      setPods(podsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load pods');
    } finally {
      setLoading(false);
    }
  };

  const loadPodLogs = async (pod: K8sPodInfo) => {
    setLoadingLogs(true);
    setError(null);
    setSelectedPod(pod);
    setAnalysis(null);
    try {
      // store=false: view only, does NOT persist to DB or Dashboard
      const logsData = await k8sAPI.getPodLogs(pod.namespace, pod.name, undefined, 100, false);
      setLogs(logsData.logs);
      setCurrentResourceId(null); // no DB resource created
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load logs');
    } finally {
      setLoadingLogs(false);
    }
  };

  const analyzeLogs = async (pod: K8sPodInfo) => {
    setAnalyzeStatus('Collecting logs...');
    setError(null);
    setSuccessMessage(null);

    try {
      // Fetch logs with store=true to persist to DB before analysis
      let resourceId = currentResourceId;
      let podLogs = logs;
      if (!selectedPod || selectedPod.name !== pod.name || podLogs.length === 0) {
        const logsData = await k8sAPI.getPodLogs(pod.namespace, pod.name, undefined, 100, true);
        podLogs = logsData.logs;
        resourceId = logsData.resource_id ?? null;
        setLogs(podLogs);
        setSelectedPod(pod);
        setCurrentResourceId(resourceId);
      } else if (resourceId === null) {
        const logsData = await k8sAPI.getPodLogs(pod.namespace, pod.name, undefined, 100, true);
        podLogs = logsData.logs;
        resourceId = logsData.resource_id ?? null;
        setCurrentResourceId(resourceId);
      }

      if (podLogs.length === 0) {
        setError('No logs available for this pod');
        setAnalyzeStatus('');
        return;
      }

      setAnalyzeStatus('Starting AI analysis…');
      const job = await logAPI.analyzeLogs(resourceId ?? undefined, undefined, 'general');
      startTracking(job.job_id, 'cluster', pod.name, resourceId ?? undefined, { pod });
      setAnalyzeStatus(`AI is analyzing ${pod.name}…`);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setAnalyzeStatus('');
    }
  };

  const togglePodExpand = (podName: string) => {
    const newExpanded = new Set(expandedPods);
    if (newExpanded.has(podName)) {
      newExpanded.delete(podName);
    } else {
      newExpanded.add(podName);
    }
    setExpandedPods(newExpanded);
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'Running':
        return 'text-green-400 bg-green-900/30';
      case 'Pending':
        return 'text-yellow-400 bg-yellow-900/30';
      case 'Failed':
      case 'CrashLoopBackOff':
        return 'text-red-400 bg-red-900/30';
      default:
        return 'text-gray-400 bg-zinc-950/30';
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin h-8 w-8 text-blue-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Cluster Browser</h1>
        <p className="text-gray-400">Browse and analyze logs from your Kubernetes cluster</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-400 mr-3 mt-0.5" />
          <p className="text-red-300">{error}</p>
        </div>
      )}

      {/* Success Message */}
      {successMessage && (
        <div className="bg-green-900/50 border border-green-700 rounded-lg p-4 flex items-start">
          <CheckCircle className="h-5 w-5 text-green-400 mr-3 mt-0.5" />
          <p className="text-green-300">{successMessage}</p>
        </div>
      )}

      {/* Analyze Status */}
      {analyzeStatus && (
        <div className="bg-blue-900/50 border border-blue-700 rounded-lg p-4 flex items-start">
          <Loader2 className="animate-spin h-5 w-5 text-blue-400 mr-3 mt-0.5" />
          <p className="text-blue-300">{analyzeStatus}</p>
        </div>
      )}

      {/* Cluster Health */}
      {health && (
        <div className="bg-zinc-900 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center">
            <Activity className="h-5 w-5 mr-2 text-blue-400" />
            Cluster Health
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-zinc-800 rounded p-3">
              <p className="text-gray-400 text-sm">Namespaces</p>
              <p className="text-2xl font-bold text-white">{health.namespaces}</p>
            </div>
            <div className="bg-zinc-800 rounded p-3">
              <p className="text-gray-400 text-sm">Total Pods</p>
              <p className="text-2xl font-bold text-white">{health.total_pods}</p>
            </div>
            <div className="bg-zinc-800 rounded p-3">
              <p className="text-gray-400 text-sm">Running</p>
              <p className="text-2xl font-bold text-green-400">{health.running_pods}</p>
            </div>
            <div className="bg-zinc-800 rounded p-3">
              <p className="text-gray-400 text-sm">Failed</p>
              <p className="text-2xl font-bold text-red-400">{health.failed_pods}</p>
            </div>
          </div>
        </div>
      )}

      {/* Namespace Selector */}
      <div className="bg-zinc-900 rounded-lg p-4">
        <label className="block text-sm font-medium text-gray-300 mb-2">Select Namespace</label>
        <select
          value={selectedNamespace}
          onChange={(e) => setSelectedNamespace(e.target.value)}
          className="w-full bg-zinc-800 text-white rounded-md px-3 py-2 border border-zinc-700 focus:outline-none focus:border-blue-500"
        >
          {namespaces.map((ns) => (
            <option key={ns} value={ns}>
              {ns}
            </option>
          ))}
        </select>
      </div>

      {/* Pods List */}
      <div className="bg-zinc-900 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center">
          <Server className="h-5 w-5 mr-2 text-blue-400" />
          Pods in {selectedNamespace}
        </h2>
        {pods.length === 0 ? (
          <p className="text-gray-500">No pods found</p>
        ) : (
          <div className="space-y-2">
            {pods.map((pod) => (
              <div key={pod.name} className="border border-zinc-800 rounded-lg overflow-hidden">
                <div
                  className="p-3 bg-zinc-800 hover:bg-zinc-700 cursor-pointer flex items-center justify-between"
                  onClick={() => togglePodExpand(pod.name)}
                >
                  <div className="flex items-center space-x-3">
                    {expandedPods.has(pod.name) ? (
                      <ChevronDown className="h-4 w-4 text-gray-400" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-gray-400" />
                    )}
                    <span className="text-white font-medium">{pod.name}</span>
                    <span className={`px-2 py-1 rounded text-xs font-medium ${getStatusColor(pod.status)}`}>
                      {pod.status}
                    </span>
                  </div>
                </div>
                {expandedPods.has(pod.name) && (
                  <div className="p-3 bg-zinc-900 space-y-2">
                    <div className="flex space-x-2">
                      <button
                        onClick={() => loadPodLogs(pod)}
                        disabled={loadingLogs}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-700 text-white text-sm px-3 py-1 rounded"
                      >
                        {loadingLogs && selectedPod?.name === pod.name ? 'Loading...' : 'View Logs'}
                      </button>
                      <button
                        onClick={() => analyzeLogs(pod)}
                        disabled={isAnalyzing}
                        className="bg-green-600 hover:bg-green-700 disabled:bg-zinc-700 text-white text-sm px-3 py-1 rounded"
                      >
                        {isAnalyzing && (clusterJob?.metadata as any)?.pod?.name === pod.name
                          ? `Analyzing… (${clusterJob!.elapsedSeconds}s)`
                          : 'Analyze'}
                      </button>
                    </div>
                    <div className="text-sm text-gray-400">
                      <p>Containers: {pod.containers.join(', ')}</p>
                      {pod.created && <p>Created: {new Date(pod.created).toLocaleString()}</p>}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Logs Display */}
      {selectedPod && logs.length > 0 && (
        <div className="bg-zinc-900 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-3">Logs from {selectedPod.name}</h2>
          <div className="bg-zinc-950 rounded p-4 max-h-96 overflow-y-auto font-mono text-sm">
            {logs.map((log, idx) => (
              <div key={idx} className="mb-1">
                <span className="text-gray-500">{log.timestamp || '-'}</span>
                <span className={`mx-2 ${
                  log.level === 'ERROR' ? 'text-red-400' :
                  log.level === 'WARNING' ? 'text-yellow-400' :
                  'text-blue-400'
                }`}>
                  {log.level || 'INFO'}
                </span>
                <span className="text-gray-300">{log.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && (
        <div className="bg-zinc-900 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-bold text-white">Analysis Results</h2>
          <div className={`p-4 rounded-lg ${
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
          </div>
          {analysis.anomalies.length > 0 && (
            <div>
              <h3 className="font-semibold text-white mb-2">Anomalies</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                {analysis.anomalies.map((anomaly, idx) => <li key={idx}>{anomaly}</li>)}
              </ul>
            </div>
          )}
          {analysis.resolutions.length > 0 && (
            <div>
              <h3 className="font-semibold text-white mb-2">Suggested Resolutions</h3>
              <ul className="list-disc list-inside space-y-1 text-gray-300">
                {analysis.resolutions.map((resolution, idx) => <li key={idx}>{resolution}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default ClusterBrowserPage;
