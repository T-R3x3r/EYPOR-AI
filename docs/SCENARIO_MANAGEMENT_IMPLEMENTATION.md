# Scenario Management Implementation (2024)

## Overview

The scenario management system in EYProject enables users to create, branch, and manage multiple scenarios, each with its own isolated database, while sharing uploaded files and analysis templates. It also supports comparison history for multi-scenario analysis.

---

## Architecture

### Directory Structure
```
EYProjectGit/
├── backend/
│   ├── scenario_manager.py         # Core scenario management logic
│   └── test_scenario_manager.py    # Automated tests for scenario management
├── scenarios/                      # Individual scenario directories (auto-created)
│   └── scenario_<timestamp>/
│       └── database.db             # Scenario-specific SQLite database
├── shared/
│   ├── uploaded_files/             # User-uploaded files (shared)
│   └── analysis_files/             # Analysis templates and queries (shared)
├── comparisons/                    # Output files from scenario comparisons
├── metadata.db                     # Central metadata and scenario registry
```

---

## Database Schema

The scenario system uses a single SQLite database (`metadata.db`) to track all scenarios, analysis files, execution history, and comparison history.

**Key Tables:**
- `scenarios`: Scenario metadata and relationships
- `analysis_files`: SQL queries, visualization templates, etc.
- `execution_history`: Command and script execution logs per scenario
- `comparison_history`: Multi-scenario comparison records

---

## Core Data Classes

### Scenario
Represents a scenario and its metadata.
- `id`, `name`, `created_at`, `modified_at`, `database_path`, `parent_scenario_id`, `is_base_scenario`, `description`
- Methods: `to_dict()`, `from_dict()`

### AnalysisFile
Represents an analysis file (SQL, visualization, etc.).
- `id`, `filename`, `file_type`, `content`, `created_at`, `created_by_scenario_id`, `is_global`
- Methods: `to_dict()`, `from_dict()`

### ExecutionHistory
Tracks execution results for a scenario.
- `id`, `scenario_id`, `command`, `output`, `error`, `timestamp`, `execution_time_ms`, `output_files`
- Methods: `to_dict()`, `from_dict()`

### ComparisonHistory
Tracks results of scenario comparisons.
- `id`, `comparison_name`, `scenario_ids`, `scenario_names`, `comparison_type`, `output_file_path`, `created_at`, `created_by_scenario_id`, `description`, `metadata`
- Methods: `to_dict()`, `from_dict()`

---

## ScenarioManager Class

The `ScenarioManager` class in `backend/scenario_manager.py` provides all scenario management operations:

- `create_scenario(name, base_scenario_id=None, description=None, original_db_path=None)`
- `switch_scenario(scenario_id)`
- `get_current_scenario()`
- `copy_database(source_scenario_id, target_scenario_id)`
- `list_scenarios()`
- `delete_scenario(scenario_id)`
- `update_scenario(scenario_id, name=None, description=None)`
- `add_execution_history(...)`, `get_execution_history(...)`
- `add_analysis_file(...)`, `get_analysis_files(...)`
- `add_comparison_history(...)`, `get_comparison_history(...)`, `delete_comparison_history(...)`
- Utility: `generate_comparison_filename(...)`, `get_comparison_file_path(...)`, `cleanup_old_comparisons(...)`

All methods are designed for robust error handling and data integrity.

---

## Usage Examples

### Basic Scenario Management
```python
from scenario_manager import ScenarioManager

manager = ScenarioManager("/path/to/EYProjectGit")

# Create a base scenario
base = manager.create_scenario("Base Scenario", description="Original")

# Branch a new scenario from base
branch = manager.create_scenario("Branch", base_scenario_id=base.id)

# Switch active scenario
manager.switch_scenario(branch.id)

# List all scenarios
scenarios = manager.list_scenarios()

# Delete a scenario
manager.delete_scenario(branch.id)
```

### Execution History
```python
manager.add_execution_history(
    scenario_id=base.id,
    command="python model.py",
    output="Success",
    error=None,
    execution_time_ms=1200
)
history = manager.get_execution_history(base.id)
```

### Analysis Files
```python
manager.add_analysis_file(
    filename="query.sql",
    file_type="sql_query",
    content="SELECT * FROM table;",
    is_global=True
)
files = manager.get_analysis_files()
```

### Comparison History
```python
manager.add_comparison_history(
    comparison_name="Base vs Branch",
    scenario_ids=[base.id, branch.id],
    scenario_names=[base.name, branch.name],
    comparison_type="table",
    output_file_path="comparisons/base_vs_branch.html",
    description="Comparison of key metrics"
)
comparisons = manager.get_comparison_history()
```

---

## Integration Points

- **Backend API**: ScenarioManager is used by FastAPI endpoints to provide scenario CRUD, history, and comparison features to the frontend.
- **Frontend**: Scenario management UI (tabs, dialogs, etc.) interacts with backend endpoints to create, switch, and manage scenarios.
- **Agent**: All database operations, file edits, and visualizations are routed through the current scenario context.

---

## Testing

A comprehensive test script (`backend/test_scenario_manager.py`) verifies:
- Scenario creation, branching, and deletion
- Switching and listing scenarios
- Execution and comparison history
- Analysis file management

Run tests with:
```bash
cd backend
python test_scenario_manager.py
```

---

## Performance & Security
- **Indexes**: Metadata DB uses indexes for fast queries.
- **Isolation**: Each scenario has its own database file.
- **Validation**: All operations validate input and state.
- **Cleanup**: Old comparison files can be auto-removed.
- **Access Control**: (Planned) Scenario-specific access control for multi-user environments.

---

## Error Handling
- Handles database corruption, missing files, invalid operations, and concurrent access issues gracefully.

---

## Summary

The scenario management system is the backbone of multi-scenario analysis in EYProject, supporting robust scenario creation, branching, comparison, and integration with all major features of the platform. 