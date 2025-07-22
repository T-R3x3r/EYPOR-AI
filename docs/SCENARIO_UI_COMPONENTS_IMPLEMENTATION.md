# Scenario UI Components Implementation (2024)

## Overview

This document describes the scenario management UI in the current EYProject frontend (`frontend-new/eypor-electron`). Scenario selection, creation, and switching are integrated into the main Workbench interface, with all state managed by the `ScenarioService` and scenario creation handled by the `CreateScenarioDialogComponent`.

---

## Key Components

### 1. Scenario Tabs (in WorkbenchComponent)

**Location:** `src/app/components/workbench/workbench.component.*`

**Purpose:**
- Display all scenarios as horizontal tabs in the top bar
- Allow switching between scenarios with a click
- Show scenario type (Base/Branch/Custom) and active indicator
- Provide a "+" button to open the scenario creation dialog

**Features:**
- Responsive, scrollable tab bar
- Active scenario highlighting
- Scenario type badges (Base, Branch, Custom)
- Tooltips with scenario metadata
- Keyboard and mouse accessibility

**Implementation:**
- Tabs are rendered from the `scenarios` array (from `ScenarioService`)
- Clicking a tab calls `selectScenario(scenario)`
- The "+" button calls `createNewScenario()` to open the dialog

### 2. CreateScenarioDialogComponent

**Location:** `src/app/components/create-scenario-dialog/`

**Purpose:**
- Modal dialog for creating new scenarios (from scratch or by branching)

**Features:**
- Form with scenario name, description, and creation type (scratch/branch)
- Real-time validation and character counters
- Keyboard shortcuts (Ctrl+Enter to submit, Esc to cancel)
- Error handling and loading states

**Integration:**
- Opened from the Workbench top bar
- On submit, calls `ScenarioService.createScenario()`
- On success, updates the scenario list and switches to the new scenario

### 3. ScenarioService

**Location:** `src/app/services/scenario.service.ts`

**Purpose:**
- Central state management for all scenario data
- Provides observables for current scenario, scenario list, and execution history
- Handles all scenario CRUD operations via backend API

**Key Observables:**
- `currentScenario$`: The active scenario
- `scenariosList$`: All available scenarios
- `executionHistory$`: Execution logs for the current scenario

**Key Methods:**
- `createScenario(request)`
- `switchScenario(scenarioId)`
- `getScenarios()`, `getScenario(scenarioId)`
- `updateScenario(scenarioId, request)`
- `deleteScenario(scenarioId)`

---

## UI Integration

- The scenario tabs are always visible at the top of the Workbench.
- Scenario switching updates all scenario-aware components (database view, chat, file editor, etc.) via `ScenarioService`.
- Scenario creation dialog is modal and overlays the main UI.
- All scenario operations are reflected in real time across the app.

---

## Styling and Accessibility

- Tabs are styled for clarity and accessibility, with clear active indicators and scenario type badges.
- The dialog uses accessible form controls, ARIA labels, and keyboard navigation.
- Responsive design ensures usability on desktop, tablet, and mobile.

---

## Error Handling & Loading States

- All scenario operations show loading indicators and user-friendly error messages.
- Form validation prevents invalid submissions.
- API/network errors are caught and displayed to the user.

---

## Extensibility & Future Enhancements

- The scenario UI is modular and can be extended for features like scenario templates, import/export, analytics, and collaboration.
- Planned improvements include virtual scrolling for large scenario lists and advanced comparison tools.

---

## Summary

Scenario management in EYProject is fully integrated into the main Workbench UI, with robust state management, accessible design, and seamless user experience. All scenario operations are handled via the `ScenarioService` and reflected instantly across the app. 