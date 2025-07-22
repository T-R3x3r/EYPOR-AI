# Parameter Synchronization Guide (2024)

## Overview

This guide explains how EYProject ensures that when parameters are modified in the scenario database (converted from Excel), all models always run with the latest values. The system uses **automatic parameter synchronization** to prevent issues where parameter changes in the database are not reflected in model execution. This is achieved by:
- Converting every workbook into a scenario-specific SQLite database
- Rewriting model Python files to fetch parameters from that database
- Validating each change before execution
- Tracking all changes and providing detailed reports

With this mechanism, models always see the most current parameters for the active scenario.

---

## System Architecture

### 1. Database Conversion
```
Excel Files → SQLite Database Tables (per scenario)
├── HubLocOpti_Inputs.xlsx
│   ├── Parameters → inputs_params table
│   ├── Hubs → hubs_data table
│   └── Destinations → destinations_data table
└── Other files → Additional tables
```

### 2. Code Transformation
Python model files are automatically updated to use SQL helper functions:

**Before (File-based):**
```python
import pandas as pd
params = pd.read_excel('Inputs/HubLocOpti_Inputs.xlsx', sheet_name='Parameters')
hubs = pd.read_excel('Inputs/HubLocOpti_Inputs.xlsx', sheet_name='Hubs')
```

**After (Database-based):**
```python
import sqlite3
import pandas as pd

def query_table(query, params=None):
    conn = sqlite3.connect("/absolute/path/to/scenario_database.db")
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

# Models now read from database
params = query_table("SELECT * FROM inputs_params")
hubs = query_table("SELECT * FROM hubs_data")
```

### 3. Parameter Synchronization
The system uses a `ModelParameterSync` class that:
- Tracks parameter changes in real-time (per scenario)
- Validates that changes are properly applied
- Ensures models use the latest parameters
- Provides detailed change reporting and snapshots

---

## How Parameter Changes Work

### Step 1: Parameter Modification
When you modify parameters through the system:
1. **User Request:** "Change maximum hub demand to 20000"
2. **System Analysis:** Identifies the relevant table and column in the scenario database
3. **Database Update:** Executes a safe SQL UPDATE statement
4. **Validation:** Verifies the change was applied correctly using ModelParameterSync

### Step 2: Model Execution
When models are executed:
1. **Parameter Snapshot:** System creates a snapshot of current parameters
2. **Model Analysis:** Checks if model is properly configured for database access
3. **Execution:** Model runs using the latest parameters from the scenario database
4. **Validation:** System verifies parameters used and reports any issues

### Step 3: Change Tracking
The system tracks all parameter changes and snapshots:
```python
# Before modification
before_snapshot = {
    "Maximum Hub Demand": 15000,
    "Operating Cost": 500,
    "Opening Cost": 1000
}

# After modification
after_snapshot = {
    "Maximum Hub Demand": 20000,  # Changed
    "Operating Cost": 500,         # Unchanged
    "Opening Cost": 1000           # Unchanged
}

# System reports the change
change_report = {
    "changes": [
        {
            "parameter": "Maximum Hub Demand",
            "before": 15000,
            "after": 20000,
            "table": "inputs_params"
        }
    ]
}
```

---

## Parameter Validation Features

- **Real-time Validation:** Validates parameter changes immediately after database updates
- **Model Compatibility Check:** Analyzes model files to ensure they use database access
- **Execution Monitoring:** Tracks which parameters are used during model execution
- **Change History:** Maintains snapshots of parameter states and all modifications with timestamps

---

## Using the System

### Modifying Parameters
1. **Through the Chat Interface:**
   ```
   User: "Change the maximum hub demand to 25000"
   System: Analyzes request → Updates scenario database → Validates change → Reports success
   ```

---

## Summary

EYProject's parameter synchronization system ensures robust, scenario-aware, and validated parameter management for all models, eliminating manual errors and guaranteeing that every model run uses the latest data.