# Scenario UI Components Implementation

## Overview

This document describes the implementation of the scenario management UI components for the EYPOR application. The implementation includes three main components and updates to existing components to make them scenario-aware.

## Components Created

### 1. ScenarioTabsComponent (`src/app/components/scenario-tabs/`)

**Purpose**: Displays scenario tabs horizontally with scenario switching, context menu, and creation functionality.

**Features**:
- Horizontal tab display with active scenario highlighting
- Scenario type indicators (Base/Branch)
- Right-click context menu for rename/delete/duplicate operations
- "Create New" button integration
- Responsive design with scrollable tabs
- Tooltips with scenario metadata

**Key Methods**:
- `switchScenario()`: Switches to selected scenario
- `onScenarioRightClick()`: Handles context menu display
- `renameScenario()`, `deleteScenario()`, `duplicateScenario()`: Context menu actions
- `createNewScenario()`: Opens creation dialog

**Integration Points**:
- Uses `ScenarioService` for state management
- Integrates with `CreateScenarioDialogComponent`
- Emits events for scenario operations

### 2. CreateScenarioDialogComponent (`src/app/components/create-scenario-dialog/`)

**Purpose**: Modal dialog for creating new scenarios with form validation and creation options.

**Features**:
- Form with scenario name and description inputs
- Radio buttons for "Start from scratch" vs "Branch from current"
- Real-time validation with character counters
- Keyboard shortcuts (Ctrl+Enter to create, Esc to cancel)
- Error handling and loading states
- Responsive design

**Form Fields**:
- **Name**: Required, 1-100 characters
- **Description**: Optional, max 500 characters
- **Creation Type**: Radio selection between scratch and branch

**Key Methods**:
- `createScenario()`: Validates and creates scenario
- `markFormGroupTouched()`: Triggers validation display
- `getCreationTypeDescription()`: Provides context for creation types

### 3. ScenarioManagementComponent (`src/app/components/scenario-management/`)

**Purpose**: Comprehensive scenario management interface with list/grid/details views and bulk operations.

**Features**:
- **Multiple View Modes**: List, Grid, and Details views
- **Advanced Filtering**: By type (All/Base/Branch) and search term
- **Sorting**: By name, created date, or modified date
- **Bulk Operations**: Select multiple scenarios for delete/duplicate/compare
- **Comparison Tools**: Side-by-side scenario comparison modal
- **Responsive Design**: Adapts to different screen sizes

**View Modes**:
- **List View**: Table format with sortable columns
- **Grid View**: Card-based layout for visual browsing
- **Details View**: Expanded information for each scenario

**Bulk Operations**:
- Select all/partial selection
- Delete multiple scenarios with confirmation
- Duplicate multiple scenarios
- Compare selected scenarios

## Updated Components

### 1. AppComponent

**Changes**:
- Added `<app-scenario-tabs>` to the main layout
- Positioned scenario tabs below the header for global access

**Integration**:
```html
<!-- Scenario Tabs -->
<app-scenario-tabs></app-scenario-tabs>
```

### 2. OutputDisplayComponent

**Changes**:
- Added `ScenarioService` dependency
- Subscribes to scenario changes to clear execution history
- Resets component state when switching scenarios

**Key Updates**:
```typescript
// Subscribe to scenario changes to clear execution history when switching scenarios
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

### 3. SqlQueryComponent

**Changes**:
- Added `ScenarioService` dependency
- Refreshes database info when switching scenarios
- Clears table selection and data when switching scenarios

**Key Updates**:
```typescript
// Subscribe to scenario changes to refresh database info
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

### 4. ChatComponent

**Changes**:
- Added `ScenarioService` dependency
- Clears chat messages when switching scenarios
- Includes scenario context in AI requests
- Resets welcome message when switching scenarios

**Key Updates**:
```typescript
// Subscribe to scenario changes to clear chat when switching scenarios
this.scenarioService.currentScenario$.subscribe(scenario => {
  if (scenario) {
    // Clear chat messages when switching scenarios
    this.messages = [];
    this.addWelcomeMessage();
    this.lastMessageCount = this.messages.length;
  }
});

// Include scenario context in API requests
let scenarioId: number | undefined;
this.scenarioService.currentScenario$.subscribe(scenario => {
  scenarioId = scenario?.id;
}).unsubscribe();

this.apiService.langGraphChat(messageToSend, scenarioId).subscribe({
```

### 5. ApiService

**Changes**:
- Updated `langGraphChat()` method to accept optional `scenarioId` parameter
- Includes scenario context in LangGraph API requests

**Key Updates**:
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

## Module Updates

### AppModule

**Added Components**:
```typescript
import { ScenarioTabsComponent } from './components/scenario-tabs/scenario-tabs.component';
import { CreateScenarioDialogComponent } from './components/create-scenario-dialog/create-scenario-dialog.component';
import { ScenarioManagementComponent } from './components/scenario-management/scenario-management.component';

declarations: [
  // ... existing components
  ScenarioTabsComponent,
  CreateScenarioDialogComponent,
  ScenarioManagementComponent,
  // ... rest of components
]
```

