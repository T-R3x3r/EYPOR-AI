import { Component, OnInit, ViewEncapsulation, ViewChild, ElementRef, AfterViewInit, AfterViewChecked } from '@angular/core';
import { ApiService } from '../../services/api.service';
import { ExecutionService } from '../../services/execution.service';
import { ScenarioService } from '../../services/scenario.service';
import { Scenario } from '../../models/scenario.model';
import { QueryFileOrganizerService, QueryFileGroup, OrganizedFiles } from '../../services/query-file-organizer.service';

interface FileNode {
  name: string;
  path: string;
  isDirectory: boolean;
  children?: FileNode[];
  expanded?: boolean;
}

@Component({
  selector: 'app-file-tree',
  templateUrl: './file-tree.component.html',
  styleUrls: ['./file-tree.component.css'],
  encapsulation: ViewEncapsulation.None
})
export class FileTreeComponent implements OnInit, AfterViewInit, AfterViewChecked {
  @ViewChild('fileTreeRoot') fileTreeRoot!: ElementRef;
  
  fileTree: FileNode[] = [];
  queryGroups: QueryFileGroup[] = [];
  isLoading = false;
  currentScenario: Scenario | null = null;
  private savedScrollPosition = 0;
  private pendingRestore = false;
  
  // Code viewer modal properties
  showCodeViewer = false;
  viewerFileContent = '';
  viewerFileName = '';
  viewerFileType = '';
  viewerFilePath = '';
  isEditMode = false;
  originalFileContent = '';
  isSaving = false;

  constructor(
    private apiService: ApiService,
    private executionService: ExecutionService,
    private scenarioService: ScenarioService,
    public queryFileOrganizer: QueryFileOrganizerService,
    private elRef: ElementRef
  ) {}

  ngOnInit() {
    // Clear old query groups on startup
    this.queryFileOrganizer.clearOldQueryGroups();
    
    // Clean up any existing empty query groups
    this.queryFileOrganizer.cleanupEmptyGroups();
    
    this.loadFiles();
    
    // Subscribe to scenario changes to update file operations context
    this.scenarioService.currentScenario$.subscribe(scenario => {
      this.currentScenario = scenario;
      console.log('File tree: Scenario changed to:', scenario?.name);
      
      // Files are global, so we don't need to refresh when switching scenarios
      // Only update the current scenario reference for context
      // But refresh query groups to ensure they're visible
      this.refreshQueryGroups();
    });
  }

  ngAfterViewInit() {
    // ViewChild will be available after this
  }

  ngAfterViewChecked() {
    if (this.fileTreeRoot && this.fileTreeRoot.nativeElement && this.savedScrollPosition > 0) {
      this.fileTreeRoot.nativeElement.scrollTop = this.savedScrollPosition;
      if (this.pendingRestore) {
        this.pendingRestore = false;
      }
    }
  }

  refreshFiles() {
    this.saveScrollPosition();
    // Skip loading spinner during automatic refresh to minimize DOM changes
    this.loadFiles(true);
  }

  refreshQueryGroups() {
    // Refresh only the query groups without reloading from API
    const organizedFiles = this.queryFileOrganizer.getOrganizedFiles();
    this.queryGroups = organizedFiles.query_groups;
    console.log('Query groups refreshed:', this.queryGroups.length);
  }

  private saveScrollPosition() {
    // Save scroll position of the component root (the .file-tree element)
    if (this.fileTreeRoot && this.fileTreeRoot.nativeElement) {
      this.savedScrollPosition = this.fileTreeRoot.nativeElement.scrollTop;
    }
  }

  private restoreScrollPosition() {
    if (this.elRef && this.elRef.nativeElement) {
      // Restore after DOM update
      setTimeout(() => {
        this.elRef.nativeElement.scrollTop = this.savedScrollPosition;
      }, 0);
    }
  }

  loadFiles(skipLoadingSpinner: boolean = false) {
    if (!skipLoadingSpinner) {
      this.isLoading = true;
    }
    this.apiService.getFiles().subscribe({
      next: (response) => {
        // Update uploaded files in organizer
        this.queryFileOrganizer.setUploadedFiles(response.uploaded_files || []);
        
        // Build file tree for uploaded files
        this.fileTree = this.buildFileTree(response.uploaded_files || []);
        
        // Get organized query groups - files should be global and accessible from any scenario
        const organizedFiles = this.queryFileOrganizer.getOrganizedFiles();
        this.queryGroups = organizedFiles.query_groups;
        
        console.log('File tree loaded:', {
          uploadedFiles: response.uploaded_files?.length || 0,
          queryGroups: this.queryGroups.length,
          currentScenario: this.currentScenario?.name
        });
        
        if (!skipLoadingSpinner) {
          this.isLoading = false;
        }
        
        // Mark for scroll restoration after view updates
        this.pendingRestore = true;
      },
      error: (error) => {
        console.error('Error loading files:', error);
        if (!skipLoadingSpinner) {
          this.isLoading = false;
        }
      }
    });
  }

