import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked, ChangeDetectorRef } from '@angular/core';
import { Subscription } from 'rxjs';
import { ScenarioAwareExecutionService, ExecutionResult, OutputFile } from '../../services/scenario-aware-execution.service';
import { HttpClient } from '@angular/common/http';
import { timeout, catchError } from 'rxjs/operators';
import { of } from 'rxjs';

@Component({
  selector: 'app-workbench-output',
  templateUrl: './workbench-output.component.html',
  styleUrls: ['./workbench-output.component.css']
})
export class WorkbenchOutputComponent implements OnInit, OnDestroy, AfterViewChecked {
  @ViewChild('outputContainer') outputContainer!: ElementRef;
  
  executionResults: ExecutionResult[] = [];
  isExecuting = false;
  shouldScrollToBottom = true;
  userHasScrolled = false;
  
  private subscription = new Subscription();
  private fileTypeLogCache: Set<string> = new Set();

  constructor(
    private executionService: ScenarioAwareExecutionService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    // Subscribe to execution results
    this.subscription.add(
      this.executionService.executionResults$.subscribe(results => {
        const wasEmpty = this.executionResults.length === 0;
        const hasNewResults = results.length > this.executionResults.length;
        this.executionResults = results;
        
        console.log('Received execution results:', results.length, 'results');
        results.forEach((result, index) => {
          console.log(`Result ${index}:`, result);
          if (result.outputFiles) {
            console.log(`Result ${index} has ${result.outputFiles.length} output files:`, result.outputFiles.map(f => f.filename));
            result.outputFiles.forEach(file => {
              console.log('Processing file:', file.filename, 'Type:', this.getFileType(file.filename));
              this.autoLoadHtmlContent(file);
            });
          }
        });
        
        // Auto-load HTML content for HTML files
        if (hasNewResults) {
          results.forEach(result => {
            if (result.outputFiles) {
              result.outputFiles.forEach(file => {
                this.autoLoadHtmlContent(file);
              });
            }
          });
        }
        
        // Auto-scroll if new results were added or if it was empty
        if (hasNewResults || wasEmpty) {
          this.shouldScrollToBottom = !this.userHasScrolled;
          // Use setTimeout to ensure DOM is updated
          setTimeout(() => {
            this.scrollToBottom();
          }, 100);
        }
      })
    );

    // Subscribe to executing state
    this.subscription.add(
      this.executionService.isExecuting$.subscribe(isExecuting => {
        this.isExecuting = isExecuting;
        if (isExecuting) {
          this.shouldScrollToBottom = !this.userHasScrolled;
          // Auto-scroll when execution starts
          setTimeout(() => {
            this.scrollToBottom();
          }, 100);
        }
      })
    );
  }

  ngOnDestroy(): void {
    this.subscription.unsubscribe();
  }

  ngAfterViewChecked(): void {
    // Remove this as we're handling scrolling in ngOnInit with setTimeout
  }

  onScroll(event: any): void {
    const element = event.target;
    const atBottom = element.scrollHeight - element.scrollTop <= element.clientHeight + 1;
    this.userHasScrolled = !atBottom;
  }

  public scrollToBottom(): void {
    if (this.outputContainer) {
      const element = this.outputContainer.nativeElement;
      element.scrollTop = element.scrollHeight;
      // Also scroll the parent workbench view if needed
      const workbenchView = element.closest('.workbench-view');
      if (workbenchView) {
        workbenchView.scrollTop = workbenchView.scrollHeight;
      }
    }
  }

  formatTimestamp(timestamp: number): string {
    return new Date(timestamp).toLocaleTimeString();
  }

  getOutputClass(result: ExecutionResult): string {
    if (result.isRunning) return 'execution-running';
    if (result.error && result.returnCode !== 0) return 'execution-error';
    return 'execution-success';
  }

  getFileIcon(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    switch (extension) {
      case 'html': return 'icon-globe';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return 'icon-image';
      case 'py': return 'icon-python';
      case 'csv': return 'icon-table';
      case 'xlsx': return 'icon-spreadsheet';
      default: return 'icon-file';
    }
  }

