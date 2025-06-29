# 🔄 Parameter Synchronization Guide

## Overview

This guide explains how the EYPOR-AI system ensures that when parameters are modified in the Excel part of the converted database, the actual model still runs correctly with those changes. The system uses **automatic parameter synchronization** to prevent the common issue where Excel parameter changes don't automatically propagate to code. EYPOR-AI eliminates this risk by:
• Converting every workbook into a unified SQLite database.  
• Rewriting model Python files to fetch parameters from that database.  
• Validating each change before execution.

With this mechanism models always see the most current parameters without manual file regeneration.

## 🏗️ System Architecture

### 1. **Database Conversion**
```
Excel Files → SQLite Database Tables
├── HubLocOpti_Inputs.xlsx
│   ├── Parameters → inputs_params table
│   ├── Hubs → hubs_data table  
│   └── Destinations → destinations_data table
└── Other files → Additional tables
```

### 2. **Code Transformation**
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
    conn = sqlite3.connect("project_data.db")
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

# Models now read from database
params = query_table("SELECT * FROM inputs_params")
hubs = query_table("SELECT * FROM hubs_data")
```

### 3. **Parameter Synchronization**
The system includes a `ModelParameterSync` class that:
- Tracks parameter changes in real-time
- Validates that changes are properly applied
- Ensures models use the latest parameters
- Provides detailed change reporting

## 🔧 How Parameter Changes Work

### Step 1: Parameter Modification
When you modify parameters through the system:

1. **User Request**: "Change maximum hub demand to 20000"
2. **System Analysis**: Identifies the relevant table and column
3. **Database Update**: Executes SQL UPDATE statement
4. **Validation**: Verifies the change was applied correctly

### Step 2: Model Execution
When models are executed:

1. **Parameter Snapshot**: System creates a snapshot of current parameters
2. **Model Analysis**: Checks if model is properly configured for database access
3. **Execution**: Model runs using the latest parameters from database
4. **Validation**: System verifies parameters used and reports any issues

### Step 3: Change Tracking
The system tracks all parameter changes:

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

## 📊 Parameter Validation Features

### 1. **Real-time Validation**
- Validates parameter changes immediately after database updates
- Ensures changes are properly applied
- Reports any issues or inconsistencies

### 2. **Model Compatibility Check**
- Analyzes model files to ensure they use database access
- Identifies any file-based operations that should be updated
- Provides recommendations for optimal parameter access

### 3. **Execution Monitoring**
- Tracks which parameters are used during model execution
- Compares before/after parameter states
- Reports any parameter changes made during execution

### 4. **Change History**
- Maintains snapshots of parameter states
- Tracks all modifications with timestamps
- Provides detailed change reports

## 🚀 Using the System

### Modifying Parameters

1. **Through the Chat Interface:**
   ```
   User: "Change the maximum hub demand to 25000"
   System: Analyzes request → Updates database → Validates change → Reports success
   ```