  buildFileTree(files: string[]): FileNode[] {
    const tree: FileNode[] = [];
    const fileMap = new Map<string, FileNode>();

    // Sort files to ensure directories come before their contents
    files.sort();

    for (const file of files) {
      const parts = file.split('/');
      let currentPath = '';
      
      for (let i = 0; i < parts.length; i++) {
        const part = parts[i];
        const isLast = i === parts.length - 1;
        const isDirectory = !isLast;
        
        currentPath = currentPath ? `${currentPath}/${part}` : part;
        
        if (!fileMap.has(currentPath)) {
          const node: FileNode = {
            name: part,
            path: currentPath,
            isDirectory: isDirectory,
            children: isDirectory ? [] : undefined,
            expanded: false
          };
          
          fileMap.set(currentPath, node);
          
          if (i === 0) {
            // Root level
            tree.push(node);
          } else {
            // Add to parent
            const parentPath = parts.slice(0, i).join('/');
            const parent = fileMap.get(parentPath);
            if (parent && parent.children) {
              parent.children.push(node);
            }
          }
        }
      }
    }

    return tree;
  }

  toggleFolder(node: FileNode) {
    if (node.isDirectory) {
      node.expanded = !node.expanded;
    }
  }

  runPythonFile(filePath: string) {
    console.log('Running Python file:', filePath, 'in scenario:', this.currentScenario?.name);
    this.executionService.setExecuting(true);
    
    // Include scenario context in execution
    const scenarioId = this.currentScenario?.id;
    if (scenarioId) {
      console.log('Executing with scenario context:', scenarioId);
    }
    
    // Find the query group this file belongs to (if any)
    const queryGroup = this.findQueryGroupForFile(filePath);
    
    this.apiService.runFile(filePath).subscribe({
      next: (result: any) => {
        console.log('Python execution result:', result);
        
        // Filter INFO messages from stderr and move them to stdout
        const processed = this.processExecutionResult(result);
        
        this.executionService.emitExecutionResult({
          command: `python ${filePath}`,
          output: processed.stdout,
          error: processed.stderr,
          returnCode: result.return_code,
          outputFiles: result.output_files || []
        });
        this.executionService.setExecuting(false);
        
        // Add new output files to the appropriate query group
        if (result.output_files && result.output_files.length > 0) {
          this.addOutputFilesToQueryGroup(filePath, result.output_files, queryGroup);
        }
        
        // Refresh file tree to show newly created files
        this.refreshFiles();
      },
      error: (error: any) => {
        console.error('Error running Python file:', error);
        this.executionService.emitExecutionResult({
          command: `python ${filePath}`,
          output: '',
          error: `Error: ${error.message || 'Failed to execute file'}`,
          returnCode: -1
        });
        this.executionService.setExecuting(false);
      }
    });
  }

  runSQLFile(filePath: string) {
    console.log('Running SQL file:', filePath);
    this.executionService.setExecuting(true);
    
    // First get the SQL content from the file
    this.apiService.getFileContent(filePath).subscribe({
      next: (fileResponse) => {
        const sqlContent = fileResponse.content;
        // Extract the actual SQL query (remove comments and extra formatting)
        const sqlLines = sqlContent.split('\n');
        const sqlQuery = sqlLines
          .filter(line => !line.trim().startsWith('--') && line.trim() !== '')
          .join('\n')
          .replace(/;$/, ''); // Remove trailing semicolon for API compatibility
        
        if (!sqlQuery.trim()) {
          this.executionService.emitExecutionResult({
            command: `SQL: ${filePath}`,
            output: '',
            error: 'No valid SQL query found in file',
            returnCode: 1
          });
          this.executionService.setExecuting(false);
          
          // Refresh file tree even on error in case partial files were created
          this.refreshFiles();
          return;
        }

        // Execute the SQL query
        this.apiService.executeSQL(sqlQuery).subscribe({
          next: (result: any) => {
            console.log('SQL execution result:', result);
            
            if (result.result && result.columns) {
              // Format results as table
              const formattedResult = this.formatSQLResults(sqlQuery, result.result, result.columns);
              this.executionService.emitExecutionResult({
                command: `SQL: ${filePath}`,
                output: formattedResult,
                error: '',
                returnCode: 0
              });
            } else {
              this.executionService.emitExecutionResult({
                command: `SQL: ${filePath}`,
                output: JSON.stringify(result, null, 2),
                error: '',
                returnCode: 0
              });
            }
            this.executionService.setExecuting(false);
            
            // Refresh file tree to show any newly created files
            this.refreshFiles();
          },
          error: (error: any) => {
            console.error('Error running SQL file:', error);
            this.executionService.emitExecutionResult({
              command: `SQL: ${filePath}`,
              output: '',
              error: `SQL Error: ${error.error?.message || error.message || 'Failed to execute SQL'}`,
              returnCode: 1
            });
            this.executionService.setExecuting(false);
            
            // Refresh file tree even on error in case partial files were created
            this.refreshFiles();
          }
        });
      },
      error: (error: any) => {
        console.error('Error reading SQL file:', error);
        this.executionService.emitExecutionResult({
          command: `SQL: ${filePath}`,
          output: '',
          error: `File Error: ${error.message || 'Failed to read SQL file'}`,
          returnCode: 1
        });
        this.executionService.setExecuting(false);
        
        // Refresh file tree even on error in case partial files were created
        this.refreshFiles();
      }
    });
  }

