import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ExecutionService, ExecutionResult, OutputFile } from '../../services/execution.service';
import { QueryFileOrganizerService } from '../../services/query-file-organizer.service';
import { timeout, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

interface UploadedFile {
  id: string;
  name: string;
  type: string;
  size: number;
  uploadedAt: Date;
  isExpanded: boolean;
  path?: string;
}

@Component({
  selector: 'app-uploaded-files',
  templateUrl: './uploaded-files.component.html',
  styleUrls: ['./uploaded-files.component.css']
})
export class UploadedFilesComponent implements OnInit {
  @Output() viewFileRequest = new EventEmitter<{filePath: string, fileName: string}>();
  
  uploadedFiles: UploadedFile[] = [];
  isLoading = false;

  // Confirmation dialog properties
  showDeleteDialog = false;
  fileToDelete: UploadedFile | null = null;

  constructor(
    private apiService: ApiService,
    private executionService: ExecutionService,
    private queryFileOrganizer: QueryFileOrganizerService
  ) {}

  ngOnInit(): void {
    this.loadUploadedFiles();
  }

  loadUploadedFiles(): void {
    this.isLoading = true;
    
    this.apiService.getFiles().subscribe({
      next: (response) => {
        console.log('Files response:', response);
        
        // Convert API response to UploadedFile objects
        this.uploadedFiles = response.uploaded_files.map((filePath: string, index: number) => {
          const fileName = filePath.split('/').pop() || filePath;
          const fileExtension = fileName.split('.').pop()?.toLowerCase() || '';
          
          return {
            id: index.toString(),
            name: fileName,
            type: this.getFileType(fileExtension),
            size: 0, // Size not available from API
            uploadedAt: new Date(),
            isExpanded: false,
            path: filePath
          };
        });
        
        this.isLoading = false;
      },
      error: (error) => {
        console.error('Error loading uploaded files:', error);
        this.uploadedFiles = [];
        this.isLoading = false;
      }
    });
  }

  getFileType(extension: string): string {
    switch (extension.toLowerCase()) {
      case 'zip': return 'zip';
      case 'py': return 'python';
      case 'r': return 'r';
      case 'csv': return 'csv';
      case 'xlsx': return 'xlsx';
      case 'db': return 'db';
      case 'sql': return 'sql';
      case 'html': return 'html';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return 'image';
      case 'txt': return 'txt';
      default: return 'file';
    }
  }

  toggleFile(file: UploadedFile): void {
    file.isExpanded = !file.isExpanded;
  }

  getFileIconClass(type: string): string {
    switch (type) {
      case 'zip': return 'icon-archive';
      case 'python': return 'icon-python';
      case 'py': return 'icon-python';
      case 'r': return 'icon-r';
      case 'csv': return 'icon-table';
      case 'xlsx': return 'icon-spreadsheet';
      case 'db': return 'icon-database';
      case 'sql': return 'icon-database';
      case 'html': return 'icon-globe';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return 'icon-image';
      case 'txt': return 'icon-file';
      default: return 'icon-file';
    }
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  viewFile(file: UploadedFile): void {
    if (file.path) {
      this.viewFileRequest.emit({
        filePath: file.path,
        fileName: file.name
      });
    }
  }

  confirmDeleteFile(file: UploadedFile): void {
    this.fileToDelete = file;
    this.showDeleteDialog = true;
  }

  onDeleteConfirm(): void {
    if (this.fileToDelete) {
      this.deleteFile(this.fileToDelete);
      this.fileToDelete = null;
    }
    this.showDeleteDialog = false;
  }

  onDeleteCancel(): void {
    this.fileToDelete = null;
    this.showDeleteDialog = false;
  }

  downloadFile(file: UploadedFile): void {
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

  deleteFile(file: UploadedFile): void {
    if (!file.path) {
      console.error('No file path available for deletion');
      return;
    }

    console.log('Deleting file:', file.path);
    
    this.apiService.deleteFile(file.path).subscribe({
      next: (response) => {
        console.log('File deleted successfully:', response);
        
        // Remove from local state
        this.uploadedFiles = this.uploadedFiles.filter(f => f.id !== file.id);
        
        // Refresh the file list to ensure consistency
        this.loadUploadedFiles();
      },
      error: (error) => {
        console.error('Error deleting file:', error);
        alert(`Error deleting file: ${error.error?.detail || error.message || 'Unknown error'}`);
      }
    });
  }

  getDeleteFileMessage(): string {
    if (this.fileToDelete) {
      return `Are you sure you want to delete '${this.fileToDelete.name}'? This action cannot be undone.`;
    }
    return '';
  }

  canRunFile(file: UploadedFile): boolean {
    return file.type === 'python' || file.type === 'py';
  }

  isRequirementsFile(file: UploadedFile): boolean {
    return file.name.toLowerCase() === 'requirements.txt';
  }

  runFile(file: UploadedFile): void {
    if (!this.canRunFile(file) || !file.path) {
      console.error('Cannot run this file type or file path is missing');
      return;
    }

    console.log('Running file:', file.name);
    
    // Set executing state
    this.executionService.setExecuting(true);
    
    this.apiService.runFile(file.name).pipe(
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
          isRunning: false
        };
        
        // Emit the result to the workbench
        this.executionService.emitExecutionResult(executionResult);
        
        // Set executing to false
        this.executionService.setExecuting(false);
        
        console.log('Execution completed with output files:', rawOutputFiles);
      },
      error: (error) => {
        console.error('Error running file:', error);
        
        const executionResult: ExecutionResult = {
          command: `python ${file.name}`,
          output: '',
          error: `Error: ${error.message || 'Failed to execute file'}`,
          returnCode: -1,
          outputFiles: [],
          timestamp: Date.now(),
          isRunning: false
        };
        
        this.executionService.emitExecutionResult(executionResult);
        this.executionService.setExecuting(false);
      }
    });
  }

  installRequirements(file: UploadedFile): void {
    if (!this.isRequirementsFile(file)) {
      console.error('Only requirements.txt files can be installed');
      return;
    }

    console.log('Installing requirements from:', file.name);
    
    // Set executing state
    this.executionService.setExecuting(true);
    
    this.apiService.installRequirements(file.name).subscribe({
      next: (response) => {
        console.log('Installation completed:', response);
        
        // Filter INFO messages from stderr and move them to stdout
        const processed = this.processExecutionResult(response);
        
        const executionResult: ExecutionResult = {
          command: `pip install -r ${file.name}`,
          output: processed.stdout,
          error: processed.stderr,
          returnCode: response.return_code,
          outputFiles: [],
          timestamp: Date.now(),
          isRunning: false
        };
        
        this.executionService.emitExecutionResult(executionResult);
        this.executionService.setExecuting(false);
      },
      error: (error) => {
        console.error('Installation error:', error);
        
        const executionResult: ExecutionResult = {
          command: `pip install -r ${file.name}`,
          output: '',
          error: `Error: ${error.message || 'Failed to install requirements'}`,
          returnCode: -1,
          outputFiles: [],
          timestamp: Date.now(),
          isRunning: false
        };
        
        this.executionService.emitExecutionResult(executionResult);
        this.executionService.setExecuting(false);
      }
    });
  }

  private processExecutionResult(result: any): { stdout: string, stderr: string } {
    const stderrLines = result.stderr ? result.stderr.split('\n') : [];
    const infoMessages: string[] = [];
    const errorMessages: string[] = [];

    // Separate INFO messages from actual errors
    for (const line of stderrLines) {
      if (line.trim().startsWith('INFO:')) {
        infoMessages.push(line);
      } else if (line.trim()) {
        errorMessages.push(line);
      }
    }

    // Combine original stdout with INFO messages
    let combinedStdout = result.stdout || '';
    if (infoMessages.length > 0) {
      combinedStdout += (combinedStdout ? '\n' : '') + infoMessages.join('\n');
    }

    // Only keep non-INFO messages in stderr
    const cleanedStderr = errorMessages.join('\n');

    return {
      stdout: combinedStdout,
      stderr: cleanedStderr
    };
  }
} 