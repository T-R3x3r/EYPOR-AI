# EYProject Temp File Management System

## Overview

The EYProject backend now uses a structured temp file management system that organizes all temporary files in a dedicated `EYProject` folder with subfolders for each server run (session).

## Directory Structure

```
C:\Users\[Username]\AppData\Local\Temp\EYProject\
├── session_20250626_224437\          # Session 1 (oldest)
│   ├── project_data.db
│   ├── test_model.py
│   └── DATABASE_SUMMARY.md
├── session_20250626_224503\          # Session 2
│   ├── project_data.db
│   ├── model.py
│   └── ...
└── session_20250626_224504\          # Session 3 (newest)
    ├── project_data.db
    ├── analysis.py
    └── ...
```

## Key Features

### 1. Organized Session Management
- Each server run creates a unique session directory with timestamp
- Session ID format: `session_YYYYMMDD_HHMMSS`
- All files for a session are contained within their session directory

### 2. Automatic Cleanup
- Old sessions are automatically cleaned up to prevent disk space issues
- By default, only the 10 most recent sessions are kept
- Cleanup happens before each new upload

### 3. Session Information API
- `/session/info` - Get information about current session and all sessions
- `/session/{session_id}` - Delete a specific session (DELETE method)

### 4. Enhanced Upload Process
The upload process now includes:
- Automatic cleanup of old sessions
- Creation of new session directory
- All file processing within the session directory
- Session ID returned in upload response

## API Endpoints

### GET /session/info
Returns information about the current session and all available sessions:

```json
{
  "current_session_id": "session_20250626_224504",
  "eyproject_temp_base": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject",
  "current_session_dir": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject\\session_20250626_224504",
  "temp_directories": {
    "current": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject\\session_20250626_224504"
  },
  "all_sessions": [
    {
      "session_id": "session_20250626_224504",
      "path": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject\\session_20250626_224504",
      "creation_time": "2025-06-26T22:45:04",
      "size_bytes": 25983,
      "is_current": true
    }
  ]
}
```

### DELETE /session/{session_id}
Deletes a specific session directory. Cannot delete the current session.

### POST /upload
Now returns additional session information:

```json
{
  "message": "Successfully processed 5 files: 2 CSV file(s) converted to SQL, 1 Excel file(s) converted to SQL, 2 Python file(s) updated for SQL",
  "session_id": "session_20250626_224504",
  "temp_dir": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject\\session_20250626_224504",
  "files": ["model.py", "project_data.db", "DATABASE_SUMMARY.md"],
  "table_names_message": "📊 Available database tables: test_data, parameters_parameters, parameters_settings",
  "sql_conversion": {
    "converted_tables": ["test_data", "parameters_parameters", "parameters_settings"],
    "total_tables": 3,
    "conversion_summary": ["✅ Converted test_data.csv → SQL table 'test_data'"],
    "python_transformations": ["✅ Updated model.py to use SQL operations"],
    "database_info": {...},
    "csv_files_removed": 2,
    "excel_files_removed": 1,
    "python_files_updated": 2
  }
}
```

## Benefits

### 1. Better Organization
- All temp files are organized in a dedicated EYProject folder
- Each session is isolated in its own directory
- Easy to identify and manage different server runs

### 2. Automatic Cleanup
- Prevents disk space issues from accumulated temp files
- Keeps only the most recent sessions
- Configurable cleanup threshold

### 3. Debugging and Support
- Easy to locate files for debugging
- Session information available via API
- Clear separation between different uploads/runs

### 4. Database-First Conversion
- Each session has its own database file
- Perfect table name inference using actual database schema
- No conflicts between different sessions

## Configuration

### Cleanup Settings
- Default: Keep 10 most recent sessions
- Configurable via `cleanup_old_sessions(max_sessions=10)`
- Cleanup happens automatically before each upload

### Base Directory
- Default: `C:\Users\[Username]\AppData\Local\Temp\EYProject`
- Can be modified by changing `EYPROJECT_TEMP_BASE`

## Usage Examples

### Creating a New Session
```python
from main import create_session_temp_dir

# Create new session
session_dir = create_session_temp_dir()
print(f"Session created: {session_dir}")
```

### Getting Session Information
```python
from main import get_current_session_dir

# Get current session directory
current_dir = get_current_session_dir()
print(f"Current session: {current_dir}")
```

### Manual Cleanup
```python
from main import cleanup_old_sessions

# Keep only 5 most recent sessions
cleanup_old_sessions(max_sessions=5)
```

## File Lifecycle

1. **Upload**: New session created, files extracted and processed
2. **Processing**: SQL conversion, Python transformation within session
3. **Execution**: Models run using session-specific database
4. **Cleanup**: Old sessions automatically removed
5. **Persistence**: Current session remains until next upload or manual cleanup

This system ensures that each server run is completely isolated, making debugging easier and preventing file conflicts between different uploads. 