  private formatSQLResults(query: string, result: any[], columns: string[]): string {
    if (!result || result.length === 0) {
      return `Query executed successfully but returned no results.\n\nQuery: ${query}`;
    }

    // Create a formatted table output
    let output = `SQL Query Results (${result.length} rows):\n\n`;
    
    // Calculate column widths
    const colWidths: number[] = columns.map(col => col.length);
    result.forEach(row => {
      columns.forEach((col, i) => {
        const value = String(row[col] || '');
        colWidths[i] = Math.max(colWidths[i], value.length);
      });
    });

    // Create header
    const headerRow = columns.map((col, i) => col.padEnd(colWidths[i])).join(' | ');
    const separator = colWidths.map(width => '-'.repeat(width)).join('-+-');
    
    output += headerRow + '\n';
    output += separator + '\n';
    
    // Add data rows (limit to first 100 rows for performance)
    const displayRows = result.slice(0, 100);
    displayRows.forEach(row => {
      const dataRow = columns.map((col, i) => {
        const value = String(row[col] || '');
        return value.padEnd(colWidths[i]);
      }).join(' | ');
      output += dataRow + '\n';
    });

    // Add summary
    if (result.length > 100) {
      output += `\n... showing first 100 of ${result.length} rows`;
    }
    output += `\n\n📊 Total: ${result.length} rows, ${columns.length} columns`;

    return output;
  }

  installRequirements() {
    console.log('Installing requirements.txt');
    this.executionService.setExecuting(true);
    
    this.apiService.installRequirements('requirements.txt').subscribe({
      next: (result: any) => {
        console.log('Requirements installation result:', result);
        
        // Filter INFO messages from stderr and move them to stdout
        const processed = this.processExecutionResult(result);
        
        this.executionService.emitExecutionResult({
          command: 'pip install -r requirements.txt',
          output: processed.stdout,
          error: processed.stderr,
          returnCode: result.return_code
        });
        this.executionService.setExecuting(false);
        
        // Refresh file tree in case installation created any files
        this.refreshFiles();
      },
      error: (error: any) => {
        console.error('Error installing requirements:', error);
        this.executionService.emitExecutionResult({
          command: 'pip install -r requirements.txt',
          output: '',
          error: `Error: ${error.message || 'Failed to install requirements'}`,
          returnCode: -1
        });
        this.executionService.setExecuting(false);
        
        // Refresh file tree even on error in case partial files were created
        this.refreshFiles();
      }
    });
  }

  private processExecutionResult(result: any): { stdout: string, stderr: string } {
    const stderrLines = result.stderr ? result.stderr.split('\n') : [];
    const infoMessages: string[] = [];
    const errorMessages: string[] = [];

    // Separate INFO messages from actual errors
    for (const line of stderrLines) {
      if (line.trim().startsWith('INFO:')) {
        infoMessages.push(line);
      } else if (line.trim()) {
        errorMessages.push(line);
      }
    }

    // Combine original stdout with INFO messages
    let combinedStdout = result.stdout || '';
    if (infoMessages.length > 0) {
      combinedStdout += (combinedStdout ? '\n' : '') + infoMessages.join('\n');
    }

    // Only keep non-INFO messages in stderr
    const cleanedStderr = errorMessages.join('\n');

    return {
      stdout: combinedStdout,
      stderr: cleanedStderr
    };
  }

