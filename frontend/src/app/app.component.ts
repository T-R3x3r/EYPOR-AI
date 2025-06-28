import { Component, ViewChild, ElementRef, HostListener } from '@angular/core';
import { FileTreeComponent } from './components/file-tree/file-tree.component';
import { ThemeService } from './services/theme.service';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent {
  title = 'EY Project';
  showFileEditor = false;
  isResizing = false;
  currentResizeHandle = '';
  activeTab = 'chat'; // Default to chat tab
  showSettings = false; // Settings menu visibility

  @ViewChild('fileTree') fileTree!: FileTreeComponent;
  @ViewChild('sidebar') sidebar!: ElementRef;
  @ViewChild('executionWindow') executionWindow!: ElementRef;

  constructor(public themeService: ThemeService) {}

  @HostListener('document:mousemove', ['$event'])
  onMouseMove(event: MouseEvent) {
    if (this.isResizing) {
      this.resizeSection(event.clientX);
    }
  }

  @HostListener('document:mouseup')
  onMouseUp() {
    this.isResizing = false;
    this.currentResizeHandle = '';
  }

  @HostListener('document:click', ['$event'])
  onDocumentClick(event: Event) {
    // Close settings menu when clicking outside
    const target = event.target as HTMLElement;
    if (!target.closest('.settings-menu') && !target.closest('.settings-btn')) {
      this.showSettings = false;
    }
  }

  toggleSettings() {
    this.showSettings = !this.showSettings;
  }

  toggleDarkMode() {
    this.themeService.toggleDarkMode();
  }

  toggleFileEditor() {
    this.showFileEditor = !this.showFileEditor;
  }

  onFilesUploaded() {
    // Refresh the file tree when files are uploaded
    if (this.fileTree) {
      this.fileTree.loadFiles();
    }
  }

  refreshFileTree() {
    // Refresh the file tree when new files are created
    if (this.fileTree) {
      this.fileTree.refreshFiles();
    }
  }

  startResize(event: MouseEvent, handle: string) {
    event.preventDefault();
    this.isResizing = true;
    this.currentResizeHandle = handle;
  }

  resizeSection(mouseX: number) {
    const sidebar = this.sidebar.nativeElement;
    const executionWindow = this.executionWindow.nativeElement;
    const minWidth = 200;
    const maxWidth = window.innerWidth * 0.6;
    
    if (this.currentResizeHandle === 'sidebar') {
      let newWidth = mouseX;
      newWidth = Math.max(minWidth, Math.min(maxWidth, newWidth));
      sidebar.style.width = newWidth + 'px';
    } else if (this.currentResizeHandle === 'execution') {
      const sidebarWidth = sidebar.offsetWidth;
      const availableWidth = window.innerWidth - sidebarWidth;
      const executionWidth = mouseX - sidebarWidth;
      const minExecutionWidth = 300;
      const maxExecutionWidth = availableWidth * 0.8;
      
      let newWidth = Math.max(minExecutionWidth, Math.min(maxExecutionWidth, executionWidth));
      executionWindow.style.width = newWidth + 'px';
    }
  }
} 