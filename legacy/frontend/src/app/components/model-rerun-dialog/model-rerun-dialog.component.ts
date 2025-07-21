import { Component, OnInit, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { DatabaseTrackingService } from '../../services/database-tracking.service';

interface ModelRerunRequest {
  id: string;
  change_description: string;
  available_models: string[];
  recommended_model?: string;
  timestamp: Date;
  status: 'pending' | 'approved' | 'rejected';
  selected_model?: string;
}

interface AvailableModel {
  filename: string;
  type: 'runall' | 'main' | 'model' | 'other';
  description: string;
  highlighted: boolean;
}

@Component({
  selector: 'app-model-rerun-dialog',
  templateUrl: './model-rerun-dialog.component.html',
  styleUrls: ['./model-rerun-dialog.component.css']
})
export class ModelRerunDialogComponent implements OnInit, OnDestroy {
  currentRequest: ModelRerunRequest | null = null;
  availableModels: AvailableModel[] = [];
  selectedModel: string = '';
  showDialog: boolean = false;

  private requestSubscription: Subscription = new Subscription();
  private modelsSubscription: Subscription = new Subscription();

  constructor(private databaseTrackingService: DatabaseTrackingService) {}

  ngOnInit(): void {
    // Subscribe to rerun requests
    this.requestSubscription = this.databaseTrackingService.getRerunRequest().subscribe(
      (request: ModelRerunRequest | null) => {
        this.currentRequest = request;
        this.showDialog = request !== null && request.status === 'pending';
        
        if (request && request.recommended_model) {
          this.selectedModel = request.recommended_model;
        }
      }
    );

    // Subscribe to available models
    this.modelsSubscription = this.databaseTrackingService.getAvailableModels().subscribe(
      (models: AvailableModel[]) => {
        this.availableModels = models;
      }
    );
  }

  ngOnDestroy(): void {
    this.requestSubscription.unsubscribe();
    this.modelsSubscription.unsubscribe();
  }

  onModelSelect(model: AvailableModel): void {
    this.selectedModel = model.filename;
  }

  onApprove(): void {
    if (this.selectedModel) {
      this.databaseTrackingService.approveModelRerun(this.selectedModel);
      this.showDialog = false;
    }
  }

  onReject(): void {
    this.databaseTrackingService.rejectModelRerun();
    this.showDialog = false;
  }

  onCancel(): void {
    this.databaseTrackingService.clearRerunRequest();
    this.showDialog = false;
  }

  isModelSelected(model: AvailableModel): boolean {
    return this.selectedModel === model.filename;
  }

  getModelTypeIcon(type: string): string {
    switch (type) {
      case 'runall': return '🔄';
      case 'main': return '🎯';
      case 'model': return '🧠';
      default: return '📄';
    }
  }

  getModelTypeBadgeClass(type: string): string {
    switch (type) {
      case 'runall': return 'badge-runall';
      case 'main': return 'badge-main';
      case 'model': return 'badge-model';
      default: return 'badge-other';
    }
  }
} 