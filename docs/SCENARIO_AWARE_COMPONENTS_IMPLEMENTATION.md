# Scenario-Aware Components Implementation (2024)

## Overview

This document describes how all major components in the current EYProject frontend (`frontend-new/eypor-electron`) are fully scenario-aware. Each component properly handles scenario context, maintains scenario-specific state, and provides clear visual indicators for the current scenario. All scenario state is managed by the `ScenarioService` and scenario-aware services.

---

## Scenario-Aware Components

### 1. WorkbenchOutputComponent
**Location:** `src/app/components/workbench-output/`

- Displays execution results, logs, and output files for the current scenario
- Subscribes to `ScenarioService.currentScenario$` to update output when the scenario changes
- Shows scenario name, type, and status in the output header
- Loads and displays scenario-specific execution history
- Clears output and state when switching scenarios

### 2. DatabaseViewComponent
**Location:** `src/app/components/database-view/`

- Provides a SQL database browser and query interface for the current scenario
- Subscribes to `ScenarioService.currentScenario$` to refresh database info and clear state on scenario switch
- All queries and operations are routed to the current scenario's database
- Displays scenario context in the UI header
- Maintains scenario-specific query history (future: backend integration)

### 3. ChatInterfaceComponent
**Location:** `src/app/components/chat-interface/`

- Handles chat and AI interactions for the current scenario
- Subscribes to `ScenarioService.currentScenario$` to clear chat and reset state on scenario switch
- Includes scenario context in all chat API requests
- Maintains scenario-specific chat history in memory
- Displays scenario name and type in the chat header

### 4. FileSelectionComponent
**Location:** `src/app/components/file-selection/`

- Displays and manages files for the current scenario
- Subscribes to `ScenarioService.currentScenario$` to update file lists and state
- All file operations (view, edit, run) are routed through the current scenario context
- Shows scenario context in the file selection UI

### 5. Scenario-Aware Services
- `ScenarioService`: Central state management for scenarios
- `scenario-aware-execution.service.ts`: Handles scenario-specific execution logic
- `scenario-aware-file.service.ts`: Handles scenario-specific file operations
- All API calls and backend requests include scenario context where appropriate

---

## Key Features

- **Scenario Context Display:** All major components show the current scenario name, type, and status
- **Scenario-Specific State:** Each component maintains and clears its own state when switching scenarios
- **Consistent UI:** Visual indicators and context are consistent across all scenario-aware components
- **API Integration:** All backend requests include scenario context for correct data routing
- **Performance:** Efficient state management and subscription cleanup using RxJS

---

## Benefits

- **User Experience:** Seamless scenario switching, clear context, and isolated data per scenario
- **Data Management:** Scenario-specific execution history, chat, queries, and files
- **Maintainability:** Consistent patterns and separation of concerns make it easy to extend scenario features

---

## Extensibility & Future Enhancements

- Backend integration for scenario-specific query and chat history
- Advanced scenario comparison and analytics tools
- Scenario export/import and collaboration features

---

## Summary

All major components in EYProject are now fully scenario-aware, providing a robust, consistent, and user-friendly experience for multi-scenario analysis and workflow. 