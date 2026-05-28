import React, { useState, useEffect } from 'react';
import { BarChart3, PieChart, TrendingUp, Loader2, AlertCircle, Filter, Brain } from 'lucide-react';
import { logAPI, parseAnalysis } from '../services/api';
import { LogEntry, K8sResource } from '../types';
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
  const [resources, setResources] = useState<K8sResource[]>([]);
  const [entries, setEntries] = useState<LogEntry[]>([]);
  const [selectedResource, setSelectedResource] = useState<number | null>(null);
  const [selectedLevel, setSelectedLevel] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzeStatus, setAnalyzeStatus] = useState<string>('');
  const [error, setError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<any>(null);
  const [showAnalysisPopup, setShowAnalysisPopup] = useState(false);

  useEffect(() => {
    loadResources();
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
    setAnalyzing(true);
    setAnalyzeStatus('Starting analysis...');
    setError(null);
    try {
      setAnalyzeStatus('Fetching log entries...');
      await new Promise(resolve => setTimeout(resolve, 500)); // Simulate processing
      
      setAnalyzeStatus('Running AI analysis...');
      const analysisData = await logAPI.analyzeLogs(resourceId, undefined, 'general');
      
      setAnalyzeStatus('Processing results...');
      await new Promise(resolve => setTimeout(resolve, 300)); // Simulate processing
      
      const parsedAnalysis = parseAnalysis(analysisData);
      setAnalysis(parsedAnalysis);
      setAnalyzeStatus('Analysis complete!');
      setShowAnalysisPopup(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Analysis failed');
      setAnalyzeStatus('');
    } finally {
      setAnalyzing(false);
    }
  };

  // Prepare data for charts
  const levelData = entries.reduce((acc, entry) => {
    const level = entry.level || 'UNKNOWN';
    acc[level] = (acc[level] || 0) + 1;
    return acc;
  }, {} as Record<string, number>);

  const levelChartData = Object.entries(levelData).map(([level, count]) => ({
    level,
    count
  }));

  const resourceData = resources.map(resource => ({
    name: resource.pod_name.length > 15 ? resource.pod_name.substring(0, 15) + '...' : resource.pod_name,
    namespace: resource.namespace,
    count: entries.filter(e => e.resource_id === resource.id).length
  }));

  const COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6'];

  const getLevelColor = (level: string) => {
    switch (level) {
      case 'ERROR':
      case 'CRITICAL':
        return '#EF4444';
      case 'WARNING':
        return '#F59E0B';
      case 'INFO':
        return '#3B82F6';
      case 'DEBUG':
        return '#8B5CF6';
      default:
        return '#10B981';
    }
  };

  if (loading && resources.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="animate-spin h-8 w-8 text-blue-400" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Analytics Dashboard</h1>
        <p className="text-gray-400">View log analytics and metrics</p>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-lg p-4 flex items-start">
          <AlertCircle className="h-5 w-5 text-red-400 mr-3 mt-0.5" />
          <p className="text-red-300">{error}</p>
        </div>
      )}

        {/* Filters */}
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-3 flex items-center">
            <Filter className="h-5 w-5 mr-2 text-blue-400" />
            Filters
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Resource</label>
              <select
                value={selectedResource || ''}
                onChange={(e) => setSelectedResource(e.target.value ? Number(e.target.value) : null)}
                className="w-full bg-gray-700 text-white rounded-md px-3 py-2 border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Resources</option>
                {resources.map((resource) => (
                  <option key={resource.id} value={resource.id}>
                    {resource.namespace}/{resource.pod_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Log Level</label>
              <select
                value={selectedLevel || ''}
                onChange={(e) => setSelectedLevel(e.target.value || null)}
                className="w-full bg-gray-700 text-white rounded-md px-3 py-2 border border-gray-600 focus:outline-none focus:border-blue-500"
              >
                <option value="">All Levels</option>
                <option value="DEBUG">DEBUG</option>
                <option value="INFO">INFO</option>
                <option value="WARNING">WARNING</option>
                <option value="ERROR">ERROR</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-300 mb-2">Actions</label>
              <button
                onClick={() => selectedResource && handleAnalyze(selectedResource)}
                disabled={!selectedResource || analyzing}
                className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 text-white font-medium py-2 px-4 rounded-md transition flex items-center justify-center"
              >
                {analyzing ? (
                  <>
                    <Loader2 className="animate-spin h-4 w-4 mr-2" />
                    {analyzeStatus || 'Analyzing...'}
                  </>
                ) : (
                  <>
                    <Brain className="h-4 w-4 mr-2" />
                    Analyze with AI
                  </>
                )}
              </button>
              {analyzing && analyzeStatus && (
                <p className="text-xs text-gray-400 mt-1 text-center">{analyzeStatus}</p>
              )}
            </div>
          </div>
        </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Total Entries</p>
              <p className="text-2xl font-bold text-white">{entries.length}</p>
            </div>
            <BarChart3 className="h-8 w-8 text-blue-400" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Errors</p>
              <p className="text-2xl font-bold text-red-400">
                {entries.filter(e => e.level === 'ERROR' || e.level === 'CRITICAL').length}
              </p>
            </div>
            <AlertCircle className="h-8 w-8 text-red-400" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Warnings</p>
              <p className="text-2xl font-bold text-yellow-400">
                {entries.filter(e => e.level === 'WARNING').length}
              </p>
            </div>
            <TrendingUp className="h-8 w-8 text-yellow-400" />
          </div>
        </div>
        <div className="bg-gray-800 rounded-lg p-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm">Resources</p>
              <p className="text-2xl font-bold text-white">{resources.length}</p>
            </div>
            <PieChart className="h-8 w-8 text-green-400" />
          </div>
        </div>
      </div>

      {/* Charts */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Log Level Distribution */}
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-4">Log Level Distribution</h2>
          {levelChartData.length > 0 ? (
            <ResponsiveContainer width="100%" height={300}>
              <RechartsPieChart>
                <Pie
                  data={levelChartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={(entry) => `${entry.level}: ${entry.count}`}
                  outerRadius={80}
                  fill="#8884d8"
                  dataKey="count"
                >
                  {levelChartData.map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </RechartsPieChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-8">No data available</p>
          )}
        </div>

        {/* Resource Distribution */}
        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-lg font-semibold text-white mb-4">Log Entries per Resource</h2>
          {resourceData.length > 0 && resourceData.some(r => r.count > 0) ? (
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={resourceData.filter(r => r.count > 0)}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="name" stroke="#9CA3AF" />
                <YAxis stroke="#9CA3AF" />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: '1px solid #374151' }}
                />
                <Legend />
                <Bar dataKey="count" fill="#3B82F6" />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <p className="text-gray-500 text-center py-8">No data available</p>
          )}
        </div>
      </div>

      {/* Recent Logs Table */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h2 className="text-lg font-semibold text-white mb-4">Recent Log Entries</h2>
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 font-medium py-2 px-4">Timestamp</th>
                <th className="text-left text-gray-400 font-medium py-2 px-4">Level</th>
                <th className="text-left text-gray-400 font-medium py-2 px-4">Message</th>
                <th className="text-left text-gray-400 font-medium py-2 px-4">Source</th>
              </tr>
            </thead>
            <tbody>
              {entries.slice(0, 20).map((entry) => (
                <tr key={entry.id} className="border-b border-gray-700 hover:bg-gray-700">
                  <td className="py-2 px-4 text-gray-300 text-sm">
                    {entry.timestamp ? new Date(entry.timestamp).toLocaleString() : '-'}
                  </td>
                  <td className="py-2 px-4">
                    <span
                      className="px-2 py-1 rounded text-xs font-medium"
                      style={{
                        backgroundColor: getLevelColor(entry.level || 'INFO') + '20',
                        color: getLevelColor(entry.level || 'INFO')
                      }}
                    >
                      {entry.level || 'INFO'}
                    </span>
                  </td>
                  <td className="py-2 px-4 text-gray-300 text-sm truncate max-w-xs">
                    {entry.message}
                  </td>
                  <td className="py-2 px-4 text-gray-400 text-sm">
                    {entry.source_file || `Resource ${entry.resource_id}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {entries.length === 0 && (
            <p className="text-gray-500 text-center py-8">No log entries found</p>
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
    </div>
  );
};

export default DashboardPage;
