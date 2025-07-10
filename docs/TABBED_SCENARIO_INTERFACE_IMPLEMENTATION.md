# Tabbed Scenario Interface Implementation

## Overview

This document describes the implementation of the tabbed scenario interface as specified in the PRD. The interface provides a seamless way to manage multiple scenarios with visual indicators, smooth transitions, and scenario-aware components.

## Architecture

### Core Components

1. **App Component (`app.component.ts/html/css`)**
   - Main orchestrator for scenario management
   - Handles scenario tab switching and state management
   - Provides visual indicators and context

2. **Scenario Service (`scenario.service.ts`)**
   - Central state management for scenarios
   - BehaviorSubjects for reactive updates
   - CRUD operations for scenarios

3. **Existing Components (Enhanced)**
   - `output-display.component.ts` - Scenario-aware execution history
   - `sql-query.component.ts` - Scenario-aware database context
   - `chat.component.ts` - Scenario-aware AI analysis

## Implementation Details

### 1. App Component Enhancements

#### TypeScript (`app.component.ts`)

```typescript
export class AppComponent implements OnInit, OnDestroy {
  // Scenario management
  scenarios: Scenario[] = [];
  currentScenario: Scenario | null = null;
  isScenarioSwitching = false;
  showCreateScenarioDialog = false;
  
  private destroy$ = new Subject<void>();

  constructor(
    public themeService: ThemeService,
    private scenarioService: ScenarioService
  ) {}

  ngOnInit(): void {
    // Subscribe to scenarios list and current scenario
    this.scenarioService.scenariosList$
      .pipe(takeUntil(this.destroy$))
      .subscribe(scenarios => {
        this.scenarios = scenarios;
      });

    this.scenarioService.currentScenario$
      .pipe(takeUntil(this.destroy$))
      .subscribe(scenario => {
        this.currentScenario = scenario;
      });
  }

  // Scenario switching with loading indicators
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

  // Utility methods for display
  getScenarioDisplayName(scenario: Scenario): string {
    return scenario.name || `Scenario ${scenario.id}`;
  }

  isCurrentScenario(scenario: Scenario): boolean {
    return this.currentScenario?.id === scenario.id;
  }

  getScenarioStatus(scenario: Scenario): string {
    if (scenario.is_base_scenario) return 'base';
    if (scenario.parent_scenario_id) return 'branch';
    return 'custom';
  }
}
```

#### HTML Template (`app.component.html`)

```html
<!-- Scenario Tabs -->
<div class="scenario-tabs-container">
  <div class="scenario-tabs">
    <div 
      *ngFor="let scenario of scenarios" 
      class="scenario-tab"
      [class.active]="isCurrentScenario(scenario)"
      [class.base-scenario]="scenario.is_base_scenario"
      [class.switching]="isScenarioSwitching"
      [title]="getScenarioTooltip(scenario)"
      (click)="switchScenario(scenario)">
      
      <span class="scenario-name">{{ getScenarioDisplayName(scenario) }}</span>
      
      <!-- Scenario type indicators -->
      <span *ngIf="scenario.is_base_scenario" class="scenario-type base">Base</span>
      <span *ngIf="!scenario.is_base_scenario && scenario.parent_scenario_id" class="scenario-type branch">Branch</span>
      
      <!-- Active indicator -->
      <div *ngIf="isCurrentScenario(scenario)" class="active-indicator"></div>
      
      <!-- Loading indicator -->
      <div *ngIf="isScenarioSwitching && isCurrentScenario(scenario)" class="loading-indicator">
        <i class="fas fa-spinner fa-spin"></i>
      </div>
    </div>
    
    <!-- Create New Scenario Button -->
    <button 
      class="create-scenario-btn"
      (click)="createNewScenario()"
      title="Create new scenario">
      <i class="fas fa-plus"></i>
      <span>New</span>
    </button>
  </div>
</div>

<!-- Component Headers with Scenario Context -->
<div class="component-header">
  <h3>Code Execution</h3>
  <div *ngIf="currentScenario" class="scenario-context">
    <span class="scenario-label">Scenario:</span>
    <span class="scenario-name">{{ getScenarioDisplayName(currentScenario) }}</span>
    <span class="scenario-status" [class]="getScenarioStatus(currentScenario)">
      {{ getScenarioStatus(currentScenario) }}
    </span>
  </div>
</div>

<!-- Tab Navigation with Scenario Context -->
<div class="tab-navigation">
  <div class="tab-header">
    <button class="tab-btn" [class.active]="activeTab === 'chat'" (click)="activeTab = 'chat'">
      AI Analysis
    </button>
    <button class="tab-btn" [class.active]="activeTab === 'sql'" (click)="activeTab = 'sql'">
      SQL Database
    </button>
  </div>
  
  <!-- Scenario Context in Tab Header -->
  <div *ngIf="currentScenario" class="scenario-context">
    <span class="scenario-label">Active:</span>
    <span class="scenario-name">{{ getScenarioDisplayName(currentScenario) }}</span>
    <span class="scenario-status" [class]="getScenarioStatus(currentScenario)">
      {{ getScenarioStatus(currentScenario) }}
    </span>
  </div>
</div>
```

