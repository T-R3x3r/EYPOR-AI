import { Component, Output, EventEmitter } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ScenarioService } from '../../services/scenario.service';

@Component({
  selector: 'app-file-upload',
  templateUrl: './file-upload.component.html',
  styleUrls: ['./file-upload.component.css']
})
export class FileUploadComponent {
  selectedFile: File | null = null;
  isUploading = false;
  uploadMessage = '';
  uploadSuccess = false;
  isDragOver = false;
  hasUploadedFiles = false;

  @Output() filesUploaded = new EventEmitter<void>();

  constructor(
    private apiService: ApiService,
    private scenarioService: ScenarioService
  ) { }

  onFileSelected(event: any) {
    const file = event.target.files[0];
    this.handleFile(file);
  }

  onDragOver(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = true;
  }

  onDragLeave(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;
  }

  onDrop(event: DragEvent) {
    event.preventDefault();
    event.stopPropagation();
    this.isDragOver = false;

    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.handleFile(files[0]);
    }
  }

  private handleFile(file: File) {
    if (file && file.name.endsWith('.zip')) {
      this.selectedFile = file;
      this.uploadMessage = '';
      this.uploadSuccess = false;
    } else {
      this.uploadMessage = 'Please select a valid zip file';
      this.uploadSuccess = false;
      this.selectedFile = null;
    }
  }

  uploadFile() {
    if (!this.selectedFile) {
      this.uploadMessage = 'Please select a file first';
      this.uploadSuccess = false;
      return;
    }

    this.isUploading = true;
    this.uploadMessage = 'Uploading...';

    this.apiService.uploadFile(this.selectedFile).subscribe({
      next: (response) => {
        this.uploadMessage = response.message;
        this.uploadSuccess = true;
        this.isUploading = false;
        this.hasUploadedFiles = true;
        
        // If a scenario was created during upload, add it to the scenarios list
        if (response.scenario) {
          this.scenarioService.addScenarioFromUpload(response.scenario);
        } else {
          // Fallback: refresh scenarios list after a short delay
          setTimeout(() => {
            this.scenarioService.refreshScenarios();
          }, 500);
        }
        
        // Emit event to refresh file tree
        this.filesUploaded.emit();
      },
      error: (error) => {
        this.uploadMessage = `Upload failed: ${error.error?.detail || error.message}`;
        this.uploadSuccess = false;
        this.isUploading = false;
      }
    });
  }

  clearSelection() {
    this.selectedFile = null;
    this.uploadMessage = '';
    this.uploadSuccess = false;
  }

  clearFiles() {
    this.apiService.clearFiles().subscribe({
      next: (response) => {
        this.uploadMessage = response.message;
        this.uploadSuccess = true;
        this.selectedFile = null;
        this.hasUploadedFiles = false;
        // Emit event to refresh file tree
        this.filesUploaded.emit();
      },
      error: (error) => {
        this.uploadMessage = `Failed to clear files: ${error.error?.detail || error.message}`;
        this.uploadSuccess = false;
      }
    });
  }

  formatFileSize(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }
} 