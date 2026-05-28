export interface LogEntry {
  id: number;
  timestamp?: string;
  level?: string;
  message: string;
  raw_log: string;
  resource_id?: number;
  source_file?: string;
  created_at: string;
}

export interface K8sResource {
  id: number;
  namespace: string;
  pod_name: string;
  container_name?: string;
  resource_type: string;
  created_at: string;
  updated_at: string;
}

export interface LogAnalysis {
  id: number;
  resource_id?: number;
  source_file?: string;
  analysis_type: string;
  findings: Record<string, any>;
  suggestions: Record<string, any>;
  created_at: string;
}

export interface LogUploadResponse {
  message: string;
  file_id: number;
  entries_count: number;
  analysis_id?: number;
}

export interface K8sPodInfo {
  name: string;
  namespace: string;
  status: string;
  containers: string[];
  created?: string;
}

export interface ClusterHealth {
  status: string;
  namespaces: number;
  total_pods: number;
  running_pods: number;
  failed_pods: number;
  error?: string;
}

export interface AnalysisResult {
  anomalies: string[];
  root_causes: string[];
  resolutions: string[];
  health_assessment?: string;
  config_issues?: string[];
  performance_insights?: string[];
  severity: string;
  confidence_score: number;
}