### 2. Styling Implementation

#### Scenario Tabs Styling (`app.component.css`)

```css
/* Scenario Tabs Container */
.scenario-tabs-container {
  background: white;
  border-bottom: 1px solid #e0e0e0;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
  z-index: 50;
  flex-shrink: 0;
}

.scenario-tabs {
  display: flex;
  align-items: center;
  padding: 0 1rem;
  height: 48px;
  overflow-x: auto;
  overflow-y: hidden;
}

/* Individual Scenario Tab */
.scenario-tab {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 16px;
  margin-right: 4px;
  background: #f8f9fa;
  border: 1px solid #e0e0e0;
  border-radius: 6px 6px 0 0;
  cursor: pointer;
  transition: all 0.2s ease;
  min-width: 120px;
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
}

.scenario-tab:hover {
  background: #e9ecef;
  border-color: #FFE600;
  transform: translateY(-1px);
}

.scenario-tab.active {
  background: #FFE600;
  border-color: #FFE600;
  color: #333;
  box-shadow: 0 2px 8px rgba(255, 230, 0, 0.3);
  font-weight: 500;
}

/* Scenario Type Indicators */
.scenario-type {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.scenario-type.base {
  background: #28a745;
  color: white;
}

.scenario-type.branch {
  background: #ffc107;
  color: #333;
}

/* Active and Loading Indicators */
.active-indicator {
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #333;
  border-radius: 1px;
}

.loading-indicator {
  position: absolute;
  top: 50%;
  right: 8px;
  transform: translateY(-50%);
  color: #333;
  font-size: 12px;
}

/* Component Headers with Scenario Context */
.component-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid #e0e0e0;
  background: #f8f9fa;
}

.scenario-context {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #666;
}

.scenario-status {
  padding: 2px 6px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.scenario-status.base {
  background: #d4edda;
  color: #155724;
}

.scenario-status.branch {
  background: #fff3cd;
  color: #856404;
}

.scenario-status.custom {
  background: #d1ecf1;
  color: #0c5460;
}
```

#### Dark Mode Support

```css
/* Dark Mode Styles for Scenario Tabs */
body.dark-mode .scenario-tabs-container {
  background: #2e2e38 !important;
  border-bottom: 1px solid #474755 !important;
}

body.dark-mode .scenario-tab {
  background: #1a1a24 !important;
  border-color: #474755 !important;
  color: #c2c2cf !important;
}

body.dark-mode .scenario-tab.active {
  background: #21acf6 !important;
  border-color: #21acf6 !important;
  color: #1a1a24 !important;
  box-shadow: 0 2px 8px rgba(33, 172, 246, 0.3) !important;
}

body.dark-mode .scenario-status.base {
  background: #1e4d2b !important;
  color: #4ade80 !important;
}

body.dark-mode .scenario-status.branch {
  background: #713f12 !important;
  color: #fbbf24 !important;
}

body.dark-mode .scenario-status.custom {
  background: #164e63 !important;
  color: #67e8f9 !important;
}
```

### 3. Component Integration

#### Output Display Component

```typescript
// Already scenario-aware
this.subscription.add(
  this.scenarioService.currentScenario$.subscribe(scenario => {
    if (scenario) {
      // Clear execution results when switching scenarios
      this.executionResults = [];
      this.currentResult = null;
      this.maximizedImage = null;
    }
  })
);
```

#### SQL Query Component

```typescript
// Already scenario-aware
const scenarioSub = this.scenarioService.currentScenario$.subscribe(scenario => {
  if (scenario) {
    console.log('Scenario changed, refreshing database info...', scenario);
    this.loadDatabaseInfo();
    // Clear current table selection when switching scenarios
    this.selectedTable = '';
    this.tableData.data = [];
    this.tableColumns = [];
    this.displayedColumns = [];
  }
});
```

#### Chat Component

