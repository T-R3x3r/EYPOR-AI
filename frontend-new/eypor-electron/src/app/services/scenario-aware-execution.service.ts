import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject, takeUntil } from 'rxjs';
import { ApiService } from './api.service';
import { ScenarioService } from './scenario.service';
import { Scenario } from '../models/scenario.model';

export interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
  isVisible?: boolean;
  timestamp: number;
  error?: string;
  htmlContent?: string;
  plotlyContent?: string;
}

export interface ExecutionResult {
  command: string;
  output: string;
  error?: string;
  returnCode: number;
  outputFiles?: OutputFile[];
  timestamp: number;
  isRunning?: boolean;
  scenarioId: number;
}

export interface ScenarioExecutionCache {
  [scenarioId: number]: {
    results: ExecutionResult[];
    isExecuting: boolean;
    lastUpdated: Date;
  };
}

@Injectable({
  providedIn: 'root'
})
export class ScenarioAwareExecutionService {
  private currentScenarioSubject = new BehaviorSubject<Scenario | null>(null);
  private executionResultsSubject = new BehaviorSubject<ExecutionResult[]>([]);
  private isExecutingSubject = new BehaviorSubject<boolean>(false);
  private executionCache: ScenarioExecutionCache = {};
  private destroy$ = new Subject<void>();

  constructor(
    private apiService: ApiService,
    private scenarioService: ScenarioService
  ) {
    this.initializeScenarioSubscription();
  }

  // Observables
  get currentScenario$(): Observable<Scenario | null> {
    return this.currentScenarioSubject.asObservable();
  }

  get executionResults$(): Observable<ExecutionResult[]> {
    return this.executionResultsSubject.asObservable();
  }

  get isExecuting$(): Observable<boolean> {
    return this.isExecutingSubject.asObservable();
  }

  // Current values
  get currentScenario(): Scenario | null {
    return this.currentScenarioSubject.value;
  }

  get executionResults(): ExecutionResult[] {
    return this.executionResultsSubject.value;
  }

  get isExecuting(): boolean {
    return this.isExecutingSubject.value;
  }

  // Initialize scenario subscription
  private initializeScenarioSubscription(): void {
    this.scenarioService.currentScenario$
      .pipe(takeUntil(this.destroy$))
      .subscribe(scenario => {
        this.currentScenarioSubject.next(scenario);
        if (scenario) {
          this.loadScenarioExecutions(scenario.id);
        } else {
          this.executionResultsSubject.next([]);
          this.isExecutingSubject.next(false);
        }
      });
  }

  // Load executions for a specific scenario
  private loadScenarioExecutions(scenarioId: number): void {
    // Check if executions are already cached
    if (this.executionCache[scenarioId]) {
      this.executionResultsSubject.next(this.executionCache[scenarioId].results);
      this.isExecutingSubject.next(this.executionCache[scenarioId].isExecuting);
      return;
    }

    // Initialize empty cache for this scenario
    this.executionCache[scenarioId] = {
      results: [],
      isExecuting: false,
      lastUpdated: new Date()
    };

    this.executionResultsSubject.next([]);
    this.isExecutingSubject.next(false);
  }

  // Emit execution result for current scenario
  emitExecutionResult(result: ExecutionResult): void {
    if (!this.currentScenario) {
      console.warn('No current scenario, cannot emit execution result');
      return;
    }

    const scenarioId = this.currentScenario.id;
    result.scenarioId = scenarioId;

    // Ensure cache exists for this scenario
    if (!this.executionCache[scenarioId]) {
      this.executionCache[scenarioId] = {
        results: [],
        isExecuting: false,
        lastUpdated: new Date()
      };
    }

    const currentResults = this.executionCache[scenarioId].results;
    
    // If there's a running execution, replace it with the final result
    const runningIndex = currentResults.findIndex(r => r.isRunning);
    if (runningIndex !== -1) {
      currentResults[runningIndex] = result;
    } else {
      currentResults.push(result);
    }
    
    // Update cache
    this.executionCache[scenarioId].results = [...currentResults];
    this.executionCache[scenarioId].lastUpdated = new Date();
    
    // Emit to current scenario
    if (this.currentScenario?.id === scenarioId) {
      this.executionResultsSubject.next([...currentResults]);
    }
  }

