import React, { useState } from 'react';
import {
  Upload, AlertCircle, CheckCircle, Loader2,
  Brain, Activity, Wrench, Zap, GitBranch, ShieldAlert, RotateCcw,
} from 'lucide-react';
import { logAPI, parseAnalysis } from '../services/api';
import { LogUploadResponse, AnalysisResult } from '../types';

const UploadPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState<LogUploadResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (selectedFile) {
      setFile(selectedFile);
      setError(null);
      setUploadResult(null);
      setAnalysis(null);
    }
  };

  const handleReset = () => {
    setFile(null);
    setUploadResult(null);
    setAnalysis(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await logAPI.uploadFile(file);
      setUploadResult(result);
      if (result.analysis_id) {
        const analysisData = await logAPI.getAnalysis(result.analysis_id);
        setAnalysis(parseAnalysis(analysisData));
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  const severityColors: Record<string, { bg: string; border: string; text: string; badge: string }> = {
    Critical: { bg: 'bg-red-950/60',    border: 'border-red-700',    text: 'text-red-300',    badge: 'bg-red-700/40 text-red-300 border-red-600' },
    Warning:  { bg: 'bg-yellow-950/60', border: 'border-yellow-700', text: 'text-yellow-300', badge: 'bg-yellow-700/40 text-yellow-300 border-yellow-600' },
    Healthy:  { bg: 'bg-green-950/60',  border: 'border-green-700',  text: 'text-green-300',  badge: 'bg-green-700/40 text-green-300 border-green-600' },
  };
  const sc = analysis ? (severityColors[analysis.severity] ?? severityColors['Healthy']) : null;

  const Section: React.FC<{ icon: React.ReactNode; title: string; accent: string; items: string[] }> = ({ icon, title, accent, items }) => (
    <div className="bg-gray-900/60 border border-gray-700 rounded-xl p-5">
      <h3 className={`flex items-center gap-2 font-semibold mb-3 ${accent}`}>
        {icon}
        {title}
        <span className="ml-auto text-xs text-gray-500 font-normal">{items.length} item{items.length !== 1 ? 's' : ''}</span>
      </h3>
      <ul className="space-y-2">
        {items.map((item, idx) => (
          <li key={idx} className="flex gap-2 text-sm text-gray-300 leading-relaxed">
            <span className={`mt-1.5 h-1.5 w-1.5 rounded-full shrink-0 ${accent.replace('text-', 'bg-')}`} />
            {item}
          </li>
        ))}
      </ul>
    </div>
  );

  return (
    <div className="space-y-6 max-w-4xl mx-auto">
      <div>
        <h1 className="text-3xl font-bold text-white mb-2">Upload Log File</h1>
        <p className="text-gray-400">Upload a log file for AI-powered anomaly detection and analysis</p>
      </div>

      {/* Upload card — hide once analysis is ready */}
      {!analysis && (
        <>
          <div className="bg-gray-800 rounded-xl p-8 border-2 border-dashed border-gray-600 hover:border-blue-500 transition-colors">
            <div className="flex flex-col items-center text-center">
              <div className="p-4 bg-gray-700/50 rounded-full mb-4">
                <Upload className="h-10 w-10 text-gray-400" />
              </div>
              <input type="file" onChange={handleFileSelect} accept=".log,.txt" className="hidden" id="file-upload" />
              <label htmlFor="file-upload" className="cursor-pointer text-blue-400 hover:text-blue-300 font-medium text-lg transition-colors">
                {file ? file.name : 'Click to select a log file'}
              </label>
              {file
                ? <p className="mt-2 text-sm text-gray-500">{(file.size / 1024).toFixed(2)} KB · .{file.name.split('.').pop()}</p>
                : <p className="mt-2 text-sm text-gray-600">Supports .log and .txt files</p>
              }
            </div>
          </div>

          {file && (
            <button
              onClick={handleUpload}
              disabled={uploading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-semibold py-3 px-4 rounded-xl transition flex items-center justify-center gap-2"
            >
              {uploading ? (
                <><Loader2 className="animate-spin h-5 w-5" /> Uploading and Analyzing…</>
              ) : (
                <><Brain className="h-5 w-5" /> Upload &amp; Analyze</>
              )}
            </button>
          )}
        </>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* ── FULL ANALYSIS RESULTS ── */}
      {analysis && uploadResult && sc && (
        <div className="space-y-5">

          {/* Header banner */}
          <div className={`rounded-xl border p-5 flex items-center justify-between gap-4 ${sc.bg} ${sc.border}`}>
            <div className="flex items-center gap-4">
              <div className="p-3 bg-black/30 rounded-full">
                <Brain className={`h-7 w-7 ${sc.text}`} />
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">AI Analysis Complete</p>
                <p className="text-white font-bold text-lg">{file?.name}</p>
                <p className="text-gray-400 text-sm">{uploadResult.entries_count} log entries processed</p>
              </div>
            </div>
            <div className="flex flex-col items-end gap-2 shrink-0">
              <span className={`text-sm font-semibold px-3 py-1 rounded-full border ${sc.badge}`}>
                {analysis.severity}
              </span>
              <span className="text-xs text-gray-500">
                {(analysis.confidence_score * 100).toFixed(1)}% confidence
              </span>
            </div>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Anomalies',    value: analysis.anomalies.length,           color: 'text-red-400' },
              { label: 'Root Causes',  value: analysis.root_causes.length,          color: 'text-orange-400' },
              { label: 'Config Issues',value: (analysis.config_issues ?? []).length, color: 'text-yellow-400' },
              { label: 'Resolutions',  value: analysis.resolutions.length,          color: 'text-green-400' },
            ].map(stat => (
              <div key={stat.label} className="bg-gray-800 border border-gray-700 rounded-xl p-4 text-center">
                <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>

          {/* Health Assessment */}
          {analysis.health_assessment && (
            <div className="bg-gray-800 border border-gray-700 rounded-xl p-5">
              <h3 className="flex items-center gap-2 font-semibold text-blue-300 mb-3">
                <Activity className="h-4 w-4" /> Health Assessment
              </h3>
              <p className="text-gray-300 text-sm leading-relaxed bg-gray-900/60 rounded-lg p-4">
                {analysis.health_assessment}
              </p>
            </div>
          )}

          {/* Anomalies */}
          {analysis.anomalies.length > 0 && (
            <Section
              icon={<ShieldAlert className="h-4 w-4" />}
              title="Anomalies Detected"
              accent="text-red-400"
              items={analysis.anomalies}
            />
          )}

          {/* Config Issues */}
          {(analysis.config_issues ?? []).length > 0 && (
            <Section
              icon={<Wrench className="h-4 w-4" />}
              title="Configuration Issues"
              accent="text-yellow-400"
              items={analysis.config_issues!}
            />
          )}

          {/* Performance Insights */}
          {(analysis.performance_insights ?? []).length > 0 && (
            <Section
              icon={<Zap className="h-4 w-4" />}
              title="Performance Insights"
              accent="text-purple-400"
              items={analysis.performance_insights!}
            />
          )}

          {/* Root Causes */}
          {analysis.root_causes.length > 0 && (
            <Section
              icon={<GitBranch className="h-4 w-4" />}
              title="Potential Root Causes"
              accent="text-orange-400"
              items={analysis.root_causes}
            />
          )}

          {/* Resolutions */}
          {analysis.resolutions.length > 0 && (
            <Section
              icon={<CheckCircle className="h-4 w-4" />}
              title="Suggested Resolutions"
              accent="text-green-400"
              items={analysis.resolutions}
            />
          )}

          {/* Upload another */}
          <button
            onClick={handleReset}
            className="w-full flex items-center justify-center gap-2 py-3 border border-gray-600 hover:border-gray-400 text-gray-400 hover:text-white rounded-xl transition-colors text-sm font-medium"
          >
            <RotateCcw className="h-4 w-4" />
            Upload Another File
          </button>
        </div>
      )}
    </div>
  );
};

export default UploadPage;