  getFileType(filename: string): string {
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    // Only log once per unique filename to avoid spam
    if (!this.fileTypeLogCache) {
      this.fileTypeLogCache = new Set();
    }
    if (!this.fileTypeLogCache.has(filename)) {
      console.log('Getting file type for:', filename, 'Extension:', extension);
      this.fileTypeLogCache.add(filename);
    }
    
    switch (extension) {
      case 'html': 
        // Detect as plotly if it contains plotly, chart, or visualization in the name
        const lowerFilename = filename.toLowerCase();
        if (lowerFilename.includes('plotly') || lowerFilename.includes('chart') || lowerFilename.includes('visualization')) {
          if (!this.fileTypeLogCache.has(filename + '_plotly')) {
            console.log('Detected as plotly-html:', filename);
            this.fileTypeLogCache.add(filename + '_plotly');
          }
          return 'plotly-html';
        } else {
          if (!this.fileTypeLogCache.has(filename + '_html')) {
            console.log('Detected as regular html:', filename);
            this.fileTypeLogCache.add(filename + '_html');
          }
          return 'html'; // Regular HTML files (including charts from AI agent)
        }
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg': return 'image';
      case 'py': return 'python';
      case 'csv': return 'csv';
      case 'xlsx': return 'xlsx';
      default: return 'file';
    }
  }

  // Helper method to check if files contain HTML files
  hasHtmlFiles(files: OutputFile[] | undefined): boolean {
    if (!files || files.length === 0) return false;
    return files.some(file => {
      const fileType = this.getFileType(file.filename);
      return fileType === 'html' || fileType === 'plotly-html';
    });
  }

  // Load HTML content directly for embedding
  private loadHtmlContent(file: OutputFile) {
    const fileType = this.getFileType(file.filename);
    console.log('loadHtmlContent called for:', file.filename, 'Type:', fileType);
    console.log('Current state - htmlContent:', !!file.htmlContent, 'plotlyContent:', !!file.plotlyContent, 'error:', !!file.error);
    
    if ((fileType === 'html' || fileType === 'plotly-html') && !file.htmlContent && !file.plotlyContent && !file.error) {
      console.log('Loading HTML content for:', file.filename, 'Type:', fileType);
      const url = this.getFileDownloadUrl(file);
      console.log('Download URL:', url);
      
      this.http.get(url, { responseType: 'text' })
        .pipe(
          timeout(10000), // 10 second timeout
          catchError(error => {
            console.error('HTTP request failed or timed out:', error);
            return of(null);
          })
        )
        .subscribe({
          next: (content) => {
            if (content) {
              console.log('Successfully loaded HTML content, length:', content.length);
              if (fileType === 'plotly-html') {
                file.plotlyContent = content;
                console.log('Set plotlyContent for:', file.filename);
              } else {
                file.htmlContent = content;
                console.log('Set htmlContent for:', file.filename);
              }
            } else {
              console.error('No content received from HTTP request');
              file.error = 'Failed to load HTML content: No response received';
            }
            // Force change detection
            this.cdr.detectChanges();
          },
          error: (error) => {
            console.error('Error loading HTML content:', error);
            console.error('Error details:', error.status, error.statusText, error.message);
            file.error = `Failed to load HTML content: ${error.status} ${error.statusText}`;
            this.cdr.detectChanges();
          }
        });
    } else {
      console.log('Skipping loadHtmlContent - conditions not met');
    }
  }

  // Auto-load HTML content when HTML files are first detected
  private autoLoadHtmlContent(file: OutputFile) {
    const fileType = this.getFileType(file.filename);
    console.log('autoLoadHtmlContent called for:', file.filename, 'Type:', fileType);
    console.log('Current state - htmlContent:', !!file.htmlContent, 'plotlyContent:', !!file.plotlyContent, 'error:', !!file.error);
    
    if ((fileType === 'html' || fileType === 'plotly-html') && !file.htmlContent && !file.plotlyContent && !file.error) {
      console.log('Auto-loading HTML content for:', file.filename, 'Type:', fileType);
      // Add a small delay to ensure the component is ready
      setTimeout(() => {
        this.loadHtmlContent(file);
      }, 100);
    } else {
      console.log('Skipping autoLoadHtmlContent - conditions not met. Reasons:');
      console.log('  - fileType is html/plotly-html:', fileType === 'html' || fileType === 'plotly-html');
      console.log('  - htmlContent exists:', !!file.htmlContent);
      console.log('  - plotlyContent exists:', !!file.plotlyContent);
      console.log('  - error exists:', !!file.error);
    }
  }

  toggleFileVisibility(file: OutputFile): void {
    file.isVisible = !file.isVisible;
  }

  getFileDownloadUrl(file: OutputFile): string {
    return `http://localhost:8001/files/${encodeURIComponent(file.filename)}/download`;
  }

  clearResults(): void {
    this.executionService.clearResults();
  }

  stopExecution(): void {
    this.executionService.stopExecution().subscribe({
      next: (response) => {
        console.log('Execution stopped:', response.message);
      },
      error: (error) => {
        console.error('Failed to stop execution:', error);
      }
    });
  }
} 