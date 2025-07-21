import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';
import { 
  Scenario, 
  ScenarioCreateRequest, 
  ScenarioUpdateRequest, 
  ScenarioResponse,
  ExecutionHistory,
  ExecutionHistoryResponse
} from '../models/scenario.model';

@Injectable({
  providedIn: 'root'
})
export class ScenarioService {
  private currentScenarioSubject = new BehaviorSubject<Scenario | null>(null);
  private scenariosListSubject = new BehaviorSubject<Scenario[]>([]);
  private executionHistorySubject = new BehaviorSubject<ExecutionHistory[]>([]);

  constructor(private apiService: ApiService) {
    this.loadCurrentScenarioFromStorage();
    this.loadScenarios();
  }

  // Observables
  get currentScenario$(): Observable<Scenario | null> {
    return this.currentScenarioSubject.asObservable();
  }

  get scenariosList$(): Observable<Scenario[]> {
    return this.scenariosListSubject.asObservable();
  }

  get executionHistory$(): Observable<ExecutionHistory[]> {
    return this.executionHistorySubject.asObservable();
  }

  // Current values
  get currentScenario(): Scenario | null {
    return this.currentScenarioSubject.value;
  }

  get scenariosList(): Scenario[] {
    return this.scenariosListSubject.value;
  }

  get executionHistory(): ExecutionHistory[] {
    return this.executionHistorySubject.value;
  }

  // Scenario Management Methods
  createScenario(request: ScenarioCreateRequest): Observable<Scenario> {
    return new Observable(observer => {
      this.apiService.createScenario(request).subscribe({
        next: (scenario: Scenario) => {
          // Add to scenarios list
          const currentList = this.scenariosListSubject.value;
          this.scenariosListSubject.next([...currentList, scenario]);
          
          // If this is the first scenario, set it as current
          if (currentList.length === 0) {
            this.setCurrentScenario(scenario);
          }
          
          observer.next(scenario);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  switchScenario(scenarioId: number): Observable<Scenario> {
    return new Observable(observer => {
      this.apiService.activateScenario(scenarioId).subscribe({
        next: (scenario: Scenario) => {
          this.setCurrentScenario(scenario);
          observer.next(scenario);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  getScenarios(): Observable<Scenario[]> {
    return new Observable(observer => {
      this.apiService.getScenarios().subscribe({
        next: (scenarios: Scenario[]) => {
          this.scenariosListSubject.next(scenarios);
          observer.next(scenarios);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  getScenario(scenarioId: number): Observable<Scenario> {
    return this.apiService.getScenario(scenarioId);
  }

  updateScenario(scenarioId: number, request: ScenarioUpdateRequest): Observable<Scenario> {
    return new Observable(observer => {
      this.apiService.updateScenario(scenarioId, request).subscribe({
        next: (updatedScenario: Scenario) => {
          // Update in scenarios list
          const currentList = this.scenariosListSubject.value;
          const updatedList = currentList.map(s => 
            s.id === scenarioId ? updatedScenario : s
          );
          this.scenariosListSubject.next(updatedList);
          
          // Update current scenario if it's the one being updated
          if (this.currentScenario?.id === scenarioId) {
            this.setCurrentScenario(updatedScenario);
          }
          
          observer.next(updatedScenario);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  deleteScenario(scenarioId: number): Observable<boolean> {
    return new Observable(observer => {
      this.apiService.deleteScenario(scenarioId).subscribe({
        next: (response: any) => {
          // Remove from scenarios list
          const currentList = this.scenariosListSubject.value;
          const updatedList = currentList.filter(s => s.id !== scenarioId);
          this.scenariosListSubject.next(updatedList);
          
          // If deleted scenario was current, switch to first available
          if (this.currentScenario?.id === scenarioId) {
            if (updatedList.length > 0) {
              this.switchScenario(updatedList[0].id).subscribe();
            } else {
              this.setCurrentScenario(null);
            }
          }
          
          observer.next(true);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  getCurrentScenario(): Observable<Scenario> {
    return this.apiService.getCurrentScenario();
  }

  getExecutionHistory(scenarioId: number): Observable<ExecutionHistory[]> {
    return new Observable(observer => {
      this.apiService.getExecutionHistory(scenarioId).subscribe({
        next: (history: ExecutionHistory[]) => {
          this.executionHistorySubject.next(history);
          observer.next(history);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  // Helper Methods
  private setCurrentScenario(scenario: Scenario | null): void {
    this.currentScenarioSubject.next(scenario);
    this.saveCurrentScenarioToStorage(scenario);
    
    // Load execution history for the scenario
    if (scenario) {
      this.getExecutionHistory(scenario.id).subscribe();
    } else {
      this.executionHistorySubject.next([]);
    }
  }

  private loadCurrentScenarioFromStorage(): void {
    const storedScenarioId = localStorage.getItem('currentScenarioId');
    if (storedScenarioId) {
      const scenarioId = parseInt(storedScenarioId, 10);
      // Try to find the scenario in the current list
      const scenario = this.scenariosList.find(s => s.id === scenarioId);
      if (scenario) {
        this.currentScenarioSubject.next(scenario);
      }
    }
  }

  private saveCurrentScenarioToStorage(scenario: Scenario | null): void {
    if (scenario) {
      localStorage.setItem('currentScenarioId', scenario.id.toString());
    } else {
      localStorage.removeItem('currentScenarioId');
    }
  }

  private loadScenarios(): void {
    this.getScenarios().subscribe();
  }

  // Utility Methods
  isCurrentScenario(scenarioId: number): boolean {
    return this.currentScenario?.id === scenarioId;
  }

  getScenarioById(scenarioId: number): Scenario | undefined {
    return this.scenariosList.find(s => s.id === scenarioId);
  }

  refreshScenarios(): void {
    this.loadScenarios();
  }

  // Add scenario from upload response
  addScenarioFromUpload(scenarioData: any): void {
    // Convert the scenario data to a Scenario object
    const scenario: Scenario = {
      id: scenarioData.id,
      name: scenarioData.name,
      created_at: scenarioData.created_at,
      modified_at: scenarioData.modified_at,
      database_path: scenarioData.database_path,
      parent_scenario_id: scenarioData.parent_scenario_id,
      is_base_scenario: scenarioData.is_base_scenario,
      description: scenarioData.description
    };

    // Add to scenarios list
    const currentList = this.scenariosListSubject.value;
    this.scenariosListSubject.next([...currentList, scenario]);
    
    // Set as current scenario if it's the first one
    if (currentList.length === 0) {
      this.setCurrentScenario(scenario);
    }
  }
} 