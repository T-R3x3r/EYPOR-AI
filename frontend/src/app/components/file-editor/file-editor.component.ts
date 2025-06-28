import { Component, OnInit } from '@angular/core';
import { ApiService } from '../../services/api.service';

@Component({
  selector: 'app-file-editor',
  templateUrl: './file-editor.component.html',
  styleUrls: ['./file-editor.component.css']
})
export class FileEditorComponent implements OnInit {
  files: string[] = [];
  selectedFile = '';
  fileContent = '';
  originalContent = '';
  isEditing = false;
  loading = false;
  fileStats = {
    lines: 0,
    characters: 0,
    type: ''
  };

  constructor(private apiService: ApiService) { }

  ngOnInit() {
    this.loadFiles();
  }

  loadFiles() {
    this.loading = true;
    this.apiService.getFiles().subscribe({
      next: (response) => {
        this.files = response.files;
        this.loading = false;
      },
      error: (error) => {
        console.error('Failed to load files:', error);
        this.loading = false;
      }
    });
  }

  onFileSelect(filename: string) {
    if (filename === 'Select a file...') {
      this.selectedFile = '';
      this.fileContent = '';
      this.originalContent = '';
      this.isEditing = false;
      return;
    }

    this.selectedFile = filename;
    this.loading = true;

    this.apiService.getFileContent(filename).subscribe({
      next: (response) => {
        this.fileContent = response.content;
        this.originalContent = response.content;
        this.calculateStats();
        this.isEditing = false;
        this.loading = false;
      },
      error: (error) => {
        console.error('Failed to load file content:', error);
        this.loading = false;
      }
    });
  }

  saveFile() {
    if (!this.selectedFile || this.fileContent === this.originalContent) {
      return;
    }

    this.loading = true;
    this.apiService.updateFile(this.selectedFile, this.fileContent).subscribe({
      next: (response) => {
        this.originalContent = this.fileContent;
        this.isEditing = false;
        this.loading = false;
        console.log('File saved:', response.message);
      },
      error: (error) => {
        console.error('Failed to save file:', error);
        this.loading = false;
      }
    });
  }

  revertFile() {
    this.fileContent = this.originalContent;
    this.isEditing = false;
    this.calculateStats();
  }

  onContentChange() {
    this.isEditing = this.fileContent !== this.originalContent;
    this.calculateStats();
  }

  calculateStats() {
    if (!this.fileContent) {
      this.fileStats = { lines: 0, characters: 0, type: '' };
      return;
    }

    const lines = this.fileContent.split('\n').length;
    const characters = this.fileContent.length;
    const extension = this.selectedFile.split('.').pop() || '';
    
    this.fileStats = {
      lines,
      characters,
      type: extension
    };
  }

  isBinaryFile(): boolean {
    return this.fileContent.includes('[Binary file or encoding error:');
  }
} 