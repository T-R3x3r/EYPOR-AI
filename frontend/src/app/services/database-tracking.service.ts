import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';

interface DatabaseChange {
  table: string;
  column: string;
  row_id: string | number;
  old_value: any;
  new_value: any;
  timestamp: Date;
}

interface CellChange {
  table: string;
  column: string;
  row_id: string | number;
  highlighted: boolean;
  timestamp: Date;
}

interface ModelRerunRequest {
  id: string;
  change_description: string;
  available_models: string[];
  recommended_model?: string;
  timestamp: Date;
  status: 'pending' | 'approved' | 'rejected';
  selected_model?: string;
}

interface AvailableModel {
  filename: string;
  type: 'runall' | 'main' | 'model' | 'other';
  description: string;
  highlighted: boolean;
}

@Injectable({
  providedIn: 'root'
})
export class DatabaseTrackingService {
  private changes: DatabaseChange[] = [];
  private highlightedCells: Map<string, CellChange> = new Map();
  private changesSubject = new BehaviorSubject<DatabaseChange[]>([]);
  private highlightedCellsSubject = new BehaviorSubject<Map<string, CellChange>>(new Map());
  
  // Human-in-the-loop for model rerun
  private pendingRerunRequest: ModelRerunRequest | null = null;
  private rerunRequestSubject = new BehaviorSubject<ModelRerunRequest | null>(null);
  private availableModels: AvailableModel[] = [];
  private availableModelsSubject = new BehaviorSubject<AvailableModel[]>([]);

  constructor(private apiService: ApiService) {}

  // Observable for components to subscribe to changes
  getChanges(): Observable<DatabaseChange[]> {
    return this.changesSubject.asObservable();
  }

  // Observable for highlighted cells
  getHighlightedCells(): Observable<Map<string, CellChange>> {
    return this.highlightedCellsSubject.asObservable();
  }

  // Observable for model rerun requests
  getRerunRequest(): Observable<ModelRerunRequest | null> {
    return this.rerunRequestSubject.asObservable();
  }

  // Observable for available models
  getAvailableModels(): Observable<AvailableModel[]> {
    return this.availableModelsSubject.asObservable();
  }

  // Record a database change
  recordChange(table: string, column: string, row_id: string | number, old_value: any, new_value: any): void {
    const change: DatabaseChange = {
      table,
      column,
      row_id,
      old_value,
      new_value,
      timestamp: new Date()
    };

    this.changes.push(change);
    this.changesSubject.next([...this.changes]);

    // Add to highlighted cells
    const cellKey = `${table}_${column}_${row_id}`;
    const cellChange: CellChange = {
      table,
      column,
      row_id,
      highlighted: true,
      timestamp: new Date()
    };

    this.highlightedCells.set(cellKey, cellChange);
    this.highlightedCellsSubject.next(new Map(this.highlightedCells));

    // Auto-remove highlight after 10 seconds
    setTimeout(() => {
      this.removeHighlight(cellKey);
    }, 10000);

    // Trigger human-in-the-loop for model rerun decision
    this.requestModelRerun(`${table}.${column}`, old_value, new_value);
  }

  // Check if a cell should be highlighted
  isCellHighlighted(table: string, column: string, row_id: string | number): boolean {
    const cellKey = `${table}_${column}_${row_id}`;
    return this.highlightedCells.has(cellKey);
  }

  // Get cell change info
  getCellChange(table: string, column: string, row_id: string | number): CellChange | null {
    const cellKey = `${table}_${column}_${row_id}`;
    return this.highlightedCells.get(cellKey) || null;
  }

  // Remove highlight for a specific cell
  removeHighlight(cellKey: string): void {
    if (this.highlightedCells.has(cellKey)) {
      this.highlightedCells.delete(cellKey);
      this.highlightedCellsSubject.next(new Map(this.highlightedCells));
    }
  }

  // Clear all highlights
  clearAllHighlights(): void {
    this.highlightedCells.clear();
    this.highlightedCellsSubject.next(new Map());
  }

  // Get all changes for a specific table
  getTableChanges(table: string): DatabaseChange[] {
    return this.changes.filter(change => change.table === table);
  }

  // Clear all changes
  clearChanges(): void {
    this.changes = [];
    this.changesSubject.next([]);
    this.clearAllHighlights();
  }

  // Parse database modification response to extract changes
  parseModificationResponse(response: string): void {
    try {
      // Look for patterns like "Updated table X, column Y from A to B"
      const updatePattern = /Updated table (\w+), column (\w+) from (.+) to (.+)/g;
      const paramPattern = /Parameter (\w+) updated from (.+) to (.+)/g;
      
      let match;
      
      // Handle table updates
      while ((match = updatePattern.exec(response)) !== null) {
        const [, table, column, oldValue, newValue] = match;
        // For parameter updates, we don't have specific row IDs, so use 'param'
        this.recordChange(table, column, 'param', oldValue.trim(), newValue.trim());
      }
      
      // Handle parameter updates
      while ((match = paramPattern.exec(response)) !== null) {
        const [, paramName, oldValue, newValue] = match;
        // Try to map parameter names to table/column combinations
        this.recordChange('parameters', paramName, 'param', oldValue.trim(), newValue.trim());
      }
    } catch (error) {
      console.error('Error parsing modification response:', error);
    }
  }

