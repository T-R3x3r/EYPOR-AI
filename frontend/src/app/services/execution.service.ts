import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';

export interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
}

export interface ExecutionResult {
  command: string;
  output: string;
  error?: string;
  returnCode: number;
  outputFiles?: OutputFile[] | string[];  // Support both new and legacy formats
}

@Injectable({
  providedIn: 'root'
})
export class ExecutionService {
  private executionResultSubject = new BehaviorSubject<ExecutionResult | null>(null);
  private isExecutingSubject = new BehaviorSubject<boolean>(false);

  executionResult$: Observable<ExecutionResult | null> = this.executionResultSubject.asObservable();
  isExecuting$: Observable<boolean> = this.isExecutingSubject.asObservable();

  emitExecutionResult(result: ExecutionResult) {
    this.executionResultSubject.next(result);
  }

  setExecuting(isExecuting: boolean) {
    this.isExecutingSubject.next(isExecuting);
  }

  clearResults() {
    this.executionResultSubject.next(null);
  }
} 