import { Component, OnInit, OnDestroy, ViewChild, ElementRef, AfterViewChecked, HostListener, ChangeDetectorRef } from '@angular/core';
import { ExecutionService, ExecutionResult } from '../../services/execution.service';
import { ScenarioService } from '../../services/scenario.service';
import { ApiService } from '../../services/api.service';
import { Subscription } from 'rxjs';
import { HttpClient } from '@angular/common/http';
import { Scenario, ExecutionHistory } from '../../models/scenario.model';

interface OutputFile {
  filename: string;
  path: string;
  url: string;
  type: string;
  isVisible?: boolean;
  timestamp: number;
  error?: string;
  plotlyContent?: string; // Add field for plotly HTML content
  htmlContent?: string; // Add field for regular HTML content
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
  currentScenario: Scenario | null = null;
  isLoadingHistory = false;
  
  private subscription: Subscription = new Subscription();
  private urlCache = new Map<string, string>();
  private shouldScrollToBottom = false;
  private userHasScrolled = false;
  private lastScrollHeight = 0;
  private resizing: { index: number; startY: number; startHeight: number } | null = null;
  // Add localStorage key prefix for plotly content caching
  private readonly PLOTLY_CACHE_PREFIX = 'plotly_content_scenario_';
  // Add per-scenario execution results storage
  private scenarioExecutionResults = new Map<number, LocalExecutionResult[]>();
  // Track processed history to prevent duplicates
  private processedHistory = new Set<string>();