## Styling and Design

### Design System

**Color Variables**:
- `--primary-color`: Main brand color for active states
- `--success-color`: Green for base scenarios
- `--warning-color`: Orange for branch scenarios
- `--danger-color`: Red for delete actions
- `--text-color`, `--text-muted`: Text hierarchy
- `--background-color`, `--secondary-background`: Background layers
- `--border-color`: Consistent borders

**Responsive Breakpoints**:
- **Desktop**: Full feature set with all columns visible
- **Tablet (768px)**: Simplified layouts, reduced columns
- **Mobile (480px)**: Single-column layouts, hidden elements

### Component Styling

**ScenarioTabsComponent**:
- Horizontal scrolling tabs with smooth animations
- Active indicator with bottom border
- Context menu with fade-in animation
- Hover effects and transitions

**CreateScenarioDialogComponent**:
- Modal overlay with backdrop blur
- Form validation with real-time feedback
- Radio button groups with custom styling
- Keyboard shortcut hints

**ScenarioManagementComponent**:
- Grid system for different view modes
- Sortable table headers with icons
- Bulk selection with visual feedback
- Comparison modal with responsive table

## State Management

### Scenario-Aware Components

All updated components now subscribe to `ScenarioService.currentScenario$` to:
1. **Clear component state** when switching scenarios
2. **Refresh data** from scenario-specific sources
3. **Include scenario context** in API requests
4. **Reset UI elements** to initial states

### Data Flow

1. **Scenario Switch**: User clicks scenario tab
2. **Service Update**: `ScenarioService` updates current scenario
3. **Component Reactions**: All subscribed components react to change
4. **State Reset**: Components clear their local state
5. **Data Refresh**: Components load scenario-specific data
6. **UI Update**: Interface reflects new scenario state

## Error Handling

### Form Validation

**CreateScenarioDialogComponent**:
- Required field validation
- Character limit validation
- Real-time feedback with error messages
- Disabled submit button when invalid

### API Error Handling

**Scenario Operations**:
- Network error handling
- Server error responses
- User-friendly error messages
- Retry mechanisms for failed operations

### Loading States

**Visual Feedback**:
- Loading spinners during operations
- Disabled buttons during processing
- Progress indicators for bulk operations
- Skeleton loading for data fetching

## Accessibility

### Keyboard Navigation

**ScenarioTabsComponent**:
- Tab navigation between scenarios
- Enter/Space to activate scenarios
- Context menu keyboard shortcuts

**CreateScenarioDialogComponent**:
- Tab navigation through form fields
- Ctrl+Enter to submit
- Esc to cancel
- Focus management

### Screen Reader Support

**ARIA Labels**:
- Scenario type indicators
- Action button descriptions
- Form field labels
- Error message announcements

## Performance Considerations

### Optimization Strategies

1. **Lazy Loading**: Components load data on demand
2. **Debounced Search**: Search input with 300ms delay
3. **Virtual Scrolling**: For large scenario lists (future enhancement)
4. **Caching**: Scenario data cached in service
5. **Unsubscribe**: Proper cleanup of subscriptions

### Memory Management

**Component Lifecycle**:
- Proper subscription cleanup in `ngOnDestroy`
- Event listener removal
- Reference clearing to prevent memory leaks

## Future Enhancements

### Planned Features

1. **Scenario Templates**: Pre-configured scenario setups
2. **Scenario Export/Import**: Share scenarios between users
3. **Advanced Comparison**: Visual diff tools for scenario data
4. **Scenario Analytics**: Usage statistics and insights
5. **Collaborative Scenarios**: Multi-user scenario editing

### Technical Improvements

1. **Virtual Scrolling**: For large scenario lists
2. **Offline Support**: Local scenario management
3. **Real-time Updates**: WebSocket integration for live changes
4. **Advanced Filtering**: Date ranges, tags, custom filters
5. **Bulk Import**: Import multiple scenarios from files

## Testing Strategy

### Unit Tests

**Component Testing**:
- Form validation logic
- State management
- Event handling
- Service integration

**Service Testing**:
- API method calls
- Error handling
- State updates
- Observable behavior

### Integration Tests

**User Flows**:
- Scenario creation workflow
- Scenario switching
- Bulk operations
- Error scenarios

### E2E Tests

**Critical Paths**:
- Complete scenario management workflow
- Cross-component interactions
- Responsive design validation
- Accessibility compliance

## Conclusion

The scenario UI components implementation provides a comprehensive and user-friendly interface for managing multiple scenarios within the EYPOR application. The modular design ensures maintainability and extensibility while the responsive approach guarantees a consistent experience across different devices.

The integration with existing components maintains backward compatibility while adding powerful scenario-aware functionality that enhances the overall user experience and workflow efficiency. 