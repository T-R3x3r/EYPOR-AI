import { Component, OnInit, OnDestroy, Output, EventEmitter } from '@angular/core';
import { FormBuilder, FormGroup, Validators } from '@angular/forms';
import { Subject, takeUntil } from 'rxjs';
import { ScenarioService } from '../../services/scenario.service';
import { Scenario } from '../../models/scenario.model';

@Component({
  selector: 'app-create-scenario-dialog',
  templateUrl: './create-scenario-dialog.component.html',
  styleUrls: ['./create-scenario-dialog.component.css']
})
export class CreateScenarioDialogComponent implements OnInit, OnDestroy {
  @Output() dialogClosed = new EventEmitter<void>();
  
  scenarioForm: FormGroup;
  currentScenario: Scenario | null = null;
  isLoading = false;
  errorMessage = '';
  
  private destroy$ = new Subject<void>();

  constructor(
    private formBuilder: FormBuilder,
    private scenarioService: ScenarioService
  ) {
    this.scenarioForm = this.formBuilder.group({
      name: ['', [Validators.required, Validators.minLength(1), Validators.maxLength(100)]],
      description: ['', [Validators.maxLength(500)]],
      creationType: ['scratch', Validators.required]
    });
  }

  ngOnInit(): void {
    // Subscribe to current scenario for branching option
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

  // Form validation helpers
  get nameControl() {
    return this.scenarioForm.get('name');
  }

  get descriptionControl() {
    return this.scenarioForm.get('description');
  }

  get creationTypeControl() {
    return this.scenarioForm.get('creationType');
  }

  get isNameInvalid(): boolean {
    return this.nameControl ? 
      (this.nameControl.invalid && (this.nameControl.dirty || this.nameControl.touched)) : false;
  }

  get isDescriptionInvalid(): boolean {
    return this.descriptionControl ? 
      (this.descriptionControl.invalid && (this.descriptionControl.dirty || this.descriptionControl.touched)) : false;
  }

  get canCreateFromCurrent(): boolean {
    return this.currentScenario !== null && !this.currentScenario.is_base_scenario;
  }

  // Create scenario
  async createScenario(): Promise<void> {
    if (this.scenarioForm.invalid) {
      this.markFormGroupTouched();
      return;
    }

    this.isLoading = true;
    this.errorMessage = '';

    try {
      const formValue = this.scenarioForm.value;
      const scenarioData: any = {
        name: formValue.name.trim(),
        description: formValue.description.trim() || undefined
      };

      if (formValue.creationType === 'branch' && this.currentScenario) {
        scenarioData.base_scenario_id = this.currentScenario.id;
      }

      const newScenario = await this.scenarioService.createScenario(scenarioData).toPromise();
      
      console.log('Scenario created successfully:', newScenario);
      this.closeDialog();
      
    } catch (error: any) {
      console.error('Error creating scenario:', error);
      this.errorMessage = error.error?.detail || error.message || 'Failed to create scenario';
    } finally {
      this.isLoading = false;
    }
  }

  // Cancel creation
  cancel(): void {
    this.closeDialog();
  }

  // Close dialog
  closeDialog(): void {
    this.dialogClosed.emit();
  }

  // Mark all form controls as touched to trigger validation display
  private markFormGroupTouched(): void {
    Object.keys(this.scenarioForm.controls).forEach(key => {
      const control = this.scenarioForm.get(key);
      control?.markAsTouched();
    });
  }

  // Handle keyboard events
  onKeyDown(event: KeyboardEvent): void {
    if (event.key === 'Escape') {
      this.cancel();
    } else if (event.key === 'Enter' && event.ctrlKey) {
      this.createScenario();
    }
  }

  // Get creation type description
  getCreationTypeDescription(type: string): string {
    switch (type) {
      case 'scratch':
        return 'Start with a clean slate - no data or modifications from other scenarios';
      case 'branch':
        return `Create a copy of the current scenario "${this.currentScenario?.name}" with all its data and modifications`;
      default:
        return '';
    }
  }

  // Get current scenario name for display
  getCurrentScenarioName(): string {
    return this.currentScenario?.name || 'Unknown Scenario';
  }
} 