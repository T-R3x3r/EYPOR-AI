export interface Scenario {
  id: number;
  name: string;
  created_at: string;
  modified_at: string;
  database_path: string;
  parent_scenario_id?: number;
  is_base_scenario: boolean;
  description?: string;
}

export interface AnalysisFile {
  id: number;
  filename: string;
  file_type: string; // 'sql_query', 'visualization_template', etc.
  content: string;
  created_at: string;
  created_by_scenario_id?: number;
  is_global: boolean;
}

export interface ExecutionHistory {
  id: number;
  scenario_id: number;
  command: string;
  output?: string;
  error?: string;
  timestamp: string;
  execution_time_ms?: number;
  output_files?: string; // JSON string of output files
}

export interface ScenarioCreateRequest {
  name?: string;
  base_scenario_id?: number;
  description?: string;
}

export interface ScenarioUpdateRequest {
  name?: string;
  description?: string;
}

export interface AnalysisFileCreateRequest {
  filename: string;
  file_type: string;
  content: string;
  is_global?: boolean;
  created_by_scenario_id?: number;
}

export interface AnalysisFileUpdateRequest {
  filename?: string;
  file_type?: string;
  content?: string;
  is_global?: boolean;
}

export interface ScenarioResponse {
  message?: string;
  scenario?: Scenario;
  scenarios?: Scenario[];
  success?: boolean;
  error?: string;
}

export interface AnalysisFileResponse {
  message?: string;
  file?: AnalysisFile;
  files?: AnalysisFile[];
  success?: boolean;
  error?: string;
}

export interface ExecutionHistoryResponse {
  history: ExecutionHistory[];
  success?: boolean;
  error?: string;
} 