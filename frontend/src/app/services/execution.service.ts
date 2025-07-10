import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, combineLatest } from 'rxjs';
import { map } from 'rxjs/operators';
import { ScenarioService } from './scenario.service';
import { ExecutionHistory } from '../models/scenario.model';

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
  scenarioId?: number;  // Add scenario context
}

@Injectable({
  providedIn: 'root'
})
export class ExecutionService {
  private executionResultSubject = new BehaviorSubject<ExecutionResult | null>(null);
  private isExecutingSubject = new BehaviorSubject<boolean>(false);
  private scenarioExecutionHistorySubject = new BehaviorSubject<ExecutionHistory[]>([]);
  // Add persistent storage for execution results per scenario
  private scenarioExecutionResults = new Map<number, ExecutionResult[]>();

  executionResult$: Observable<ExecutionResult | null> = this.executionResultSubject.asObservable();
  isExecuting$: Observable<boolean> = this.isExecutingSubject.asObservable();
  scenarioExecutionHistory$: Observable<ExecutionHistory[]> = this.scenarioExecutionHistorySubject.asObservable();

  // Combined observable for current scenario's execution history
  currentScenarioExecutionHistory$: Observable<ExecutionHistory[]> = combineLatest([
    this.scenarioExecutionHistory$,
    this.scenarioService.currentScenario$
  ]).pipe(
    map(([history, currentScenario]) => {
      if (!currentScenario) return [];
      return history.filter(h => h.scenario_id === currentScenario.id);
    })
  );

  constructor(private scenarioService: ScenarioService) {
    // Subscribe to scenario changes to update execution history
    this.scenarioService.executionHistory$.subscribe(history => {
      this.scenarioExecutionHistorySubject.next(history);
    });

    // Subscribe to scenario changes to preserve execution results
    this.scenarioService.currentScenario$.subscribe(scenario => {
      if (scenario) {
        // Load persistent execution results for this scenario
        this.loadScenarioExecutionResults(scenario.id);
      }
    });
  }

  emitExecutionResult(result: ExecutionResult) {
    // Add current scenario ID if not provided
    if (!result.scenarioId && this.scenarioService.currentScenario) {
      result.scenarioId = this.scenarioService.currentScenario.id;
    }
    
    // Store the result for the current scenario
    if (result.scenarioId) {
      this.storeExecutionResult(result.scenarioId, result);
    }
    
    this.executionResultSubject.next(result);
  }

  setExecuting(isExecuting: boolean) {
    this.isExecutingSubject.next(isExecuting);
  }

  clearResults() {
    this.executionResultSubject.next(null);
  }

  // Store execution result for a specific scenario
  private storeExecutionResult(scenarioId: number, result: ExecutionResult): void {
    if (!this.scenarioExecutionResults.has(scenarioId)) {
      this.scenarioExecutionResults.set(scenarioId, []);
    }
    const results = this.scenarioExecutionResults.get(scenarioId)!;
    results.push(result);
    // Keep only the last 50 results per scenario
    if (results.length > 50) {
      results.splice(0, results.length - 50);
    }
  }

  // Load execution results for a specific scenario
  private loadScenarioExecutionResults(scenarioId: number): void {
    const results = this.scenarioExecutionResults.get(scenarioId);
    if (results && results.length > 0) {
      // Emit the most recent result
      this.executionResultSubject.next(results[results.length - 1]);
    }
  }

  // Get all execution results for a specific scenario
  getScenarioExecutionResults(scenarioId: number): ExecutionResult[] {
    return this.scenarioExecutionResults.get(scenarioId) || [];
  }

  // Scenario-aware methods
  getCurrentScenarioExecutionHistory(): ExecutionHistory[] {
    const currentScenario = this.scenarioService.currentScenario;
    if (!currentScenario) return [];
    
    return this.scenarioExecutionHistorySubject.value.filter(
      h => h.scenario_id === currentScenario.id
    );
  }

  refreshExecutionHistory(): void {
    const currentScenario = this.scenarioService.currentScenario;
    if (currentScenario) {
      this.scenarioService.getExecutionHistory(currentScenario.id).subscribe();
    }
  }

  // Utility methods
  get isExecuting(): boolean {
    return this.isExecutingSubject.value;
  }

  get currentExecutionResult(): ExecutionResult | null {
    return this.executionResultSubject.value;
  }

  get currentScenarioHistory(): ExecutionHistory[] {
    return this.getCurrentScenarioExecutionHistory();
  }
} 