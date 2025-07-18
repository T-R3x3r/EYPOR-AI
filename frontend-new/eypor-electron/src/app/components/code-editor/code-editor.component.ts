import { Component, Input, Output, EventEmitter, OnInit, OnDestroy, ViewChild, ElementRef } from '@angular/core';
import { ApiService, FileContentResponse } from '../../services/api.service';

interface OpenFile {
  id: string;
  filePath: string;
  fileName: string;
  content: string;
  isModified: boolean;
  isLoading: boolean;
  error: string;
  saveMessage: string;
  lineNumbers: number[];
}

@Component({
  selector: 'app-code-editor',
  templateUrl: './code-editor.component.html',
  styleUrls: ['./code-editor.component.css']
})
export class CodeEditorComponent implements OnInit, OnDestroy {
  @Input() filePath: string = '';
  @Input() fileName: string = '';
  @Output() closeEditor = new EventEmitter<void>();

  openFiles: OpenFile[] = [];
  activeTabId: string = '';
  isLoading = false;
  error: string = '';
  
  @ViewChild('lineNumbersContainer', { static: false }) lineNumbersContainer!: ElementRef;
  @ViewChild('codeTextarea', { static: false }) codeTextarea!: ElementRef;

  constructor(private apiService: ApiService) {}

  ngOnInit(): void {
    // If initial file is provided, open it
    if (this.filePath && this.fileName) {
      this.openFile(this.filePath, this.fileName);
    }
  }

  ngOnDestroy(): void {
    // Cleanup if needed
  }

  openFile(filePath: string, fileName: string): void {
    // Check if file is already open
    const existingFile = this.openFiles.find(f => f.filePath === filePath);
    if (existingFile) {
      this.activeTabId = existingFile.id;
      return;
    }

    // Create new file tab
    const newFile: OpenFile = {
      id: this.generateFileId(),
      filePath,
      fileName,
      content: '',
      isModified: false,
      isLoading: true,
      error: '',
      saveMessage: '',
      lineNumbers: []
    };

    this.openFiles.push(newFile);
    this.activeTabId = newFile.id;

    // Load file content
    this.loadFileContent(newFile);
  }

  private generateFileId(): string {
    return Date.now().toString() + Math.random().toString(36).substr(2, 9);
  }

  private loadFileContent(file: OpenFile): void {
    file.isLoading = true;
    file.error = '';

    this.apiService.getFileContent(file.filePath).subscribe({
      next: (response: FileContentResponse) => {
        file.content = response.content;
        this.generateLineNumbers(file);
        file.isLoading = false;
      },
      error: (err: any) => {
        file.error = 'Failed to load file content.';
        file.isLoading = false;
      }
    });
  }

  private generateLineNumbers(file: OpenFile): void {
    const lines = file.content.split('\n');
    file.lineNumbers = Array.from({ length: lines.length }, (_, i) => i + 1);
  }

  onCodeChange(event: any, file: OpenFile): void {
    file.content = event.target.value;
    file.isModified = true;
    file.saveMessage = '';
    this.generateLineNumbers(file);
  }

  saveFile(file: OpenFile): void {
    file.isLoading = true;
    file.saveMessage = '';
    
    this.apiService.updateFile(file.filePath, file.content).subscribe({
      next: (response: { message: string }) => {
        file.saveMessage = 'File saved successfully!';
        file.isModified = false;
        file.isLoading = false;
      },
      error: (err: any) => {
        file.saveMessage = 'Failed to save file.';
        file.isLoading = false;
      }
    });
  }

  closeTab(fileId: string): void {
    const fileIndex = this.openFiles.findIndex(f => f.id === fileId);
    if (fileIndex !== -1) {
      this.openFiles.splice(fileIndex, 1);
      
      // If we closed the active tab, switch to another tab
      if (this.activeTabId === fileId) {
        if (this.openFiles.length > 0) {
          this.activeTabId = this.openFiles[0].id;
        } else {
          // No more tabs, close the editor
          this.closeCodeEditor();
        }
      }
    }
  }

  switchTab(fileId: string): void {
    this.activeTabId = fileId;
  }

  closeCodeEditor(): void {
    this.closeEditor.emit();
  }

  getActiveFile(): OpenFile | undefined {
    return this.openFiles.find(f => f.id === this.activeTabId);
  }

  getFileExtension(fileName: string): string {
    return fileName.split('.').pop()?.toLowerCase() || '';
  }

  isPythonFile(fileName: string): boolean {
    return this.getFileExtension(fileName) === 'py';
  }

  isRFile(fileName: string): boolean {
    return this.getFileExtension(fileName) === 'r';
  }

  // Method to be called from parent component to open new files
  openNewFile(filePath: string, fileName: string): void {
    this.openFile(filePath, fileName);
  }

  // Synchronize line numbers scroll with code scroll
  onCodeScroll(event: any): void {
    if (this.lineNumbersContainer) {
      this.lineNumbersContainer.nativeElement.scrollTop = event.target.scrollTop;
    }
  }

  // Synchronize code scroll with line numbers scroll
  onLineNumbersScroll(event: any): void {
    if (this.codeTextarea) {
      this.codeTextarea.nativeElement.scrollTop = event.target.scrollTop;
    }
  }
} 