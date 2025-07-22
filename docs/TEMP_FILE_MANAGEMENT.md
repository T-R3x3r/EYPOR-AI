# Temp File Management System (2024)

## Overview

EYProject uses a robust temp file/session management system in the backend to organize all temporary files for uploads, processing, and model execution. Each server run or upload creates a unique session directory, ensuring isolation, easy debugging, and automatic cleanup.

---

## Directory Structure

```
C:\Users\[Username]\AppData\Local\Temp\EYProject\
├── session_YYYYMMDD_HHMMSS\   # Each session is a separate directory
│   ├── project_data.db
│   ├── [uploaded/processed files]
│   └── ...
├── session_YYYYMMDD_HHMMSS\
│   └── ...
└── ...
```

- Each session directory is named with a timestamp for uniqueness
- All files for a session (databases, scripts, logs) are contained within that directory

---

## Key Features

- **Session Isolation:** Each upload or server run gets its own temp directory
- **Automatic Cleanup:** Only the most recent 10 sessions are kept by default; older sessions are deleted automatically
- **API Access:** Endpoints to list, inspect, and delete session directories
- **Debugging:** Easy to locate files for debugging and support
- **No Cross-Session Conflicts:** Each session has its own database and files

---

## API Endpoints

- `GET /session/info`: Returns info about the current session and all available sessions
- `DELETE /session/{session_id}`: Deletes a specific session directory (cannot delete the current session)
- `POST /upload`: Returns session info in the upload response

### Example: GET /session/info
```json
{
  "current_session_id": "session_20250710_153000",
  "eyproject_temp_base": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject",
  "current_session_dir": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject\\session_20250710_153000",
  "all_sessions": [
    {
      "session_id": "session_20250710_153000",
      "path": "C:\\Users\\Username\\AppData\\Local\\Temp\\EYProject\\session_20250710_153000",
      "creation_time": "2025-07-10T15:30:00",
      "size_bytes": 25983,
      "is_current": true
    },
    ...
  ]
}
```

### Example: DELETE /session/{session_id}
- Deletes the specified session directory (except the current one)

---

## Usage Examples

### Creating a New Session (Python backend)
```python
from main import create_session_temp_dir
session_dir = create_session_temp_dir()
print(f"Session created: {session_dir}")
```

### Getting Session Information
```python
from main import get_current_session_dir
current_dir = get_current_session_dir()
print(f"Current session: {current_dir}")
```

### Manual Cleanup
```python
from main import cleanup_old_sessions
cleanup_old_sessions(max_sessions=5)
```

---

## File Lifecycle

1. **Upload:** New session created, files extracted and processed
2. **Processing:** SQL conversion, Python transformation within session
3. **Execution:** Models run using session-specific database
4. **Cleanup:** Old sessions automatically removed
5. **Persistence:** Current session remains until next upload or manual cleanup

---

## Configuration

- **Cleanup Threshold:** Default is 10 sessions; can be changed in backend code
- **Base Directory:** Default is `C:\Users\[Username]\AppData\Local\Temp\EYProject`; can be changed via `EYPROJECT_TEMP_BASE`

---

## Benefits

- **Organization:** All temp files are organized and isolated by session
- **Automatic Cleanup:** Prevents disk space issues
- **Debugging:** Easy to find files for support
- **No Conflicts:** Each session is fully isolated

---

## Summary

The temp file/session management system in EYProject ensures robust, isolated, and automatically cleaned-up storage for all uploads and processing, making debugging and support easy while preventing file conflicts and disk space issues. 