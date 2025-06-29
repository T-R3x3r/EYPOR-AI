import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked, HostListener } from '@angular/core';
import { ExecutionService, ExecutionResult } from '../../services/execution.service';
import { Subscription } from 'rxjs';

interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
  isVisible?: boolean;
  timestamp: number;
  error?: string;
}

interface LocalExecutionResult {
  command: string;
  output: string;
  error: string;
  outputFiles: OutputFile[];
  timestamp: number;
  isRunning: boolean;
  height?: number;
}

@Component({
  selector: 'app-output-display',
  templateUrl: './output-display.component.html',
  styleUrls: ['./output-display.component.css']
})
export class OutputDisplayComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('outputContainer') outputContainer!: ElementRef;
  
  executionResults: LocalExecutionResult[] = [];
  currentResult: LocalExecutionResult | null = null;
  maximizedImage: OutputFile | null = null;
  private subscription: Subscription = new Subscription();
  private urlCache = new Map<string, string>();
  private shouldScrollToBottom = false;
  private userHasScrolled = false;
  private lastScrollHeight = 0;
  private resizing: { index: number; startY: number; startHeight: number } | null = null;

  constructor(private executionService: ExecutionService) {}

  ngOnInit() {
    this.subscription.add(
      this.executionService.executionResult$.subscribe((result: ExecutionResult | null) => {
        if (result) {
          // Save current scroll position before updating
          if (this.outputContainer) {
            this.lastScrollHeight = this.outputContainer.nativeElement.scrollHeight;
          }
          this.handleExecutionResult(result);
          this.shouldScrollToBottom = !this.userHasScrolled;
        }
      })
    );

    this.subscription.add(
      this.executionService.isExecuting$.subscribe((isExecuting: boolean) => {
        if (isExecuting) {
          const newResult: LocalExecutionResult = {
            command: 'Executing...',
            output: '',
            error: '',
            outputFiles: [],
            timestamp: Date.now(),
            isRunning: true
          };
          this.currentResult = newResult;
          this.executionResults.push(newResult);
          this.shouldScrollToBottom = !this.userHasScrolled;
        }
      })
    );
  }

  ngAfterViewChecked() {
    if (this.shouldScrollToBottom && this.outputContainer) {
      const element = this.outputContainer.nativeElement;
      const newScrollHeight = element.scrollHeight;
      
      // Only scroll if content height has changed
      if (newScrollHeight !== this.lastScrollHeight) {
        element.scrollTop = element.scrollHeight;
        this.lastScrollHeight = newScrollHeight;
      }
      this.shouldScrollToBottom = false;
    }
  }

  onScroll(event: Event) {
    const element = event.target as HTMLElement;
    const atBottom = Math.abs(element.scrollHeight - element.scrollTop - element.clientHeight) < 50;
    
    // Only mark as user scrolled if not at bottom
    this.userHasScrolled = !atBottom;
    
    // If user scrolls to bottom, enable auto-scroll
    if (atBottom) {
      this.userHasScrolled = false;
      this.shouldScrollToBottom = true;
    }
  }

  startResize(event: MouseEvent | TouchEvent, index: number) {
    event.preventDefault();
    const result = this.executionResults[index];
    const element = (event.target as HTMLElement).closest('.execution-result') as HTMLElement;
    
    if (!element) return;
    
    const startY = event instanceof MouseEvent ? event.pageY : event.touches[0].pageY;
    const startHeight = element.offsetHeight;
    
    // Initialize height if not set
    if (!result.height) {
      result.height = startHeight;
    }
    
    this.resizing = { index, startY, startHeight };
    
    // Add resize class to body
    document.body.classList.add('resizing');
  }

  @HostListener('window:mousemove', ['$event'])
  @HostListener('window:touchmove', ['$event'])
  onResize(event: MouseEvent | TouchEvent) {
    if (!this.resizing) return;
    
    const currentY = event instanceof MouseEvent ? event.pageY : event.touches[0].pageY;
    const deltaY = currentY - this.resizing.startY;
    const newHeight = Math.max(100, this.resizing.startHeight + deltaY); // Minimum height of 100px
    
    this.executionResults[this.resizing.index].height = newHeight;
  }

  @HostListener('window:mouseup')
  @HostListener('window:touchend')
  stopResize() {
    if (this.resizing) {
      document.body.classList.remove('resizing');
      this.resizing = null;
    }
  }

  ngOnDestroy() {
    this.subscription.unsubscribe();
    document.body.style.overflow = 'auto';
  }

  private handleExecutionResult(result: ExecutionResult) {
    const localResult: LocalExecutionResult = {
      command: result.command || '',
      output: result.output || '',
      error: result.error || '',
      outputFiles: this.processOutputFiles(result.outputFiles || []),
      timestamp: Date.now(),
      isRunning: result.returnCode === undefined
    };

    // Update existing result if it's a running update
    const existingIndex = this.executionResults.findIndex(r => r.command === result.command && r.isRunning);
    if (existingIndex !== -1 && localResult.isRunning) {
      this.executionResults[existingIndex] = localResult;
    } else {
      this.executionResults.push(localResult);
    }
    this.currentResult = localResult;
  }

  private processOutputFiles(files: any[]): OutputFile[] {
    console.log('DEBUG: Processing output files:', files);
    
    // Process all files first to ensure they have timestamps
    const processedFiles = files.map(file => {
      if (typeof file === 'string') {
        // For string paths, create a full OutputFile object
        const filename = file.split(/[/\\]/).pop() || file;
        return {
          filename,
          path: file,
          url: `/files/${encodeURIComponent(file)}/download`,
          type: this.getFileType(filename),
          isVisible: true,
          error: undefined,
          timestamp: this.extractTimestampFromFilename(filename) || Date.now()
        };
      }
      
      // For object files, ensure all required fields are present
      return {
        ...file,
        filename: file.filename || file.path.split(/[/\\]/).pop() || 'unknown',
        path: file.path || file.filename,
        type: this.getFileType(file.filename || file.path),
        isVisible: true,
        error: undefined,
        timestamp: this.extractTimestampFromFilename(file.filename) || Date.now()
      };
    });

    // Group files by their base name (without timestamp)
    const fileGroups = new Map<string, OutputFile[]>();
    processedFiles.forEach(file => {
      const baseFileName = this.getBaseFileName(file.filename);
      if (!fileGroups.has(baseFileName)) {
        fileGroups.set(baseFileName, []);
      }
      fileGroups.get(baseFileName)!.push(file);
    });

    // For each group, only keep the most recent file
    const latestFiles = Array.from(fileGroups.values()).map(group => {
      return group.reduce((latest, current) => {
        return (current.timestamp > latest.timestamp) ? current : latest;
      }, group[0]); // Provide initial value to ensure type safety
    });

    console.log('DEBUG: Latest files selected:', latestFiles);
    return latestFiles;
  }

  private extractTimestampFromFilename(filename: string): number | null {
    // Match timestamp pattern like _1751052238_2287 in filenames
    const match = filename.match(/_(\d{10})_\d+/);
    if (match) {
      return parseInt(match[1]) * 1000; // Convert to milliseconds
    }
    return null;
  }

  private getBaseFileName(filename: string): string {
    // Remove timestamp pattern from filename to get base name
    return filename.replace(/_\d{10}_\d+/, '');
  }

  private getFileType(filename: string): string {
    console.log('DEBUG: Getting file type for:', filename);
    const extension = filename.toLowerCase().split('.').pop() || '';
    const type = ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg'].includes(extension) ? 'image' :
                ['html', 'htm'].includes(extension) ? 'html' : 'file';
    console.log('DEBUG: File type determined:', type);
    return type;
  }

  getFileIcon(filename: string): string {
    const extension = filename.toLowerCase().split('.').pop() || '';
    switch (extension) {
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg':
        return 'fa-image';
      case 'csv':
        return 'fa-table';
      case 'html':
        return 'fa-code';
      case 'pdf':
        return 'fa-file-pdf';
      default:
        return 'fa-file';
    }
  }

  getFileDownloadUrl(file: OutputFile): string {
    if (this.urlCache.has(file.path)) {
      return this.urlCache.get(file.path)!;
    }
    
    // Add debug logging to see what we're working with
    console.log('DEBUG: Constructing URL for file:', {
      filename: file.filename,
      path: file.path,
      type: file.type
    });

    // Ensure the path is properly formatted
    const cleanPath = file.path.replace(/\\/g, '/').replace(/^\//, '');
    const url = `http://localhost:8001/files/${encodeURIComponent(cleanPath)}/download`;
    
    console.log('DEBUG: Constructed URL:', url);
    
    this.urlCache.set(file.path, url);
    return url;
  }

  formatTimestamp(timestamp: number): string {
    return new Date(timestamp).toLocaleTimeString();
  }

  getOutputClass(result: LocalExecutionResult): string {
    if (result.error) return 'execution-error';
    if (result.isRunning) return 'execution-running';
    return 'execution-success';
  }

  clearOutput() {
    this.executionResults = [];
    this.currentResult = null;
    this.urlCache.clear();
  }

  toggleImageVisibility(file: OutputFile) {
    file.isVisible = !file.isVisible;
  }

  onImageLoad(file: OutputFile) {
    console.log('DEBUG: Image loaded successfully:', file.filename);
    const statusElement = document.getElementById(`status-${file.filename}`);
    if (statusElement) {
      statusElement.textContent = 'Loaded successfully';
      statusElement.style.color = 'green';
    }
    file.error = undefined;
  }

  onImageError(file: OutputFile, event: any) {
    file.error = `Could not load image. Check console for details. Path: ${file.path}`;
    const statusEl = document.getElementById(`status-${file.filename}`);
    if (statusEl) {
      statusEl.textContent = 'Error';
      statusEl.style.color = 'red';
    }
  }

  maximizeImage(file: OutputFile) {
    this.maximizedImage = file;
    document.body.style.overflow = 'hidden';
  }

  closeMaximizedImage() {
    this.maximizedImage = null;
    document.body.style.overflow = 'auto';
  }

  handleOverlayClick(event: MouseEvent) {
    // Only close if clicking the overlay background, not the image
    if (event.target === event.currentTarget) {
      this.closeMaximizedImage();
    }
  }
} 