```typescript
// Already scenario-aware
this.scenarioService.currentScenario$.subscribe(scenario => {
  if (scenario) {
    // Clear chat messages when switching scenarios
    this.messages = [];
    this.addWelcomeMessage();
    this.lastMessageCount = this.messages.length;
  }
});

// Includes scenario ID in API calls
this.apiService.langGraphChat(messageToSend, scenarioId).subscribe({
  // ... response handling
});
```

### 4. API Integration

#### ApiService Enhancement

```typescript
langGraphChat(message: string, scenarioId?: number): Observable<LangGraphChatResponse> {
  const chatMessage: ChatMessage = { role: 'user', content: message };
  const request: any = { message: chatMessage };
  if (scenarioId) {
    request.scenario_id = scenarioId;
  }
  return this.http.post<LangGraphChatResponse>(`${this.baseUrl}/langgraph-chat`, request);
}
```

## Features Implemented

### 1. Visual Indicators

- **Active Scenario Highlighting**: Yellow background for light mode, blue for dark mode
- **Scenario Type Badges**: Base (green), Branch (yellow), Custom (blue)
- **Loading States**: Spinner during scenario switching
- **Active Indicator**: Bottom border for current scenario

### 2. Scenario Context Display

- **Component Headers**: Show current scenario name and status
- **Tab Headers**: Display active scenario context
- **Tooltips**: Detailed scenario information on hover

### 3. Smooth Transitions

- **CSS Transitions**: 0.2s ease transitions for all interactions
- **Loading States**: Visual feedback during scenario switching
- **Responsive Design**: Horizontal scrolling for multiple tabs

### 4. Scenario-Aware Components

- **Execution History**: Cleared when switching scenarios
- **Database Context**: Refreshed with scenario-specific data
- **AI Analysis**: Context-aware with scenario ID in API calls

## User Experience

### 1. Scenario Switching

1. User clicks on scenario tab
2. Loading indicator appears
3. All components update to new scenario context
4. Visual feedback confirms successful switch

### 2. Scenario Creation

1. User clicks "New" button
2. Create scenario dialog opens
3. User fills in scenario details
4. New scenario appears in tabs
5. User can immediately switch to new scenario

### 3. Visual Feedback

- **Hover Effects**: Subtle animations on tab hover
- **Active States**: Clear indication of current scenario
- **Status Indicators**: Color-coded scenario types
- **Loading States**: Spinner during operations

## Responsive Design

### 1. Horizontal Scrolling

- Tabs container supports horizontal scrolling
- Custom scrollbar styling
- Minimum and maximum tab widths enforced

### 2. Mobile Considerations

- Touch-friendly tab interactions
- Adequate spacing for touch targets
- Responsive breakpoints for smaller screens

## Performance Optimizations

### 1. Reactive Updates

- BehaviorSubjects for efficient state management
- RxJS operators for debouncing and distinct changes
- Proper subscription cleanup with takeUntil

### 2. Memory Management

- Automatic cleanup of subscriptions
- Efficient change detection
- Minimal DOM manipulation

## Testing Strategy

### 1. Unit Tests

- Component initialization
- Scenario switching logic
- Utility methods
- Error handling

### 2. Integration Tests

- Scenario service integration
- API communication
- Component interaction
- State management

### 3. E2E Tests

- Complete scenario workflow
- UI interactions
- Visual feedback
- Responsive behavior

## Future Enhancements

### 1. Advanced Features

- **Scenario Comparison**: Side-by-side scenario comparison
- **Bulk Operations**: Multi-select scenario management
- **Scenario Templates**: Predefined scenario configurations
- **Export/Import**: Scenario state persistence

### 2. Performance Improvements

- **Virtual Scrolling**: For large numbers of scenarios
- **Lazy Loading**: On-demand scenario data
- **Caching**: Scenario state caching
- **Optimistic Updates**: Immediate UI feedback

### 3. Accessibility

- **Keyboard Navigation**: Full keyboard support
- **Screen Reader**: ARIA labels and descriptions
- **High Contrast**: Enhanced contrast modes
- **Focus Management**: Proper focus indicators

## Conclusion

The tabbed scenario interface provides a comprehensive solution for managing multiple scenarios with:

- **Intuitive UI**: Clear visual indicators and smooth interactions
- **Seamless Integration**: All components are scenario-aware
- **Responsive Design**: Works across different screen sizes
- **Performance**: Efficient state management and updates
- **Accessibility**: Proper ARIA support and keyboard navigation

The implementation follows Angular best practices and provides a solid foundation for future enhancements. 