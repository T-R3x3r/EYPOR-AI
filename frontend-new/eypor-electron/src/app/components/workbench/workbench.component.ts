import { Component, OnInit, ViewChild, ElementRef, HostListener, AfterViewInit } from '@angular/core';
import { ThemeService } from '../../services/theme.service';
import { ApiService } from '../../services/api.service';
import { WorkbenchOutputComponent } from '../workbench-output/workbench-output.component';

@Component({
  selector: 'app-workbench',
  templateUrl: './workbench.component.html',
  styleUrls: ['./workbench.component.css']
})
export class WorkbenchComponent implements OnInit, AfterViewInit {
  @ViewChild('leftSidebar') leftSidebar!: ElementRef;
  @ViewChild('rightSidebar') rightSidebar!: ElementRef;
  @ViewChild('codeEditor') codeEditor!: any;
  @ViewChild('workbenchOutput') workbenchOutput!: WorkbenchOutputComponent;

  title = 'EYPOR';
  activeView: 'workbench' | 'database' | 'code-editor' = 'workbench';
  scenarios: any[] = [];
  currentScenario: any = null;
  showUploadedFiles = true;
  isResizing = false;
  resizeSide = '';
  
  // Code Editor properties
  showCodeEditor = false;
  pendingFileToOpen: { filePath: string; fileName: string } | null = null;

  constructor(
    public themeService: ThemeService,
    private apiService: ApiService
  ) {}

  ngOnInit(): void {
    try {
      // Initialize the application
      this.loadScenarios();
      console.log('Workbench component initialized');
    } catch (error) {
      console.error('Error initializing workbench:', error);
    }
  }

  ngAfterViewInit(): void {
    // Check if there's a pending file to open after the view is initialized
    if (this.pendingFileToOpen) {
      this.openFileInEditor(this.pendingFileToOpen.filePath, this.pendingFileToOpen.fileName);
      this.pendingFileToOpen = null;
    }
  }

  loadScenarios(): void {
    try {
      // Load scenarios from API
      this.apiService.getScenarios().subscribe({
        next: (scenarios: any[]) => {
          console.log('Scenarios loaded from API:', scenarios);
          
          // Convert API response to component format
          this.scenarios = scenarios.map((scenario: any) => ({
            id: scenario.id,
            name: scenario.name,
            isActive: scenario.is_base_scenario || false, // Base scenario should be active by default
            description: scenario.description,
            database_path: scenario.database_path
          }));
          
          // Set current scenario to base scenario or first scenario
          this.currentScenario = this.scenarios.find(s => s.isActive) || this.scenarios[0];
          
          console.log('Scenarios processed:', this.scenarios.length);
          console.log('Current scenario:', this.currentScenario);
        },
        error: (error: any) => {
          console.error('Error loading scenarios:', error);
          this.scenarios = [];
          this.currentScenario = null;
        }
      });
    } catch (error) {
      console.error('Error loading scenarios:', error);
      this.scenarios = [];
    }
  }

  toggleUploadedFiles(): void {
    this.showUploadedFiles = !this.showUploadedFiles;
  }

  switchView(view: 'workbench' | 'database' | 'code-editor'): void {
    this.activeView = view;
  }

  openCodeEditor(filePath: string, fileName: string): void {
    // Show code editor if not already visible
    if (!this.showCodeEditor) {
      this.showCodeEditor = true;
      this.activeView = 'code-editor';
      
      // Wait for the view to be updated, then open the file
      setTimeout(() => {
        this.openFileInEditor(filePath, fileName);
      }, 100);
    } else {
      // Code editor is already visible, open file directly
      this.openFileInEditor(filePath, fileName);
    }
  }

  private openFileInEditor(filePath: string, fileName: string): void {
    // Check if code editor is available
    if (this.codeEditor && this.codeEditor.openNewFile) {
      this.codeEditor.openNewFile(filePath, fileName);
    } else {
      // Code editor not ready yet, queue the file
      this.pendingFileToOpen = { filePath, fileName };
    }
  }

  closeCodeEditor(): void {
    this.showCodeEditor = false;
    this.activeView = 'workbench';
    this.pendingFileToOpen = null;
  }

  createNewScenario(): void {
    try {
      // TODO: Implement scenario creation
      console.log('Create new scenario');
    } catch (error) {
      console.error('Error creating scenario:', error);
    }
  }

  selectScenario(scenario: any): void {
    try {
      this.scenarios.forEach(s => s.isActive = false);
      scenario.isActive = true;
      this.currentScenario = scenario;
      console.log('Selected scenario:', scenario.name);
    } catch (error) {
      console.error('Error selecting scenario:', error);
    }
  }

  @HostListener('mousedown', ['$event'])
  onMouseDown(event: MouseEvent): void {
    const target = event.target as HTMLElement;
    if (target.classList.contains('resize-handle')) {
      this.isResizing = true;
      this.resizeSide = target.classList.contains('left-resize') ? 'left' : 'right';
      event.preventDefault();
    }
  }

  @HostListener('mousemove', ['$event'])
  onMouseMove(event: MouseEvent): void {
    if (this.isResizing) {
      if (this.resizeSide === 'left') {
        this.resizeLeftSidebar(event.clientX);
      } else if (this.resizeSide === 'right') {
        this.resizeRightSidebar(event.clientX);
      }
    }
  }

  @HostListener('mouseup')
  onMouseUp(): void {
    this.isResizing = false;
    this.resizeSide = '';
  }

  private resizeLeftSidebar(mouseX: number): void {
    if (this.leftSidebar) {
      const newWidth = Math.max(200, Math.min(500, mouseX));
      this.leftSidebar.nativeElement.style.width = `${newWidth}px`;
    }
  }

  private resizeRightSidebar(mouseX: number): void {
    if (this.rightSidebar) {
      const windowWidth = window.innerWidth;
      const newWidth = Math.max(250, Math.min(600, windowWidth - mouseX));
      this.rightSidebar.nativeElement.style.width = `${newWidth}px`;
    }
  }

  // Method to scroll workbench to show new outputs
  scrollWorkbenchToBottom(): void {
    if (this.workbenchOutput) {
      this.workbenchOutput.scrollToBottom();
    }
  }

  // Handle files created from chat
  onFilesCreated(): void {
    // Refresh user queries to show new files
    // This will be handled by the user queries component automatically
    console.log('Files created from chat, refreshing user queries');
  }
} 