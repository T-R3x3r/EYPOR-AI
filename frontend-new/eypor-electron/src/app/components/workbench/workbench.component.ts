import { Component, OnInit, ViewChild, ElementRef, HostListener, AfterViewInit, OnDestroy } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';
import { ThemeService } from '../../services/theme.service';
import { ApiService } from '../../services/api.service';
import { DatabaseService } from '../../services/database.service';
import { ScenarioService } from '../../services/scenario.service';
import { WorkbenchOutputComponent } from '../workbench-output/workbench-output.component';
import { Scenario } from '../../models/scenario.model';

@Component({
  selector: 'app-workbench',
  templateUrl: './workbench.component.html',
  styleUrls: ['./workbench.component.css']
})
export class WorkbenchComponent implements OnInit, AfterViewInit, OnDestroy {
  @ViewChild('leftSidebar') leftSidebar!: ElementRef;
  @ViewChild('rightSidebar') rightSidebar!: ElementRef;
  @ViewChild('codeEditor') codeEditor!: any;
  @ViewChild('workbenchOutput') workbenchOutput!: WorkbenchOutputComponent;

  title = 'EYPOR';
  activeView: 'workbench' | 'database' | 'code-editor' = 'workbench';
  scenarios: Scenario[] = [];
  currentScenario: Scenario | null = null;
  showUploadedFiles = true;
  isResizing = false;
  resizeSide = '';
  showCreateDialog = false;
  
  // Code Editor properties
  showCodeEditor = false;
  pendingFileToOpen: { filePath: string; fileName: string } | null = null;

  private destroy$ = new Subject<void>();

  constructor(
    public themeService: ThemeService,
    private apiService: ApiService,
    private databaseService: DatabaseService,
    private scenarioService: ScenarioService
  ) {}

  ngOnInit(): void {
    try {
      // Subscribe to scenarios from scenario service
      this.scenarioService.scenariosList$
        .pipe(takeUntil(this.destroy$))
        .subscribe(scenarios => {
          this.scenarios = scenarios;
        });

      // Subscribe to current scenario
      this.scenarioService.currentScenario$
        .pipe(takeUntil(this.destroy$))
        .subscribe(scenario => {
          this.currentScenario = scenario;
          if (scenario) {
            this.databaseService.setCurrentScenario(scenario);
          }
        });

      console.log('Workbench component initialized');
    } catch (error) {
      console.error('Error initializing workbench:', error);
    }
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

  ngAfterViewInit(): void {
    // Check if there's a pending file to open after the view is initialized
    if (this.pendingFileToOpen) {
      this.openFileInEditor(this.pendingFileToOpen.filePath, this.pendingFileToOpen.fileName);
      this.pendingFileToOpen = null;
    }
  }

  // Scenario management methods
  createNewScenario(): void {
    this.showCreateDialog = true;
  }

  onCreateDialogClosed(): void {
    this.showCreateDialog = false;
  }

  selectScenario(scenario: Scenario): void {
    try {
      this.scenarioService.switchScenario(scenario.id).subscribe({
        next: () => {
          console.log('Switched to scenario:', scenario.name);
        },
        error: (error) => {
          console.error('Error switching scenario:', error);
        }
      });
    } catch (error) {
      console.error('Error selecting scenario:', error);
    }
  }

  isCurrentScenario(scenario: Scenario): boolean {
    return this.currentScenario?.id === scenario.id;
  }

  getScenarioTooltip(scenario: Scenario): string {
    const parts = [
      `Name: ${scenario.name}`,
      `Created: ${new Date(scenario.created_at).toLocaleString()}`,
      `Modified: ${new Date(scenario.modified_at).toLocaleString()}`
    ];
    
    if (scenario.description) {
      parts.push(`Description: ${scenario.description}`);
    }
    
    // Use the new scenario type detection logic
    const scenarioType = this.scenarioService.getScenarioTypeDisplay(scenario);
    parts.push(`Type: ${scenarioType} Scenario`);
    
    return parts.join('\n');
  }

  // Helper method to get scenario type for template
  getScenarioType(scenario: Scenario): string {
    return this.scenarioService.getScenarioTypeDisplay(scenario);
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