  // Set executing state for current scenario
  setExecuting(isExecuting: boolean): void {
    if (!this.currentScenario) {
      console.warn('No current scenario, cannot set executing state');
      return;
    }

    const scenarioId = this.currentScenario.id;

    // Ensure cache exists for this scenario
    if (!this.executionCache[scenarioId]) {
      this.executionCache[scenarioId] = {
        results: [],
        isExecuting: false,
        lastUpdated: new Date()
      };
    }

    this.executionCache[scenarioId].isExecuting = isExecuting;
    this.executionCache[scenarioId].lastUpdated = new Date();

    // Update current scenario state
    if (this.currentScenario?.id === scenarioId) {
      this.isExecutingSubject.next(isExecuting);
    }

    if (isExecuting) {
      // Add a running execution result
      const runningResult: ExecutionResult = {
        command: 'Executing...',
        output: '',
        error: '',
        returnCode: 0,
        outputFiles: [],
        timestamp: Date.now(),
        isRunning: true,
        scenarioId: scenarioId
      };
      
      const currentResults = this.executionCache[scenarioId].results;
      currentResults.push(runningResult);
      this.executionCache[scenarioId].results = [...currentResults];
      
      // Emit to current scenario
      if (this.currentScenario?.id === scenarioId) {
        this.executionResultsSubject.next([...currentResults]);
      }
      
      // Set a safety timeout to ensure executing state doesn't get stuck
      setTimeout(() => {
        if (this.executionCache[scenarioId]?.isExecuting) {
          console.warn('Execution timeout - forcing executing state to false');
          this.executionCache[scenarioId].isExecuting = false;
          if (this.currentScenario?.id === scenarioId) {
            this.isExecutingSubject.next(false);
          }
        }
      }, 65000); // 65 seconds (slightly longer than the 60-second API timeout)
    }
  }

  // Clear results for current scenario
  clearResults(): void {
    if (!this.currentScenario) {
      console.warn('No current scenario, cannot clear results');
      return;
    }

    const scenarioId = this.currentScenario.id;
    
    if (this.executionCache[scenarioId]) {
      this.executionCache[scenarioId].results = [];
      this.executionCache[scenarioId].lastUpdated = new Date();
    }

    this.executionResultsSubject.next([]);
  }

  // Clear results for specific scenario
  clearScenarioResults(scenarioId: number): void {
    if (this.executionCache[scenarioId]) {
      this.executionCache[scenarioId].results = [];
      this.executionCache[scenarioId].lastUpdated = new Date();
    }

    // If this is the current scenario, update the observable
    if (this.currentScenario?.id === scenarioId) {
      this.executionResultsSubject.next([]);
    }
  }

  // Stop execution
  stopExecution(): Observable<{ message: string }> {
    return this.apiService.stopExecution();
  }

  // Performance optimization methods
  preloadScenarioExecutions(scenarioId: number): void {
    if (!this.executionCache[scenarioId]) {
      this.loadScenarioExecutions(scenarioId);
    }
  }

  clearCache(): void {
    this.executionCache = {};
  }

  clearScenarioCache(scenarioId: number): void {
    delete this.executionCache[scenarioId];
  }

  // Get cache statistics
  getCacheStats(): { totalScenarios: number; cachedScenarios: number; memoryUsage: number } {
    const totalScenarios = Object.keys(this.executionCache).length;
    const cachedScenarios = Object.values(this.executionCache).filter(cache => cache.results.length > 0).length;
    const memoryUsage = JSON.stringify(this.executionCache).length;

    return {
      totalScenarios,
      cachedScenarios,
      memoryUsage
    };
  }

  // Get executions by scenario
  getExecutionsByScenario(scenarioId: number): ExecutionResult[] {
    return this.executionCache[scenarioId]?.results || [];
  }

  // Check if scenario has executions
  hasScenarioExecutions(scenarioId: number): boolean {
    return this.executionCache[scenarioId]?.results.length > 0;
  }

  // Get execution count for scenario
  getScenarioExecutionCount(scenarioId: number): number {
    return this.executionCache[scenarioId]?.results.length || 0;
  }

  // Refresh current scenario executions
  refreshCurrentScenarioExecutions(): void {
    if (this.currentScenario) {
      this.clearScenarioCache(this.currentScenario.id);
      this.loadScenarioExecutions(this.currentScenario.id);
    }
  }

  // Cleanup
  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
} 