  // Human-in-the-loop: Request model rerun decision
  private requestModelRerun(changeLocation: string, oldValue: any, newValue: any): void {
    // Don't create duplicate requests
    if (this.pendingRerunRequest && this.pendingRerunRequest.status === 'pending') {
      return;
    }

    const changeDescription = `Modified ${changeLocation}: ${oldValue} → ${newValue}`;
    
    // Discover available models
    this.discoverAvailableModels().then(models => {
      const request: ModelRerunRequest = {
        id: Date.now().toString(),
        change_description: changeDescription,
        available_models: models.map(m => m.filename),
        recommended_model: models.find(m => m.type === 'runall')?.filename,
        timestamp: new Date(),
        status: 'pending'
      };

      this.pendingRerunRequest = request;
      this.rerunRequestSubject.next(request);
      this.availableModelsSubject.next(models);
    });
  }

  // Discover available models in the project
  private async discoverAvailableModels(): Promise<AvailableModel[]> {
    try {
      const response = await this.apiService.discoverModels().toPromise();
      const models: AvailableModel[] = [];
      
      // Common model file patterns
      const modelPatterns = [
        { pattern: /runall/i, type: 'runall' as const, description: 'Run all models' },
        { pattern: /main\.py$/i, type: 'main' as const, description: 'Main execution script' },
        { pattern: /model.*\.py$/i, type: 'model' as const, description: 'Model script' },
        { pattern: /run.*\.py$/i, type: 'model' as const, description: 'Run script' },
        { pattern: /execute.*\.py$/i, type: 'model' as const, description: 'Execute script' }
      ];

      // Process discovered files from backend
      const discoveredFiles = response.files || [];
      
      discoveredFiles.forEach((filename: string) => {
        for (const pattern of modelPatterns) {
          if (pattern.pattern.test(filename)) {
            models.push({
              filename,
              type: pattern.type,
              description: pattern.description,
              highlighted: pattern.type === 'runall' // Highlight runall files
            });
            break;
          }
        }
      });

      // If no files discovered from backend, use fallback
      if (models.length === 0) {
        const fallbackFiles = [
          'runall.py',
          'runall.bat', 
          'run_all_models.py',
          'main.py',
          'model_runner.py',
          'execute_model.py',
          'run_analysis.py'
        ];

        fallbackFiles.forEach(filename => {
          for (const pattern of modelPatterns) {
            if (pattern.pattern.test(filename)) {
              models.push({
                filename,
                type: pattern.type,
                description: pattern.description,
                highlighted: pattern.type === 'runall'
              });
              break;
            }
          }
        });
      }

      return models;
    } catch (error) {
      console.error('Error discovering models:', error);
      return [];
    }
  }

  // User approves model rerun
  approveModelRerun(selectedModel: string): void {
    if (this.pendingRerunRequest) {
      this.pendingRerunRequest.status = 'approved';
      this.pendingRerunRequest.selected_model = selectedModel;
      this.rerunRequestSubject.next(this.pendingRerunRequest);
      
      console.log(`User approved rerunning model: ${selectedModel}`);
      // Here you would typically call the backend to execute the selected model
      this.executeModel(selectedModel);
    }
  }

  // User rejects model rerun
  rejectModelRerun(): void {
    if (this.pendingRerunRequest) {
      this.pendingRerunRequest.status = 'rejected';
      this.rerunRequestSubject.next(this.pendingRerunRequest);
      
      console.log('User rejected model rerun');
      // Clear the request after a delay
      setTimeout(() => {
        this.clearRerunRequest();
      }, 2000);
    }
  }

  // Clear the current rerun request
  clearRerunRequest(): void {
    this.pendingRerunRequest = null;
    this.rerunRequestSubject.next(null);
    this.availableModelsSubject.next([]);
  }

  // Execute the selected model
  private executeModel(modelFilename: string): void {
    console.log(`Executing model: ${modelFilename}`);
    
    this.apiService.executeModel(modelFilename).subscribe({
      next: (response) => {
        console.log('Model execution response:', response);
        // Handle successful execution
        setTimeout(() => {
          this.clearRerunRequest();
        }, 1000);
      },
      error: (error) => {
        console.error('Model execution error:', error);
        // Handle execution error
        setTimeout(() => {
          this.clearRerunRequest();
        }, 1000);
      }
    });
  }
} 