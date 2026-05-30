/**
 * Global Analysis Context
 *
 * Tracks all in-flight LLM analysis jobs across every page.
 * Pages call `startTracking` when they kick off a job, then read
 * `getLatestJob(source, resourceId?)` to get live status/result.
 * Active (pending/running) jobs are persisted to sessionStorage so
 * they survive page navigation and are automatically resumed on mount.
 */

import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from 'react';
import { logAPI } from '../services/api';
import { LogAnalysis } from '../types';

// ─── Public types ─────────────────────────────────────────────────────────────
export type JobSource = 'upload' | 'dashboard' | 'cluster';
export type JobStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface TrackedJob {
  jobId: string;
  source: JobSource;
  /** Human-readable label shown in the status bar (filename, pod name, etc.) */
  label: string;
  resourceId?: number;
  status: JobStatus;
  /** Seconds since the job was started */
  elapsedSeconds: number;
  result?: LogAnalysis;
  error?: string;
  startedAt: number;
  /** Caller-supplied extra data (e.g. uploadResult, pod info) */
  metadata?: Record<string, unknown>;
}

interface AnalysisContextValue {
  jobs: Record<string, TrackedJob>;
  /** Register a job_id returned by the backend and begin polling. */
  startTracking: (
    jobId: string,
    source: JobSource,
    label: string,
    resourceId?: number,
    metadata?: Record<string, unknown>,
  ) => void;
  /** Most recent job for the given source (+ optional resourceId). */
  getLatestJob: (source: JobSource, resourceId?: number) => TrackedJob | undefined;
  /** Remove a job from tracking (e.g. after displaying its result). */
  clearJob: (jobId: string) => void;
  /** Number of pending/running jobs (used for the nav badge). */
  activeCount: number;
}

// ─── Internal persistence type ───────────────────────────────────────────────
interface PersistedEntry {
  jobId: string;
  source: JobSource;
  label: string;
  resourceId?: number;
  startedAt: number;
  metadata?: Record<string, unknown>;
}

// ─── Context ──────────────────────────────────────────────────────────────────
const AnalysisContext = createContext<AnalysisContextValue | null>(null);

export const useAnalysis = (): AnalysisContextValue => {
  const ctx = useContext(AnalysisContext);
  if (!ctx) throw new Error('useAnalysis must be used inside <AnalysisProvider>');
  return ctx;
};

// ─── Provider ────────────────────────────────────────────────────────────────
const STORAGE_KEY = 'analysisJobs_v2';
const POLL_INTERVAL_MS = 2500;
const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

