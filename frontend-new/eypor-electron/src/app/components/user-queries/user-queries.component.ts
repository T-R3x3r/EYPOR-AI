import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { QueryFileOrganizerService, QueryFileGroup } from '../../services/query-file-organizer.service';
import { ApiService } from '../../services/api.service';
import { ScenarioAwareExecutionService, ExecutionResult, OutputFile } from '../../services/scenario-aware-execution.service';
import { timeout, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

interface GeneratedFile {
  id: string;
  name: string;
  type: 'html' | 'python' | 'py' | 'csv' | 'png' | 'jpg' | 'jpeg' | 'gif' | 'svg' | 'other';
  size: number;
  createdAt: Date;
  path?: string;
}

interface UserQuery {
  id: string;
  query: string;
  timestamp: Date;
  isExpanded: boolean;
  generatedFiles: GeneratedFile[];
  status: 'completed' | 'running' | 'error';
}

@Component({
  selector: 'app-user-queries',
  templateUrl: './user-queries.component.html',
  styleUrls: ['./user-queries.component.css']
})
export class UserQueriesComponent implements OnInit {
  @Output() viewFileRequest = new EventEmitter<{filePath: string, fileName: string}>();
  
  userQueries: UserQuery[] = [];
  isLoading = false;

  // Confirmation dialog properties
  showDeleteFileDialog = false;
  showDeleteQueryDialog = false;
  showClearAllDataDialog = false;
  fileToDelete: GeneratedFile | null = null;
  queryToDelete: UserQuery | null = null;

  constructor(
    private queryFileOrganizer: QueryFileOrganizerService,
    private apiService: ApiService,
    private executionService: ScenarioAwareExecutionService
  ) {}

  ngOnInit(): void {
    this.loadUserQueries();
    
    // Refresh user queries when files are created
    // This will be triggered by the workbench component
    setInterval(() => {
      this.loadUserQueries();
    }, 5000); // Refresh every 5 seconds
  }

  loadUserQueries(): void {
    this.isLoading = true;
    
    // Get organized files from the service
    const organizedFiles = this.queryFileOrganizer.getOrganizedFiles();
    
    // Preserve expanded state of existing queries
    const existingQueries = new Map(this.userQueries.map(q => [q.id, q]));
    
    this.userQueries = organizedFiles.query_groups.map(group => {
      const existing = existingQueries.get(group.queryId);
      return {
      id: group.queryId,
      query: group.query,
      timestamp: new Date(group.timestamp),
        isExpanded: existing?.isExpanded || false,
      status: 'completed' as const,
        generatedFiles: group.files
          .filter((file): file is string => typeof file === 'string')
          .map((file, index) => ({
        id: `${group.queryId}_${index}`,
        name: file,
        type: this.getFileType(file),
        size: 0, // TODO: Get actual file size
        createdAt: new Date(group.timestamp),
        path: file
      }))
      };
    });
    
    this.isLoading = false;
  }

  toggleQuery(query: UserQuery): void {
    query.isExpanded = !query.isExpanded;
  }

  getStatusIconClass(status: string): string {
    switch (status) {
      case 'completed': return 'icon-check';
      case 'running': return 'icon-spinner';
      case 'error': return 'icon-x';
      default: return 'icon-clock';
    }
  }

  getFileIconClass(type: string): string {
    switch (type) {
      case 'html': return 'icon-globe';
      case 'python': return 'icon-python';
      case 'py': return 'icon-python';
      case 'r': return 'icon-r';
      case 'csv': return 'icon-table';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return 'icon-image';
      default: return 'icon-file';
    }
  }

  private getFileType(filename: string): 'html' | 'python' | 'py' | 'csv' | 'png' | 'jpg' | 'jpeg' | 'gif' | 'svg' | 'other' {
    if (typeof filename !== 'string') {
      return 'other';
    }
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    switch (extension) {
      case 'html': return 'html';
      case 'py': return 'python';
      case 'csv': return 'csv';
      case 'png': return 'png';
      case 'jpg': return 'jpg';
      case 'jpeg': return 'jpeg';
      case 'gif': return 'gif';
      case 'svg': return 'svg';
      default: return 'other';
    }
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  viewFile(file: GeneratedFile): void {
    if (file.path) {
      this.viewFileRequest.emit({
        filePath: file.path,
        fileName: file.name
      });
    }
  }

  downloadFile(file: GeneratedFile): void {
    if (!file.path) {
      console.error('No file path available for download');
      return;
    }
    
    console.log('Downloading file:', file.path);
    const downloadUrl = `http://localhost:8001/files/${encodeURIComponent(file.path)}/download`;
    
    // Create a temporary link and click it to trigger download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = file.name;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  confirmDeleteFile(file: GeneratedFile): void {
    this.fileToDelete = file;
    this.showDeleteFileDialog = true;
  }

  onDeleteFileConfirm(): void {
    if (this.fileToDelete) {
      this.deleteFile(this.fileToDelete);
      this.fileToDelete = null;
    }
    this.showDeleteFileDialog = false;
  }

  onDeleteFileCancel(): void {
    this.fileToDelete = null;
    this.showDeleteFileDialog = false;
  }

  deleteFile(file: GeneratedFile): void {
    if (!file.path) {
      console.error('No file path available for deletion');
      return;
    }

    console.log('Deleting file:', file.path);
    
    this.apiService.deleteFile(file.path).subscribe({
      next: (response) => {
        console.log('File deleted successfully:', response);
        
        // Remove the file from the query group in the organizer service
        const queryGroup = this.queryFileOrganizer.findQueryGroupByFile(file.name);
        if (queryGroup) {
          this.queryFileOrganizer.removeFilesFromQueryGroup(queryGroup.queryId, [file.name]);
        }
        
    // Remove from the current query's generated files
    this.userQueries.forEach(query => {
      query.generatedFiles = query.generatedFiles.filter(f => f.id !== file.id);
    });
    
    // Remove queries that have no generated files
    this.userQueries = this.userQueries.filter(query => query.generatedFiles.length > 0);
      },
      error: (error) => {
        console.error('Error deleting file:', error);
        alert(`Error deleting file: ${error.error?.detail || error.message || 'Unknown error'}`);
      }
    });
  }

  confirmDeleteQuery(query: UserQuery): void {
    this.queryToDelete = query;
    this.showDeleteQueryDialog = true;
  }

  onDeleteQueryConfirm(): void {
    if (this.queryToDelete) {
      this.deleteQuery(this.queryToDelete);
      this.queryToDelete = null;
    }
    this.showDeleteQueryDialog = false;
  }

  onDeleteQueryCancel(): void {
    this.queryToDelete = null;
    this.showDeleteQueryDialog = false;
  }

  deleteQuery(query: UserQuery): void {
    console.log('Deleting query:', query.query);
    
    // Delete all generated files for this query
    const deletePromises = query.generatedFiles.map(file => {
      if (file.path) {
        return this.apiService.deleteFile(file.path).toPromise();
      }
      return Promise.resolve();
    });
    
    // Wait for all files to be deleted, then remove the query group
    Promise.all(deletePromises).then(() => {
      // Remove the query group from the organizer service
      this.queryFileOrganizer.removeQueryGroup(query.id);
      
      // Remove from local state
    this.userQueries = this.userQueries.filter(q => q.id !== query.id);
      
      console.log('Query and all its files deleted successfully');
    }).catch(error => {
      console.error('Error deleting query files:', error);
      alert(`Error deleting query files: ${error.message || 'Unknown error'}`);
    });
  }

  getDeleteFileMessage(): string {
    if (this.fileToDelete) {
      return `Are you sure you want to delete '${this.fileToDelete.name}'? This action cannot be undone.`;
    }
    return '';
  }

  getDeleteQueryMessage(): string {
    if (this.queryToDelete) {
      return `Are you sure you want to delete the query '${this.queryToDelete.query}' and all its generated files? This action cannot be undone.`;
    }
    return '';
  }

  canRunFile(file: GeneratedFile): boolean {
    return file.type === 'python' || file.type === 'py';
  }

  private processExecutionResult(result: any): { stdout: string, stderr: string } {
    let stdout = result.stdout || '';
    let stderr = result.stderr || '';

    // Filter INFO messages from stderr and move them to stdout
    const infoLines: string[] = [];
    const errorLines: string[] = [];

    if (stderr) {
      stderr.split('\n').forEach((line: string) => {
        if (line.includes('INFO:') || line.includes('INFO ')) {
          infoLines.push(line);
        } else {
          errorLines.push(line);
        }
      });
    }

    // Combine INFO messages with stdout
    if (infoLines.length > 0) {
      stdout = infoLines.join('\n') + (stdout ? '\n' + stdout : '');
    }

    // Keep only actual errors in stderr
    stderr = errorLines.join('\n');

    return { stdout, stderr };
  }

  runFile(file: GeneratedFile): void {
    if (!this.canRunFile(file) || !file.path) {
      console.error('Cannot run this file type or file path is missing');
      return;
    }

    console.log('Running file:', file.path);
    console.log('File name:', file.name);
    console.log('File type:', file.type);
    console.log('File path:', file.path);
    
    // Set executing state
    this.executionService.setExecuting(true);
    
    this.apiService.runFile(file.path).pipe(
      timeout(150000), // 150 second timeout (increased to match backend 120s + buffer)
      catchError(error => {
        console.error('File execution timeout or error:', error);
        return of({
          stdout: '',
          stderr: `Execution timeout or error: ${error.message || 'Unknown error'}`,
          return_code: -1,
          output_files: []
        });
      })
    ).subscribe({
      next: (response) => {
        console.log('File execution result:', response);
        console.log('Response type:', typeof response);
        console.log('Response keys:', Object.keys(response || {}));
        console.log('Output files:', response.output_files);
        
        // Filter INFO messages from stderr and move them to stdout
        const processed = this.processExecutionResult(response);
        
        // Use output_files directly like the old frontend
        const rawOutputFiles = response.output_files || [];
        
        // Convert string filenames to OutputFile objects
        const outputFiles: OutputFile[] = rawOutputFiles.map((filename: any) => {
          if (typeof filename === 'string') {
            return {
              filename,
              path: filename,
              url: `/files/${encodeURIComponent(filename)}/download`,
              type: this.getFileType(filename.split('.').pop() || ''),
              timestamp: Date.now()
            };
          } else if (filename && typeof filename === 'object' && filename.filename) {
            return {
              filename: filename.filename,
              path: filename.filename,
              url: `/files/${encodeURIComponent(filename.filename)}/download`,
              type: this.getFileType(filename.filename.split('.').pop() || ''),
              timestamp: Date.now()
            };
          }
          return null;
        }).filter((file: OutputFile | null) => file !== null) as OutputFile[];
        
        // Create execution result - use output_files directly
        const executionResult: ExecutionResult = {
          command: `python ${file.name}`,
          output: processed.stdout,
          error: processed.stderr,
          returnCode: response.return_code,
          outputFiles: outputFiles,
          timestamp: Date.now(),
          isRunning: false,
          scenarioId: 0 // Will be set by the service
        };
        
        // Emit the result to the workbench
        this.executionService.emitExecutionResult(executionResult);
        
        // Set executing to false
        this.executionService.setExecuting(false);
        
        // Add new output files to the query group (like the old frontend)
        if (rawOutputFiles.length > 0) {
          // Find the query group this file belongs to using the file path
          const queryGroup = this.queryFileOrganizer.findQueryGroupByFile(file.name);
          if (queryGroup) {
            // Add the new output files to the existing query group
            const newFileNames = rawOutputFiles.map((filename: any) => {
              if (typeof filename === 'string') {
                return filename;
              } else if (filename && typeof filename === 'object' && filename.filename) {
                return filename.filename;
              }
              return null;
            }).filter((name: string | null) => name !== null);
            
            const success = this.queryFileOrganizer.addFilesToExistingQueryGroup(
              queryGroup.queryId,
              newFileNames
            );
            
            if (success) {
              console.log('Successfully added files to existing query group:', newFileNames);
              // Refresh the user queries to show the new files
              this.loadUserQueries();
            } else {
              console.log('Failed to add files to existing query group');
            }
          }
        }
        
        console.log('Execution completed with output files:', rawOutputFiles);
        console.log('Execution result emitted successfully');
      },
      error: (error) => {
        console.error('Error running file:', error);
        console.error('Error type:', typeof error);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
        
        const executionResult: ExecutionResult = {
          command: `python ${file.name}`,
          output: '',
          error: `Error: ${error.message || 'Failed to execute file'}`,
          returnCode: -1,
          outputFiles: [],
          timestamp: Date.now(),
          isRunning: false,
          scenarioId: 0 // Will be set by the service
        };
        
        this.executionService.emitExecutionResult(executionResult);
        this.executionService.setExecuting(false);
        console.log('Error execution result emitted');
      }
    });
  }

  /**
   * Show confirmation dialog for clearing all data
   */
  confirmClearAllData(): void {
    this.showClearAllDataDialog = true;
  }

  /**
   * Handle confirmation of clearing all data
   */
  onClearAllDataConfirm(): void {
    this.queryFileOrganizer.clearAllData();
    this.userQueries = [];
    this.showClearAllDataDialog = false;
    console.log('All query data cleared');
  }

  /**
   * Handle cancellation of clearing all data
   */
  onClearAllDataCancel(): void {
    this.showClearAllDataDialog = false;
  }

  /**
   * Get the message for the clear all data dialog
   */
  getClearAllDataMessage(): string {
    return 'Are you sure you want to clear all stored query data? This will remove all query history and cannot be undone.';
  }
} 