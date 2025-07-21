import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subject, takeUntil } from 'rxjs';
import { ScenarioService } from '../../services/scenario.service';
import { Scenario } from '../../models/scenario.model';

@Component({
  selector: 'app-scenario-management',
  templateUrl: './scenario-management.component.html',
  styleUrls: ['./scenario-management.component.css']
})
export class ScenarioManagementComponent implements OnInit, OnDestroy {
  scenarios: Scenario[] = [];
  currentScenario: Scenario | null = null;
  selectedScenarios: Set<number> = new Set();
  showDeleteConfirm = false;
  showComparisonView = false;
  comparisonScenarios: Scenario[] = [];
  isLoading = false;
  errorMessage = '';
  
  // View modes
  viewMode: 'list' | 'grid' | 'details' = 'list';
  sortBy: 'name' | 'created' | 'modified' = 'name';
  sortOrder: 'asc' | 'desc' = 'asc';
  
  // Filter options
  filterType: 'all' | 'base' | 'branch' = 'all';
  searchTerm = '';
  
  private destroy$ = new Subject<void>();

  constructor(public scenarioService: ScenarioService) {}

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

  // Selection management
  toggleScenarioSelection(scenarioId: number): void {
    if (this.selectedScenarios.has(scenarioId)) {
      this.selectedScenarios.delete(scenarioId);
    } else {
      this.selectedScenarios.add(scenarioId);
    }
  }

  selectAllScenarios(): void {
    this.filteredScenarios.forEach(scenario => {
      this.selectedScenarios.add(scenario.id);
    });
  }

  deselectAllScenarios(): void {
    this.selectedScenarios.clear();
  }

  get isAllSelected(): boolean {
    return this.filteredScenarios.length > 0 && 
           this.filteredScenarios.every(s => this.selectedScenarios.has(s.id));
  }

  get isPartiallySelected(): boolean {
    return this.selectedScenarios.size > 0 && !this.isAllSelected;
  }

  // Scenario switching
  switchToScenario(scenario: Scenario): void {
    this.scenarioService.switchScenario(scenario.id).subscribe({
      next: () => {
        console.log(`Switched to scenario: ${scenario.name}`);
      },
      error: (error) => {
        console.error('Error switching scenario:', error);
        this.errorMessage = 'Failed to switch scenario';
      }
    });
  }

  // Bulk operations
  deleteSelectedScenarios(): void {
    if (this.selectedScenarios.size === 0) return;
    
    const scenarioNames = this.scenarios
      .filter(s => this.selectedScenarios.has(s.id))
      .map(s => s.name)
      .join(', ');
    
    const confirmMessage = `Are you sure you want to delete ${this.selectedScenarios.size} scenario(s): ${scenarioNames}? This action cannot be undone.`;
    
    if (confirm(confirmMessage)) {
      this.isLoading = true;
      this.errorMessage = '';
      
      const deletePromises = Array.from(this.selectedScenarios).map(id =>
        this.scenarioService.deleteScenario(id).toPromise()
      );
      
      Promise.all(deletePromises)
        .then(() => {
          console.log('Scenarios deleted successfully');
          this.selectedScenarios.clear();
        })
        .catch(error => {
          console.error('Error deleting scenarios:', error);
          this.errorMessage = 'Failed to delete some scenarios';
        })
        .finally(() => {
          this.isLoading = false;
        });
    }
  }

  duplicateSelectedScenarios(): void {
    if (this.selectedScenarios.size === 0) return;
    
    this.isLoading = true;
    this.errorMessage = '';
    
    const duplicatePromises = Array.from(this.selectedScenarios).map(id => {
      const scenario = this.scenarios.find(s => s.id === id);
      if (!scenario) return Promise.reject('Scenario not found');
      
      return this.scenarioService.createScenario({
        name: `${scenario.name} (Copy)`,
        base_scenario_id: scenario.id,
        description: `Copy of ${scenario.name}`
      }).toPromise();
    });
    
    Promise.all(duplicatePromises)
      .then(() => {
        console.log('Scenarios duplicated successfully');
        this.selectedScenarios.clear();
      })
      .catch(error => {
        console.error('Error duplicating scenarios:', error);
        this.errorMessage = 'Failed to duplicate some scenarios';
      })
      .finally(() => {
        this.isLoading = false;
      });
  }