export const AnalysisProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [jobs, setJobs] = useState<Record<string, TrackedJob>>({});
  /** Tracks which job IDs have an active polling loop running. */
  const pollingRef = useRef<Set<string>>(new Set());
  /** Allows a polling loop to detect when its job was cleared. */
  const cancelledRef = useRef<Set<string>>(new Set());

  // ── Single-job state updater ───────────────────────────────────────────────
  const updateJob = useCallback((jobId: string, updates: Partial<TrackedJob>) => {
    setJobs(prev => {
      if (!prev[jobId]) return prev;
      return { ...prev, [jobId]: { ...prev[jobId], ...updates } };
    });
  }, []);

  // ── Background polling loop ────────────────────────────────────────────────
  const startPolling = useCallback(
    (jobId: string, startedAt: number) => {
      if (pollingRef.current.has(jobId)) return; // already running
      pollingRef.current.add(jobId);
      cancelledRef.current.delete(jobId);

      (async () => {
        while (!cancelledRef.current.has(jobId)) {
          await sleep(POLL_INTERVAL_MS);
          if (cancelledRef.current.has(jobId)) break;

          let current;
          try {
            current = await logAPI.getJobStatus(jobId);
          } catch {
            updateJob(jobId, {
              status: 'failed',
              error: 'Job not found — the server may have restarted. Please re-analyse.',
            });
            pollingRef.current.delete(jobId);
            return;
          }

          if (cancelledRef.current.has(jobId)) break;

          const elapsed = Math.floor((Date.now() - startedAt) / 1000);

          if (current.status === 'completed') {
            updateJob(jobId, {
              status: 'completed',
              result: current.result ?? undefined,
              elapsedSeconds: elapsed,
            });
            pollingRef.current.delete(jobId);
            return;
          }
          if (current.status === 'failed') {
            updateJob(jobId, {
              status: 'failed',
              error: current.error ?? 'Analysis failed',
              elapsedSeconds: elapsed,
            });
            pollingRef.current.delete(jobId);
            return;
          }
          // still pending / running
          updateJob(jobId, { status: current.status as JobStatus, elapsedSeconds: elapsed });
        }
        pollingRef.current.delete(jobId);
      })();
    },
    [updateJob],
  );

  // ── Persist active jobs so navigation doesn't lose them ───────────────────
  useEffect(() => {
    const toSave: PersistedEntry[] = Object.values(jobs)
      .filter(j => j.status === 'pending' || j.status === 'running')
      .map(({ jobId, source, label, resourceId, startedAt, metadata }) => ({
        jobId,
        source,
        label,
        resourceId,
        startedAt,
        metadata,
      }));
    if (toSave.length > 0) {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(toSave));
    } else {
      sessionStorage.removeItem(STORAGE_KEY);
    }
  }, [jobs]);

  // ── Restore jobs from sessionStorage on first mount ───────────────────────
  useEffect(() => {
    const saved = sessionStorage.getItem(STORAGE_KEY);
    if (!saved) return;
    try {
      const persisted: PersistedEntry[] = JSON.parse(saved);
      persisted.forEach(async p => {
        let current;
        try {
          current = await logAPI.getJobStatus(p.jobId);
        } catch {
          return; // job gone (backend restarted)
        }
        const restored: TrackedJob = {
          jobId: p.jobId,
          source: p.source,
          label: p.label,
          resourceId: p.resourceId,
          metadata: p.metadata,
          status: current.status as JobStatus,
          elapsedSeconds: Math.floor((Date.now() - p.startedAt) / 1000),
          result: current.result ?? undefined,
          startedAt: p.startedAt,
        };
        setJobs(prev => ({ ...prev, [p.jobId]: restored }));
        if (current.status === 'pending' || current.status === 'running') {
          startPolling(p.jobId, p.startedAt);
        }
      });
    } catch { /* ignore corrupt storage */ }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []); // intentionally run once — startPolling is stable

  // ── Public API ────────────────────────────────────────────────────────────
  const startTracking = useCallback(
    (
      jobId: string,
      source: JobSource,
      label: string,
      resourceId?: number,
      metadata?: Record<string, unknown>,
    ) => {
      const now = Date.now();
      setJobs(prev => ({
        ...prev,
        [jobId]: {
          jobId,
          source,
          label,
          resourceId,
          metadata,
          status: 'pending',
          elapsedSeconds: 0,
          startedAt: now,
        },
      }));
      startPolling(jobId, now);
    },
    [startPolling],
  );

  const getLatestJob = useCallback(
    (source: JobSource, resourceId?: number): TrackedJob | undefined => {
      const matching = Object.values(jobs).filter(
        j =>
          j.source === source &&
          (resourceId === undefined || j.resourceId === resourceId),
      );
      if (matching.length === 0) return undefined;
      return matching.sort((a, b) => b.startedAt - a.startedAt)[0];
    },
    [jobs],
  );

  const clearJob = useCallback((jobId: string) => {
    cancelledRef.current.add(jobId);
    setJobs(prev => {
      const next = { ...prev };
      delete next[jobId];
      return next;
    });
  }, []);

  const activeCount = Object.values(jobs).filter(
    j => j.status === 'pending' || j.status === 'running',
  ).length;

  return (
    <AnalysisContext.Provider value={{ jobs, startTracking, getLatestJob, clearJob, activeCount }}>
      {children}
    </AnalysisContext.Provider>
  );
};
