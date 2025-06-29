import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable, Subject } from 'rxjs';

export interface ChatMessage {
  role: string;
  content: string;
}

export interface ChatRequest {
  message: string;
  thread_id?: string;
}

export interface ChatResponse {
  response: string;
  created_files?: string[];
}

export interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
}

export interface LangGraphChatResponse {
  response: string;
  created_files: string[];
  current_model: string;
  agent_type: string;
  execution_output?: string;
  execution_error?: string;
  has_execution_results?: boolean;
  output_files?: OutputFile[];
  error?: string;
}

export interface FileContent {
  filename: string;
  content: string;
}

export interface FileEditRequest {
  filename: string;
  content: string;
}

export interface ExecutionResult {
  stdout: string;
  stderr: string;
  return_code: number;
}

export interface UploadResponse {
  message: string;
  files: string[];
  file_contents: { [key: string]: string };
  table_names_message?: string;
  sql_conversion?: {
    converted_tables: string[];
    total_tables: number;
    conversion_summary: string[];
    python_transformations: string[];
    database_info: any;
    csv_files_removed: number;
    excel_files_removed: number;
    python_files_updated: number;
  };
}

export interface StatusResponse {
  files_count: number;
  has_code_output: boolean;
  has_code_error: boolean;
  current_ai_model: string;
  available_models: {
    openai: boolean;
    gemini: boolean;
  };
}

export interface SwitchAIRequest {
  model: string;
}

export interface SwitchAIResponse {
  message: string;
  current_model: string;
}

export interface CurrentAIResponse {
  current_model: string;
  available_models: {
    openai: boolean;
    gemini: boolean;
  };
}

export interface AgentInfo {
  agents: { [key: string]: string };
  current_agent: string;
  default_agent: string;
}

export interface ChatModeInfo {
  use_langgraph: boolean;
  mode: string;
  current_agent: string;
}

// SQL-related interfaces
export interface SQLQueryRequest {
  question: string;
}

export interface SQLResult {
  success: boolean;
  question: string;
  sql: string;
  result: any[];
  columns: string[];
  row_count: number;
  error?: string;
  explanation?: string;
  visualization_code?: string;
  is_general_response?: boolean;
}

export interface DatabaseInfo {
  tables: DatabaseTable[];
  total_tables: number;
  database_path: string;
  table_mappings: any;
}

export interface DatabaseTable {
  name: string;
  columns: DatabaseColumn[];
  row_count: number;
  sample_data: any[];
}

export interface DatabaseColumn {
  name: string;
  type: string;
}

export interface UpdateDataRequest {
  table_name: string;
  updates: any;
  condition?: string;
}

export interface InsertDataRequest {
  table_name: string;
  data: any;
}

// Action-based system interfaces
export interface ActionRequest {
  message: string;
  action_type?: string;
  conversation_history?: ChatMessage[];
}

export interface ActionResponse {
  response?: string;
  action_type: string;
  success: boolean;
  error?: string;
  // SQL Query specific fields
  sql_query?: string;
  result_data?: any[];
  columns?: any[];
  // Visualization specific fields
  created_files?: string[];
  output_files?: OutputFile[];
  // Database modification specific fields
  parameter_updated?: string;
  new_value?: any;
  // Common fields
  execution_output?: string;
  execution_error?: string;
}

export interface ActionType {
  description: string;
  examples: string[];
}

export interface ActionTypesResponse {
  action_types: {
    SQL_QUERY: ActionType;
    VISUALIZATION: ActionType;
    DATABASE_MODIFICATION: ActionType;
  };
  classification_info: string;
}

interface FileResponse {
  files: string[];
  uploaded_files: string[];
  ai_created_files: string[];
  file_contents: { [key: string]: string };
}

