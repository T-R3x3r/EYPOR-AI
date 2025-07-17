import { Component } from '@angular/core';
import { Router } from '@angular/router';
import { ApiService } from '../../services/api.service';
import { ThemeService } from '../../services/theme.service';

@Component({
  selector: 'app-file-selection',
  templateUrl: './file-selection.component.html',
  styleUrls: ['./file-selection.component.css']
})
export class FileSelectionComponent {
  selectedFiles: File[] = [];
  isUploading = false;
  uploadMessage = '';
  uploadSuccess = false;
  isDragOver = false;
  savedProjects: any[] = [];

  constructor(
    private router: Router,
    private apiService: ApiService,
    public themeService: ThemeService
  ) { }

  onFileSelected(event: any) {
    const files = Array.from(event.target.files) as File[];
    this.handleFiles(files);
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

    const files = Array.from(event.dataTransfer?.files || []);
    this.handleFiles(files);
  }

  private handleFiles(files: File[]) {
    const zipFiles = files.filter(file => file.name.endsWith('.zip'));
    
    if (zipFiles.length === 0) {
      this.uploadMessage = 'Please select valid ZIP files only';
      this.uploadSuccess = false;
      return;
    }

    this.selectedFiles = zipFiles;
    this.uploadMessage = '';
    this.uploadSuccess = false;
  }

  launchWorkbench() {
    if (this.selectedFiles.length === 0) {
      this.uploadMessage = 'Please select files first';
      this.uploadSuccess = false;
      return;
    }

    this.isUploading = true;
    this.uploadMessage = 'Uploading files...';

    // Upload the first file (backend expects one file at a time)
    const fileToUpload = this.selectedFiles[0];
    
    this.apiService.uploadFile(fileToUpload).subscribe({
      next: (response) => {
        this.uploadMessage = response.message;
        this.uploadSuccess = true;
        this.isUploading = false;
        
        // Navigate to workbench after successful upload
        setTimeout(() => {
          this.router.navigate(['/workbench']);
        }, 1000);
      },
      error: (error) => {
        this.uploadMessage = `Upload failed: ${error.error?.detail || error.message}`;
        this.uploadSuccess = false;
        this.isUploading = false;
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

  deleteProject(project: any) {
    // Remove project from the list
    this.savedProjects = this.savedProjects.filter(p => p !== project);
  }
} 