import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface ChatMessage {
  role: string;
  content: string;
  thread_id?: string;
}

export interface UploadResponse {
  message: string;
  files: string[];
  file_contents: { [key: string]: string };
  table_names_message?: string;
  scenario?: any; // Scenario created during upload
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

export interface FileResponse {
  files: string[];
  uploaded_files: string[];
  ai_created_files: string[];
  file_contents: { [key: string]: string };
}

export interface Scenario {
  id: number;
  name: string;
  description?: string;
  database_path: string;
  is_base_scenario: boolean;
  parent_scenario_id?: number;
}

export interface FileContentResponse {
  filename: string;
  content: string;
}

// Database-related interfaces
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

export interface WhitelistResponse {
  whitelist: string[];
  available_tables: string[];
  total_whitelisted: number;
  total_available: number;
}

export interface WhitelistUpdateResponse {
  message: string;
  whitelist: string[];
  total_whitelisted: number;
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

@Injectable({
  providedIn: 'root'
})
export class ApiService {
  private baseUrl = 'http://localhost:8001';

  constructor(private http: HttpClient) { }

  uploadFile(file: File): Observable<UploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    return this.http.post<UploadResponse>(`${this.baseUrl}/upload`, formData);
  }

  getFiles(): Observable<FileResponse> {
    return this.http.get<FileResponse>(`${this.baseUrl}/files`);
  }

  clearFiles(): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/files`);
  }

  getScenarios(): Observable<Scenario[]> {
    return this.http.get<Scenario[]>(`${this.baseUrl}/scenarios/list`);
  }

  getFileContent(filename: string): Observable<FileContentResponse> {
    return this.http.get<FileContentResponse>(`${this.baseUrl}/files/${encodeURIComponent(filename)}`);
  }

  updateFile(filename: string, content: string): Observable<{ message: string }> {
    return this.http.put<{ message: string }>(`${this.baseUrl}/files/${encodeURIComponent(filename)}`, { filename, content });
  }

  installRequirements(filename: string): Observable<{ stdout: string; stderr: string; return_code: number }> {
    return this.http.post<{ stdout: string; stderr: string; return_code: number }>(`${this.baseUrl}/install?filename=${encodeURIComponent(filename)}`, {});
  }

  runFile(filename: string): Observable<{ stdout: string; stderr: string; return_code: number; output_files?: string[] }> {
    return this.http.post<{ stdout: string; stderr: string; return_code: number; output_files?: string[] }>(`${this.baseUrl}/run?filename=${encodeURIComponent(filename)}`, {});
  }

  stopExecution(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(`${this.baseUrl}/stop-execution`, {});
  }

  // LangGraph Chat methods
  langGraphChatV2(message: string, scenarioId?: number): Observable<any> {
    const payload = {
      role: 'user',
      content: message,
      thread_id: 'default'
    };
    return this.http.post<any>(`${this.baseUrl}/langgraph-chat-v2`, payload);
  }

  actionChatV2(message: string, actionType?: string, conversationHistory?: any[], threadId: string = 'default'): Observable<any> {
    const payload = {
      message: message,
      action_type: actionType,
      conversation_history: conversationHistory || [],
      thread_id: threadId
    };
    return this.http.post<any>(`${this.baseUrl}/action-chat-v2`, payload);
  }

  getActionTypes(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/action-types`);
  }

  getConversationHistory(threadId: string = 'default', limit: number = 10): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/memory/history/${threadId}?limit=${limit}`);
  }

  clearConversationHistory(threadId: string = 'default'): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}/memory/history/${threadId}`);
  }

  listConversationThreads(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/memory/threads`);
  }

  getServerStartupInfo(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/server-startup`);
  }

  deleteFile(filename: string): Observable<{ message: string }> {
    return this.http.delete<{ message: string }>(`${this.baseUrl}/files/${encodeURIComponent(filename)}`);
  }

  // Database-related methods
  executeSQL(sql: string): Observable<SQLResult> {
    const formData = new FormData();
    formData.append('sql', sql);
    return this.http.post<SQLResult>(`${this.baseUrl}/sql/execute`, formData);
  }

  getDatabaseInfo(): Observable<DatabaseInfo> {
    return this.http.get<DatabaseInfo>(`${this.baseUrl}/database/info`);
  }

  getDetailedDatabaseInfo(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/database/detailed-info`);
  }

  downloadDatabase(): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/database/download`, { responseType: 'blob' });
  }

  exportDatabase(format: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/database/export/${format}`, { responseType: 'blob' });
  }

  getDatabaseWhitelist(): Observable<WhitelistResponse> {
    return this.http.get<WhitelistResponse>(`${this.baseUrl}/database/whitelist`);
  }

  updateDatabaseWhitelist(tables: string[]): Observable<WhitelistUpdateResponse> {
    return this.http.post<WhitelistUpdateResponse>(`${this.baseUrl}/database/whitelist`, { tables });
  }

  updateData(request: UpdateDataRequest): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/database/update`, request);
  }

  insertData(request: InsertDataRequest): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/database/insert`, request);
  }

  // Scenario-related methods
  getCurrentScenario(): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/scenarios/current`);
  }

  activateScenario(scenarioId: number): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/scenarios/${scenarioId}/activate`, {});
  }

  createScenario(request: any): Observable<any> {
    return this.http.post<any>(`${this.baseUrl}/scenarios/create`, request);
  }

  updateScenario(scenarioId: number, request: any): Observable<any> {
    return this.http.put<any>(`${this.baseUrl}/scenarios/${scenarioId}`, request);
  }

  deleteScenario(scenarioId: number): Observable<any> {
    return this.http.delete<any>(`${this.baseUrl}/scenarios/${scenarioId}`);
  }

  getScenario(scenarioId: number): Observable<any> {
    return this.http.get<any>(`${this.baseUrl}/scenarios/${scenarioId}`);
  }
} 