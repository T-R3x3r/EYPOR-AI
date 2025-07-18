import { Injectable } from '@angular/core';
import { BehaviorSubject, Observable, Subject, takeUntil } from 'rxjs';
import { ApiService } from './api.service';
import { ScenarioService } from './scenario.service';
import { Scenario } from '../models/scenario.model';

export interface ScenarioFile {
  filename: string;
  content: string;
  fileType: string;
  scenarioId: number;
  isGlobal: boolean;
  createdAt: Date;
  modifiedAt: Date;
}

export interface FileCache {
  [scenarioId: number]: {
    files: ScenarioFile[];
    lastLoaded: Date;
    isLoaded: boolean;
  };
}

@Injectable({
  providedIn: 'root'
})
export class ScenarioAwareFileService {
  private currentScenarioSubject = new BehaviorSubject<Scenario | null>(null);
  private scenarioFilesSubject = new BehaviorSubject<ScenarioFile[]>([]);
  private fileCache: FileCache = {};
  private isLoadingSubject = new BehaviorSubject<boolean>(false);
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

  get scenarioFiles$(): Observable<ScenarioFile[]> {
    return this.scenarioFilesSubject.asObservable();
  }

  get isLoading$(): Observable<boolean> {
    return this.isLoadingSubject.asObservable();
  }

  // Current values
  get currentScenario(): Scenario | null {
    return this.currentScenarioSubject.value;
  }

  get scenarioFiles(): ScenarioFile[] {
    return this.scenarioFilesSubject.value;
  }

  // Initialize scenario subscription
  private initializeScenarioSubscription(): void {
    this.scenarioService.currentScenario$
      .pipe(takeUntil(this.destroy$))
      .subscribe(scenario => {
        this.currentScenarioSubject.next(scenario);
        if (scenario) {
          this.loadScenarioFiles(scenario.id);
        } else {
          this.scenarioFilesSubject.next([]);
        }
      });
  }

  // Load files for a specific scenario
  loadScenarioFiles(scenarioId: number): void {
    // Check if files are already cached
    if (this.fileCache[scenarioId]?.isLoaded) {
      this.scenarioFilesSubject.next(this.fileCache[scenarioId].files);
      return;
    }

    this.isLoadingSubject.next(true);

    // Load files from API
    this.apiService.getFiles().subscribe({
      next: (response) => {
        const files: ScenarioFile[] = [];
        
        // Process uploaded files
        if (response.uploaded_files) {
          response.uploaded_files.forEach(filename => {
            files.push({
              filename,
              content: response.file_contents[filename] || '',
              fileType: this.getFileType(filename),
              scenarioId,
              isGlobal: false,
              createdAt: new Date(),
              modifiedAt: new Date()
            });
          });
        }

        // Process AI created files
        if (response.ai_created_files) {
          response.ai_created_files.forEach(filename => {
            files.push({
              filename,
              content: response.file_contents[filename] || '',
              fileType: this.getFileType(filename),
              scenarioId,
              isGlobal: false,
              createdAt: new Date(),
              modifiedAt: new Date()
            });
          });
        }

        // Cache the files
        this.fileCache[scenarioId] = {
          files,
          lastLoaded: new Date(),
          isLoaded: true
        };

        this.scenarioFilesSubject.next(files);
        this.isLoadingSubject.next(false);
      },
      error: (error) => {
        console.error('Error loading scenario files:', error);
        this.isLoadingSubject.next(false);
        this.scenarioFilesSubject.next([]);
      }
    });
  }

  // Get file content
  getFileContent(filename: string): Observable<any> {
    return this.apiService.getFileContent(filename);
  }

  // Update file content
  updateFileContent(filename: string, content: string): Observable<any> {
    return this.apiService.updateFile(filename, content);
  }

  // Delete file
  deleteFile(filename: string): Observable<any> {
    return this.apiService.deleteFile(filename);
  }

  // Run file
  runFile(filename: string): Observable<any> {
    return this.apiService.runFile(filename);
  }

  // Install requirements for file
  installRequirements(filename: string): Observable<any> {
    return this.apiService.installRequirements(filename);
  }

  // Performance optimization methods
  preloadScenarioFiles(scenarioId: number): void {
    if (!this.fileCache[scenarioId]?.isLoaded) {
      this.loadScenarioFiles(scenarioId);
    }
  }

  clearCache(): void {
    this.fileCache = {};
  }

  clearScenarioCache(scenarioId: number): void {
    delete this.fileCache[scenarioId];
  }

  // Get cache statistics
  getCacheStats(): { totalScenarios: number; cachedScenarios: number; memoryUsage: number } {
    const totalScenarios = Object.keys(this.fileCache).length;
    const cachedScenarios = Object.values(this.fileCache).filter(cache => cache.isLoaded).length;
    const memoryUsage = JSON.stringify(this.fileCache).length;

    return {
      totalScenarios,
      cachedScenarios,
      memoryUsage
    };
  }

  // Utility methods
  private getFileType(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase();
    
    switch (extension) {
      case 'py':
        return 'python';
      case 'r':
        return 'r';
      case 'sql':
        return 'sql';
      case 'html':
        return 'html';
      case 'css':
        return 'css';
      case 'js':
        return 'javascript';
      case 'json':
        return 'json';
      case 'csv':
        return 'csv';
      case 'xlsx':
      case 'xls':
        return 'excel';
      case 'txt':
        return 'text';
      default:
        return 'unknown';
    }
  }

  // Get files by type
  getFilesByType(fileType: string): ScenarioFile[] {
    return this.scenarioFiles.filter(file => file.fileType === fileType);
  }

  // Get files by scenario
  getFilesByScenario(scenarioId: number): ScenarioFile[] {
    return this.fileCache[scenarioId]?.files || [];
  }

  // Check if scenario has files
  hasScenarioFiles(scenarioId: number): boolean {
    return this.fileCache[scenarioId]?.isLoaded && this.fileCache[scenarioId].files.length > 0;
  }

  // Get file by name
  getFileByName(filename: string): ScenarioFile | undefined {
    return this.scenarioFiles.find(file => file.filename === filename);
  }

  // Refresh current scenario files
  refreshCurrentScenarioFiles(): void {
    if (this.currentScenario) {
      this.clearScenarioCache(this.currentScenario.id);
      this.loadScenarioFiles(this.currentScenario.id);
    }
  }

  // Cleanup
  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }
} 