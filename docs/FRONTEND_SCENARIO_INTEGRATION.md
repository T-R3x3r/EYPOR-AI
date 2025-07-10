# Frontend Scenario Integration Implementation

## Overview

This document describes the implementation of scenario management in the Angular frontend, including services, state management, and integration with the backend scenario system.

## Architecture

### File Structure
```
frontend/src/app/
├── models/
│   └── scenario.model.ts          # Scenario interfaces and types
├── services/
│   ├── scenario.service.ts        # Scenario management service
│   ├── analysis-file.service.ts   # Analysis files management
│   ├── execution.service.ts       # Updated for scenario awareness
│   ├── database-tracking.service.ts # Updated for scenario awareness
│   └── api.service.ts             # Updated with scenario endpoints
```

## Implementation Details

### 1. Scenario Models (`scenario.model.ts`)

**Interfaces:**
- `Scenario`: Core scenario data structure
- `AnalysisFile`: Analysis files (SQL queries, visualization templates)
- `ExecutionHistory`: Execution history per scenario
- Request/Response interfaces for API communication

**Key Features:**
- Type-safe interfaces matching backend data structures
- Support for scenario relationships (parent-child)
- Global vs scenario-specific analysis files

### 2. Scenario Service (`scenario.service.ts`)

**Core Functionality:**
- `BehaviorSubject` for current scenario state
- `BehaviorSubject` for scenarios list
- `BehaviorSubject` for execution history
- Local storage integration for scenario persistence

**Methods:**
- `createScenario()`: Create new scenarios (base or branched)
- `switchScenario()`: Activate a different scenario
- `getScenarios()`: Fetch all scenarios
- `updateScenario()`: Update scenario metadata
- `deleteScenario()`: Remove scenario and its data
- `getExecutionHistory()`: Get execution history for scenario

**State Management:**
- Automatic scenario persistence in localStorage
- Scenario switching with execution history loading
- Reactive updates across all components

### 3. Analysis File Service (`analysis-file.service.ts`)

**Core Functionality:**
- `BehaviorSubject` for analysis files list
- Support for global and scenario-specific files
- Type-specific methods (SQL queries, visualization templates)

**Methods:**
- `getAnalysisFiles()`: Fetch all analysis files
- `createAnalysisFile()`: Create new analysis file
- `updateAnalysisFile()`: Update existing file
- `deleteAnalysisFile()`: Remove analysis file
- `getSQLQueries()`: Get SQL query files
- `getVisualizationTemplates()`: Get visualization templates

**Features:**
- Automatic file type categorization
- Global vs scenario-specific file filtering
- Integration with scenario context

### 4. Updated Execution Service (`execution.service.ts`)

**Scenario Integration:**
- Execution results include scenario context
- Scenario-specific execution history tracking
- Combined observables for current scenario data

**New Features:**
- `currentScenarioExecutionHistory$`: Observable for current scenario's history
- `getCurrentScenarioExecutionHistory()`: Get current scenario's execution history
- `refreshExecutionHistory()`: Refresh execution history for current scenario

### 5. Updated Database Tracking Service (`database-tracking.service.ts`)

**Scenario Awareness:**
- Database changes tracked per scenario
- Highlighted cells with scenario context
- Model rerun requests with scenario information

**New Features:**
- `getCurrentScenarioChanges()`: Get changes for current scenario only
- `getCurrentScenarioHighlightedCells()`: Get highlighted cells for current scenario
- Automatic highlight clearing on scenario switch

### 6. Updated API Service (`api.service.ts`)

**New Endpoints:**
- `createScenario()`: POST /scenarios/create
- `getScenarios()`: GET /scenarios/list
- `getScenario()`: GET /scenarios/{id}
- `updateScenario()`: PUT /scenarios/{id}
- `deleteScenario()`: DELETE /scenarios/{id}
- `activateScenario()`: POST /scenarios/{id}/activate
- `getCurrentScenario()`: GET /scenarios/current
- `getExecutionHistory()`: GET /scenarios/{id}/execution-history
- `getAnalysisFiles()`: GET /analysis-files/list
- `createAnalysisFile()`: POST /analysis-files/create
- `updateAnalysisFile()`: PUT /analysis-files/{id}
- `deleteAnalysisFile()`: DELETE /analysis-files/{id}

## State Management Strategy

### 1. Scenario Context
- Current scenario ID stored in localStorage
- Automatic scenario restoration on app startup
- Reactive scenario switching across all services

### 2. Data Isolation
- Each scenario maintains its own execution history
- Database changes tracked per scenario
- Analysis files can be global or scenario-specific

### 3. Service Integration
- All services subscribe to scenario changes
- Automatic data refresh on scenario switch
- Consistent scenario context across the application

## Usage Examples

### Creating a New Scenario
```typescript
this.scenarioService.createScenario({
  name: 'Test Scenario',
  base_scenario_id: 1,
  description: 'Test scenario for parameter changes'
}).subscribe(scenario => {
  console.log('Created scenario:', scenario);
});
```

### Switching Scenarios
```typescript
this.scenarioService.switchScenario(2).subscribe(scenario => {
  console.log('Switched to scenario:', scenario);
});
```

### Getting Current Scenario's Execution History
```typescript
this.executionService.currentScenarioExecutionHistory$.subscribe(history => {
  console.log('Current scenario history:', history);
});
```

### Creating Analysis Files
```typescript
this.analysisFileService.createSQLQuery(
  'test_query.sql',
  'SELECT * FROM test_data',
  true // global
).subscribe(file => {
  console.log('Created SQL query:', file);
});
```

## Integration Points

### 1. Component Integration
- Components subscribe to scenario observables
- Automatic UI updates on scenario changes
- Scenario context in all user interactions

### 2. Backend Integration
- All API calls include scenario context where needed
- Scenario-aware database operations
- Execution history logging per scenario

### 3. File Management
- Uploaded files stored in shared directory
- Scenario-specific database copies
- Analysis files shared or isolated per scenario

## Future Enhancements

### 1. Scenario Comparison
- Side-by-side scenario comparison UI
- Diff visualization for parameter changes
- Execution result comparison

### 2. Scenario Templates
- Save scenario configurations as templates
- Quick scenario creation from templates
- Template sharing between users

### 3. Advanced State Management
- NgRx integration for complex state
- Scenario undo/redo functionality
- Scenario branching visualization

## Testing Strategy

### 1. Unit Tests
- Service method testing
- Observable behavior testing
- Error handling testing

### 2. Integration Tests
- API endpoint testing
- Service interaction testing
- State management testing

### 3. E2E Tests
- Scenario creation workflow
- Scenario switching workflow
- Analysis file management workflow

## Conclusion

The frontend scenario integration provides a robust foundation for multi-scenario management with:
- Reactive state management
- Type-safe interfaces
- Comprehensive service integration
- Automatic data isolation
- Persistent scenario context

This implementation enables users to effectively manage multiple scenarios while maintaining data integrity and providing a seamless user experience. 