interface SQLModeStatus {
  sql_enabled: boolean;
  database_path: string | null;
  total_tables: number;
}

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8001';
  private executionResultSubject = new Subject<ExecutionResult>();

  constructor(private http: HttpClient) { }

  // Observable for execution results
  get executionResult$() {
    return this.executionResultSubject.asObservable();
  }

  // Method to emit execution results
  emitExecutionResult(result: ExecutionResult) {
    console.log('ApiService emitting execution result:', result);
    this.executionResultSubject.next(result);
  }

  uploadFile(file: File): Observable<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<UploadResponse>(`${this.baseUrl}/upload`, formData);
  }

  getFiles(): Observable<FileResponse> {
    return this.http.get<FileResponse>(`${this.baseUrl}/files`);
  }

  getFileContent(filename: string): Observable<FileContent> {
    return this.http.get<FileContent>(`${this.baseUrl}/files/${filename}`);
  }

  updateFile(filename: string, content: string): Observable<{ message: string }> {
    const request: FileEditRequest = { filename, content };
    return this.http.put<{ message: string }>(`${this.baseUrl}/files/${filename}`, request);
  }

  runFile(filename: string): Observable<ExecutionResult> {
    console.log('ApiService runFile called with:', filename);
    return this.http.post<ExecutionResult>(`${this.baseUrl}/run?filename=${filename}`, {});
  }

  installRequirements(filename: string): Observable<ExecutionResult> {
    console.log('ApiService installRequirements called with:', filename);
    return this.http.post<ExecutionResult>(`${this.baseUrl}/install?filename=${filename}`, {});
  }

  chat(message: string): Observable<ChatResponse> {
    const request: ChatRequest = { message };
    return this.http.post<ChatResponse>(`${this.baseUrl}/chat`, request);
  }

  langGraphChat(message: string): Observable<LangGraphChatResponse> {
    const chatMessage: ChatMessage = { role: 'user', content: message };
    return this.http.post<LangGraphChatResponse>(`${this.baseUrl}/langgraph-chat`, chatMessage);
  }

  clearFiles(): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/files`);
  }

  getStatus(): Observable<StatusResponse> {
    return this.http.get<StatusResponse>(`${this.baseUrl}/status`);
  }

  switchAI(model: string): Observable<SwitchAIResponse> {
    const request: SwitchAIRequest = { model };
    return this.http.post<SwitchAIResponse>(`${this.baseUrl}/switch-ai`, request);
  }

  getCurrentAI(): Observable<CurrentAIResponse> {
    return this.http.get<CurrentAIResponse>(`${this.baseUrl}/current-ai`);
  }

  getAvailableAgents(): Observable<AgentInfo> {
    return this.http.get<AgentInfo>(`${this.baseUrl}/agents`);
  }

  switchAgent(agentType: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/switch-agent`, { agent_type: agentType });
  }

  getChatMode(): Observable<ChatModeInfo> {
    return this.http.get<ChatModeInfo>(`${this.baseUrl}/chat-mode`);
  }

  toggleChatMode(useLangGraph: boolean): Observable<any> {
    return this.http.post(`${this.baseUrl}/toggle-chat-mode`, { use_langgraph: useLangGraph });
  }

  // === SQL Database Methods ===
  executeSQL(sql: string): Observable<any> {
    const formData = new FormData();
    formData.append('sql', sql);
    return this.http.post<any>(`${this.baseUrl}/sql/execute`, formData);
  }

  getDatabaseInfo(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/database/info`);
  }

  downloadDatabase(): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/database/download`, { responseType: 'blob' });
  }

  getDetailedDatabaseInfo(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/database/info/detailed`);
  }

  exportDatabase(format: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/database/export/${format}`, { responseType: 'blob' });
  }

  // === SQL Mode Status ===
  getSQLModeStatus(): Observable<SQLModeStatus> {
    return this.http.get<SQLModeStatus>(`${this.baseUrl}/sql/mode`);
  }

  // ====== DATABASE FILE MANAGEMENT ======

  downloadFileBlob(url: string): void {
    const link = document.createElement('a');
    link.href = url;
    link.download = '';
    link.click();
  }

  // Action-based system methods
  actionChat(message: string, actionType?: string, conversationHistory?: any[], threadId: string = 'default'): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/action-chat`, {
      message,
      action_type: actionType,
      conversation_history: conversationHistory || [],
      thread_id: threadId
    });
  }

  getActionTypes(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/action-types`);
  }

  // LangGraph Memory Management
  getConversationHistory(threadId: string = 'default', limit: number = 10): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/memory/history/${threadId}?limit=${limit}`);
  }

  clearConversationHistory(threadId: string = 'default'): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}/memory/history/${threadId}`);
  }

  listConversationThreads(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/memory/threads`);
  }

  // Model Selection
  respondToModelSelection(threadId: string, selectionResponse: string): Observable<any> {
    return this.http.post(`${this.baseUrl}/approval/respond`, {
      thread_id: threadId,
      approval_response: selectionResponse
    });
  }

  getModelSelectionStatus(threadId: string): Observable<any> {
    return this.http.get(`${this.baseUrl}/approval/status/${threadId}`);
  }

  // Model discovery and execution for human-in-the-loop
  discoverModels(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/discover-models`);
  }

  executeModel(modelFilename: string, parameters?: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/execute-model`, {
      model_filename: modelFilename,
      parameters: parameters || {}
    });
  }

  deleteFile(filename: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/files/${filename}`);
  }
} 