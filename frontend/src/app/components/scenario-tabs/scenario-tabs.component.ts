import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';
import { ScenarioService } from '../../services/scenario.service';
import { Scenario } from '../../models/scenario.model';

@Component({
  selector: 'app-scenario-tabs',
  templateUrl: './scenario-tabs.component.html',
  styleUrls: ['./scenario-tabs.component.css']
})
export class ScenarioTabsComponent implements OnInit, OnDestroy {
  scenarios: Scenario[] = [];
  currentScenario: Scenario | null = null;
  showContextMenu = false;
  contextMenuX = 0;
  contextMenuY = 0;
  selectedScenario: Scenario | null = null;
  showCreateDialog = false;

  private destroy$ = new Subject<void>();

  constructor(private scenarioService: ScenarioService) {}

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

  // Scenario switching
  switchScenario(scenario: Scenario): void {
    this.scenarioService.switchScenario(scenario.id).subscribe({
      next: () => {
        console.log(`Switched to scenario: ${scenario.name}`);
      },
      error: (error) => {
        console.error('Error switching scenario:', error);
      }
    });
  }

  // Context menu handling
  onScenarioRightClick(event: MouseEvent, scenario: Scenario): void {
    event.preventDefault();
    this.selectedScenario = scenario;
    this.contextMenuX = event.clientX;
    this.contextMenuY = event.clientY;
    this.showContextMenu = true;
  }

  onDocumentClick(): void {
    this.showContextMenu = false;
  }

  // Context menu actions
  renameScenario(): void {
    if (this.selectedScenario) {
      const newName = prompt('Enter new scenario name:', this.selectedScenario.name);
      if (newName && newName.trim() !== '') {
        this.scenarioService.updateScenario(this.selectedScenario.id, {
          name: newName.trim()
        }).subscribe({
          next: () => {
            console.log('Scenario renamed successfully');
          },
          error: (error) => {
            console.error('Error renaming scenario:', error);
          }
        });
      }
    }
    this.showContextMenu = false;
  }

  deleteScenario(): void {
    if (this.selectedScenario) {
      const confirmDelete = confirm(
        `Are you sure you want to delete scenario "${this.selectedScenario.name}"? This action cannot be undone.`
      );
      
      if (confirmDelete) {
        this.scenarioService.deleteScenario(this.selectedScenario.id).subscribe({
          next: () => {
            console.log('Scenario deleted successfully');
          },
          error: (error) => {
            console.error('Error deleting scenario:', error);
          }
        });
      }
    }
    this.showContextMenu = false;
  }

  duplicateScenario(): void {
    if (this.selectedScenario) {
      const newName = prompt('Enter name for duplicated scenario:', `${this.selectedScenario.name} (Copy)`);
      if (newName && newName.trim() !== '') {
        this.scenarioService.createScenario({
          name: newName.trim(),
          base_scenario_id: this.selectedScenario.id,
          description: `Copy of ${this.selectedScenario.name}`
        }).subscribe({
          next: (newScenario) => {
            console.log('Scenario duplicated successfully:', newScenario);
          },
          error: (error) => {
            console.error('Error duplicating scenario:', error);
          }
        });
      }
    }
    this.showContextMenu = false;
  }

  // Create new scenario
  createNewScenario(): void {
    this.showCreateDialog = true;
  }

  onCreateDialogClosed(): void {
    this.showCreateDialog = false;
  }

  // Utility methods
  isCurrentScenario(scenario: Scenario): boolean {
    return this.currentScenario?.id === scenario.id;
  }

  getScenarioDisplayName(scenario: Scenario): string {
    return scenario.name || `Scenario ${scenario.id}`;
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