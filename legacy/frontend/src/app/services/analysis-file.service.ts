import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable } from 'rxjs';
import { ApiService } from './api.service';
import { 
  AnalysisFile, 
  AnalysisFileCreateRequest, 
  AnalysisFileUpdateRequest,
  AnalysisFileResponse
} from '../models/scenario.model';

@Injectable({
  providedIn: 'root'
})
export class AnalysisFileService {
  private analysisFilesSubject = new BehaviorSubject<AnalysisFile[]>([]);

  constructor(private apiService: ApiService) {
    this.loadAnalysisFiles();
  }

  // Observables
  get analysisFiles$(): Observable<AnalysisFile[]> {
    return this.analysisFilesSubject.asObservable();
  }

  // Current values
  get analysisFiles(): AnalysisFile[] {
    return this.analysisFilesSubject.value;
  }

  // Analysis File Management Methods
  getAnalysisFiles(): Observable<AnalysisFile[]> {
    return new Observable(observer => {
      this.apiService.getAnalysisFiles().subscribe({
        next: (files: AnalysisFile[]) => {
          this.analysisFilesSubject.next(files);
          observer.next(files);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  createAnalysisFile(request: AnalysisFileCreateRequest): Observable<AnalysisFile> {
    return new Observable(observer => {
      this.apiService.createAnalysisFile(request).subscribe({
        next: (file: AnalysisFile) => {
          // Add to analysis files list
          const currentList = this.analysisFilesSubject.value;
          this.analysisFilesSubject.next([...currentList, file]);
          
          observer.next(file);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  updateAnalysisFile(fileId: number, request: AnalysisFileUpdateRequest): Observable<AnalysisFile> {
    return new Observable(observer => {
      this.apiService.updateAnalysisFile(fileId, request).subscribe({
        next: (updatedFile: AnalysisFile) => {
          // Update in analysis files list
          const currentList = this.analysisFilesSubject.value;
          const updatedList = currentList.map(f => 
            f.id === fileId ? updatedFile : f
          );
          this.analysisFilesSubject.next(updatedList);
          
          observer.next(updatedFile);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  deleteAnalysisFile(fileId: number): Observable<boolean> {
    return new Observable(observer => {
      this.apiService.deleteAnalysisFile(fileId).subscribe({
        next: (response: any) => {
          // Remove from analysis files list
          const currentList = this.analysisFilesSubject.value;
          const updatedList = currentList.filter(f => f.id !== fileId);
          this.analysisFilesSubject.next(updatedList);
          
          observer.next(true);
          observer.complete();
        },
        error: (error: any) => {
          observer.error(error);
        }
      });
    });
  }

  // Helper Methods
  private loadAnalysisFiles(): void {
    this.getAnalysisFiles().subscribe();
  }

  // Utility Methods
  getAnalysisFileById(fileId: number): AnalysisFile | undefined {
    return this.analysisFiles.find(f => f.id === fileId);
  }

  getAnalysisFilesByType(fileType: string): AnalysisFile[] {
    return this.analysisFiles.filter(f => f.file_type === fileType);
  }

  getGlobalAnalysisFiles(): AnalysisFile[] {
    return this.analysisFiles.filter(f => f.is_global);
  }

  getScenarioAnalysisFiles(scenarioId: number): AnalysisFile[] {
    return this.analysisFiles.filter(f => f.created_by_scenario_id === scenarioId);
  }

  refreshAnalysisFiles(): void {
    this.loadAnalysisFiles();
  }

  // SQL Query specific methods
  getSQLQueries(): AnalysisFile[] {
    return this.getAnalysisFilesByType('sql_query');
  }

  createSQLQuery(filename: string, content: string, isGlobal: boolean = true): Observable<AnalysisFile> {
    const request: AnalysisFileCreateRequest = {
      filename,
      file_type: 'sql_query',
      content,
      is_global: isGlobal
    };
    return this.createAnalysisFile(request);
  }

  // Visualization template specific methods
  getVisualizationTemplates(): AnalysisFile[] {
    return this.getAnalysisFilesByType('visualization_template');
  }

  createVisualizationTemplate(filename: string, content: string, isGlobal: boolean = true): Observable<AnalysisFile> {
    const request: AnalysisFileCreateRequest = {
      filename,
      file_type: 'visualization_template',
      content,
      is_global: isGlobal
    };
    return this.createAnalysisFile(request);
  }
} 