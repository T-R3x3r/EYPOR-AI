# Scenario Management Implementation

## Overview

This document describes the implementation of the core scenario management system for the EYProject application. The system allows users to create and manage multiple scenarios, each with its own database state while sharing uploaded files and analysis templates.

## Architecture

### File Structure
```
backend/
├── scenario_manager.py          # Core scenario management classes
├── test_scenario_manager.py     # Test script for verification
└── main.py                      # FastAPI application (to be updated)

project_root/
├── scenarios/                   # Individual scenario directories
│   ├── scenario_20250708_202115/
│   │   └── database.db         # Scenario-specific database
│   └── scenario_20250708_202116/
│       └── database.db
├── shared/                      # Shared resources across scenarios
│   ├── uploaded_files/         # Original uploaded files
│   └── analysis_files/         # Analysis templates and queries
└── metadata.db                 # Scenario metadata database
```

### Database Schema

#### scenarios table
```sql
CREATE TABLE scenarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    database_path TEXT NOT NULL,
    parent_scenario_id INTEGER,
    is_base_scenario BOOLEAN DEFAULT FALSE,
    description TEXT,
    FOREIGN KEY (parent_scenario_id) REFERENCES scenarios(id)
);
```

#### analysis_files table
```sql
CREATE TABLE analysis_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by_scenario_id INTEGER,
    is_global BOOLEAN DEFAULT TRUE,
    FOREIGN KEY (created_by_scenario_id) REFERENCES scenarios(id)
);
```

#### execution_history table
```sql
CREATE TABLE execution_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id INTEGER NOT NULL,
    command TEXT NOT NULL,
    output TEXT,
    error TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    execution_time_ms INTEGER,
    FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
);
```

## Core Classes

### Scenario
Represents a scenario with its metadata and state.

**Properties:**
- `id`: Unique identifier
- `name`: Human-readable name
- `created_at`: Creation timestamp
- `modified_at`: Last modification timestamp
- `database_path`: Path to scenario-specific database
- `parent_scenario_id`: ID of parent scenario (for branching)
- `is_base_scenario`: Whether this is a base scenario
- `description`: Optional description

**Methods:**
- `to_dict()`: Convert to dictionary for JSON serialization
- `from_dict(data)`: Create from dictionary

### AnalysisFile
Represents an analysis file (SQL query, visualization template, etc.).

**Properties:**
- `id`: Unique identifier
- `filename`: File name
- `file_type`: Type of analysis file ('sql_query', 'visualization_template', etc.)
- `content`: File content
- `created_at`: Creation timestamp
- `created_by_scenario_id`: ID of scenario that created it
- `is_global`: Whether file is shared across all scenarios

### ExecutionHistory
Represents execution history for a scenario.

**Properties:**
- `id`: Unique identifier
- `scenario_id`: ID of associated scenario
- `command`: Executed command
- `output`: Command output
- `error`: Error message (if any)
- `timestamp`: Execution timestamp
- `execution_time_ms`: Execution time in milliseconds

### ScenarioState
Tracks the current active scenario state.

**Properties:**
- `current_scenario_id`: ID of currently active scenario
- `scenarios_dir`: Path to scenarios directory
- `metadata_db_path`: Path to metadata database

### ScenarioManager
Main class for managing scenarios and their associated databases.

**Key Methods:**

#### `__init__(project_root)`
Initialize the scenario manager with project root directory.

#### `create_scenario(name, base_scenario_id=None, description=None)`
Create a new scenario.
- `name`: Scenario name
- `base_scenario_id`: ID of scenario to branch from (None for scratch)
- `description`: Optional description

#### `switch_scenario(scenario_id)`
Switch to the specified scenario.

#### `get_current_scenario()`
Get the currently active scenario.

#### `copy_database(source_scenario_id, target_scenario_id)`
Copy database from source scenario to target scenario.

#### `list_scenarios()`
List all scenarios.

#### `delete_scenario(scenario_id)`
Delete a scenario and its associated data.

#### `add_execution_history(scenario_id, command, output=None, error=None, execution_time_ms=None)`
Add execution history entry for a scenario.

#### `get_execution_history(scenario_id, limit=None)`
Get execution history for a scenario.

#### `add_analysis_file(filename, file_type, content, created_by_scenario_id=None, is_global=True)`
Add an analysis file.

#### `get_analysis_files(scenario_id=None)`
Get analysis files (global or scenario-specific).

## Usage Examples

### Basic Scenario Management
```python
from scenario_manager import ScenarioManager

# Initialize manager
manager = ScenarioManager("/path/to/project")

# Create base scenario
base_scenario = manager.create_scenario("Base Scenario", description="Original scenario")

# Create branch scenario
branch_scenario = manager.create_scenario("Branch Scenario", base_scenario_id=base_scenario.id)

# Switch to branch scenario
manager.switch_scenario(branch_scenario.id)

# Get current scenario
current = manager.get_current_scenario()
print(f"Current scenario: {current.name}")
```

### Execution History
```python
# Add execution history
manager.add_execution_history(
    scenario_id=base_scenario.id,
    command="python model.py",
    output="Model executed successfully",
    error=None,
    execution_time_ms=2500
)

# Get execution history
history = manager.get_execution_history(base_scenario.id)
for entry in history:
    print(f"{entry.timestamp}: {entry.command}")
```

### Analysis Files
```python
# Add SQL query
sql_file = manager.add_analysis_file(
    filename="sales_query.sql",
    file_type="sql_query",
    content="SELECT * FROM sales WHERE amount > 1000",
    is_global=True
)

# Add visualization template
viz_file = manager.add_analysis_file(
    filename="chart_template.py",
    file_type="visualization_template",
    content="import plotly.express as px\nfig = px.bar(data, x='x', y='y')",
    is_global=True
)

# Get analysis files
files = manager.get_analysis_files()
```

## Integration Points

### With Existing System
The scenario management system is designed to integrate with the existing EYProject system:

1. **File Upload**: When files are uploaded, a base scenario is automatically created
2. **Database Operations**: All database operations use the current scenario's database
3. **Model Execution**: Models execute using the current scenario's database
4. **AI Analysis**: AI operates on the current scenario's data

### Global Functions
```python
from scenario_manager import get_scenario_manager, set_scenario_manager

# Get global scenario manager instance
manager = get_scenario_manager()

# Set global scenario manager instance
set_scenario_manager(manager)
```

## Testing

The implementation includes a comprehensive test script (`test_scenario_manager.py`) that verifies:

- Scenario creation (base, branch, scratch)
- Scenario switching
- Execution history management
- Analysis file management
- Scenario updates and deletion
- Database copying

Run the test with:
```bash
cd backend
python test_scenario_manager.py
```

## Next Steps

1. **API Integration**: Add FastAPI endpoints for scenario management
2. **Frontend Integration**: Create Angular services and components
3. **UI Implementation**: Implement tabbed interface for scenarios
4. **Database Integration**: Update existing database operations to be scenario-aware
5. **Model Integration**: Update LangGraph agent to use current scenario

## Performance Considerations

- **Lazy Loading**: Scenario data is loaded only when needed
- **Database Indexing**: Proper indexes for efficient queries
- **File Management**: Efficient copying and cleanup of scenario data
- **Memory Management**: Minimal memory footprint for inactive scenarios

## Error Handling

The system includes comprehensive error handling for:
- Database corruption
- Missing files
- Invalid scenario operations
- Concurrent access issues

## Security

- **Isolation**: Complete isolation between scenarios
- **Validation**: Input validation for all operations
- **Access Control**: Scenario-specific access control (future enhancement) 