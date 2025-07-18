import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
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
  private scenarioCache = new Map<number, Scenario>();
  private executionHistoryCache = new Map<number, ExecutionHistory[]>();

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
          
          // Cache the scenario
          this.scenarioCache.set(scenario.id, scenario);
          
          // If this is the first scenario, set it as current
          if (currentList.length === 0) {
            this.setCurrentScenario(scenario);
          } else if (!this.currentScenario) {
            // If no current scenario is set, try to set the base scenario
            const updatedList = [...currentList, scenario];
            const baseScenario = updatedList.find(s => s.is_base_scenario);
            if (baseScenario) {
              this.setCurrentScenario(baseScenario);
            } else {
              // If no base scenario exists, set the first scenario
              this.setCurrentScenario(updatedList[0]);
            }
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
        next: (apiScenarios: any[]) => {
          // Convert API scenarios to our Scenario model
          const scenarios: Scenario[] = apiScenarios.map(apiScenario => ({
            id: apiScenario.id,
            name: apiScenario.name,
            created_at: apiScenario.created_at || new Date().toISOString(),
            modified_at: apiScenario.modified_at || new Date().toISOString(),
            database_path: apiScenario.database_path,
            parent_scenario_id: apiScenario.parent_scenario_id,
            is_base_scenario: apiScenario.is_base_scenario,
            description: apiScenario.description
          }));
          
          this.scenariosListSubject.next(scenarios);
          
          // Cache all scenarios for performance
          scenarios.forEach(scenario => {
            this.scenarioCache.set(scenario.id, scenario);
          });
          
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
    // Check cache first for performance
    const cachedScenario = this.scenarioCache.get(scenarioId);
    if (cachedScenario) {
      return new Observable(observer => {
        observer.next(cachedScenario);
        observer.complete();
      });
    }

    return new Observable(observer => {
      this.apiService.getScenario(scenarioId).subscribe({
        next: (scenario: Scenario) => {
          this.scenarioCache.set(scenarioId, scenario);
          observer.next(scenario);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
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
          
          // Update cache
          this.scenarioCache.set(scenarioId, updatedScenario);
          
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
          
          // Remove from cache
          this.scenarioCache.delete(scenarioId);
          this.executionHistoryCache.delete(scenarioId);
          
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
    // For now, return empty array since the API doesn't support this yet
    return new Observable(observer => {
      observer.next([]);
      observer.complete();
    });
  }

  // Performance optimization methods
  preloadScenarioData(scenarioId: number): void {
    // Preload scenario and execution history for better performance
    this.getScenario(scenarioId).subscribe();
    this.getExecutionHistory(scenarioId).subscribe();
  }

  clearCache(): void {
    this.scenarioCache.clear();
    this.executionHistoryCache.clear();
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
      } else {
        // If stored scenario doesn't exist, clear the storage
        console.log('Stored scenario not found, clearing storage');
        localStorage.removeItem('currentScenarioId');
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
    this.getScenarios().subscribe({
      next: (scenarios: Scenario[]) => {
        // If no current scenario is set, try to set the base scenario as current
        if (!this.currentScenario && scenarios.length > 0) {
          const baseScenario = scenarios.find(s => s.is_base_scenario);
          if (baseScenario) {
            console.log('Setting base scenario as current:', baseScenario.name);
            this.setCurrentScenario(baseScenario);
          } else {
            // If no base scenario exists, set the first scenario as current
            console.log('Setting first scenario as current:', scenarios[0].name);
            this.setCurrentScenario(scenarios[0]);
          }
        }
      }
    });
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
    
    // Cache the scenario
    this.scenarioCache.set(scenario.id, scenario);
  }

  // New method to determine scenario type display
  getScenarioTypeDisplay(scenario: Scenario): 'Base' | 'Custom' | 'Branch' {
    // If it's a branch (has parent_scenario_id), always show "Branch"
    if (scenario.parent_scenario_id) {
      return 'Branch';
    }
    
    // If it's a base scenario, check if it has been modified
    if (scenario.is_base_scenario) {
      // Compare created_at and modified_at to determine if scenario has been modified
      const createdDate = new Date(scenario.created_at);
      const modifiedDate = new Date(scenario.modified_at);
      
      // If modified_at is significantly different from created_at, it's been modified
      const timeDifference = Math.abs(modifiedDate.getTime() - createdDate.getTime());
      const oneMinute = 60 * 1000; // 1 minute in milliseconds
      
      if (timeDifference > oneMinute) {
        return 'Custom';
      } else {
        return 'Base';
      }
    }
    
    // For non-base scenarios without parent, default to "Custom"
    return 'Custom';
  }

  // Helper method to get scenario type for current scenario
  getCurrentScenarioType(): 'Base' | 'Custom' | 'Branch' {
    const currentScenario = this.currentScenario;
    if (!currentScenario) return 'Base';
    return this.getScenarioTypeDisplay(currentScenario);
  }
} 