import axios from 'axios';
import {
  LogEntry,
  K8sResource,
  LogAnalysis,
  LogUploadResponse,
  K8sPodInfo,
  ClusterHealth,
  AnalysisResult
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const logAPI = {
  uploadFile: async (file: File): Promise<LogUploadResponse> => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<LogUploadResponse>('/logs/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  getEntries: async (resourceId?: number, level?: string, limit = 100): Promise<LogEntry[]> => {
    const params: any = { limit };
    if (resourceId) params.resource_id = resourceId;
    if (level) params.level = level;
    const response = await api.get<LogEntry[]>('/logs/entries', { params });
    return response.data;
  },

  getResources: async (): Promise<K8sResource[]> => {
    const response = await api.get<K8sResource[]>('/logs/resources');
    return response.data;
  },

  analyzeLogs: async (resourceId?: number, sourceFile?: string, analysisType = 'general'): Promise<LogAnalysis> => {
    const response = await api.post<LogAnalysis>('/logs/analyze', {
      resource_id: resourceId,
      source_file: sourceFile,
      analysis_type: analysisType,
    });
    return response.data;
  },

  getAnalysis: async (analysisId: number): Promise<LogAnalysis> => {
    const response = await api.get<LogAnalysis>(`/logs/analysis/${analysisId}`);
    return response.data;
  },
};

export const k8sAPI = {
  getHealth: async (): Promise<ClusterHealth> => {
    const response = await api.get<ClusterHealth>('/k8s/health');
    return response.data;
  },

  getNamespaces: async (): Promise<{ namespaces: string[] }> => {
    const response = await api.get<{ namespaces: string[] }>('/k8s/namespaces');
    return response.data;
  },

  getPods: async (namespace: string): Promise<K8sPodInfo[]> => {
    const response = await api.get<K8sPodInfo[]>(`/k8s/pods/${namespace}`);
    return response.data;
  },

  getPodLogs: async (
    namespace: string,
    podName: string,
    container?: string,
    tailLines = 100
  ): Promise<{
    logs: any[];
    resource_id: number;
    entries_count: number;
    raw_logs: string;
  }> => {
    const params: any = { tail_lines: tailLines };
    if (container) params.container = container;
    const response = await api.get(`/k8s/logs/${namespace}/${podName}`, { params });
    return response.data;
  },

  collectAllLogs: async (namespaces?: string[]): Promise<{ message: string }> => {
    const response = await api.post('/k8s/collect-all', { namespaces });
    return response.data;
  },
};

export const parseAnalysis = (analysis: LogAnalysis): AnalysisResult => {
  try {
    // If suggestions is already an object, use it directly
    if (typeof analysis.suggestions === 'object' && analysis.suggestions !== null) {
      return {
        anomalies: analysis.suggestions.anomalies || [],
        root_causes: analysis.suggestions.root_causes || [],
        resolutions: analysis.suggestions.resolutions || [],
        health_assessment: analysis.suggestions.health_assessment || 'Analysis completed',
        config_issues: analysis.suggestions.config_issues || [],
        performance_insights: analysis.suggestions.performance_insights || [],
        severity: analysis.suggestions.severity || 'Unknown',
        confidence_score: analysis.suggestions.confidence_score || 0,
      };
    }
    
    // If it's a string, try to parse it
    if (typeof analysis.suggestions === 'string') {
      const parsed = JSON.parse(analysis.suggestions);
      return {
        anomalies: parsed.anomalies || [],
        root_causes: parsed.root_causes || [],
        resolutions: parsed.resolutions || [],
        health_assessment: parsed.health_assessment || 'Analysis completed',
        config_issues: parsed.config_issues || [],
        performance_insights: parsed.performance_insights || [],
        severity: parsed.severity || 'Unknown',
        confidence_score: parsed.confidence_score || 0,
      };
    }
    
    // Fallback
    return {
      anomalies: [],
      root_causes: [],
      resolutions: ['Analysis data unavailable'],
      health_assessment: 'Analysis unavailable',
      config_issues: [],
      performance_insights: [],
      severity: 'Unknown',
      confidence_score: 0,
    };
  } catch {
    return {
      anomalies: [],
      root_causes: [],
      resolutions: ['Analysis data unavailable'],
      health_assessment: 'Analysis unavailable',
      config_issues: [],
      performance_insights: [],
      severity: 'Unknown',
      confidence_score: 0,
    };
  }
};
