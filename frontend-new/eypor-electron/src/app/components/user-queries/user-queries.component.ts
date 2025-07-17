import { Component, OnInit, Output, EventEmitter } from '@angular/core';
import { QueryFileOrganizerService, QueryFileGroup } from '../../services/query-file-organizer.service';

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
  fileToDelete: GeneratedFile | null = null;
  queryToDelete: UserQuery | null = null;

  constructor(private queryFileOrganizer: QueryFileOrganizerService) {}

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
    this.userQueries = organizedFiles.query_groups.map(group => ({
      id: group.queryId,
      query: group.query,
      timestamp: new Date(group.timestamp),
      isExpanded: false,
      status: 'completed' as const,
      generatedFiles: group.files.map((file, index) => ({
        id: `${group.queryId}_${index}`,
        name: file,
        type: this.getFileType(file),
        size: 0, // TODO: Get actual file size
        createdAt: new Date(group.timestamp),
        path: file
      }))
    }));
    
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
    // TODO: Implement download
    console.log('Downloading file:', file.name);
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
    // TODO: Implement delete
    console.log('Deleting file:', file.name);
    // Remove from the current query's generated files
    this.userQueries.forEach(query => {
      query.generatedFiles = query.generatedFiles.filter(f => f.id !== file.id);
    });
    
    // Remove queries that have no generated files
    this.userQueries = this.userQueries.filter(query => query.generatedFiles.length > 0);
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
    // TODO: Implement delete
    console.log('Deleting query:', query.query);
    this.userQueries = this.userQueries.filter(q => q.id !== query.id);
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

  runFile(file: GeneratedFile): void {
    // TODO: Implement run
    console.log('Running file:', file.name);
  }
} 