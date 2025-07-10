import { Component, ViewChild, ElementRef, HostListener, OnInit, OnDestroy } from '@angular/core';
import { FileTreeComponent } from './components/file-tree/file-tree.component';
import { ThemeService } from './services/theme.service';
import { ScenarioService } from './services/scenario.service';
import { Scenario } from './models/scenario.model';
import { Subject, takeUntil } from 'rxjs';

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.css']
})
export class AppComponent implements OnInit, OnDestroy {
  title = 'EY Project';
  showFileEditor = false;
  isResizing = false;
  currentResizeHandle = '';
  activeTab = 'chat'; // Default to chat tab
  showSettings = false; // Settings menu visibility
  
  // Scenario management
  scenarios: Scenario[] = [];
  currentScenario: Scenario | null = null;
  isScenarioSwitching = false;
  showCreateScenarioDialog = false;
  
  private destroy$ = new Subject<void>();

  @ViewChild('fileTree') fileTree!: FileTreeComponent;
  @ViewChild('sidebar') sidebar!: ElementRef;
  @ViewChild('executionWindow') executionWindow!: ElementRef;

  constructor(
    public themeService: ThemeService,
    private scenarioService: ScenarioService
  ) {}

  ngOnInit(): void {
    // Subscribe to scenarios list
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
      });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
  }

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
    
    // Refresh scenarios list to show the newly created base scenario
    this.scenarioService.refreshScenarios();
  }

  refreshFileTree() {
    // Refresh the file tree when new files are created
    if (this.fileTree) {
      this.fileTree.refreshFiles();
      // Also refresh query groups to ensure they're visible
      this.fileTree.refreshQueryGroups();
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

  // Scenario management methods
  async switchScenario(scenario: Scenario): Promise<void> {
    if (this.isScenarioSwitching || scenario.id === this.currentScenario?.id) {
      return;
    }

    this.isScenarioSwitching = true;
    
    try {
      await this.scenarioService.switchScenario(scenario.id).toPromise();
      console.log(`Switched to scenario: ${scenario.name}`);
    } catch (error) {
      console.error('Error switching scenario:', error);
    } finally {
      this.isScenarioSwitching = false;
    }
  }

  createNewScenario(): void {
    this.showCreateScenarioDialog = true;
  }

  onCreateDialogClosed(): void {
    this.showCreateScenarioDialog = false;
  }

  // Utility methods for scenario display
  getScenarioDisplayName(scenario: Scenario): string {
    return scenario.name || `Scenario ${scenario.id}`;
  }

  isCurrentScenario(scenario: Scenario): boolean {
    return this.currentScenario?.id === scenario.id;
  }

  getScenarioStatus(scenario: Scenario): string {
    if (scenario.is_base_scenario) {
      return 'base';
    } else if (scenario.parent_scenario_id) {
      return 'branch';
    }
    return 'custom';
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
    
    if (scenario.is_base_scenario) {
      parts.push('Type: Base Scenario');
    } else if (scenario.parent_scenario_id) {
      parts.push(`Type: Branch from Scenario ${scenario.parent_scenario_id}`);
    }
    
    return parts.join('\n');
  }
} 