  // Comparison tools
  startComparison(): void {
    if (this.selectedScenarios.size < 2) {
      this.errorMessage = 'Please select at least 2 scenarios to compare';
      return;
    }
    
    this.comparisonScenarios = this.scenarios.filter(s => 
      this.selectedScenarios.has(s.id)
    );
    this.showComparisonView = true;
  }

  closeComparison(): void {
    this.showComparisonView = false;
    this.comparisonScenarios = [];
  }

  // Sorting and filtering
  get filteredScenarios(): Scenario[] {
    let filtered = this.scenarios.filter(scenario => {
      // Filter by type
      if (this.filterType === 'base' && !scenario.is_base_scenario) return false;
      if (this.filterType === 'branch' && scenario.is_base_scenario) return false;
      
      // Filter by search term
      if (this.searchTerm) {
        const searchLower = this.searchTerm.toLowerCase();
        return scenario.name.toLowerCase().includes(searchLower) ||
               (scenario.description && scenario.description.toLowerCase().includes(searchLower));
      }
      
      return true;
    });

    // Sort scenarios
    filtered.sort((a, b) => {
      let aValue: any, bValue: any;
      
      switch (this.sortBy) {
        case 'name':
          aValue = a.name.toLowerCase();
          bValue = b.name.toLowerCase();
          break;
        case 'created':
          aValue = new Date(a.created_at).getTime();
          bValue = new Date(b.created_at).getTime();
          break;
        case 'modified':
          aValue = new Date(a.modified_at).getTime();
          bValue = new Date(b.modified_at).getTime();
          break;
        default:
          return 0;
      }
      
      if (this.sortOrder === 'asc') {
        return aValue < bValue ? -1 : aValue > bValue ? 1 : 0;
      } else {
        return aValue > bValue ? -1 : aValue < bValue ? 1 : 0;
      }
    });

    return filtered;
  }

  toggleSort(field: 'name' | 'created' | 'modified'): void {
    if (this.sortBy === field) {
      this.sortOrder = this.sortOrder === 'asc' ? 'desc' : 'asc';
    } else {
      this.sortBy = field;
      this.sortOrder = 'asc';
    }
  }

  getSortIcon(field: 'name' | 'created' | 'modified'): string {
    if (this.sortBy !== field) return 'fas fa-sort';
    return this.sortOrder === 'asc' ? 'fas fa-sort-up' : 'fas fa-sort-down';
  }

  // Utility methods
  isCurrentScenario(scenario: Scenario): boolean {
    return this.currentScenario?.id === scenario.id;
  }

  isSelected(scenario: Scenario): boolean {
    return this.selectedScenarios.has(scenario.id);
  }

  getScenarioTypeLabel(scenario: Scenario): string {
    return scenario.is_base_scenario ? 'Base' : 'Branch';
  }

  getScenarioTypeClass(scenario: Scenario): string {
    return scenario.is_base_scenario ? 'base' : 'branch';
  }

  formatDate(dateString: string): string {
    return new Date(dateString).toLocaleString();
  }

  getFileSize(bytes: number): string {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  // View mode switching
  setViewMode(mode: 'list' | 'grid' | 'details'): void {
    this.viewMode = mode;
  }

  // Clear error message
  clearError(): void {
    this.errorMessage = '';
  }

  // Rename scenario with proper prompt
  renameScenario(scenario: Scenario): void {
    const newName = prompt('Enter new name:', scenario.name);
    if (newName && newName.trim() && newName !== scenario.name) {
      this.scenarioService.updateScenario(scenario.id, { name: newName.trim() }).subscribe({
        next: () => {
          console.log(`Scenario renamed to: ${newName}`);
        },
        error: (error) => {
          console.error('Error renaming scenario:', error);
          this.errorMessage = 'Failed to rename scenario';
        }
      });
    }
  }

  // Delete scenario with confirmation
  deleteScenario(scenario: Scenario): void {
    const confirmMessage = `Are you sure you want to delete scenario "${scenario.name}"? This action cannot be undone.`;
    
    if (confirm(confirmMessage)) {
      this.scenarioService.deleteScenario(scenario.id).subscribe({
        next: () => {
          console.log(`Scenario deleted: ${scenario.name}`);
        },
        error: (error) => {
          console.error('Error deleting scenario:', error);
          this.errorMessage = 'Failed to delete scenario';
        }
      });
    }
  }
} 