import React, { useState, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Upload, AlertCircle, CheckCircle, Loader2, FileText,
  Brain, Activity, Wrench, Zap, GitBranch, ShieldAlert, RotateCcw,
  BarChart3, ArrowRight, UploadCloud,
} from 'lucide-react';
import { logAPI, parseAnalysis } from '../services/api';
import { LogUploadResponse, AnalysisResult } from '../types';
import { useAnalysis } from '../context/AnalysisContext';
type Phase = 'select' | 'uploading' | 'uploaded' | 'analyzing' | 'analyzed';

const UploadPage: React.FC = () => {
  const navigate = useNavigate();
  const { startTracking, getLatestJob, clearJob } = useAnalysis();

  const [phase, setPhase] = useState<Phase>('select');
  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploadResult, setUploadResult] = useState<LogUploadResponse | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  // ── Sync context upload job → local display state ──────────────────────────
  // This runs whenever the job status/elapsed changes (every ~2.5s while active).
  const uploadJob = getLatestJob('upload');

  useEffect(() => {
    if (!uploadJob) return;
    const meta = uploadJob.metadata as { uploadResult?: LogUploadResponse } | undefined;
    // Restore uploadResult from context metadata if local state is empty
    if (meta?.uploadResult && !uploadResult) {
      setUploadResult(meta.uploadResult);
    }
    if (uploadJob.status === 'completed' && uploadJob.result) {
      setAnalysis(parseAnalysis(uploadJob.result));
      setPhase('analyzed');
      setError(null);
    } else if (uploadJob.status === 'failed') {
      setError(uploadJob.error || 'Analysis failed');
      setPhase(meta?.uploadResult || uploadResult ? 'uploaded' : 'select');
    } else if (uploadJob.status === 'pending' || uploadJob.status === 'running') {
      setPhase('analyzing');
    }
  // elapsedSeconds changes on every poll — keeps the elapsed display fresh
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [uploadJob?.status, uploadJob?.elapsedSeconds]);

  const handleFileSelect = (f: File) => {
    setFile(f);
    setError(null);
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (f) handleFileSelect(f);
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFileSelect(f);
  }, []);

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); setDragOver(true); };

  const handleReset = () => {
    if (uploadJob) clearJob(uploadJob.jobId);
    setFile(null);
    setUploadResult(null);
    setAnalysis(null);
    setError(null);
    setPhase('select');
  };

  const handleUpload = async () => {
    if (!file) return;
    setPhase('uploading');
    setError(null);
    try {
      const result = await logAPI.uploadFile(file);
      setUploadResult(result);
      if (result.job_id) {
        // The upload endpoint already started an analysis job — track it.
        startTracking(result.job_id, 'upload', file.name, result.file_id, { uploadResult: result });
        setPhase('analyzing');
      } else {
        setPhase('uploaded');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
      setPhase('select');
    }
  };

  const handleAnalyze = async () => {
    if (!uploadResult) return;
    setError(null);
    try {
      const job = await logAPI.analyzeLogs(uploadResult.file_id, undefined, 'general');
      startTracking(job.job_id, 'upload', file?.name ?? 'Log file', uploadResult.file_id, { uploadResult });
      setPhase('analyzing');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start analysis');
      setPhase('uploaded');
    }
  };

  const severityColors: Record<string, { bg: string; border: string; text: string; badge: string }> = {
    Critical: { bg: 'bg-red-950/60',    border: 'border-red-700',    text: 'text-red-300',    badge: 'bg-red-700/40 text-red-300 border-red-600' },
    Warning:  { bg: 'bg-yellow-950/60', border: 'border-yellow-700', text: 'text-yellow-300', badge: 'bg-yellow-700/40 text-yellow-300 border-yellow-600' },
    Healthy:  { bg: 'bg-green-950/60',  border: 'border-green-700',  text: 'text-green-300',  badge: 'bg-green-700/40 text-green-300 border-green-600' },
  };
  const sc = analysis ? (severityColors[analysis.severity] ?? severityColors['Healthy']) : null;

  const Section: React.FC<{ icon: React.ReactNode; title: string; accent: string; items: string[] }> = ({ icon, title, accent, items }) => (
    <div className="bg-zinc-950/60 border border-zinc-800 rounded-xl p-5">
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

      {/* Page Header */}
      <div className="flex flex-col gap-1.5 pb-5 border-b border-zinc-800/50">
        <h1 className="text-3xl font-extrabold text-white tracking-tight">Upload Log File</h1>
        <p className="text-gray-400 text-sm">Upload a log file for AI-powered anomaly detection and DevOps analysis</p>
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-900/50 border border-red-700 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="h-5 w-5 text-red-400 shrink-0 mt-0.5" />
          <p className="text-red-300 text-sm">{error}</p>
        </div>
      )}

      {/* ── PHASE: SELECT ── */}
      {(phase === 'select' || phase === 'uploading') && (
        <div className="space-y-5">
          {/* Drop zone */}
          <div
            onDrop={handleDrop}
            onDragOver={handleDragOver}
            onDragLeave={() => setDragOver(false)}
            onDragEnter={handleDragOver}
            className={`relative rounded-xl border-2 border-dashed transition-all p-10 flex flex-col items-center text-center gap-4
              ${dragOver
                ? 'border-blue-500 bg-blue-900/10 scale-[1.01]'
                : file
                  ? 'border-green-600 bg-green-900/10'
                  : 'border-zinc-700 bg-zinc-900/50 hover:border-blue-500 hover:bg-blue-900/5'
              }`}
          >
            <div className={`p-4 rounded-full ${dragOver ? 'bg-blue-500/20' : file ? 'bg-green-500/15' : 'bg-zinc-800/60'}`}>
              {file
                ? <CheckCircle className="h-10 w-10 text-green-400" />
                : <UploadCloud className={`h-10 w-10 ${dragOver ? 'text-blue-400' : 'text-gray-500'}`} />
              }
            </div>

            {file ? (
              <div className="space-y-1">
                <p className="text-white font-semibold text-lg">{file.name}</p>
                <p className="text-gray-400 text-sm">
                  {(file.size / 1024).toFixed(1)} KB · .{file.name.split('.').pop()?.toUpperCase()}
                </p>
                <p className="text-green-400 text-xs font-medium">File ready for upload</p>
              </div>
            ) : (
              <div className="space-y-1">
                <p className="text-gray-300 font-medium">Drag &amp; drop your log file here</p>
                <p className="text-gray-500 text-sm">or click to browse · Supports .log, .txt</p>
              </div>
            )}

            <input
              type="file"
              onChange={handleInputChange}
              accept=".log,.txt"
              className="absolute inset-0 opacity-0 cursor-pointer"
              id="file-upload"
            />
          </div>

          {/* Upload button */}
          {file && (
            <button
              onClick={handleUpload}
              disabled={phase === 'uploading'}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-zinc-800 disabled:text-gray-500 text-white font-semibold py-3.5 px-4 rounded-xl transition-colors flex items-center justify-center gap-2.5 text-base"
            >
              {phase === 'uploading' ? (
                <><Loader2 className="animate-spin h-5 w-5" /> Uploading file…</>
              ) : (
                <><Upload className="h-5 w-5" /> Upload File</>
              )}
            </button>
          )}

          {!file && (
            <label
              htmlFor="file-upload"
              className="w-full flex items-center justify-center gap-2 py-3 border border-zinc-700 hover:border-blue-500 text-gray-400 hover:text-blue-300 rounded-xl transition-colors text-sm font-medium cursor-pointer"
            >
              <FileText className="h-4 w-4" /> Browse and select a file
            </label>
          )}
        </div>
      )}

      {/* ── PHASE: UPLOADED (status card + Analyze button) ── */}
      {(phase === 'uploaded' || phase === 'analyzing') && uploadResult && (
        <div className="space-y-5">

          {/* Upload success card */}
          <div className="bg-green-900/20 border border-green-700/60 rounded-xl p-5 flex items-center gap-5">
            <div className="p-3 bg-green-500/15 rounded-full shrink-0">
              <CheckCircle className="h-8 w-8 text-green-400" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-green-500 font-semibold uppercase tracking-wide mb-0.5">Upload Successful</p>
              <p className="text-white font-semibold text-lg truncate">{file?.name}</p>
              <div className="flex flex-wrap gap-4 mt-1.5">
                <span className="flex items-center gap-1.5 text-sm text-gray-400">
                  <BarChart3 className="h-3.5 w-3.5 text-blue-400" />
                  <span className="text-white font-semibold">{uploadResult.entries_count}</span> log entries parsed
                </span>
                <span className="flex items-center gap-1.5 text-sm text-gray-400">
                  <FileText className="h-3.5 w-3.5 text-gray-500" />
                  Resource ID: <span className="text-gray-300 font-medium ml-1">#{uploadResult.file_id}</span>
                </span>
              </div>
            </div>
          </div>

          {/* Analyze button */}
          <button
            onClick={handleAnalyze}
            disabled={phase === 'analyzing'}
            className="w-full bg-purple-600 hover:bg-purple-700 disabled:bg-zinc-800 disabled:text-gray-500 text-white font-semibold py-4 px-4 rounded-xl transition-colors flex items-center justify-center gap-2.5 text-base shadow-lg shadow-purple-900/30"
          >
            {phase === 'analyzing' ? (
              <><Loader2 className="animate-spin h-5 w-5" />
                {uploadJob ? `AI is analyzing your logs (${uploadJob.elapsedSeconds}s)…` : 'Analyzing…'}
              </>
            ) : (
              <><Brain className="h-5 w-5" /> Analyze with AI &nbsp;<span className="text-purple-300 text-sm font-normal">(Senior DevOps)</span></>
            )}
          </button>

          {/* Analyzing progress steps */}
          {phase === 'analyzing' && (
            <div className="bg-zinc-900/60 border border-zinc-800 rounded-xl p-4 flex items-center gap-3">
              <div className="flex gap-1 shrink-0">
                {['Uploading', 'Processing', 'Analysing', 'Done'].map((_, i) => (
                  <span key={i} className={`h-1.5 w-6 rounded-full ${i < 3 ? 'bg-purple-500 animate-pulse' : 'bg-zinc-800'}`} />
                ))}
              </div>
              <p className="text-gray-400 text-sm">
                {uploadJob ? `AI is analyzing your logs (${uploadJob.elapsedSeconds}s)…` : 'Analyzing…'}
              </p>
            </div>
          )}

          {/* Re-upload link */}
          {phase !== 'analyzing' && (
            <button
              onClick={handleReset}
              className="w-full flex items-center justify-center gap-2 py-2.5 border border-zinc-800 hover:border-gray-500 text-gray-500 hover:text-gray-300 rounded-xl transition-colors text-sm"
            >
              <RotateCcw className="h-3.5 w-3.5" /> Upload a different file
            </button>
          )}
        </div>
      )}

      {/* ── PHASE: ANALYZED ── */}
      {phase === 'analyzed' && analysis && uploadResult && sc && (
        <div className="space-y-5">

          {/* Severity/header banner */}
          <div className={`rounded-xl border p-5 flex items-center justify-between gap-4 ${sc.bg} ${sc.border}`}>
            <div className="flex items-center gap-4">
              <div className="p-3 bg-black/30 rounded-full shrink-0">
                <Brain className={`h-7 w-7 ${sc.text}`} />
              </div>
              <div>
                <p className="text-xs text-gray-400 uppercase tracking-wide mb-0.5">AI Analysis Complete · Senior DevOps</p>
                <p className="text-white font-bold text-lg">{file?.name}</p>
                <p className="text-gray-400 text-sm">{uploadResult.entries_count} log entries analysed</p>
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

          {/* Action buttons */}
          <div className="grid grid-cols-2 gap-3">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-xl transition-colors"
            >
              <BarChart3 className="h-4 w-4" /> Go to Dashboard <ArrowRight className="h-4 w-4 ml-auto" />
            </button>
            <button
              onClick={handleReset}
              className="flex items-center justify-center gap-2 border border-zinc-700 hover:border-gray-400 text-gray-400 hover:text-white py-3 px-4 rounded-xl transition-colors text-sm font-medium"
            >
              <RotateCcw className="h-4 w-4" /> Upload Another File
            </button>
          </div>

          {/* Stats row */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {[
              { label: 'Anomalies',     value: analysis.anomalies.length,            color: 'text-red-400',    bg: 'bg-red-500/10 border-red-500/20' },
              { label: 'Root Causes',   value: analysis.root_causes.length,           color: 'text-orange-400', bg: 'bg-orange-500/10 border-orange-500/20' },
              { label: 'Config Issues', value: (analysis.config_issues ?? []).length, color: 'text-yellow-400', bg: 'bg-yellow-500/10 border-yellow-500/20' },
              { label: 'Resolutions',   value: analysis.resolutions.length,           color: 'text-green-400',  bg: 'bg-green-500/10 border-green-500/20' },
            ].map(stat => (
              <div key={stat.label} className={`border rounded-xl p-4 text-center ${stat.bg}`}>
                <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
                <p className="text-xs text-gray-500 mt-1">{stat.label}</p>
              </div>
            ))}
          </div>

          {/* Health Assessment */}
          {analysis.health_assessment && (
            <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
              <h3 className="flex items-center gap-2 font-semibold text-blue-300 mb-3">
                <Activity className="h-4 w-4" /> Health Assessment
              </h3>
              <p className="text-gray-300 text-sm leading-relaxed bg-zinc-950/60 rounded-lg p-4">
                {analysis.health_assessment}
              </p>
            </div>
          )}

          {/* Anomalies */}
          {analysis.anomalies.length > 0 && (
            <Section icon={<ShieldAlert className="h-4 w-4" />} title="Anomalies Detected" accent="text-red-400" items={analysis.anomalies} />
          )}

          {/* Config Issues */}
          {(analysis.config_issues ?? []).length > 0 && (
            <Section icon={<Wrench className="h-4 w-4" />} title="Configuration Issues" accent="text-yellow-400" items={analysis.config_issues!} />
          )}

          {/* Performance Insights */}
          {(analysis.performance_insights ?? []).length > 0 && (
            <Section icon={<Zap className="h-4 w-4" />} title="Performance Insights" accent="text-purple-400" items={analysis.performance_insights!} />
          )}

          {/* Root Causes */}
          {analysis.root_causes.length > 0 && (
            <Section icon={<GitBranch className="h-4 w-4" />} title="Potential Root Causes" accent="text-orange-400" items={analysis.root_causes} />
          )}

          {/* Resolutions */}
          {analysis.resolutions.length > 0 && (
            <Section icon={<CheckCircle className="h-4 w-4" />} title="Suggested Resolutions" accent="text-green-400" items={analysis.resolutions} />
          )}

          {/* Bottom actions (repeat for convenience) */}
          <div className="grid grid-cols-2 gap-3 pt-2">
            <button
              onClick={() => navigate('/dashboard')}
              className="flex items-center justify-center gap-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold py-3 px-4 rounded-xl transition-colors"
            >
              <BarChart3 className="h-4 w-4" /> Go to Dashboard
            </button>
            <button
              onClick={handleReset}
              className="flex items-center justify-center gap-2 border border-zinc-700 hover:border-gray-400 text-gray-400 hover:text-white py-3 px-4 rounded-xl transition-colors text-sm font-medium"
            >
              <RotateCcw className="h-4 w-4" /> Upload Another File
            </button>
          </div>

        </div>
      )}
    </div>
  );
};

export default UploadPage;
