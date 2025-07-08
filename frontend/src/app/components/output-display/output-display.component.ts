import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked, HostListener } from '@angular/core';
import { ExecutionService, ExecutionResult } from '../../services/execution.service';
import { Subscription } from 'rxjs';
import { HttpClient } from '@angular/common/http';

interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
  isVisible?: boolean;
  timestamp: number;
  error?: string;
  plotlyContent?: string; // Add field for plotly HTML content
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

  constructor(
    private executionService: ExecutionService,
    private http: HttpClient
  ) {}

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

    // Find any running execution to update (there should only be one at a time)
    const existingIndex = this.executionResults.findIndex(r => r.isRunning);
    if (existingIndex !== -1) {
      // Update the existing running result with the final result
      this.executionResults[existingIndex] = localResult;
    } else {
      this.executionResults.push(localResult);
    }
    this.currentResult = localResult;
  }

  private processOutputFiles(files: any[]): OutputFile[] {
    
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

    // Auto-load plotly content for plotly-html files
    latestFiles.forEach(file => {
      this.autoLoadPlotlyContent(file);
    });

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

  private fileTypeCache = new Map<string, string>();

  private getFileType(filename: string): string {
    // Check cache first to avoid repeated calculations
    if (this.fileTypeCache.has(filename)) {
      return this.fileTypeCache.get(filename)!;
    }

    const extension = filename.toLowerCase().split('.').pop() || '';
    let type: string;
    
    if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'svg'].includes(extension)) {
      type = 'image';
    } else if (['html', 'htm'].includes(extension)) {
      // Check if it's a plotly chart based on filename patterns
      if (filename.toLowerCase().includes('chart') || 
          filename.toLowerCase().includes('plot') || 
          filename.toLowerCase().includes('interactive') ||
          filename.toLowerCase().includes('sql_results') ||
          filename.toLowerCase().includes('visualization')) {
        type = 'plotly-html';
      } else {
        type = 'html';
      }
    } else {
      type = 'file';
    }
    
    // Cache the result
    this.fileTypeCache.set(filename, type);
    return type;
  }

  getFileIcon(filename: string): string {
    const extension = filename.toLowerCase().split('.').pop() || '';
    const fileType = this.getFileType(filename);
    
    if (fileType === 'plotly-html') {
      return 'fa-chart-line';
    }
    
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
    // Use a composite key of path + timestamp to differentiate updated versions
    const cacheKey = `${file.path}|${file.timestamp}`;

    if (this.urlCache.has(cacheKey)) {
      return this.urlCache.get(cacheKey)!;
    }

    // Ensure the path is properly formatted
    const cleanPath = file.path.replace(/\\/g, '/').replace(/^\//, '');

    // Append a cache-busting query parameter so the browser fetches the latest version.
    // We prefer the provided timestamp (derived from filename or Date.now during processing)
    const cacheBust = file.timestamp || Date.now();
    const url = `http://localhost:8001/files/${encodeURIComponent(cleanPath)}/download?t=${cacheBust}`;

    this.urlCache.set(cacheKey, url);
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
    this.fileTypeCache.clear(); // Clear file type cache as well
  }

  toggleImageVisibility(file: OutputFile) {
    file.isVisible = !file.isVisible;
  }

  togglePlotlyVisibility(file: OutputFile) {
    file.isVisible = !file.isVisible;
    if (file.isVisible && !file.plotlyContent) {
      this.loadPlotlyContent(file);
    }
  }

  // Auto-load plotly content when plotly-html files are first detected
  private autoLoadPlotlyContent(file: OutputFile) {
    if (file.type === 'plotly-html' && !file.plotlyContent && !file.error) {
      console.log('Auto-loading plotly content for:', file.filename);
      // Add a small delay to ensure the component is ready
      setTimeout(() => {
        this.loadPlotlyContent(file);
      }, 100);
    }
  }

  private loadPlotlyContent(file: OutputFile) {
    console.log('Loading plotly content for file:', file.filename);
    console.log('File URL:', this.getFileDownloadUrl(file));
    
    this.http.get(this.getFileDownloadUrl(file), { responseType: 'text' })
      .subscribe({
        next: (content) => {
          console.log('Successfully loaded plotly content, length:', content.length);
          console.log('Content preview:', content.substring(0, 500));
          file.plotlyContent = content;
        },
        error: (error) => {
          console.error('Error loading plotly content:', error);
          file.error = 'Failed to load interactive chart content';
        }
      });
  }

  onImageLoad(file: OutputFile) {
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