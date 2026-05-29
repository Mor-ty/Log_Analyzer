import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Server, Activity, AlertCircle, Loader2, ChevronDown, ChevronRight, CheckCircle } from 'lucide-react';
import { k8sAPI, logAPI, parseAnalysis } from '../services/api';
import { K8sPodInfo, ClusterHealth, AnalysisResult } from '../types';

const SESSION_KEY = 'clusterBrowserState';

const ClusterBrowserPage: React.FC = () => {
  const navigate = useNavigate();
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
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [expandedPods, setExpandedPods] = useState<Set<string>>(new Set());

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
    setAnalyzing(true);
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
        // Logs were fetched without store=true before; re-fetch with store=true now
        const logsData = await k8sAPI.getPodLogs(pod.namespace, pod.name, undefined, 100, true);
        podLogs = logsData.logs;
        resourceId = logsData.resource_id ?? null;
        setCurrentResourceId(resourceId);
      }

      if (podLogs.length === 0) {
        setError('No logs available for this pod');
        return;
      }

      setAnalyzeStatus('Running AI analysis...');
      // Use resource_id so the backend can find the stored entries
      const analysisData = await logAPI.analyzeLogs(resourceId ?? undefined, undefined, 'general');
      const parsedAnalysis = parseAnalysis(analysisData);
      setAnalysis(parsedAnalysis);

      setAnalyzeStatus('Done!');
      setSuccessMessage(`Analysis complete for ${pod.name}! Redirecting to Dashboard...`);

      setTimeout(() => {
        navigate('/dashboard', {
          state: {
            analysis: parsedAnalysis,
            sourcePod: pod.name,
            sourceNamespace: pod.namespace,
          },
        });
      }, 1200);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
    } finally {
      setAnalyzing(false);
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
        return 'text-gray-400 bg-gray-900/30';
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

      {/* Cluster Health */}
      {health && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center">
            <Activity className="h-5 w-5 mr-2 text-blue-400" />
            Cluster Health
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="bg-gray-700 rounded p-3">
              <p className="text-gray-400 text-sm">Namespaces</p>
              <p className="text-2xl font-bold text-white">{health.namespaces}</p>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <p className="text-gray-400 text-sm">Total Pods</p>
              <p className="text-2xl font-bold text-white">{health.total_pods}</p>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <p className="text-gray-400 text-sm">Running</p>
              <p className="text-2xl font-bold text-green-400">{health.running_pods}</p>
            </div>
            <div className="bg-gray-700 rounded p-3">
              <p className="text-gray-400 text-sm">Failed</p>
              <p className="text-2xl font-bold text-red-400">{health.failed_pods}</p>
            </div>
          </div>
        </div>
      )}

      {/* Namespace Selector */}
      <div className="bg-gray-800 rounded-lg p-4">
        <label className="block text-sm font-medium text-gray-300 mb-2">Select Namespace</label>
        <select
          value={selectedNamespace}
          onChange={(e) => setSelectedNamespace(e.target.value)}
          className="w-full bg-gray-700 text-white rounded-md px-3 py-2 border border-gray-600 focus:outline-none focus:border-blue-500"
        >
          {namespaces.map((ns) => (
            <option key={ns} value={ns}>
              {ns}
            </option>
          ))}
        </select>
      </div>

      {/* Pods List */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-white mb-3 flex items-center">
          <Server className="h-5 w-5 mr-2 text-blue-400" />
          Pods in {selectedNamespace}
        </h2>
        {pods.length === 0 ? (
          <p className="text-gray-500">No pods found</p>
        ) : (
          <div className="space-y-2">
            {pods.map((pod) => (
              <div key={pod.name} className="border border-gray-700 rounded-lg overflow-hidden">
                <div
                  className="p-3 bg-gray-700 hover:bg-gray-600 cursor-pointer flex items-center justify-between"
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
                  <div className="p-3 bg-gray-800 space-y-2">
                    <div className="flex space-x-2">
                      <button
                        onClick={() => loadPodLogs(pod)}
                        disabled={loadingLogs}
                        className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white text-sm px-3 py-1 rounded"
                      >
                        {loadingLogs && selectedPod?.name === pod.name ? 'Loading...' : 'View Logs'}
                      </button>
                      <button
                        onClick={() => analyzeLogs(pod)}
                        disabled={analyzing}
                        className="bg-green-600 hover:bg-green-700 disabled:bg-gray-600 text-white text-sm px-3 py-1 rounded"
                      >
                        {analyzing && selectedPod?.name === pod.name
                          ? analyzeStatus || 'Analyzing...'
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
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-3">Logs from {selectedPod.name}</h2>
          <div className="bg-gray-900 rounded p-4 max-h-96 overflow-y-auto font-mono text-sm">
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
        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
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
