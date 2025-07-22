# Frontend Scenario Integration Implementation (2024)

## Overview

This document describes how scenario management is implemented in the current EYProject frontend (`frontend-new/eypor-electron`). Scenario state and integration are handled by the `ScenarioService`, scenario-aware services, and scenario-aware components, providing seamless multi-scenario management and data isolation.

---

## Architecture

### File Structure
```
frontend-new/eypor-electron/src/app/
├── models/
│   └── scenario.model.ts            # Scenario interfaces and types
├── services/
│   ├── scenario.service.ts          # Scenario management service
│   ├── scenario-aware-execution.service.ts # Scenario-specific execution logic
│   ├── scenario-aware-file.service.ts      # Scenario-specific file operations
│   ├── api.service.ts               # Backend API integration
│   └── ...
├── components/
│   ├── workbench/                   # Main UI with scenario tabs and switching
│   ├── create-scenario-dialog/      # Scenario creation dialog
│   ├── workbench-output/            # Scenario-aware output display
│   ├── database-view/               # Scenario-aware SQL/database view
│   ├── chat-interface/              # Scenario-aware chat
│   ├── file-selection/              # Scenario-aware file management
│   └── ...
```

---

## Implementation Details

### 1. Scenario Models (`scenario.model.ts`)
- TypeScript interfaces for `Scenario`, `AnalysisFile`, `ExecutionHistory`, and request/response types
- Match backend data structures for type safety
- Support for scenario relationships (parent/branch)

### 2. ScenarioService (`scenario.service.ts`)
- Central state management for all scenario data
- Provides observables for current scenario, scenario list, and execution history
- Handles all scenario CRUD operations via backend API
- Persists current scenario in localStorage for session restoration
- Notifies all scenario-aware components and services on scenario switch

### 3. Scenario-Aware Services
- `scenario-aware-execution.service.ts`: Handles scenario-specific execution logic and history
- `scenario-aware-file.service.ts`: Handles scenario-specific file operations
- All API calls include scenario context where needed

### 4. Scenario-Aware Components
- `workbench/`: Displays scenario tabs, handles scenario switching, and integrates scenario context across the UI
- `create-scenario-dialog/`: Modal dialog for creating new scenarios (scratch or branch)
- `workbench-output/`: Displays execution results for the current scenario
- `database-view/`: SQL/database browser for the current scenario
- `chat-interface/`: Chat and AI interactions for the current scenario
- `file-selection/`: File management for the current scenario

---

## State Management Strategy

- **Scenario Context:**
  - Current scenario is stored in localStorage and restored on app startup
  - All scenario-aware services and components subscribe to `ScenarioService.currentScenario$`
  - Scenario switching triggers data refresh and state clearing in all relevant components
- **Data Isolation:**
  - Each scenario maintains its own execution history, chat, queries, and files
  - Scenario-aware services ensure all operations are routed to the correct scenario context
- **Service Integration:**
  - All services and components reactively update on scenario changes
  - Consistent scenario context across the entire application

---

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
this.scenarioAwareExecutionService.getCurrentScenarioExecutionHistory().subscribe(history => {
  console.log('Current scenario history:', history);
});
```

---

## Integration Points

- **Component Integration:**
  - All scenario-aware components subscribe to scenario observables
  - UI updates automatically on scenario changes
  - Scenario context included in all user interactions
- **Backend Integration:**
  - All API calls include scenario context where needed
  - Scenario-aware database and file operations
  - Execution history and chat logging per scenario
- **File Management:**
  - Uploaded files are managed per scenario
  - Scenario-specific database copies and analysis files

---

## Extensibility & Future Enhancements

- Scenario comparison and diff visualization tools
- Scenario templates and quick creation
- Advanced state management (undo/redo, branching visualization)
- Collaboration and sharing features

---

## Summary

The frontend scenario integration in EYProject provides robust, reactive, and type-safe multi-scenario management. All scenario state is managed centrally and reflected instantly across the UI, enabling seamless data isolation and a smooth user experience. 