  hasRequirementsFile(): boolean {
    return this.fileTree.some(node => 
      node.name === 'requirements.txt' || 
      (node.children && this.hasRequirementsInChildren(node.children))
    );
  }

  private hasRequirementsInChildren(children: FileNode[]): boolean {
    return children.some(child => 
      child.name === 'requirements.txt' || 
      (child.children && this.hasRequirementsInChildren(child.children))
    );
  }

  getFileIcon(node: FileNode): string {
    if (node.isDirectory) {
      return node.expanded ? 'fas fa-folder-open' : 'fas fa-folder';
    }
    
    const extension = node.name.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'py':
        return 'fab fa-python';
      case 'sql':
        return 'fas fa-database';
      case 'txt':
      case 'log':
        return 'fas fa-file-alt';
      case 'csv':
        return 'fas fa-file-csv';
      case 'json':
        return 'fas fa-file-code';
      case 'md':
        return 'fas fa-file-alt';
      case 'db':
        return 'fas fa-database';
      case 'png':
      case 'jpg':
      case 'jpeg':
      case 'gif':
      case 'svg':
        return 'fas fa-image';
      default:
        return 'fas fa-file';
    }
  }

  // Check if file can be viewed as code
  isViewableFile(fileName: string): boolean {
    const extension = fileName.split('.').pop()?.toLowerCase();
    return ['py', 'sql', 'txt', 'log', 'md', 'json', 'csv'].includes(extension || '');
  }

  // Check if file should have a download button (AI-created files)
  isDownloadableFile(fileName: string): boolean {
    const extension = fileName.split('.').pop()?.toLowerCase();
    return ['py', 'sql', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'csv', 'txt', 'log', 'json', 'html', 'pdf', 'db'].includes(extension || '');
  }

  // Check if file is a database file
  isDatabaseFile(fileName: string): boolean {
    return fileName.toLowerCase().endsWith('.db');
  }

  // View file content in modal
  viewFileContent(filePath: string) {
    console.log('Viewing file content:', filePath);
    this.apiService.getFileContent(filePath).subscribe({
      next: (response) => {
        this.viewerFileContent = response.content;
        this.originalFileContent = response.content; // Store original for cancel functionality
        this.viewerFileName = filePath.split('/').pop() || filePath;
        this.viewerFileType = this.viewerFileName.split('.').pop()?.toLowerCase() || '';
        this.viewerFilePath = filePath;
        this.isEditMode = false; // Start in view mode
        this.showCodeViewer = true;
      },
      error: (error) => {
        console.error('Error loading file content:', error);
        alert(`Error loading file: ${error.message || 'Unknown error'}`);
      }
    });
  }

  // Download file
  downloadFile(filePath: string) {
    console.log('Downloading file:', filePath);
    const downloadUrl = `http://localhost:8001/files/${encodeURIComponent(filePath)}/download`;
    
    // Create a temporary link and click it to trigger download
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filePath.split('/').pop() || filePath;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  }

  // Close code viewer modal
  closeCodeViewer() {
    // Check if there are unsaved changes
    if (this.isEditMode && this.viewerFileContent !== this.originalFileContent) {
      if (!confirm('You have unsaved changes. Are you sure you want to close?')) {
        return;
      }
    }
    
    this.showCodeViewer = false;
    this.viewerFileContent = '';
    this.viewerFileName = '';
    this.viewerFileType = '';
    this.viewerFilePath = '';
    this.isEditMode = false;
    this.originalFileContent = '';
    this.isSaving = false;
  }

  // Get syntax highlighting class for code viewer
  getCodeViewerClass(): string {
    switch (this.viewerFileType) {
      case 'py':
        return 'language-python';
      case 'json':
        return 'language-json';
      case 'csv':
        return 'language-csv';
      case 'md':
        return 'language-markdown';
      case 'log':
        return 'language-log';
      default:
        return 'language-text';
    }
  }

  // Check if file is editable (exclude binary files and logs)
  isEditableFile(fileName: string): boolean {
    const extension = fileName.split('.').pop()?.toLowerCase();
    return ['py', 'txt', 'md', 'json', 'csv'].includes(extension || '');
  }

  // Toggle edit mode
  toggleEditMode() {
    this.isEditMode = !this.isEditMode;
    if (!this.isEditMode) {
      // When switching back to view mode, reset content if not saved
      if (this.viewerFileContent !== this.originalFileContent) {
        if (confirm('Discard changes and return to view mode?')) {
          this.viewerFileContent = this.originalFileContent;
        } else {
          this.isEditMode = true; // Stay in edit mode
        }
      }
    }
  }

  // Save file changes
  saveFileChanges() {
    if (!this.viewerFilePath || !this.isEditMode) {
      return;
    }

    this.isSaving = true;
    this.apiService.updateFile(this.viewerFilePath, this.viewerFileContent).subscribe({
      next: (response) => {
        console.log('File saved successfully:', response);
        this.originalFileContent = this.viewerFileContent; // Update original content
        this.isEditMode = false; // Switch back to view mode
        this.isSaving = false;
        
        // Show success message
        alert('File saved successfully!');
        
        // Refresh file list to update any changes
        this.loadFiles();
      },
      error: (error) => {
        console.error('Error saving file:', error);
        this.isSaving = false;
        alert(`Error saving file: ${error.error?.detail || error.message || 'Unknown error'}`);
      }
    });
  }

  // Cancel edit mode and revert changes
  cancelEdit() {
    if (this.viewerFileContent !== this.originalFileContent) {
      if (confirm('Discard all changes?')) {
        this.viewerFileContent = this.originalFileContent;
        this.isEditMode = false;
      }
    } else {
      this.isEditMode = false;
    }
  }

  // Check if content has changed
  hasUnsavedChanges(): boolean {
    return this.isEditMode && this.viewerFileContent !== this.originalFileContent;
  }

  isImageFile(fileName: string): boolean {
    const imageExtensions = ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.bmp'];
    return imageExtensions.some(ext => fileName.toLowerCase().endsWith(ext));
  }

  displayImage(filePath: string) {
    // Create an output file object for the execution service
    const fileName = filePath.split('/').pop() || filePath;
    const outputFile = {
      filename: fileName,
      path: filePath,
      url: `/files/${encodeURIComponent(filePath)}/download`,
      type: 'image'
    };

    // Emit an execution result with just this image
    this.executionService.emitExecutionResult({
      command: `Display: ${fileName}`,
      output: '',
      error: '',
      returnCode: 0,
      outputFiles: [outputFile]
    });
  }

  deleteFile(filePath: string) {
    if (!filePath) {
      return;
    }

    const confirmDelete = confirm(`Are you sure you want to delete ${filePath}? This action cannot be undone.`);
    if (!confirmDelete) {
      return;
    }

    // Get the filename to remove from query groups
    const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || filePath;

    this.apiService.deleteFile(filePath).subscribe({
      next: (response) => {
        console.log('File deleted:', response);
        
        // Remove the file from any query groups that contain it
        const queryGroup = this.findQueryGroupForFile(filePath);
        if (queryGroup) {
          this.queryFileOrganizer.removeFilesFromQueryGroup(queryGroup.queryId, [fileName]);
        }
        
        // Refresh file list after deletion
        this.refreshFiles();
      },
      error: (error) => {
        console.error('Error deleting file:', error);
        alert(`Error deleting file: ${error.error?.detail || error.message || 'Unknown error'}`);
      }
    });
  }

  // Get scenario display name for context
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

  removeQueryGroup(queryId: string): void {
    this.queryFileOrganizer.removeQueryGroup(queryId);
    // Refresh the query groups and trigger cleanup
    this.refreshQueryGroups();
  }

  /**
   * Find the query group that contains the specified file
   */
  private findQueryGroupForFile(filePath: string): QueryFileGroup | null {
    const fileName = filePath.split('/').pop() || filePath.split('\\').pop() || filePath;
    
    // Use the service method to find the query group
    return this.queryFileOrganizer.findQueryGroupByFile(fileName);
  }

  /**
   * Add new output files to the appropriate query group
   */
  private addOutputFilesToQueryGroup(filePath: string, outputFiles: any[], queryGroup: QueryFileGroup | null): void {
    if (!queryGroup) {
      console.log('No query group found for file:', filePath);
      return;
    }

    // Extract file names from output files
    const newFileNames = outputFiles.map((file: any) => {
      if (typeof file === 'string') {
        return file;
      } else if (file && typeof file === 'object' && file.filename) {
        return file.filename;
      }
      return null;
    }).filter((name: string | null) => name !== null);

    if (newFileNames.length > 0) {
      console.log('Adding new files to existing query group:', newFileNames);
      
      // Add the new files to the existing query group using the query ID
      const success = this.queryFileOrganizer.addFilesToExistingQueryGroup(
        queryGroup.queryId,
        newFileNames
      );
      
      if (success) {
        console.log('Successfully added files to existing query group');
        // Refresh the query groups display
        this.refreshQueryGroups();
      } else {
        console.log('Failed to add files to existing query group');
      }
    }
  }
} 