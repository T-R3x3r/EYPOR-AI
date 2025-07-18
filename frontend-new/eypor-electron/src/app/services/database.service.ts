import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject } from 'rxjs';
import { ApiService, DatabaseInfo, SQLResult, WhitelistResponse, WhitelistUpdateResponse } from './api.service';

export interface DatabaseChange {
  table: string;
  column: string;
  row_id: string | number;
  old_value: any;
  new_value: any;
  timestamp: Date;
  scenarioId?: number;
}

export interface CellChange {
  table: string;
  column: string;
  row_id: string | number;
  highlighted: boolean;
  timestamp: Date;
}

@Injectable({
  providedIn: 'root'
})
export class DatabaseService {
  private changesSubject = new BehaviorSubject<DatabaseChange[]>([]);
  private highlightedCellsSubject = new BehaviorSubject<Map<string, CellChange>>(new Map());
  private currentScenarioSubject = new BehaviorSubject<any>(null);
  private databaseInfoSubject = new BehaviorSubject<DatabaseInfo | null>(null);
  private isLoadingSubject = new BehaviorSubject<boolean>(false);

  constructor(private apiService: ApiService) {}

  // Observable getters
  get changes$(): Observable<DatabaseChange[]> {
    return this.changesSubject.asObservable();
  }

  get highlightedCells$(): Observable<Map<string, CellChange>> {
    return this.highlightedCellsSubject.asObservable();
  }

  get currentScenario$(): Observable<any> {
    return this.currentScenarioSubject.asObservable();
  }

  get databaseInfo$(): Observable<DatabaseInfo | null> {
    return this.databaseInfoSubject.asObservable();
  }

  get isLoading$(): Observable<boolean> {
    return this.isLoadingSubject.asObservable();
  }

  // Database operations
  loadDatabaseInfo(): Observable<DatabaseInfo> {
    this.isLoadingSubject.next(true);
    return new Observable(observer => {
      this.apiService.getDatabaseInfo().subscribe({
        next: (data: DatabaseInfo) => {
          this.databaseInfoSubject.next(data);
          this.isLoadingSubject.next(false);
          observer.next(data);
          observer.complete();
        },
        error: (error) => {
          this.isLoadingSubject.next(false);
          observer.error(error);
        }
      });
    });
  }

  executeSQL(sql: string): Observable<SQLResult> {
    return this.apiService.executeSQL(sql);
  }

  getDetailedDatabaseInfo(): Observable<any> {
    return this.apiService.getDetailedDatabaseInfo();
  }

  downloadDatabase(): Observable<Blob> {
    return this.apiService.downloadDatabase();
  }

  exportDatabase(format: string): Observable<Blob> {
    return this.apiService.exportDatabase(format);
  }

  // Whitelist management
  loadWhitelistData(): Observable<WhitelistResponse> {
    return this.apiService.getDatabaseWhitelist();
  }

  updateWhitelist(tables: string[]): Observable<WhitelistUpdateResponse> {
    return this.apiService.updateDatabaseWhitelist(tables);
  }

  // Data modification
  updateData(request: any): Observable<any> {
    return this.apiService.updateData(request);
  }

  insertData(request: any): Observable<any> {
    return this.apiService.insertData(request);
  }

  // Scenario management
  setCurrentScenario(scenario: any): void {
    this.currentScenarioSubject.next(scenario);
  }

  getCurrentScenario(): any {
    return this.currentScenarioSubject.value;
  }

  // Change tracking
  recordChange(table: string, column: string, row_id: string | number, old_value: any, new_value: any): void {
    const change: DatabaseChange = {
      table,
      column,
      row_id,
      old_value,
      new_value,
      timestamp: new Date(),
      scenarioId: this.currentScenarioSubject.value?.id
    };

    const currentChanges = this.changesSubject.value;
    currentChanges.push(change);
    this.changesSubject.next([...currentChanges]);

    // Add to highlighted cells
    const cellKey = `${table}_${column}_${row_id}`;
    const cellChange: CellChange = {
      table,
      column,
      row_id,
      highlighted: true,
      timestamp: new Date()
    };

    const currentHighlightedCells = this.highlightedCellsSubject.value;
    currentHighlightedCells.set(cellKey, cellChange);
    this.highlightedCellsSubject.next(new Map(currentHighlightedCells));

    // Auto-remove highlight after 10 seconds
    setTimeout(() => {
      this.removeHighlight(cellKey);
    }, 10000);
  }

  removeHighlight(cellKey: string): void {
    const currentHighlightedCells = this.highlightedCellsSubject.value;
    currentHighlightedCells.delete(cellKey);
    this.highlightedCellsSubject.next(new Map(currentHighlightedCells));
  }

  clearChanges(): void {
    this.changesSubject.next([]);
    this.highlightedCellsSubject.next(new Map());
  }

  // Utility methods
  getChanges(): DatabaseChange[] {
    return this.changesSubject.value;
  }

  getHighlightedCells(): Map<string, CellChange> {
    return this.highlightedCellsSubject.value;
  }

  isCellHighlighted(table: string, column: string, row_id: string | number): boolean {
    const cellKey = `${table}_${column}_${row_id}`;
    return this.highlightedCellsSubject.value.has(cellKey);
  }

  // Database info getters
  getDatabaseInfo(): DatabaseInfo | null {
    return this.databaseInfoSubject.value;
  }

  async getTables(): Promise<any[]> {
    const dbInfo = this.databaseInfoSubject.value;
    return dbInfo ? dbInfo.tables : [];
  }

  async getTableData(tableName: string): Promise<any> {
    return new Promise((resolve, reject) => {
      const sqlQuery = `SELECT * FROM ${tableName}`;
      this.executeSQL(sqlQuery).subscribe({
        next: (result: SQLResult) => {
          if (result.success) {
            resolve({
              data: result.result,
              columns: result.columns,
              total_rows: result.row_count,
              filtered_rows: result.row_count
            });
          } else {
            reject(new Error(result.error || 'Failed to load table data'));
          }
        },
        error: (error) => {
          reject(error);
        }
      });
    });
  }

  getTableCount(): number {
    const dbInfo = this.databaseInfoSubject.value;
    return dbInfo ? dbInfo.total_tables : 0;
  }

  getDatabasePath(): string {
    const dbInfo = this.databaseInfoSubject.value;
    return dbInfo ? dbInfo.database_path : '';
  }

  // Loading state
  setLoading(loading: boolean): void {
    this.isLoadingSubject.next(loading);
  }
} 