  constructor(
    private executionService: ExecutionService,
    private scenarioService: ScenarioService,
    private apiService: ApiService,
    private http: HttpClient,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit() {
    console.log('OutputDisplayComponent: ngOnInit called');
    
    // Subscribe to execution results
    this.subscription.add(
      this.executionService.executionResult$.subscribe((result: ExecutionResult | null) => {
        console.log('OutputDisplayComponent: Received execution result:', result);
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
        console.log('OutputDisplayComponent: Execution status changed:', isExecuting);
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

    // Subscribe to scenario changes
    this.subscription.add(
      this.scenarioService.currentScenario$.subscribe(scenario => {
        this.currentScenario = scenario;
        if (!scenario) {
          // Clear execution results when no scenario is active
          this.executionResults = [];
          this.currentResult = null;
          this.maximizedImage = null;
        } else {
          // Load scenario-specific execution results
          this.loadScenarioExecutionResults(scenario.id);
        }
      })
    );

    // Subscribe to execution history changes from scenario service
    this.subscription.add(
      this.scenarioService.executionHistory$.subscribe(history => {
        console.log('OutputDisplayComponent: Execution history updated:', history.length, 'items');
        if (this.currentScenario) {
          const scenarioHistory = history.filter(h => h.scenario_id === this.currentScenario!.id);
          console.log('OutputDisplayComponent: Filtered history for current scenario:', scenarioHistory.length, 'items');
          
          // Only process history if we don't have cached results for this scenario
          if (!this.scenarioExecutionResults.has(this.currentScenario.id)) {
            console.log('OutputDisplayComponent: No cached results, updating from history');
            this.updateExecutionResultsFromHistory(scenarioHistory);
            // Cache the results after loading from history
            this.scenarioExecutionResults.set(this.currentScenario.id, [...this.executionResults]);
          } else {
            console.log('OutputDisplayComponent: Have cached results, ignoring history updates');
          }
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

  // Update execution results from scenario history
  private updateExecutionResultsFromHistory(history: ExecutionHistory[]): void {
    // Convert history items to LocalExecutionResult format
    const historyResults = history.map(item => {
      let outputFiles: OutputFile[] = [];
      
      // Parse output files from execution history if available
      if (item.output_files) {
        try {
          const parsedFiles = JSON.parse(item.output_files);
          outputFiles = this.processOutputFiles(parsedFiles);
        } catch (e) {
          console.error('OutputDisplayComponent: Error parsing output files from history:', e);
        }
      }
      
      return {
        command: item.command || 'Execution',
        output: item.output || '',
        error: item.error || '',
        outputFiles: outputFiles,
        timestamp: new Date(item.timestamp).getTime(),
        isRunning: false
      };
    });

    // Replace existing results with history results (no merging)
    this.executionResults = historyResults;
    console.log('OutputDisplayComponent: Loaded', historyResults.length, 'history results for scenario');

    // Set the most recent result as current
    if (this.executionResults.length > 0) {
      this.currentResult = this.executionResults[this.executionResults.length - 1];
      
      // Only restore cached plotly content for successful results
      this.restoreCachedPlotlyContent();
      
      // Auto-load plotly content for visible files that don't have cached content
      // But only for successful executions
      if (!this.currentResult.error) {
        this.currentResult.outputFiles.forEach(file => {
          if (file.type === 'plotly-html' && file.isVisible && !file.plotlyContent && !file.error) {
            this.loadPlotlyContent(file);
          }
        });
      }
    }
    
    this.shouldScrollToBottom = true;
  }

  // Cache plotly content in localStorage per scenario
  private cachePlotlyContent(filename: string, content: string): void {
    if (!this.currentScenario) return;
    
    try {
      const cacheKey = `${this.PLOTLY_CACHE_PREFIX}${this.currentScenario.id}_${filename}`;
      localStorage.setItem(cacheKey, content);
      console.log('OutputDisplayComponent: Cached plotly content for:', filename);
    } catch (e) {
      console.warn('Failed to cache plotly content:', e);
    }
  }

  // Restore cached plotly content for all execution results
  private restoreCachedPlotlyContent(): void {
    if (!this.currentScenario) return;
    
    console.log('OutputDisplayComponent: Restoring cached plotly content for scenario:', this.currentScenario.id);
    
    this.executionResults.forEach(result => {
      // Don't restore cached content for failed executions
      if (result.error) {
        console.log('OutputDisplayComponent: Skipping cached content restoration for failed execution');
        return;
      }
      
      // Only restore content for files that were actually generated in this execution
      // Check if the file has a recent timestamp (within last 5 minutes of execution)
      const executionTime = result.timestamp;
      const fiveMinutesAgo = Date.now() - (5 * 60 * 1000);
      
      result.outputFiles.forEach(file => {
        // Only restore content for files that were created around the same time as this execution
        const fileTime = file.timestamp || executionTime;
        const isRecentFile = Math.abs(fileTime - executionTime) < (5 * 60 * 1000); // 5 minutes tolerance
        
        if (file.type === 'plotly-html' && !file.plotlyContent && !file.error && isRecentFile) {
          const cacheKey = `${this.PLOTLY_CACHE_PREFIX}${this.currentScenario!.id}_${file.filename}`;
          const cachedContent = localStorage.getItem(cacheKey);
          
          if (cachedContent) {
            console.log('OutputDisplayComponent: Restored cached content for:', file.filename);
            file.plotlyContent = cachedContent;
          }
        } else if (file.type === 'plotly-html' && !isRecentFile) {
          console.log('OutputDisplayComponent: Skipping old file:', file.filename);
        }
      });
    });
  }

  // Clear cached plotly content for a scenario (optional cleanup method)
  private clearCachedPlotlyContent(scenarioId: number): void {
    try {
      const keysToRemove: string[] = [];
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith(`${this.PLOTLY_CACHE_PREFIX}${scenarioId}_`)) {
          keysToRemove.push(key);
        }
      }
      
      keysToRemove.forEach(key => localStorage.removeItem(key));
      console.log('OutputDisplayComponent: Cleared cached plotly content for scenario:', scenarioId);
    } catch (e) {
      console.warn('Failed to clear cached plotly content:', e);
    }
  }

  // Ensure plotly content is loaded for visible files
  private ensurePlotlyContentLoaded(): void {
    if (!this.currentResult) return;
    
    this.currentResult.outputFiles.forEach(file => {
      if (file.type === 'plotly-html' && file.isVisible && !file.plotlyContent && !file.error) {
        console.log('OutputDisplayComponent: Loading plotly content for file:', file.filename);
        this.loadPlotlyContent(file);
      }
    });
  }

  // Load scenario-specific execution history (kept for backward compatibility)
  private loadScenarioExecutionHistory(scenarioId: number): void {
    this.isLoadingHistory = true;
    
    // Don't clear results immediately - preserve UI during loading
    this.apiService.getExecutionHistory(scenarioId).subscribe({
      next: (history) => {
        if (!Array.isArray(history)) {
          console.error('OutputDisplayComponent: History is not an array:', history);
          // Clear results only on invalid data
          this.executionResults = [];
          this.currentResult = null;
          this.maximizedImage = null;
          this.isLoadingHistory = false;
          return;
        }

        this.updateExecutionResultsFromHistory(history);
        this.isLoadingHistory = false;
      },
      error: (error) => {
        console.error('OutputDisplayComponent: Error loading execution history for scenario:', scenarioId, error);
        // On API error, clear results
        this.executionResults = [];
        this.currentResult = null;
        this.maximizedImage = null;
        this.isLoadingHistory = false;
      }
    });
  }

  // Load scenario-specific execution results
  private loadScenarioExecutionResults(scenarioId: number): void {
    // Check if we have cached results for this scenario
    if (this.scenarioExecutionResults.has(scenarioId)) {
      console.log('OutputDisplayComponent: Loading cached results for scenario:', scenarioId);
      this.executionResults = [...this.scenarioExecutionResults.get(scenarioId)!];
      if (this.executionResults.length > 0) {
        this.currentResult = this.executionResults[this.executionResults.length - 1];
      }
      return;
    }

    // No cached results, load from backend and local storage
    console.log('OutputDisplayComponent: Loading fresh results for scenario:', scenarioId);
    this.executionResults = [];
    this.currentResult = null;
    
    // Load from both backend history and local execution service storage
    this.loadScenarioExecutionHistory(scenarioId);
    this.loadLocalExecutionResults(scenarioId);
    
    // Cache the results for this scenario
    this.scenarioExecutionResults.set(scenarioId, [...this.executionResults]);
  }

  // Load local execution results from execution service
  private loadLocalExecutionResults(scenarioId: number): void {
    const localResults = this.executionService.getScenarioExecutionResults(scenarioId);
    console.log('OutputDisplayComponent: Loading local execution results for scenario:', scenarioId, 'count:', localResults.length);
    
    if (localResults.length > 0) {
      // Convert local results to LocalExecutionResult format
      const localExecutionResults = localResults.map(result => ({
        command: result.command || '',
        output: result.output || '',
        error: result.error || '',
        outputFiles: this.processOutputFiles(result.outputFiles || []),
        timestamp: Date.now(), // Use current time for local results
        isRunning: false
      }));
      
      // Add local results to existing results (these are current session results)
      this.executionResults.push(...localExecutionResults);
      console.log('OutputDisplayComponent: Added', localExecutionResults.length, 'local execution results');
      
      // Update current result if we have new results
      if (localExecutionResults.length > 0) {
        this.currentResult = localExecutionResults[localExecutionResults.length - 1];
      }
    }
  }

  // Get scenario display name for headers
  getScenarioDisplayName(): string {
    return this.currentScenario?.name || 'No Scenario';
  }

  // Get scenario status for display
  getScenarioStatus(): string {
    if (!this.currentScenario) return 'none';
    if (this.currentScenario.is_base_scenario) return 'base';
    if (this.currentScenario.parent_scenario_id) return 'branch';
    return 'custom';
  }

  private handleExecutionResult(result: ExecutionResult) {
    // Only handle results for the current scenario
    if (!this.currentScenario || result.scenarioId !== this.currentScenario.id) {
      console.log('OutputDisplayComponent: Ignoring execution result for different scenario');
      return;
    }

    const localResult: LocalExecutionResult = {
      command: result.command || '',
      output: result.output || '',
      error: result.error || '',
      outputFiles: result.returnCode === undefined ? [] : this.processOutputFiles(result.outputFiles || []),
      timestamp: Date.now(),
      isRunning: result.returnCode === undefined
    };

    // Find any running execution to update (there should only be one at a time)
    const existingIndex = this.executionResults.findIndex(r => r.isRunning);
    if (existingIndex !== -1) {
      // Update the existing running result with the final result
      // Don't preserve old content - let the new result stand on its own
      this.executionResults[existingIndex] = localResult;
    } else {
      this.executionResults.push(localResult);
    }
    this.currentResult = localResult;
    
    // Cache the updated results for the current scenario
    this.scenarioExecutionResults.set(this.currentScenario.id, [...this.executionResults]);
    console.log('OutputDisplayComponent: Cached execution results for scenario:', this.currentScenario.id);
    
    // Ensure the execution service also stores this result for persistence
    console.log('OutputDisplayComponent: Storing execution result for scenario:', this.currentScenario.id);
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
    let latestFiles = Array.from(fileGroups.values()).map(group => {
      return group.reduce((latest, current) => {
        return (current.timestamp > latest.timestamp) ? current : latest;
      }, group[0]); // Provide initial value to ensure type safety
    });

    // Filter out non-plotly files if they appear to be from SQL queries
    latestFiles = this.filterSQLQueryFiles(latestFiles);

      // Auto-load content for HTML files (both plotly and regular HTML)
  latestFiles.forEach(file => {
    if (file.type === 'plotly-html') {
      this.autoLoadPlotlyContent(file);
    } else if (file.type === 'html') {
      // Load HTML content directly for embedding
      this.loadHtmlContent(file);
    }
  });

    return latestFiles;
  }

  // Filter out non-plotly files from SQL queries
  private filterSQLQueryFiles(files: OutputFile[]): OutputFile[] {
    console.log('OutputDisplayComponent: Filtering SQL query files:', files.length, 'files');
    
    // Check if any file has SQL query patterns
    const hasSQLQueryPattern = files.some(file => {
      const filename = file.filename.toLowerCase();
      const isSQLQuery = filename.includes('sql_query') ||
             filename.includes('sql_results') ||
             filename.includes('query_') ||
             filename.includes('sql_') ||
             filename.includes('database_') ||
             filename.includes('table_') ||
             filename.includes('results_');
      
      if (isSQLQuery) {
        console.log('OutputDisplayComponent: Found SQL query pattern in file:', file.filename);
      }
      
      return isSQLQuery;
    });

    if (hasSQLQueryPattern) {
      console.log('OutputDisplayComponent: SQL query detected, filtering files');
      // For SQL queries, show HTML files (both plotly and regular) and images
      const filteredFiles = files.filter(file => 
        file.type === 'plotly-html' || 
        file.type === 'html' ||
        file.type === 'image'
      );
      console.log('OutputDisplayComponent: Filtered to', filteredFiles.length, 'files');
      return filteredFiles;
    }

    console.log('OutputDisplayComponent: No SQL query pattern detected, returning all files');
    return files;
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
    const extension = filename.split('.').pop()?.toLowerCase() || '';
    let type = 'file';
    if (['png', 'jpg', 'jpeg', 'svg'].includes(extension)) {
      type = 'image';
    } else if (['html', 'htm'].includes(extension)) {
      // Check if it's a Plotly chart or regular HTML
      // Only detect as plotly if it explicitly contains plotly in the name
      if (filename.toLowerCase().includes('plotly')) {
        type = 'plotly-html';
      } else {
        type = 'html'; // Regular HTML files (including charts from AI agent)
      }
    } else if (extension === 'csv') {
      type = 'csv';
    } else if (extension === 'pdf') {
      type = 'pdf';
    }
    return type;
  }

  getFileIcon(filename: string): string {
    const extension = filename.toLowerCase().split('.').pop() || '';
    const fileType = this.getFileType(filename);
    
    if (fileType === 'plotly-html') {
      return 'fa-chart-line';
    } else if (fileType === 'html') {
      return 'fa-file-code';
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
        return 'fa-file-code';
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

  // Load HTML content directly for embedding
  private loadHtmlContent(file: OutputFile) {
    if (file.type === 'html' && !file.htmlContent && !file.error) {
      console.log('Loading HTML content for:', file.filename);
      this.http.get(this.getFileDownloadUrl(file), { responseType: 'text' })
        .subscribe({
          next: (content) => {
            console.log('Successfully loaded HTML content, length:', content.length);
            file.htmlContent = content;
            // Force change detection
            this.cdr.detectChanges();
          },
          error: (error) => {
            console.error('Error loading HTML content:', error);
            file.error = 'Failed to load HTML content';
          }
        });
    }
  }

  // Helper method to check if files contain HTML files
  hasHtmlFiles(files: OutputFile[] | undefined): boolean {
    if (!files || files.length === 0) return false;
    return files.some(file => file.type === 'html' || file.type === 'plotly-html');
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
          
          // Cache the loaded content
          this.cachePlotlyContent(file.filename, content);
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