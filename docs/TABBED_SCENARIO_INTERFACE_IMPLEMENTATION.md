# Tabbed Scenario Interface Implementation (2024)

## Overview

This document describes the tabbed scenario interface in the current EYProject frontend (`frontend-new/eypor-electron`). The interface provides a seamless way to manage multiple scenarios with visual indicators, smooth transitions, and scenario-aware components. All state is managed by `ScenarioService` and scenario-aware services.

---

## Architecture

### Key Components
- **WorkbenchComponent** (`src/app/components/workbench/`):
  - Renders scenario tabs in the top bar
  - Handles scenario switching and creation
  - Provides visual indicators and context for the active scenario
- **ScenarioService** (`src/app/services/scenario.service.ts`):
  - Central state management for all scenarios
  - Provides observables for current scenario and scenario list
  - Handles all scenario CRUD operations via backend API
- **Scenario-Aware Components**:
  - `workbench-output/`: Scenario-specific execution results
  - `database-view/`: Scenario-specific SQL/database view
  - `chat-interface/`: Scenario-specific chat and AI analysis
  - `file-selection/`: Scenario-specific file management

---

## Implementation Details

### 1. Scenario Tabs in WorkbenchComponent
- Tabs are rendered from the `scenarios` array (from `ScenarioService`)
- Clicking a tab switches to that scenario and updates all scenario-aware components
- The "+" button opens the scenario creation dialog
- Active scenario is highlighted with a visual indicator
- Scenario type badges (Base, Branch, Custom) are shown on each tab
- Loading indicator appears during scenario switching

### 2. ScenarioService
- Manages all scenario state and provides observables for components
- Notifies all scenario-aware components and services on scenario switch
- Persists current scenario in localStorage for session restoration

### 3. Scenario-Aware Components
- All major components subscribe to `ScenarioService.currentScenario$`
- Each component maintains and clears its own state when switching scenarios
- Visual indicators and context are consistent across all scenario-aware components

---

## Styling and Accessibility
- Tabs are styled for clarity and accessibility, with clear active indicators and scenario type badges
- Responsive design ensures usability on desktop, tablet, and mobile
- Dark mode support is included for all scenario UI elements
- Keyboard navigation and ARIA labels are supported for accessibility

---

## User Experience
- **Scenario Switching:**
  - User clicks a scenario tab
  - Loading indicator appears
  - All components update to the new scenario context
  - Visual feedback confirms successful switch
- **Scenario Creation:**
  - User clicks the "+" button
  - Scenario creation dialog opens
  - New scenario appears in tabs and can be selected immediately
- **Visual Feedback:**
  - Hover effects, active states, and status indicators provide clear feedback

---

## Performance and Testing
- Efficient state management with RxJS and BehaviorSubjects
- Proper subscription cleanup in all components
- Unit, integration, and E2E tests cover scenario switching, tab UI, and state management

---

## Extensibility & Future Enhancements
- Scenario comparison and diff visualization tools
- Bulk scenario operations and templates
- Virtual scrolling for large numbers of scenarios
- Advanced accessibility and collaboration features

---

## Summary

The tabbed scenario interface in EYProject is fully integrated into the Workbench UI, providing robust, accessible, and user-friendly multi-scenario management. All state is managed centrally and reflected instantly across the app, enabling seamless data isolation and a smooth user experience. 