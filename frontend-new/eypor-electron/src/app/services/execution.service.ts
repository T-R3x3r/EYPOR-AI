import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';

export interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
  isVisible?: boolean;
  timestamp: number;
  error?: string;
  htmlContent?: string; // Add field for regular HTML content
  plotlyContent?: string; // Add field for plotly HTML content
}

export interface ExecutionResult {
  command: string;
  output: string;
  error?: string;
  returnCode: number;
  outputFiles?: OutputFile[];
  timestamp: number;
  isRunning?: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class ExecutionService {
  private executionResultsSubject = new BehaviorSubject<ExecutionResult[]>([]);
  private isExecutingSubject = new BehaviorSubject<boolean>(false);

  executionResults$: Observable<ExecutionResult[]> = this.executionResultsSubject.asObservable();
  isExecuting$: Observable<boolean> = this.isExecutingSubject.asObservable();

  constructor(private apiService: ApiService) {}

  emitExecutionResult(result: ExecutionResult) {
    const currentResults = this.executionResultsSubject.value;
    
    // If there's a running execution, replace it with the final result
    const runningIndex = currentResults.findIndex(r => r.isRunning);
    if (runningIndex !== -1) {
      currentResults[runningIndex] = result;
    } else {
      currentResults.push(result);
    }
    
    this.executionResultsSubject.next([...currentResults]);
  }

  setExecuting(isExecuting: boolean) {
    this.isExecutingSubject.next(isExecuting);
    
    if (isExecuting) {
      // Add a running execution result
      const runningResult: ExecutionResult = {
        command: 'Executing...',
        output: '',
        error: '',
        returnCode: 0,
        outputFiles: [],
        timestamp: Date.now(),
        isRunning: true
      };
      
      const currentResults = this.executionResultsSubject.value;
      currentResults.push(runningResult);
      this.executionResultsSubject.next([...currentResults]);
    }
  }

  clearResults() {
    this.executionResultsSubject.next([]);
  }

  get isExecuting(): boolean {
    return this.isExecutingSubject.value;
  }

  get executionResults(): ExecutionResult[] {
    return this.executionResultsSubject.value;
  }

  stopExecution(): Observable<{ message: string }> {
    return this.apiService.stopExecution();
  }
} 