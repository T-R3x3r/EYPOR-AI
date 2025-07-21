from fastapi import FastAPI, UploadFile, File, HTTPException, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Dict, Optional, Any
import os
import tempfile
import zipfile
import io
import subprocess
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime
import google.generativeai as genai
from openai import OpenAI
import json
import re
import shutil
import pandas as pd
import glob
import sqlite3
from langgraph_agent_v2 import SimplifiedAgent, create_agent_v2

# Scenario Manager imports and initialization
from scenario_manager import ScenarioManager, Scenario, AnalysisFile, ExecutionHistory, ScenarioState

# Set project_root to the backend directory (where this file is located)
project_root = os.path.dirname(os.path.abspath(__file__))

# Use this project_root for ScenarioManager
scenario_manager = ScenarioManager(project_root=project_root)

# Clear scenarios on server startup to ensure fresh state
def clear_scenarios_on_startup():
    """Clear all scenarios on server startup to ensure fresh state"""
    try:
        scenarios = scenario_manager.list_scenarios()
        for scenario in scenarios:
            scenario_manager.delete_scenario(scenario.id)
        print("DEBUG: Cleared all scenarios on server startup")
    except Exception as e:
        print(f"DEBUG: Error clearing scenarios on startup: {e}")

# Clear scenarios on server startup to ensure fresh state
print("🔄 Clearing all scenarios on startup...")
clear_scenarios_on_startup()
print("✅ Scenario clearing completed")

# Ensure the first scenario is activated if any exist
scenarios = scenario_manager.list_scenarios()
if scenarios:
    scenario_manager.state.current_scenario_id = scenarios[0].id
    print(f"DEBUG: Activated scenario on startup: {scenarios[0].name} (ID: {scenarios[0].id})")
else:
    print("DEBUG: No scenarios available after startup clearing")

# Server startup timestamp for frontend localStorage clearing
server_startup_timestamp = datetime.now().isoformat()
print(f"🔄 Server started at: {server_startup_timestamp}")

# Fallback agent functions
def list_available_agents():
    return ["data_analyst", "code_fixer", "database_modifier"]

def get_default_agent():
    return "data_analyst"


# Load environment variables from parent directory
load_dotenv("../EY.env")

app = FastAPI(title="AI Agent API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:4200"],  # Angular dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize both AI clients
openai_api_key = os.getenv("OPENAI_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")

if not openai_api_key:
    print("Warning: OpenAI API key not found in EY.env file")
    openai_client = None
else:
    openai_client = OpenAI(api_key=openai_api_key)

if not gemini_api_key:
    print("Warning: Gemini API key not found in EY.env file")
    genai_configured = False
else:
    genai.configure(api_key=gemini_api_key)
    genai_configured = True

# Global setting for AI model selection
current_ai_model = "openai"  # Default to OpenAI

# Global variables for file management
uploaded_files = {}
temp_directories = {}
file_contents = {}
ai_created_files = set()
converted_files = set()  # Track files that have been converted to SQL
code_output = ""
code_error = ""

# Database handling
current_database_path = None

# Global database schema cache (automatically generated when database is created)
database_schema = None

# Database whitelist system
table_whitelist = set()  # Tables allowed for modifications

# Global agent v2 instance
agent_v2 = None
use_langgraph_by_default = True

# Temp directory management
EYPROJECT_TEMP_BASE = os.path.join(tempfile.gettempdir(), "EYProject")
current_session_id = None

def ensure_eyproject_temp_dir():
    """Ensure the EYProject temp directory exists"""
    if not os.path.exists(EYPROJECT_TEMP_BASE):
        os.makedirs(EYPROJECT_TEMP_BASE)
        print(f"Created EYProject temp directory: {EYPROJECT_TEMP_BASE}")

def create_session_temp_dir():
    """Create a new session temp directory with timestamp"""
    global current_session_id
    
    # Ensure base directory exists
    ensure_eyproject_temp_dir()
    
    # Create session directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    session_id = f"session_{timestamp}"
    session_dir = os.path.join(EYPROJECT_TEMP_BASE, session_id)
    
    # Create the session directory
    os.makedirs(session_dir)
    current_session_id = session_id
    
    print(f"Created session temp directory: {session_dir}")
    return session_dir

def cleanup_old_sessions(max_sessions=10):
    """Clean up old session directories, keeping only the most recent ones"""
    if not os.path.exists(EYPROJECT_TEMP_BASE):
        return
    
    # Get all session directories
    session_dirs = []
    for item in os.listdir(EYPROJECT_TEMP_BASE):
        item_path = os.path.join(EYPROJECT_TEMP_BASE, item)
        if os.path.isdir(item_path) and item.startswith("session_"):
            session_dirs.append((item_path, os.path.getctime(item_path)))
    
    # Sort by creation time (oldest first)
    session_dirs.sort(key=lambda x: x[1])
    
    # Remove old sessions if we have too many
    if len(session_dirs) > max_sessions:
        sessions_to_remove = session_dirs[:-max_sessions]
        for session_path, _ in sessions_to_remove:
            try:
                import shutil
                shutil.rmtree(session_path)
                print(f"Cleaned up old session: {session_path}")
            except Exception as e:
                print(f"Could not clean up session {session_path}: {e}")

def get_current_session_dir():
    """Get the current session directory, create one if it doesn't exist"""
    if current_session_id is None:
        return create_session_temp_dir()
    
    session_dir = os.path.join(EYPROJECT_TEMP_BASE, current_session_id)
    if not os.path.exists(session_dir):
        # Session directory was deleted, create a new one
        return create_session_temp_dir()
    
    return session_dir

class ChatMessage(BaseModel):
    role: str
    content: str
    thread_id: Optional[str] = "default"

class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = "default"

class FileEditRequest(BaseModel):
    filename: str
    content: str

class SwitchAIRequest(BaseModel):
    model: str

class ActionRequest(BaseModel):
    message: str
    action_type: Optional[str] = None  # User can specify action type or let AI detect it
    conversation_history: Optional[List[dict]] = []  # Previous messages for context
    thread_id: Optional[str] = "default"  # Thread ID for LangGraph memory

class ApprovalRequest(BaseModel):
    thread_id: str
    approval_response: str  # Model selection response
    approval_id: Optional[str] = None

class ModelExecutionRequest(BaseModel):
    model_filename: str
    parameters: Optional[Dict[str, Any]] = {}

class WhitelistRequest(BaseModel):
    tables: List[str]

def initialize_default_whitelist():
    """Initialize default whitelist with inputs_ prefixed tables and params tables"""
    global table_whitelist
    
    # Get current database info to find tables that should be whitelisted by default
    if current_database_path and os.path.exists(current_database_path):
        try:
            db_info = get_database_info(current_database_path)
            if "tables" in db_info:
                default_tables = set()
                for table in db_info["tables"]:
                    table_name = table.get("name", "")
                    # Add tables with "inputs_" prefix or "params" in name
                    if table_name.startswith("inputs_") or "params" in table_name.lower():
                        default_tables.add(table_name)
                table_whitelist.update(default_tables)
                print(f"DEBUG: Initialized whitelist with default tables: {default_tables}")
        except Exception as e:
            print(f"DEBUG: Error initializing default whitelist: {e}")
    
    # If no database or error, set basic defaults
    if not table_whitelist:
        table_whitelist.update({"inputs_destinations", "inputs_params", "params"})
        print(f"DEBUG: Using fallback default whitelist: {table_whitelist}")

def get_table_whitelist():
    """Get current table whitelist, initializing if empty"""
    global table_whitelist
    if not table_whitelist:
        initialize_default_whitelist()
    return table_whitelist

def read_file_content(file_path: str) -> str:
    """Read file content safely, handling different encodings"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception:
            return f"[Binary file or encoding error: {os.path.basename(file_path)}]"
    except Exception as e:
        return f"[Error reading file: {str(e)}]"

def write_file_content(file_path: str, content: str) -> bool:
    """Write content to file safely"""
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except Exception as e:
        print(f"Error writing file: {str(e)}")
        return False

def get_all_file_contents(file_paths: Dict[str, str]) -> Dict[str, str]:
    """Get contents of all files"""
    contents = {}
    for rel_path, abs_path in file_paths.items():
        contents[rel_path] = read_file_content(abs_path)
    return contents

def build_context_for_agent(file_paths: Dict[str, str], code_output: str, code_error: str) -> str:
    """Build context string for AI agent"""
    context_parts = []
    
    file_contents = get_all_file_contents(file_paths)
    
    for rel_path, content in file_contents.items():
        context_parts.append(f"=== File: {rel_path} ===")
        context_parts.append(content)
        context_parts.append("")
    
    if code_output:
        context_parts.append("=== Previous Output ===")
        context_parts.append(code_output)
        context_parts.append("")
    
    if code_error:
        context_parts.append("=== Previous Error ===")
        context_parts.append(code_error)
        context_parts.append("")
    
    return "\n".join(context_parts)

def parse_file_edit_request(response_text: str) -> List[tuple]:
    """Parse AI response for file edit requests"""
    # Implementation for parsing file edits from AI response
    # This would need to be implemented based on the AI response format
    return []

def connect_to_database(db_path: str):
    """Connect to database and return connection"""
    try:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
        return connection
    except Exception as e:
        print(f"Error connecting to database: {e}")
        return None

def get_database_info(db_path: str) -> Dict[str, Any]:
    """Get information about the database"""
    if not os.path.exists(db_path):
        return {"error": "Database file not found"}
    
    try:
        conn = connect_to_database(db_path)
        if not conn:
            return {"error": "Could not connect to database"}
        
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        table_names = [row[0] for row in cursor.fetchall()]
        
        # Build tables array with detailed info
        tables = []
        table_details = {}
        
        for table_name in table_names:
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [{"name": row[1], "type": row[2]} for row in cursor.fetchall()]
            
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]
            
            # Create table object that frontend expects
            table_obj = {
                "name": table_name,
                "columns": columns,
                "row_count": row_count
            }
            tables.append(table_obj)
            
            # Also keep the details dictionary for compatibility
            table_details[table_name] = {
                "columns": columns,
                "row_count": row_count
            }
        
        conn.close()
        
        return {
            "tables": tables,
            "table_details": table_details,
            "total_tables": len(tables),
            "database_path": db_path
        }
        
    except Exception as e:
        return {"error": f"Error reading database: {str(e)}"}

# Removed v1 agent function - now using v2 agent only

async def get_or_create_agent_v2():
    """Get or create the simplified agent v2 instance"""
    global agent_v2
    
    if agent_v2 is None:
        # Get the current AI model setting
        current_ai = await get_current_ai()
        ai_model = current_ai.get("model", "openai")
        
        # Create agent with scenario manager
        agent_v2 = create_agent_v2(ai_model=ai_model, scenario_manager=scenario_manager)
    
    return agent_v2

def refresh_file_list():
    """Refresh the file list to include newly created files and outputs from current scenario only"""
    global uploaded_files, file_contents, ai_created_files
    
    # Get current scenario directory instead of temp directory
    current_scenario = scenario_manager.get_current_scenario()
    if not current_scenario:
        print("DEBUG: No current scenario, skipping file refresh")
        return
    
    scenario_dir = os.path.dirname(current_scenario.database_path)
    print(f"DEBUG: refresh_file_list called with scenario_dir: {scenario_dir}")
    
    if scenario_dir and os.path.exists(scenario_dir):
        # Scan for all files in the current scenario directory only
        for root, dirs, files in os.walk(scenario_dir):
            print(f"DEBUG: Scanning scenario directory: {root}")
            print(f"DEBUG: Found files: {files}")
            for fname in files:
                abs_path = os.path.join(root, fname)
                # Create a relative path from the scenario directory
                rel_path = os.path.relpath(abs_path, scenario_dir)
                # Normalize path for web compatibility (forward slashes)
                rel_path = rel_path.replace('\\', '/')
                print(f"DEBUG: Processing scenario file: {fname} -> {rel_path}")
                
                if rel_path not in uploaded_files:
                    print(f"DEBUG: Adding new scenario file: {rel_path}")
                    uploaded_files[rel_path] = abs_path
                    ai_created_files.add(rel_path)  # Mark as AI-created
                    
                    # Load file content for text files
                    if fname.endswith(('.py', '.txt', '.csv', '.html', '.json', '.md')):
                        try:
                            with open(abs_path, 'r', encoding='utf-8') as f:
                                file_contents[rel_path] = f.read()
                        except Exception as e:
                            print(f"Error reading created scenario file {rel_path}: {e}")
                    else:
                        # For binary files (images, etc.), just mark as available
                        file_contents[rel_path] = f"[Binary file: {fname}]"
                else:
                    print(f"DEBUG: Scenario file already exists: {rel_path}")
    
    print(f"DEBUG: Final uploaded_files: {list(uploaded_files.keys())}")
    print(f"DEBUG: Final ai_created_files: {list(ai_created_files)}")

@app.post("/upload")
async def upload_files(file: UploadFile = File(...)):
    """Upload a zip file and extract its contents, create a Base Scenario, and store files in shared directory"""
    global uploaded_files, temp_directories, file_contents, ai_created_files, current_database_path, database_schema

    if not file.filename.endswith('.zip'):
        raise HTTPException(status_code=400, detail="Only zip files are supported")

    try:
        # Clean up old sessions first
        cleanup_old_sessions()

        # Create new session temp directory
        temp_dir = create_session_temp_dir()
        temp_directories['current'] = temp_dir

        print(f"DEBUG: Using session temp directory: {temp_dir}")

        # Read and extract zip file
        zip_content = await file.read()
        with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
            z.extractall(temp_dir)

        # Build file paths - keep files in session temp directory for compatibility
        file_paths = {}
        db_files = []  # Track .db files

        for root, dirs, files in os.walk(temp_dir):
            for fname in files:
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, temp_dir)
                rel_path = rel_path.replace('\\', '/')
                file_paths[rel_path] = abs_path  # Keep in session temp directory
                if fname.lower().endswith('.db'):
                    db_files.append((rel_path, abs_path))

        uploaded_files = file_paths
        ai_created_files = set()  # Clear AI-created files when uploading new project

        # Check if there's a database file and set up database access
        db_info = {"tables": [], "total_tables": 0}
        table_names_message = ""
        base_scenario = None
        original_db_path = os.path.join(scenario_manager.shared_dir, "original_upload.db")
        if db_files:
            # Use the first .db file found
            base_db_path = db_files[0][1]  # abs_path in session temp dir
            print(f"DEBUG: Found database file: {base_db_path}")
            
            # Save a protected copy of the original upload
            shutil.copy2(base_db_path, original_db_path)
            print(f"DEBUG: Saved original upload database to: {original_db_path}")
            
            # Create Base Scenario (this will be the first scenario, so it will be marked as base)
            base_scenario = scenario_manager.create_scenario(
                name="Base Scenario",
                base_scenario_id=None,
                description="Initial scenario created from upload",
                original_db_path=original_db_path
            )
            
            # Set the current scenario in the scenario manager
            scenario_manager.state.current_scenario_id = base_scenario.id
            
            # Use the scenario's database path for all operations
            current_database_path = base_scenario.database_path
            
            # Get database information from the scenario's database path
            try:
                db_info = get_database_info(current_database_path)
                print(f"DEBUG: Database has {len(db_info.get('tables', []))} tables")
                database_schema = db_info
                initialize_default_whitelist()
                if db_info.get("tables"):
                    table_names = [table["name"] for table in db_info["tables"]]
                    table_names_message = f"📊 Available database tables: {', '.join(table_names)}"
            except Exception as e:
                print(f"DEBUG: Error reading database: {e}")
                db_info = {"error": str(e)}
        else:
            current_database_path = None
            database_schema = None

        # Load file contents (skip binary files)
        file_contents = {}
        for rel_path, abs_path in file_paths.items():
            if not rel_path.endswith(('.db', '.png', '.jpg', '.jpeg', '.gif', '.pdf')):
                file_contents[rel_path] = read_file_content(abs_path)

        file_count = len(file_paths)
        db_count = len(db_files)
        summary_parts = []
        if db_count > 0:
            tables_count = db_info.get('total_tables', 0) if not db_info.get('error') else 0
            summary_parts.append(f"database with {tables_count} table(s)")
        if summary_parts:
            message = f"Successfully uploaded {file_count} files including " + ", ".join(summary_parts)
        else:
            message = f"Successfully uploaded {file_count} files"

        return {
            "message": message,
            "files": list(file_paths.keys()),
            "file_contents": file_contents,
            "table_names_message": table_names_message,
            "session_id": current_session_id,
            "temp_dir": temp_dir,
            "database_info": db_info,
            "scenario": base_scenario.to_dict() if base_scenario else None
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")

@app.get("/files")
async def get_files():
    """Get list of uploaded files and ALL scenario-generated files for cross-scenario compatibility"""
    uploaded_list = [f for f in uploaded_files.keys() if f not in ai_created_files]
    ai_created_list = [f for f in uploaded_files.keys() if f in ai_created_files]
    
    # Get files from ALL scenarios (cross-scenario compatibility)
    scenario_files = []
    all_scenarios = scenario_manager.list_scenarios()
    
    for scenario in all_scenarios:
        # Check in the database directory (where both Python and HTML files are stored)
        db_dir = os.path.dirname(scenario.database_path)
        print(f"DEBUG: Checking scenario directory: {db_dir}")
        
        if os.path.exists(db_dir):
            try:
                all_files_in_dir = os.listdir(db_dir)
                print(f"DEBUG: Files in scenario {scenario.name}: {all_files_in_dir}")
                
                for file in all_files_in_dir:
                    if file.endswith(('.html', '.csv', '.png', '.jpg', '.jpeg', '.svg', '.pdf', '.json', '.py')):
                        # Add scenario prefix to avoid filename conflicts
                        scenario_file = f"[{scenario.name}] {file}"
                        if scenario_file not in scenario_files:
                            scenario_files.append(scenario_file)
                            print(f"DEBUG: Added scenario file: {scenario_file}")
            except Exception as e:
                print(f"DEBUG: Error reading scenario directory {db_dir}: {e}")
        
        # Also check in the old scenario directory for backward compatibility
        old_scenario_dir = os.path.join(scenario_manager.scenarios_dir, f"scenario_{scenario.id}")
        if os.path.exists(old_scenario_dir):
            try:
                all_files_in_old_dir = os.listdir(old_scenario_dir)
                print(f"DEBUG: Files in old scenario directory {scenario.name}: {all_files_in_old_dir}")
                
                for file in all_files_in_old_dir:
                    if file.endswith(('.html', '.csv', '.png', '.jpg', '.jpeg', '.svg', '.pdf', '.json', '.py')):
                        # Add scenario prefix to avoid filename conflicts
                        scenario_file = f"[{scenario.name}] {file}"
                        if scenario_file not in scenario_files:
                            scenario_files.append(scenario_file)
                            print(f"DEBUG: Added old scenario file: {scenario_file}")
            except Exception as e:
                print(f"DEBUG: Error reading old scenario directory {old_scenario_dir}: {e}")
    
    print(f"DEBUG: All scenario files found: {scenario_files}")
    
    # Combine all files
    all_files = list(uploaded_files.keys()) + scenario_files
    
    return {
        "files": all_files,
        "uploaded_files": uploaded_list,
        "ai_created_files": ai_created_list + scenario_files,  # Mark scenario files as AI-created
        "file_contents": file_contents
    }

@app.get("/files/{filename}")
async def get_file_content(filename: str):
    """Get content of a specific file"""
    # First check if file is in uploaded_files
    if filename in uploaded_files:
        content = read_file_content(uploaded_files[filename])
        return {"filename": filename, "content": content}
    
    # Check if it's a scenario-prefixed file (e.g., "[Base Scenario] file.py")
    if filename.startswith('[') and ']' in filename:
        scenario_name = filename[1:filename.find(']')]
        actual_filename = filename[filename.find(']') + 2:]  # Skip "] "
        
        # Find the scenario by name
        all_scenarios = scenario_manager.list_scenarios()
        for scenario in all_scenarios:
            if scenario.name == scenario_name:
                scenario_dir = os.path.dirname(scenario.database_path)
                scenario_file_path = os.path.join(scenario_dir, actual_filename)
                if os.path.exists(scenario_file_path):
                    content = read_file_content(scenario_file_path)
                    return {"filename": filename, "content": content}
                break
    
    # Search ALL scenario directories for the file (cross-scenario compatibility)
    all_scenarios = scenario_manager.list_scenarios()
    
    for scenario in all_scenarios:
        # Look in the database directory (where both Python and HTML files are stored)
        db_dir = os.path.dirname(scenario.database_path)
        scenario_file_path = os.path.join(db_dir, filename)
        if os.path.exists(scenario_file_path):
            content = read_file_content(scenario_file_path)
            return {"filename": filename, "content": content}
        
        # Also check in the old scenario directory for backward compatibility
        old_scenario_dir = os.path.join(scenario_manager.scenarios_dir, f"scenario_{scenario.id}")
        scenario_file_path = os.path.join(old_scenario_dir, filename)
        if os.path.exists(scenario_file_path):
            content = read_file_content(scenario_file_path)
            return {"filename": filename, "content": content}
    
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/files/{filename:path}/download")
async def download_file(filename: str):
    """Download a file (for images, binary files, etc.) - supports paths with subdirectories"""
    try:
        print(f"DEBUG: Download request for file: {filename}")
        print(f"DEBUG: Current working directory: {os.getcwd()}")
        print(f"DEBUG: Available files in uploaded_files: {list(uploaded_files.keys())}")
        
        # Normalize the filename to use forward slashes
        filename = filename.replace('\\', '/')
        print(f"DEBUG: Normalized filename: {filename}")
        
        # First check if file is in uploaded_files (session files)
        if filename in uploaded_files:
            file_path = uploaded_files[filename]
        else:
            # Check if it's a scenario-prefixed file (e.g., "[Base Scenario] file.py")
            if filename.startswith('[') and ']' in filename:
                scenario_name = filename[1:filename.find(']')]
                actual_filename = filename[filename.find(']') + 2:]  # Skip "] "
                
                # Find the scenario by name
                all_scenarios = scenario_manager.list_scenarios()
                for scenario in all_scenarios:
                    if scenario.name == scenario_name:
                        scenario_dir = os.path.dirname(scenario.database_path)
                        scenario_file_path = os.path.join(scenario_dir, actual_filename)
                        if os.path.exists(scenario_file_path):
                            file_path = scenario_file_path
                            print(f"DEBUG: Found scenario-prefixed file: {file_path}")
                            break
                else:
                    print(f"DEBUG: Scenario-prefixed file not found: {filename}")
                    raise HTTPException(status_code=404, detail="File not found")
            else:
                # Search ALL scenario directories for the file (cross-scenario compatibility)
                all_scenarios = scenario_manager.list_scenarios()
                file_found = False
                
                for scenario in all_scenarios:
                    # Look in the database directory (where both Python and HTML files are stored)
                    db_dir = os.path.dirname(scenario.database_path)
                    scenario_file_path = os.path.join(db_dir, filename)
                    if os.path.exists(scenario_file_path):
                        file_path = scenario_file_path
                        file_found = True
                        print(f"DEBUG: Found file in scenario '{scenario.name}': {file_path}")
                        break
                    
                    # Also check in the old scenario directory for backward compatibility
                    scenario_dir = os.path.join(scenario_manager.scenarios_dir, f"scenario_{scenario.id}")
                    scenario_file_path = os.path.join(scenario_dir, filename)
                    if os.path.exists(scenario_file_path):
                        file_path = scenario_file_path
                        file_found = True
                        print(f"DEBUG: Found file in old scenario directory '{scenario.name}': {file_path}")
                        break
                
                if not file_found:
                    print(f"DEBUG: File not found in uploaded_files or any scenario: {filename}")
                    print(f"DEBUG: Available keys: {list(uploaded_files.keys())}")
                    raise HTTPException(status_code=404, detail="File not found")
        print(f"DEBUG: File path from uploaded_files: {file_path}")
        print(f"DEBUG: File path exists: {os.path.exists(file_path)}")
        print(f"DEBUG: File path is absolute: {os.path.isabs(file_path)}")
        
        if not os.path.exists(file_path):
            print(f"DEBUG: File not found on disk: {file_path}")
            # Try to get more info about the directory
            dir_path = os.path.dirname(file_path)
            print(f"DEBUG: Directory exists: {os.path.exists(dir_path)}")
            if os.path.exists(dir_path):
                print(f"DEBUG: Directory contents: {os.listdir(dir_path)}")
            raise HTTPException(status_code=404, detail="File not found on disk")
        
        # Check file size and permissions
        try:
            file_size = os.path.getsize(file_path)
            print(f"DEBUG: File size: {file_size} bytes")
        except Exception as e:
            print(f"DEBUG: Error getting file size: {e}")
        
        # Import here to avoid potential import issues
        try:
            from fastapi.responses import FileResponse
            import mimetypes
            print(f"DEBUG: Successfully imported FileResponse and mimetypes")
        except Exception as e:
            print(f"DEBUG: Error importing modules: {e}")
            raise HTTPException(status_code=500, detail=f"Import error: {str(e)}")
        
        # Determine content type based on file extension
        try:
            content_type, _ = mimetypes.guess_type(file_path)
            if not content_type:
                # Default to binary for unknown types
                content_type = "application/octet-stream"
            print(f"DEBUG: Content type: {content_type}")
        except Exception as e:
            print(f"DEBUG: Error determining content type: {e}")
            content_type = "application/octet-stream"
        
        print(f"DEBUG: About to serve file: {file_path} with content type: {content_type}")
        
        # Create FileResponse with explicit path
        try:
            response = FileResponse(
                path=file_path, 
                filename=os.path.basename(filename),
                media_type=content_type
            )
            print(f"DEBUG: FileResponse created successfully")
            return response
        except Exception as e:
            print(f"DEBUG: Error creating FileResponse: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"FileResponse creation failed: {str(e)}")
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        print(f"DEBUG: Download error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")

@app.put("/files/{filename}")
async def update_file(filename: str, request: FileEditRequest):
    """Update content of a specific file or create a new file"""
    global file_contents, uploaded_files, ai_created_files
    
    # If file doesn't exist, create it in the current temp directory
    if filename not in uploaded_files:
        temp_dir = temp_directories.get('current')
        if not temp_dir:
            # Create a temp directory if none exists
            temp_dir = tempfile.mkdtemp(prefix="ey_project_")
            temp_directories['current'] = temp_dir
        
        file_path = os.path.join(temp_dir, filename)
        uploaded_files[filename] = file_path
        ai_created_files.add(filename)  # Mark as AI-created
    
    file_path = uploaded_files[filename]
    
    if write_file_content(file_path, request.content):
        file_contents[filename] = request.content
        return {"message": f"File {filename} {'created' if filename in ai_created_files else 'updated'} successfully"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update file")

@app.post("/run")
async def run_file(filename: str):
    """Run a Python file with dynamic database path injection for cross-scenario compatibility"""
    global code_output, code_error
    
    # Always define current_scenario at the very start
    current_scenario = scenario_manager.get_current_scenario()
    temp_dir = temp_directories.get('current')
    
    # Ensure we have a valid execution directory
    if temp_dir is None:
        # Create a temporary directory if none exists
        temp_dir = create_session_temp_dir()
        temp_directories['current'] = temp_dir
        print(f"DEBUG: Created new temp directory for execution: {temp_dir}")
    
    execution_cwd = temp_dir  # Always set a default
    
    # First, try to find the file in global locations
    abs_path = None
    original_filename = filename  # Keep track of original filename for display
    
    # Check if it's a scenario-prefixed file (e.g., "[Base Scenario] file.py")
    if filename.startswith('[') and ']' in filename:
        scenario_name = filename[1:filename.find(']')]
        actual_filename = filename[filename.find(']') + 2:]  # Skip "] "
        
        # Find the scenario by name
        all_scenarios = scenario_manager.list_scenarios()
        for scenario in all_scenarios:
            if scenario.name == scenario_name:
                scenario_dir = os.path.dirname(scenario.database_path)
                scenario_file_path = os.path.join(scenario_dir, actual_filename)
                if os.path.exists(scenario_file_path):
                    abs_path = scenario_file_path
                    print(f"DEBUG: Found scenario-prefixed file: {abs_path}")
                    break
        else:
            raise HTTPException(status_code=404, detail=f"Scenario '{scenario_name}' not found or file '{actual_filename}' not found in that scenario")
    
    # Check if file is in uploaded_files (global)
    elif filename in uploaded_files:
        abs_path = uploaded_files[filename]
    else:
        # Check in shared/uploaded_files directory (global)
        shared_dir = os.path.join(os.path.dirname(os.getcwd()), "shared", "uploaded_files")
        shared_file_path = os.path.join(shared_dir, filename)
        if os.path.exists(shared_file_path):
            abs_path = shared_file_path
        else:
            # Search ALL scenario directories for the file (cross-scenario compatibility)
            all_scenarios = scenario_manager.list_scenarios()
            file_found = False
            
            for scenario in all_scenarios:
                # Look in the database directory (where both Python and HTML files are now stored)
                db_dir = os.path.dirname(scenario.database_path)
                scenario_file_path = os.path.join(db_dir, filename)
                if os.path.exists(scenario_file_path):
                    abs_path = scenario_file_path
                    file_found = True
                    print(f"DEBUG: Found file in scenario '{scenario.name}': {abs_path}")
                    break
                
                # Also check in the old scenario directory for backward compatibility
                scenario_dir = os.path.join(scenario_manager.scenarios_dir, f"scenario_{scenario.id}")
                scenario_file_path = os.path.join(scenario_dir, filename)
                if os.path.exists(scenario_file_path):
                    abs_path = scenario_file_path
                    file_found = True
                    print(f"DEBUG: Found file in old scenario directory '{scenario.name}': {abs_path}")
                    break
            
            if not file_found:
                raise HTTPException(status_code=404, detail=f"File '{filename}' not found in any scenario or global location")
    
    if not filename.endswith('.py'):
        raise HTTPException(status_code=400, detail="Only Python files can be executed")
    
    try:
        # Determine the correct working directory for execution
        # For uploaded model files, execute in the uploaded files directory
        # For scenario-generated files, execute in the scenario's database directory
        # Otherwise, use the temp directory
        
        print(f"DEBUG: current_scenario exists: {current_scenario is not None}")
        print(f"DEBUG: abs_path: {abs_path}")
        print(f"DEBUG: current_scenario database_path: {current_scenario.database_path if current_scenario else 'None'}")
        
        # Check if this is a comparison file (contains multiple database paths or comparison logic)
        is_comparison_file = (
            'comparison' in filename.lower() or
            'vs_' in filename.lower() or
            'scenario' in filename.lower() and ('vs' in filename.lower() or 'comparison' in filename.lower())
        )
        
        # Check if this is an uploaded model file (like runall.py, model.py, etc.)
        is_uploaded_model = False
        if filename in uploaded_files:
            is_uploaded_model = True
            # For uploaded model files, execute in the uploaded files directory where all dependencies are located
            execution_cwd = temp_dir  # Uploaded files directory
            print(f"DEBUG: Using uploaded files directory for model execution: {execution_cwd}")
        elif is_comparison_file and current_scenario:
            # For comparison files, we need to determine the correct execution directory
            # First, try to find where the comparison file was originally created
            file_dir = os.path.dirname(abs_path) if abs_path else None
            
            if file_dir and os.path.exists(file_dir):
                # If the file exists in a scenario directory, use that directory
                # This ensures output files are created in the same location as the comparison file
                execution_cwd = file_dir
                print(f"DEBUG: Using comparison file's original directory: {execution_cwd}")
            else:
                # Fallback to current scenario's database directory
                execution_cwd = os.path.dirname(current_scenario.database_path)
                print(f"DEBUG: Using scenario execution directory for comparison file: {execution_cwd}")
        elif current_scenario and abs_path.startswith(os.path.dirname(current_scenario.database_path)):
            # This is a scenario file, execute in the scenario's database directory
            execution_cwd = os.path.dirname(current_scenario.database_path)
            print(f"DEBUG: Using scenario execution directory: {execution_cwd}")
        elif current_scenario and filename.startswith('[') and ']' in filename:
            # This is a scenario-prefixed file, execute in the scenario's database directory
            execution_cwd = os.path.dirname(current_scenario.database_path)
            print(f"DEBUG: Using scenario execution directory for prefixed file: {execution_cwd}")
        elif current_scenario:
            # For any file in the current scenario context, use the scenario's database directory
            execution_cwd = os.path.dirname(current_scenario.database_path)
            print(f"DEBUG: Using scenario execution directory for current scenario: {execution_cwd}")
        else:
            # Default to temp directory
            execution_cwd = temp_dir
            print(f"DEBUG: Using temp directory for execution: {execution_cwd}")
        
        # For uploaded model files, we're already executing in the uploaded files directory
        # No need to check for shared uploaded files directory since we're using temp_dir
        
        # Store file modification times before execution to detect changes
        file_mod_times_before = {}
        scan_dir = execution_cwd if execution_cwd else temp_dir
        if scan_dir and os.path.exists(scan_dir):
            for root, dirs, files in os.walk(scan_dir):
                for file in files:
                    abs_file_path = os.path.join(root, file)
                    try:
                        file_mod_times_before[abs_file_path] = os.path.getmtime(abs_file_path)
                    except OSError:
                        pass
        
        # Record execution start time
        import time
        execution_start_time = time.time()
        
        # Execute the file with dynamic database path injection
        file_content = None
        temp_file_path = None
        
        try:
            with open(abs_path, 'r', encoding='utf-8') as f:
                file_content = f.read()
            
            # Check if this is a comparison file (contains multiple database paths or comparison logic)
            is_comparison_file = (
                'comparison' in filename.lower() or
                'vs_' in filename.lower() or
                'scenario' in filename.lower() and ('vs' in filename.lower() or 'comparison' in filename.lower()) or
                any(keyword in file_content.lower() for keyword in [
                    'base_scenario_db', 'test_scenario_db', 'alternative_scenario_db',
                    'scenario_names', 'multi_database', 'comparison_visualization',
                    'scenario_name', 'scenario_names', 'scenario_data'
                ]) or
                file_content.count('database.db') > 1 or  # Multiple database references
                file_content.count('sqlite3.connect') > 1  # Multiple database connections
            )
            
            # Get current scenario's database path for injection
            current_db_path = None
            print(f"DEBUG: About to check current_scenario: {current_scenario}")
            print(f"DEBUG: Is comparison file: {is_comparison_file}")
            
            if current_scenario and not is_comparison_file:
                print(f"DEBUG: current_scenario is not None, database_path: {current_scenario.database_path}")
                current_db_path = current_scenario.database_path
                # Convert Windows backslashes to double backslashes to avoid escape sequence issues
                current_db_path = current_db_path.replace('\\', '\\\\')
                
                print(f"DEBUG: Original database path: {current_scenario.database_path}")
                print(f"DEBUG: Converted database path: {current_db_path}")
                
                # Replace any hardcoded database paths with the current scenario's database
                # Use double backslashes to avoid escape sequence issues
                file_content = file_content.replace('database.db', current_db_path)
                file_content = file_content.replace('project_data.db', current_db_path)
                file_content = file_content.replace('"database.db"', f'"{current_db_path}"')
                file_content = file_content.replace("'database.db'", f"'{current_db_path}'")  # Use double backslashes
                file_content = file_content.replace('"project_data.db"', f'"{current_db_path}"')
                file_content = file_content.replace("'project_data.db'", f"'{current_db_path}'")  # Use double backslashes
                
                # For uploaded model files, also replace any relative database paths
                if is_uploaded_model:
                    # Replace common database filenames with the current scenario's database
                    file_content = file_content.replace('"project_data.db"', f'"{current_db_path}"')
                    file_content = file_content.replace("'project_data.db'", f"'{current_db_path}'")
                    file_content = file_content.replace('"original_upload.db"', f'"{current_db_path}"')
                    file_content = file_content.replace("'original_upload.db'", f"'{current_db_path}'")
                    file_content = file_content.replace('"uploaded_files.db"', f'"{current_db_path}"')
                    file_content = file_content.replace("'uploaded_files.db'", f"'{current_db_path}'")
                    
                    # Also replace any database path variables that might be set in the model
                    file_content = file_content.replace('database_path = "project_data.db"', f'database_path = "{current_db_path}"')
                    file_content = file_content.replace("database_path = 'project_data.db'", f"database_path = '{current_db_path}'")
                    file_content = file_content.replace('database_path = "original_upload.db"', f'database_path = "{current_db_path}"')
                    file_content = file_content.replace("database_path = 'original_upload.db'", f"database_path = '{current_db_path}'")
                    
                    # Replace any hardcoded database names in SQL queries or file operations
                    file_content = file_content.replace('"project_data.db"', f'"{current_db_path}"')
                    file_content = file_content.replace("'project_data.db'", f"'{current_db_path}'")
                    file_content = file_content.replace('"original_upload.db"', f'"{current_db_path}"')
                    file_content = file_content.replace("'original_upload.db'", f"'{current_db_path}'")
                    
                    # Replace database names in sqlite3.connect calls
                    file_content = file_content.replace('sqlite3.connect("project_data.db")', f'sqlite3.connect("{current_db_path}")')
                    file_content = file_content.replace("sqlite3.connect('project_data.db')", f"sqlite3.connect('{current_db_path}')")
                    file_content = file_content.replace('sqlite3.connect("original_upload.db")', f'sqlite3.connect("{current_db_path}")')
                    file_content = file_content.replace("sqlite3.connect('original_upload.db')", f"sqlite3.connect('{current_db_path}')")
                    
                    # Replace database names in pd.read_sql_query calls
                    file_content = file_content.replace('pd.read_sql_query(query, "project_data.db")', f'pd.read_sql_query(query, "{current_db_path}")')
                    file_content = file_content.replace("pd.read_sql_query(query, 'project_data.db')", f"pd.read_sql_query(query, '{current_db_path}')")
                    
                    # Add import path fix for uploaded model files
                    if ('import dataprocessing' in file_content or 'from dataprocessing' in file_content or 
                        'import model' in file_content or 'from model' in file_content):
                        # Add uploaded files directory to Python path to ensure imports work
                        import_path_fix = f"""
import sys
import os
# Ensure uploaded files take precedence over backend files
sys.path.insert(0, r"{temp_dir}")
# Only add backend directory if needed for other dependencies
if r"{temp_dir}" not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""
                        # Insert the path fix at the beginning of the file
                        if file_content.startswith('# -*- coding: utf-8 -*-'):
                            # Insert after encoding declaration
                            file_content = file_content.replace('# -*- coding: utf-8 -*-', '# -*- coding: utf-8 -*-\n' + import_path_fix)
                        else:
                            # Insert at the beginning
                            file_content = import_path_fix + file_content
                
                print(f"DEBUG: Injected database path: {current_db_path}")
                print(f"DEBUG: File content after replacement (first 200 chars): {file_content[:200]}")
            else:
                print(f"DEBUG: current_scenario is None, skipping database path injection")
            
            # Create a temporary file with the modified content in the backend directory
            # This ensures dependencies (like dataprocessing.py) are available for imports
            import tempfile
            import time
            
            # Create temp file in the backend directory where dependencies are located
            backend_dir = os.path.dirname(os.path.abspath(__file__))
            timestamp = int(time.time() * 1000)  # Unique timestamp
            temp_filename = f"__temp_exec_{timestamp}.py"
            temp_file_path = os.path.join(backend_dir, temp_filename)
            
            # Write the modified content to the temp file
            with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
                temp_file.write(file_content)
            
            # Use the temporary file for execution
            abs_path = temp_file_path
            
        except Exception as e:
            print(f"Warning: Could not modify file content: {e}")
            # Continue with original file if modification fails
        
        result = subprocess.run(
            [sys.executable, abs_path],
            cwd=execution_cwd,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # Clean up temporary file if it was created
        if temp_file_path and temp_file_path != uploaded_files.get(filename, ''):
            try:
                # Clean up the temp file in the backend directory
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    print(f"DEBUG: Cleaned up temp file: {temp_file_path}")
            except Exception as e:
                print(f"DEBUG: Could not clean up temp file {temp_file_path}: {e}")
                pass
        
        code_output = result.stdout
        code_error = result.stderr
        
        # Refresh file list to detect new files created during execution
        refresh_file_list()
        
        # Detect output files (visualizations, reports, etc.) - both new and modified
        output_files = []
        try:
            # Scan for output files in the execution directory
            scan_dir = execution_cwd if execution_cwd else temp_dir
            if scan_dir and os.path.exists(scan_dir):
                # Scan for output files in the execution directory
                output_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.html', '.csv', '.pdf', '.txt', '.json']
                
                # Get all output files in execution directory with their modification times
                recently_modified_files = []
                for root, dirs, files in os.walk(scan_dir):
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in output_extensions):
                            abs_file_path = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_file_path, scan_dir)
                            rel_path = rel_path.replace('\\', '/')  # Normalize for web
                            
                            try:
                                current_mod_time = os.path.getmtime(abs_file_path)
                                
                                # Check if file is new or was modified during execution
                                is_new_or_modified = False
                                if abs_file_path not in file_mod_times_before:
                                    # New file created during execution
                                    is_new_or_modified = True
                                    print(f"DEBUG: New file detected: {rel_path}")
                                elif current_mod_time > file_mod_times_before[abs_file_path]:
                                    # Existing file modified during execution
                                    is_new_or_modified = True
                                    print(f"DEBUG: Modified file detected: {rel_path}")
                                elif current_mod_time >= execution_start_time - 1:  # 1 second tolerance
                                    # File modified around execution time (catch edge cases)
                                    is_new_or_modified = True
                                    print(f"DEBUG: Recently modified file detected: {rel_path}")
                                
                                if is_new_or_modified:
                                    recently_modified_files.append((rel_path, abs_file_path))
                                    
                            except OSError:
                                # If we can't get mod time, include it to be safe
                                recently_modified_files.append((rel_path, abs_file_path))
                
                # Create output file objects for recently modified/created files
                for rel_path, abs_file_path in recently_modified_files:
                    # Determine file type for frontend handling
                    file_type = "file"
                    if rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
                        file_type = "image"
                    elif rel_path.lower().endswith('.html'):
                        # Check if it's a plotly chart based on filename patterns
                        filename = os.path.basename(rel_path)
                        if ('chart' in filename.lower() or 
                            'plot' in filename.lower() or 
                            'interactive' in filename.lower() or
                            'sql_results' in filename.lower() or
                            'visualization' in filename.lower() or
                            'map' in filename.lower() or
                            'hubs' in filename.lower() or
                            'geo' in filename.lower() or
                            'scatter' in filename.lower() or
                            'bar' in filename.lower() or
                            'line' in filename.lower() or
                            'pie' in filename.lower() or
                            'heatmap' in filename.lower() or
                            'box' in filename.lower() or
                            'histogram' in filename.lower()):
                            file_type = "plotly-html"
                        else:
                            file_type = "html"
                    elif rel_path.lower().endswith('.csv'):
                        file_type = "csv"
                    elif rel_path.lower().endswith('.pdf'):
                        file_type = "pdf"
                    
                    # Prioritize image files for display
                    if file_type == "image":
                        output_files.insert(0, {
                            "filename": os.path.basename(rel_path),
                            "path": rel_path,
                            "url": f"/files/{rel_path}/download",
                            "type": file_type
                        })
                    else:
                        output_files.append({
                            "filename": os.path.basename(rel_path),
                            "path": rel_path,
                            "url": f"/files/{rel_path}/download",
                            "type": file_type
                        })
                        
                print(f"DEBUG: Found {len(output_files)} output files for display")
                        
        except Exception as e:
            print(f"Error detecting output files: {e}")
        
        # Log execution to current scenario's history (only if output files were generated)
        if output_files:
            log_execution_to_scenario(
                command=f"python {filename}",
                output=result.stdout,
                error=result.stderr,
                output_files=output_files
            )
        
        # Refresh file list to ensure newly created files are tracked
        refresh_file_list()
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode,
            "output_files": output_files,
            "created_files": [f["filename"] for f in output_files]  # List of created/modified output files
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@app.post("/install")
async def install_requirements(filename: str):
    """Install requirements from a requirements.txt file"""
    # Check if file is in uploaded_files
    if filename in uploaded_files:
        abs_path = uploaded_files[filename]
    else:
        # Check if it's a scenario-generated file
        current_scenario = scenario_manager.get_current_scenario()
        if current_scenario:
            scenario_dir = os.path.dirname(current_scenario.database_path)
            scenario_file_path = os.path.join(scenario_dir, filename)
            if os.path.exists(scenario_file_path):
                abs_path = scenario_file_path
            else:
                raise HTTPException(status_code=404, detail="File not found")
        else:
            raise HTTPException(status_code=404, detail="File not found")
    
    if not filename.endswith('requirements.txt'):
        raise HTTPException(status_code=400, detail="Only requirements.txt files can be installed")
    
    try:
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", abs_path],
            capture_output=True,
            text=True,
            timeout=300
        )
        
        # Log execution to current scenario's history (only if there were errors)
        if result.stderr:
            log_execution_to_scenario(
                command=f"pip install -r {filename}",
                output=result.stdout,
                error=result.stderr
            )
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Installation timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Installation failed: {str(e)}")

@app.post("/chat")
async def chat(request: ChatRequest):
    """Send a message to AI Agent and get response (now defaults to LangGraph)"""
    global uploaded_files, code_output, code_error, file_contents
    
    # Use LangGraph by default
    if use_langgraph_by_default:
        return await langgraph_chat(ChatMessage(role="user", content=request.message))
    
    try:
        # Build context with execution results only
        context = build_context_for_agent(uploaded_files, code_output, code_error)
        
        # Prepare the full prompt with context
        full_prompt = request.message
        if context:
            full_prompt = f"""Context about the user's project:
{context}

User's question: {request.message}

You can edit files by using this format:
[EDIT:filename]
new file content here
[/EDIT]

Only use the EDIT format when the user specifically asks you to modify a file. Always explain what changes you're making."""

        # Get response from selected AI model
        if current_ai_model == "openai":
            if openai_client is None:
                raise HTTPException(status_code=500, detail="OpenAI client not configured")
            
            response = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": "You are a helpful coding assistant. You can see the user's uploaded files and code execution results. When asked to edit files, use the [EDIT:filename]content[/EDIT] format."},
                    {"role": "user", "content": full_prompt}
                ],
                temperature=0.7,
                max_tokens=2000
            )
            assistant_message = response.choices[0].message.content
            
        elif current_ai_model == "gemini":
            if not genai_configured:
                raise HTTPException(status_code=500, detail="Gemini client not configured")
            
            model = genai.GenerativeModel('gemini-2.5-flash')
            
            # Combine system and user prompts for Gemini
            combined_prompt = f"""You are a helpful coding assistant. You can see the user's uploaded files and code execution results. When asked to edit files, use the [EDIT:filename]content[/EDIT] format.

{full_prompt}"""
            
            response = model.generate_content(
                combined_prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2000,
                )
            )
            assistant_message = response.text
        else:
            raise HTTPException(status_code=500, detail=f"Unsupported AI model: {current_ai_model}")
        
        # Check for file edit requests
        edit_requests = parse_file_edit_request(assistant_message)
        file_updates = []
        
        if edit_requests and uploaded_files:
            for filename, new_content in edit_requests:
                # Find the file path
                matching_files = [path for rel_path, path in uploaded_files.items() if rel_path == filename or os.path.basename(rel_path) == filename]
                if matching_files:
                    file_path = matching_files[0]
                    if write_file_content(file_path, new_content.strip()):
                        rel_path = next((rp for rp, ap in uploaded_files.items() if ap == file_path), filename)
                        file_contents[rel_path] = new_content.strip()
                        file_updates.append({"filename": filename, "status": "success"})
                    else:
                        file_updates.append({"filename": filename, "status": "failed"})
                else:
                    file_updates.append({"filename": filename, "status": "not_found"})
        
        return {
            "response": assistant_message,
            "file_updates": file_updates
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")

@app.delete("/files")
async def clear_files():
    """Clear all uploaded files and reset the system"""
    global uploaded_files, temp_directories, file_contents, ai_created_files, current_database_path, database_schema
    
    try:
        # Clear all global variables
        uploaded_files = {}
        file_contents = {}
        ai_created_files = set()
        database_schema = None
        current_database_path = None
        
        # Clean up temp directories
        for session_name, temp_dir in temp_directories.items():
            if os.path.exists(temp_dir):
                try:
                    import shutil
                    shutil.rmtree(temp_dir)
                    print(f"Cleaned up temp directory: {temp_dir}")
                except Exception as e:
                    print(f"Could not clean up temp directory {temp_dir}: {e}")
        
        temp_directories = {}
        
        # Reset session
        global current_session_id
        current_session_id = None
        
        return {"message": "All files cleared and system reset"}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear files: {str(e)}")

@app.get("/status")
async def get_status():
    """Get current status of the application"""
    return {
        "files_count": len(uploaded_files),
        "has_code_output": bool(code_output),
        "has_code_error": bool(code_error),
        "current_ai_model": current_ai_model,
        "available_models": {
            "openai": openai_client is not None,
            "gemini": genai_configured
        }
    }

@app.post("/switch-ai")
async def switch_ai_model(request: SwitchAIRequest):
    """Switch between AI models"""
    global current_ai_model
    
    if request.model == "openai" and openai_client is None:
        raise HTTPException(status_code=400, detail="OpenAI API key not configured")
    elif request.model == "gemini" and not genai_configured:
        raise HTTPException(status_code=400, detail="Gemini API key not configured")
    elif request.model not in ["openai", "gemini"]:
        raise HTTPException(status_code=400, detail="Invalid model. Choose 'openai' or 'gemini'")
    
    current_ai_model = request.model
    return {"message": f"Switched to {request.model}", "current_model": current_ai_model}

@app.get("/current-ai")
async def get_current_ai():
    """Get the currently selected AI model"""
    return {
        "current_model": current_ai_model,
        "available_models": {
            "openai": openai_client is not None,
            "gemini": genai_configured
        }
    }

@app.post("/langgraph-chat")
async def langgraph_chat(message: ChatMessage, request: Request = None):
    """Chat endpoint using LangGraph agent that can create and execute files"""
    global code_output, code_error
    
    try:
        print(f"DEBUG: LangGraph chat started with message: {message.content}")
        
        # Get current scenario and database path
        db_path = get_active_scenario_database()
        scenario = scenario_manager.get_current_scenario()
        
        print(f"DEBUG: Using database path: {db_path}")
        print(f"DEBUG: Current scenario: {scenario.id if scenario else 'None'}")
        
        # Clear execution context for each new request to avoid accumulation
        print(f"DEBUG: Clearing previous execution context")
        print(f"DEBUG: Previous code_output length: {len(code_output) if code_output else 0}")
        print(f"DEBUG: Previous code_error length: {len(code_error) if code_error else 0}")
        
        agent = await get_or_create_agent_v2()
        
        # Set the database path for the agent
        if db_path and os.path.exists(db_path):
            try:
                db_info = get_database_info(db_path)
                agent.set_cached_schema(db_info)
                print(f"DEBUG: Updated agent schema with {len(db_info.get('tables', []))} tables")
            except Exception as e:
                print(f"DEBUG: Error updating agent schema: {e}")
        
        # Start with clean execution context for each request
        response, created_files = agent.run(
            user_message=message.content,
            execution_output="",  # Start clean for each request
            execution_error="",   # Start clean for each request
            thread_id=getattr(message, 'thread_id', 'default'),  # Use thread ID if provided
            scenario_id=scenario.id if scenario else None,
            database_path=db_path
        )
        
        print(f"DEBUG: Agent response: {response[:200]}...")
        print(f"DEBUG: Created files: {created_files}")
        
        # Update global execution output if agent executed code
        if hasattr(agent, 'last_execution_output'):
            code_output = agent.last_execution_output
        if hasattr(agent, 'last_execution_error'):
            code_error = agent.last_execution_error
        
        print(f"DEBUG: Updated code_output: {code_output[:100] if code_output else 'None'}...")
        print(f"DEBUG: Updated code_error: {code_error[:100] if code_error else 'None'}...")
        
        # Only log actual executions that generate files or have errors, not chat messages
        should_log_execution = scenario and (code_output or code_error or created_files)
        
        # Always refresh the file list to show new files and outputs
        print(f"DEBUG: Before refresh - uploaded_files: {list(uploaded_files.keys())}")
        print(f"DEBUG: Before refresh - ai_created_files: {list(ai_created_files)}")
        
        # Store the AI-created files before refresh to detect new ones
        previous_ai_files = set(ai_created_files)
        refresh_file_list()
        new_files = ai_created_files - previous_ai_files
        print(f"DEBUG: Newly created files in this execution: {list(new_files)}")
        
        print(f"DEBUG: After refresh - uploaded_files: {list(uploaded_files.keys())}")
        print(f"DEBUG: After refresh - ai_created_files: {list(ai_created_files)}")
        
        # Detect output files (visualizations, reports, etc.)
        output_files = []
        should_log_execution = False
        try:
            # Get the current temp directory
            temp_dir = temp_directories.get('current')
            print(f"DEBUG: Checking for output files in temp_dir: {temp_dir}")
            
            if temp_dir and os.path.exists(temp_dir):
                # Scan for output files in the temp directory
                output_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.html', '.csv', '.pdf', '.txt', '.json']
                print(f"DEBUG: Looking for files with extensions: {output_extensions}")
                
                # Get all output files in temp directory
                all_files = []
                for root, dirs, files in os.walk(temp_dir):
                    print(f"DEBUG: Scanning directory: {root}")
                    print(f"DEBUG: Found files: {files}")
                    for file in files:
                        if any(file.lower().endswith(ext) for ext in output_extensions):
                            abs_path = os.path.join(root, file)
                            rel_path = os.path.relpath(abs_path, temp_dir)
                            rel_path = rel_path.replace('\\', '/')  # Normalize for web
                            all_files.append((rel_path, abs_path))
                            print(f"DEBUG: Found output file: {rel_path} -> {abs_path}")
                
                print(f"DEBUG: All output files found: {all_files}")
                print(f"DEBUG: Current uploaded_files keys: {list(uploaded_files.keys())}")
                print(f"DEBUG: New AI created files: {list(new_files)}")
                
                # Only include files that were actually created in this execution
                output_files_to_include = []
                for rel_path, abs_path in all_files:
                    # Check if file was created in this execution
                    is_recent = rel_path in new_files
                    
                    # Only include files that were created in this execution
                    if is_recent and rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.html', '.csv', '.pdf', '.txt', '.json')):
                        output_files_to_include.append((rel_path, abs_path))
                        print(f"DEBUG: Including NEW output file: {rel_path}")
                    elif rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.html', '.csv', '.pdf', '.txt', '.json')):
                        print(f"DEBUG: Skipping old output file: {rel_path}")
                    else:
                        print(f"DEBUG: Skipping non-output file: {rel_path}")
                
                # Copy output files to scenario directory for persistence
                scenario_output_files = []
                if scenario and output_files_to_include:
                    scenario_dir = os.path.dirname(scenario.database_path)
                    scenario_output_dir = os.path.join(scenario_dir, "outputs")
                    os.makedirs(scenario_output_dir, exist_ok=True)
                    
                    for rel_path, abs_path in output_files_to_include:
                        # Copy file to scenario output directory
                        filename = os.path.basename(rel_path)
                        scenario_file_path = os.path.join(scenario_output_dir, filename)
                        
                        try:
                            shutil.copy2(abs_path, scenario_file_path)
                            # Create relative path from scenario directory
                            scenario_rel_path = os.path.relpath(scenario_file_path, scenario_dir)
                            scenario_rel_path = scenario_rel_path.replace('\\', '/')  # Normalize for web
                            scenario_output_files.append(scenario_rel_path)
                            print(f"DEBUG: Copied output file to scenario: {rel_path} -> {scenario_rel_path}")
                        except Exception as e:
                            print(f"DEBUG: Error copying output file to scenario: {e}")
                            # Fallback to original path
                            scenario_output_files.append(rel_path)
                else:
                    # No scenario or no output files, use original paths
                    scenario_output_files = [rel_path for rel_path, _ in output_files_to_include]
                
                # Create output file objects for frontend
                for i, (rel_path, abs_path) in enumerate(output_files_to_include):
                    # Use scenario path if available, otherwise use original path
                    file_path = scenario_output_files[i] if i < len(scenario_output_files) else rel_path
                    
                    # Determine file type for frontend handling
                    file_type = "file"
                    if rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
                        file_type = "image"
                    elif rel_path.lower().endswith('.html'):
                        # Check if it's a plotly chart based on filename patterns
                        filename = os.path.basename(rel_path)
                        if ('chart' in filename.lower() or 
                            'plot' in filename.lower() or 
                            'interactive' in filename.lower() or
                            'sql_results' in filename.lower() or
                            'visualization' in filename.lower() or
                            'map' in filename.lower() or
                            'hubs' in filename.lower() or
                            'geo' in filename.lower() or
                            'scatter' in filename.lower() or
                            'bar' in filename.lower() or
                            'line' in filename.lower() or
                            'pie' in filename.lower() or
                            'heatmap' in filename.lower() or
                            'box' in filename.lower() or
                            'histogram' in filename.lower()):
                            file_type = "plotly-html"
                        else:
                            file_type = "html"
                    elif rel_path.lower().endswith('.csv'):
                        file_type = "csv"
                    elif rel_path.lower().endswith('.pdf'):
                        file_type = "pdf"
                    
                    elif rel_path.lower().endswith('.txt'):
                        file_type = "text"
                    elif rel_path.lower().endswith('.json'):
                        file_type = "json"
                    
                    # Prioritize image files for display
                    if file_type == "image":
                        output_files.insert(0, {
                            "filename": os.path.basename(rel_path),
                            "path": file_path,
                            "url": f"/files/{file_path}/download",
                            "type": file_type
                        })
                    else:
                        output_files.append({
                            "filename": os.path.basename(rel_path),
                            "path": file_path,
                            "url": f"/files/{file_path}/download",
                            "type": file_type
                        })
            
            print(f"DEBUG: Output files for frontend: {output_files}")
        except Exception as e:
            print(f"Error detecting output files: {e}")
            import traceback
            traceback.print_exc()
            # Ensure output_files is defined even if there's an error
            output_files = []
        
        # Log execution to scenario history with processed output files (only if files were generated)
        if should_log_execution and output_files and len(output_files) > 0:
            # Use the processed output_files list for logging
            files_to_log = [file["path"] for file in output_files]
            log_execution_to_scenario(
                command=f"LangGraph Agent Execution: {message.content[:100]}...",
                output=code_output,
                error=code_error,
                output_files=files_to_log
            )
        
        return {
            "response": response,
            "created_files": created_files,
            "current_model": current_ai_model,
            "agent_type": current_agent_type,
            "execution_output": code_output,
            "execution_error": code_error,
            "has_execution_results": bool(code_output or code_error),
            "output_files": output_files if 'output_files' in locals() else []
        }
        
    except Exception as e:
        print(f"DEBUG: LangGraph chat error: {str(e)}")
        return {"error": f"LangGraph chat error: {str(e)}", "current_model": current_ai_model}

@app.post("/langgraph-chat-v2")
async def langgraph_chat_v2(message: ChatMessage, request: Request = None):
    """Enhanced chat endpoint using the new simplified agent v2"""
    try:
        # Get the agent
        agent = await get_or_create_agent_v2()
        
        # Get current scenario ID for context
        current_scenario = scenario_manager.get_current_scenario()
        scenario_id = current_scenario.id if current_scenario else None
        
        # Run the agent
        response, generated_files, execution_output, execution_error = agent.run(
            user_message=message.content,
            scenario_id=scenario_id
        )
        

        
        # Log execution to scenario history if files were generated
        if generated_files:
            log_execution_to_scenario(
                command=f"Agent v2: {message.content}",
                output=response,
                output_files=generated_files
            )
        
        return {
            "response": response,
            "generated_files": generated_files,
            "scenario_id": scenario_id,
            "agent_version": "v2",
            "user_query": message.content,  # Include the original user query
            "query_timestamp": int(time.time() * 1000),  # Convert to milliseconds for frontend
            "execution_output": execution_output,  # Include actual execution output
            "execution_error": execution_error,  # Include actual execution error
            "has_execution_results": bool(execution_output or execution_error or generated_files)
        }
        
    except Exception as e:
        print(f"ERROR in langgraph_chat_v2: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "response": f"❌ Error: {str(e)}",
            "generated_files": [],
            "scenario_id": None,
            "agent_version": "v2"
        }

@app.get("/agents")
async def get_available_agents():
    """Get list of available agent types (only returns the main user-facing agent)"""
    agents = list_available_agents()
    return {
        "agents": agents,
        "current_agent": current_agent_type,
        "default_agent": get_default_agent(),
        "note": "Only data_analyst is user-selectable. Other agents are internal workflow agents."
    }

@app.post("/switch-agent")
async def switch_agent(request: dict):
    """Switch to a different agent type (deprecated - agents are now invoked by workflow)"""
    return {
        "error": "Manual agent switching is no longer supported",
        "message": "Agents are now automatically invoked by the workflow. Only data_analyst is user-facing.",
        "current_agent": current_agent_type,
        "available_agent": "data_analyst"
    }

@app.get("/current-agent")
async def get_current_agent():
    """Get the currently selected agent type"""
    available_agents = list_available_agents()
    return {
        "current_agent": current_agent_type,
        "agent_description": available_agents.get(current_agent_type, "Unknown agent"),
        "available_agents": available_agents,
        "note": "Only data_analyst is user-selectable. Other agents are internal workflow agents."
    }

@app.post("/toggle-chat-mode")
async def toggle_chat_mode(request: dict):
    """Toggle between LangGraph and traditional chat"""
    global use_langgraph_by_default
    
    use_langgraph = request.get("use_langgraph", True)
    use_langgraph_by_default = use_langgraph
    
    mode = "LangGraph" if use_langgraph_by_default else "Traditional"
    return {
        "message": f"Chat mode set to {mode}",
        "use_langgraph": use_langgraph_by_default,
        "current_agent": current_agent_type if use_langgraph_by_default else "traditional"
    }

@app.get("/chat-mode")
async def get_chat_mode():
    """Get current chat mode"""
    mode = "LangGraph" if use_langgraph_by_default else "Traditional"
    return {
        "use_langgraph": use_langgraph_by_default,
        "mode": mode,
        "current_agent": current_agent_type if use_langgraph_by_default else "traditional"
    }

# ====== NEW SQL-BASED ENDPOINTS ======

@app.get("/database/info")
async def get_database_info_endpoint():
    """Get basic database information"""
    db_path = get_active_scenario_database()
    
    if not db_path:
        raise HTTPException(status_code=400, detail="No database available. Please upload files first.")
    
    info = get_database_info(db_path)
    if "error" in info:
        # Distinguish between not found and other errors
        if info["error"].startswith("Database file not found"):
            raise HTTPException(status_code=400, detail=info["error"])
        else:
            raise HTTPException(status_code=500, detail=info["error"])
    return info

@app.get("/database/schema")
async def get_cached_database_schema():
    """Get cached database schema (generated automatically when database is created)"""
    db_path = get_active_scenario_database()
    
    if not db_path:
        raise HTTPException(status_code=400, detail="No database schema available. Please upload files to create a database first.")
    
    schema = get_database_info(db_path)
    return {
        "schema": schema,
        "cached": True,
        "message": "Schema automatically generated when database was created"
    }

@app.post("/sql/execute")
async def execute_raw_sql(sql: str = Form(...)):
    """Execute raw SQL query"""
    db_path = get_active_scenario_database()
    
    if not db_path:
        raise HTTPException(status_code=400, detail="No database available. Please upload files first.")
    
    conn = None
    try:
        conn = connect_to_database(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        
        if sql.strip().upper().startswith('SELECT'):
            # For SELECT queries, return results
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
            
            # Don't log background SQL queries to execution history
            
            return {
                "success": True,
                "sql": sql,
                "result": result,
                "columns": columns,
                "row_count": len(result)
            }
        else:
            # For other queries (INSERT, UPDATE, DELETE), return affected rows
            conn.commit()
            
            # Don't log background SQL queries to execution history
            
            return {
                "success": True,
                "sql": sql,
                "rows_affected": cursor.rowcount,
                "message": f"Query executed successfully. {cursor.rowcount} rows affected."
            }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SQL execution failed: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/database/tables/{table_name}/schema")
async def get_table_schema(table_name: str):
    """Get schema for a specific table"""
    db_path = get_active_scenario_database()
    
    if not db_path:
        raise HTTPException(status_code=400, detail="No database available. Please upload files first.")
    
    conn = None
    try:
        conn = connect_to_database(db_path)
        cursor = conn.cursor()
        
        # Get schema information
        cursor.execute(f"PRAGMA table_info({table_name})")
        schema_info = cursor.fetchall()
        schema = [{"name": row[1], "type": row[2]} for row in schema_info]
        
        # Get sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
        columns = [description[0] for description in cursor.description]
        rows = cursor.fetchall()
        sample_data = [dict(zip(columns, row)) for row in rows]
        
        return {
            "table_name": table_name,
            "schema": schema,
            "sample_data": sample_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get table schema: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/sql/mode")
async def get_sql_mode_status():
    """Get current SQL mode status"""
    db_path = get_active_scenario_database()
    
    if db_path and os.path.exists(db_path):
        try:
            db_info = get_database_info(db_path)
            total_tables = db_info.get("total_tables", 0)
        except:
            total_tables = 0
    else:
        total_tables = 0
    
    return {
        "sql_enabled": db_path is not None and os.path.exists(db_path),
        "database_path": db_path,
        "total_tables": total_tables
    }

@app.get("/database/download")
async def download_database():
    """Download the SQLite database file"""
    db_path = get_active_scenario_database()
    
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="No database available for download")
    
    from fastapi.responses import FileResponse
    
    return FileResponse(
        db_path,
        filename=os.path.basename(db_path),
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(db_path)}"}
    )

@app.get("/database/info/detailed")
async def get_detailed_database_info():
    """Get detailed database information including file stats"""
    db_path = get_active_scenario_database()
    
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="No database available")
    
    # Get basic database info
    db_info = get_database_info(db_path)
    
    # Add file statistics
    file_stats = os.stat(db_path)
    
    return {
        **db_info,
        "database_file": {
            "path": db_path,
            "filename": os.path.basename(db_path),
            "size_bytes": file_stats.st_size,
            "size_mb": round(file_stats.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            "modified": datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
    }

@app.get("/database/export/{format}")
async def export_database(format: str):
    """Export database to different formats (sql, csv)"""
    global temp_directories
    
    db_path = get_active_scenario_database()
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="No database available")
    
    if format.lower() not in ['sql', 'csv']:
        raise HTTPException(status_code=400, detail="Supported formats: sql, csv")
    
    conn = None
    try:
        conn = connect_to_database(db_path)
        temp_dir = temp_directories.get('current', tempfile.gettempdir())
        
        if format.lower() == 'sql':
            # Export as SQL dump
            export_path = os.path.join(temp_dir, "database_export.sql")
            
            with open(export_path, 'w') as f:
                for line in conn.iterdump():
                    f.write('%s\n' % line)
            
            from fastapi.responses import FileResponse
            return FileResponse(
                export_path,
                filename="database_export.sql",
                media_type="text/plain",
                headers={"Content-Disposition": "attachment; filename=database_export.sql"}
            )
        
        elif format.lower() == 'csv':
            # Export all tables as CSV files in a zip
            import zipfile
            
            export_zip_path = os.path.join(temp_dir, "database_csv_export.zip")
            
            with zipfile.ZipFile(export_zip_path, 'w') as zipf:
                # Get all tables
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]
                
                for table in tables:
                    # Export each table to CSV
                    csv_path = os.path.join(temp_dir, f"{table}.csv")
                    df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                    df.to_csv(csv_path, index=False)
                    zipf.write(csv_path, f"{table}.csv")
                    os.remove(csv_path)  # Clean up individual CSV
            
            from fastapi.responses import FileResponse
            return FileResponse(
                export_zip_path,
                filename="database_csv_export.zip",
                media_type="application/zip",
                headers={"Content-Disposition": "attachment; filename=database_csv_export.zip"}
            )
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export failed: {str(e)}")
    finally:
        if conn:
            conn.close()

@app.get("/database/whitelist")
async def get_database_whitelist():
    """Get current database table whitelist"""
    global table_whitelist
    
    # Initialize whitelist if empty
    current_whitelist = get_table_whitelist()
    
    # Get available tables for reference
    available_tables = []
    db_path = get_active_scenario_database()
    if db_path and os.path.exists(db_path):
        try:
            db_info = get_database_info(db_path)
            if "tables" in db_info:
                available_tables = [table["name"] for table in db_info["tables"]]
        except Exception as e:
            print(f"DEBUG: Error getting available tables: {e}")
    
    return {
        "whitelist": list(current_whitelist),
        "available_tables": available_tables,
        "total_whitelisted": len(current_whitelist),
        "total_available": len(available_tables)
    }

@app.post("/database/whitelist")
async def update_database_whitelist(request: WhitelistRequest):
    """Update database table whitelist"""
    global table_whitelist
    
    try:
        # Validate that the tables exist in the database
        db_path = get_active_scenario_database()
        if db_path and os.path.exists(db_path):
            db_info = get_database_info(db_path)
            if "tables" in db_info:
                available_tables = {table["name"] for table in db_info["tables"]}
                invalid_tables = set(request.tables) - available_tables
                
                if invalid_tables:
                    raise HTTPException(
                        status_code=400, 
                        detail=f"Invalid tables: {list(invalid_tables)}. Available tables: {list(available_tables)}"
                    )
        
        # Update the whitelist
        table_whitelist = set(request.tables)
        
        print(f"DEBUG: Updated table whitelist: {table_whitelist}")
        
        # Refresh the agent's schema to apply the new whitelist
        try:
            agent = await get_or_create_agent_v2()
            if hasattr(agent, 'refresh_schema_whitelist'):
                agent.refresh_schema_whitelist()
                print(f"DEBUG: Agent schema refreshed with new whitelist")
            else:
                print(f"DEBUG: Agent does not support schema refresh")
        except Exception as e:
            print(f"DEBUG: Error refreshing agent schema: {e}")
            # Don't fail the whitelist update if schema refresh fails
        
        return {
            "message": "Table whitelist updated successfully",
            "whitelist": list(table_whitelist),
            "total_whitelisted": len(table_whitelist)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating whitelist: {str(e)}")

@app.post("/action-chat")
async def action_chat(request: ActionRequest):
    """Enhanced chat endpoint with action-based routing using LangGraph agent"""
    global code_output, code_error, ai_created_files
    
    try:
        print(f"DEBUG: Action-based chat started with message: {request.message}")
        print(f"DEBUG: Action type: {request.action_type}")
        print(f"DEBUG: Thread ID: {request.thread_id}")
        
        # Get or create the LangGraph agent
        agent = await get_or_create_agent_v2()
        
        # Use the LangGraph agent to process the request
        response, created_files = agent.run(
            user_message=request.message,
            execution_output=code_output,
            execution_error=code_error,
            thread_id=request.thread_id,
            user_feedback=""
        )
        
        # Update global execution output
        if hasattr(agent, 'last_execution_output'):
            code_output = agent.last_execution_output
        if hasattr(agent, 'last_execution_error'):
            code_error = agent.last_execution_error
        
        # Track created files globally
        for file_path in created_files:
            ai_created_files.add(file_path)
            # Add to uploaded_files for file management
            abs_path = os.path.abspath(file_path)
            rel_path = os.path.relpath(abs_path)
            uploaded_files[rel_path] = abs_path
        
        # Refresh file list to detect new files
        refresh_file_list()
        
        # Determine action type from agent's classification
        action_type = request.action_type or "UNKNOWN"
        if hasattr(agent, 'last_action_type'):
            action_type = agent.last_action_type
        
        # Detect output files for visualization
        output_files = []
        output_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.html', '.csv', '.pdf']
        
        for file_path in created_files:
            if any(file_path.lower().endswith(ext) for ext in output_extensions):
                normalized_path = file_path.replace('\\', '/')
                # Determine file type for frontend handling
                file_type = "file"
                if normalized_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    file_type = "image"
                elif normalized_path.lower().endswith('.html'):
                    # Check if it's a plotly chart based on filename patterns
                    filename = os.path.basename(file_path)
                    if ('chart' in filename.lower() or 
                        'plot' in filename.lower() or 
                        'interactive' in filename.lower() or
                        'sql_results' in filename.lower() or
                        'visualization' in filename.lower() or
                        'map' in filename.lower() or
                        'hubs' in filename.lower() or
                        'geo' in filename.lower() or
                        'scatter' in filename.lower() or
                        'bar' in filename.lower() or
                        'line' in filename.lower() or
                        'pie' in filename.lower() or
                        'heatmap' in filename.lower() or
                        'box' in filename.lower() or
                        'histogram' in filename.lower()):
                        file_type = "plotly-html"
                    else:
                        file_type = "html"
                elif normalized_path.lower().endswith('.csv'):
                    file_type = "csv"
                elif normalized_path.lower().endswith('.pdf'):
                    file_type = "pdf"
                output_files.append({
                    "filename": os.path.basename(file_path),
                    "path": normalized_path,
                    "url": f"/files/{normalized_path}/download",
                    "type": file_type
                })
        
        # Check if this was a database modification that requires human-in-the-loop
        requires_approval = False
        db_modification_detected = False
        
        if ("parameter" in response.lower() and "updated" in response.lower()) or \
           ("database" in response.lower() and ("modified" in response.lower() or "changed" in response.lower())):
            db_modification_detected = True
            print("DEBUG: Database modification detected - triggering human-in-the-loop")
        
        # Log execution to scenario history with output files (only if files were generated)
        if output_files:
            log_execution_to_scenario(
                command=f"Action Execution: {action_type}: {request.message[:100]}...",
                output=code_output,
                error=code_error,
                output_files=output_files
            )
        
        return {
            "response": response,
            "action_type": action_type,
            "success": True,
            "created_files": created_files,
            "output_files": output_files,
            "execution_output": code_output,
            "execution_error": code_error,
            "has_execution_results": bool(code_output or code_error),
            "db_modification_detected": db_modification_detected,
            "requires_approval": requires_approval
        }
            
    except Exception as e:
        print(f"DEBUG: Action chat error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {
            "error": f"Action chat error: {str(e)}", 
            "current_model": current_ai_model,
            "action_type": "ERROR",
            "success": False
        }

@app.post("/action-chat-v2")
async def action_chat_v2(request: ActionRequest):
    """Enhanced action chat using simplified agent v2"""
    try:
        # Get the agent
        agent = await get_or_create_agent_v2()
        
        # Get current scenario
        current_scenario = scenario_manager.get_current_scenario()
        scenario_id = current_scenario.id if current_scenario else None
        
        # Run the agent (it will automatically classify and route the request)
        response, generated_files = agent.run(
            user_message=request.message,
            scenario_id=scenario_id
        )
        
        # Log to scenario history
        if generated_files or "modification completed" in response.lower():
            log_execution_to_scenario(
                command=f"Action v2: {request.message}",
                output=response,
                output_files=generated_files
            )
        
        return {
            "response": response,
            "generated_files": generated_files,
            "scenario_id": scenario_id,
            "classification": "auto-detected",
            "agent_version": "v2",
            "user_query": request.message,  # Include the original user query
            "query_timestamp": int(time.time())  # Include timestamp for organization
        }
        
    except Exception as e:
        print(f"ERROR in action_chat_v2: {e}")
        return {
            "response": f"❌ Error: {str(e)}",
            "generated_files": [],
            "scenario_id": None,
            "agent_version": "v2"
        }

async def handle_database_modification(message: str, conversation_history: List[dict], thread_id: str):
    """Handle requests to modify database parameters or data"""
    global code_output, code_error, current_database_path
    
    if not current_database_path:
        return {
            "response": "❌ **No Database Available**\n\nPlease upload files with data first to enable database operations.",
            "message_type": "error"
        }
    
    try:
        # For now, return a placeholder response
        return {
            "response": "🔧 **Database Modification**\n\nDatabase modification functionality is not yet implemented. Please use the SQL Database tab for direct SQL operations.",
            "message_type": "info"
        }
    except Exception as e:
        print(f"DEBUG: Database modification error: {e}")
        return {
            "error": f"Database modification error: {str(e)}",
            "message_type": "error"
        }

async def handle_visualization_request(message: str, conversation_history: List[dict], thread_id: str):
    """Handle visualization requests by creating and executing Python scripts"""
    global code_output, code_error
    
    print(f"DEBUG: Handling visualization request: {message}")
    
    try:
        # Use LangGraph agent with visualization focus
        agent = await get_or_create_agent_v2()
        
        # Run with the message, agent should detect it's a visualization request
        response, created_files = agent.run(
            user_message=message,
            execution_output="",
            execution_error="",
            thread_id=thread_id
        )
        
        # Update execution output
        if hasattr(agent, 'last_execution_output'):
            code_output = agent.last_execution_output
        if hasattr(agent, 'last_execution_error'):
            code_error = agent.last_execution_error
        
        # Refresh file list to detect new visualization files
        refresh_file_list()
        
        # Detect output files (visualizations)
        output_files = []
        output_extensions = ['.png', '.jpg', '.jpeg', '.svg', '.html', '.csv', '.pdf']
        
        for file_path in created_files:
            if any(file_path.lower().endswith(ext) for ext in output_extensions):
                normalized_path = file_path.replace('\\', '/')
                # Determine file type for frontend handling
                file_type = "file"
                if normalized_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
                    file_type = "image"
                elif normalized_path.lower().endswith('.html'):
                    # Check if it's a plotly chart based on filename patterns
                    filename = os.path.basename(file_path)
                    if ('chart' in filename.lower() or 
                        'plot' in filename.lower() or 
                        'interactive' in filename.lower() or
                        'sql_results' in filename.lower() or
                        'visualization' in filename.lower() or
                        'map' in filename.lower() or
                        'hubs' in filename.lower() or
                        'geo' in filename.lower() or
                        'scatter' in filename.lower() or
                        'bar' in filename.lower() or
                        'line' in filename.lower() or
                        'pie' in filename.lower() or
                        'heatmap' in filename.lower() or
                        'box' in filename.lower() or
                        'histogram' in filename.lower()):
                        file_type = "plotly-html"
                    else:
                        file_type = "html"
                elif normalized_path.lower().endswith('.csv'):
                    file_type = "csv"
                elif normalized_path.lower().endswith('.pdf'):
                    file_type = "pdf"
                output_files.append({
                    "filename": os.path.basename(file_path),
                    "path": normalized_path,
                    "url": f"/files/{normalized_path}/download",
                    "type": file_type
                })
        
        # Log execution to scenario history with output files
        log_execution_to_scenario(
            command=f"VISUALIZATION: {message}",
            output=code_output,
            error=code_error,
            output_files=output_files
        )
        
        return {
            "response": response,
            "action_type": "VISUALIZATION",
            "success": True,
            "created_files": created_files,
            "output_files": output_files,
            "execution_output": code_output,
            "execution_error": code_error
        }
        
    except Exception as e:
        print(f"DEBUG: Visualization error: {e}")
        return {
            "error": f"Visualization error: {str(e)}",
            "action_type": "VISUALIZATION",
            "success": False
        }

async def handle_sql_query(message: str, conversation_history: List[dict], thread_id: str):
    """Handle SQL query requests"""
    global current_database_path
    
    if not current_database_path:
        return {
            "response": "❌ **No Database Available**\n\nPlease upload files with data first to enable SQL queries.",
            "message_type": "error"
        }
    
    try:
        # For now, return a placeholder response directing users to the SQL tab
        return {
            "response": "🗄️ **SQL Query Request**\n\nFor SQL queries, please use the **SQL Database** tab where you can:\n- Browse all database tables\n- Execute custom SQL queries\n- Search and filter data\n\nThe SQL Database tab provides a complete interface for database operations.",
            "message_type": "info"
        }
    except Exception as e:
        print(f"DEBUG: SQL query error: {e}")
        return {
            "error": f"SQL query error: {str(e)}",
            "message_type": "error"
        }

@app.get("/action-types")
async def get_action_types():
    """Get available action types for the action-based system"""
    return {
        "action_types": [
            {
                "id": "SQL_QUERY",
                "name": "SQL Query",
                "description": "Execute database queries and data analysis",
                "icon": "📊",
                "examples": [
                    "Show me the top 10 records",
                    "What is the average value?",
                    "How many unique entries are there?"
                ]
            },
            {
                "id": "VISUALIZATION", 
                "name": "Visualization",
                "description": "Create charts, maps, and visual representations",
                "icon": "📈",
                "examples": [
                    "Create a bar chart of sales by region",
                    "Show me a map of customer locations",
                    "Generate a pie chart of categories"
                ]
            },
            {
                "id": "DATABASE_MODIFICATION",
                "name": "Database Modification", 
                "description": "Modify database parameters and re-run models",
                "icon": "⚙️",
                "examples": [
                    "Change the maximum capacity to 5000",
                    "Set the minimum threshold to 100",
                    "Update the cost parameter to 2.5"
                ]
            }
        ]
    }

@app.get("/memory/history/{thread_id}")
async def get_conversation_history(thread_id: str, limit: int = 10):
    """Get conversation history for a specific thread"""
    try:
        agent = await get_or_create_agent_v2()
        if hasattr(agent, 'get_conversation_history'):
            history = agent.get_conversation_history(thread_id, limit)
            # Convert LangChain messages to simple dict format
            formatted_history = []
            for msg in history:
                if hasattr(msg, 'content'):
                    formatted_history.append({
                        "role": "human" if msg.__class__.__name__ == "HumanMessage" else "assistant",
                        "content": msg.content,
                        "timestamp": getattr(msg, 'timestamp', None)
                    })
            return {"history": formatted_history, "thread_id": thread_id}
        else:
            return {"history": [], "thread_id": thread_id, "message": "Memory not available"}
    except Exception as e:
        return {"error": f"Failed to get conversation history: {str(e)}", "thread_id": thread_id}

@app.delete("/memory/history/{thread_id}")
async def clear_conversation_history(thread_id: str):
    """Clear conversation history for a specific thread"""
    try:
        agent = await get_or_create_agent_v2()
        if hasattr(agent, 'clear_conversation_history'):
            success = agent.clear_conversation_history(thread_id)
            return {"success": success, "thread_id": thread_id, "message": "Conversation history cleared"}
        else:
            return {"success": False, "thread_id": thread_id, "message": "Memory not available"}
    except Exception as e:
        return {"error": f"Failed to clear conversation history: {str(e)}", "thread_id": thread_id}

@app.get("/memory/threads")
async def list_conversation_threads():
    """List all available conversation threads"""
    try:
        agent = await get_or_create_agent_v2()
        if hasattr(agent, 'checkpointer') and agent.checkpointer:
            # This would need to be implemented based on the specific checkpointer
            # For now, return a placeholder
            return {"threads": ["default"], "message": "Memory system active"}
        else:
            return {"threads": [], "message": "Memory not available"}
    except Exception as e:
        return {"error": f"Failed to list conversation threads: {str(e)}"}

@app.post("/approval/respond")
async def respond_to_model_selection(request: ApprovalRequest):
    """Respond to a model selection request"""
    try:
        print(f"DEBUG: Model selection response received for thread {request.thread_id}: {request.approval_response}")
        
        agent = await get_or_create_agent_v2()
        if not hasattr(agent, 'continue_after_model_selection'):
            return {
                "error": "Agent does not support model selection workflow",
                "success": False
            }
        
        # Continue the workflow with the model selection response
        response, created_files = agent.continue_after_model_selection(
            thread_id=request.thread_id,
            selection_response=request.approval_response
        )
        
        # Check if this resulted in another model selection request
        if "MODEL_SELECTION_REQUIRED" in response:
            return {
                "response": response,
                "requires_model_selection": True,
                "success": True,
                "created_files": created_files
            }
        else:
            return {
                "response": response,
                "requires_model_selection": False,
                "success": True,
                "created_files": created_files
            }
            
    except Exception as e:
        print(f"DEBUG: Model selection response error: {str(e)}")
        return {
            "error": f"Model selection response error: {str(e)}",
            "success": False
        }

@app.get("/approval/status/{thread_id}")
async def get_model_selection_status(thread_id: str):
    """Get the current model selection status for a thread"""
    try:
        agent = await get_or_create_agent_v2()
        if not hasattr(agent, 'checkpointer') or not agent.checkpointer:
            return {
                "has_pending_selection": False,
                "message": "Memory not available"
            }
        
        config = {"configurable": {"thread_id": thread_id}}
        checkpoint = agent.checkpointer.get(config)
        
        if checkpoint and "pending_approval" in checkpoint.values:
            pending = checkpoint.values["pending_approval"]
            if pending and pending.get("type") == "MODEL_SELECTION":
                return {
                    "has_pending_selection": True,
                    "selection_data": pending,
                    "thread_id": thread_id
                }
        
        return {
            "has_pending_selection": False,
            "thread_id": thread_id
        }
        
    except Exception as e:
        return {
            "error": f"Failed to get model selection status: {str(e)}",
            "has_pending_selection": False
        }

@app.get("/discover-models")
async def discover_models():
    """Discover available model files in the project"""
    try:
        # Look for model files in the current directory and subdirectories
        model_files = []
        
        # Common patterns for model files
        patterns = [
            "**/runall.*",
            "**/run_all*.*",
            "**/main.py",
            "**/model*.py",
            "**/run*.py",
            "**/execute*.py",
            "**/*.py",
            "**/*.bat",
            "**/*.sh"
        ]
        
        # Search in uploaded files first
        for rel_path in uploaded_files.keys():
            filename = os.path.basename(rel_path)
            if any(
                'runall' in filename.lower() or
                'run_all' in filename.lower() or
                filename.lower().startswith('main.') or
                filename.lower().startswith('model') or
                filename.lower().startswith('run') or
                filename.lower().startswith('execute')
                for _ in [None]  # Just to make this a generator expression
            ):
                model_files.append(rel_path)
        
        # Also search in current working directory
        current_dir = os.getcwd()
        for pattern in patterns:
            for file_path in glob.glob(pattern, recursive=True):
                if os.path.isfile(file_path):
                    # Get relative path from current directory
                    rel_path = os.path.relpath(file_path, current_dir)
                    if rel_path not in model_files:
                        model_files.append(rel_path)
        
        # Prioritize runall files
        runall_files = [f for f in model_files if 'runall' in f.lower()]
        other_files = [f for f in model_files if 'runall' not in f.lower()]
        
        # Sort: runall files first, then others
        sorted_files = runall_files + other_files
        
        return {
            "files": sorted_files[:20],  # Limit to top 20 files
            "total_found": len(model_files),
            "runall_files": runall_files
        }
        
    except Exception as e:
        return {
            "files": [],
            "error": str(e),
            "total_found": 0,
            "runall_files": []
        }

@app.post("/execute-model")
async def execute_model(request: ModelExecutionRequest):
    """Execute a selected model file using current scenario's database"""
    try:
        model_filename = request.model_filename
        parameters = request.parameters or {}
        
        # Get current scenario info for logging
        scenario = scenario_manager.get_current_scenario()
        db_path = get_active_scenario_database()
        
        # Check if file exists in uploaded files
        if model_filename in uploaded_files:
            file_path = uploaded_files[model_filename]
        else:
            # Check if file exists in current directory
            if os.path.exists(model_filename):
                file_path = os.path.abspath(model_filename)
            else:
                return {
                    "success": False,
                    "error": f"Model file '{model_filename}' not found",
                    "filename": model_filename
                }
        
        # Determine execution method based on file extension
        file_ext = os.path.splitext(model_filename)[1].lower()
        
        if file_ext == '.py':
            # Execute Python file
            try:
                # Change to the directory containing the file
                file_dir = os.path.dirname(file_path)
                original_cwd = os.getcwd()
                
                if file_dir:
                    os.chdir(file_dir)
                
                # Execute the Python file
                result = subprocess.run(
                    [sys.executable, os.path.basename(file_path)],
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
                
                # Restore original working directory
                os.chdir(original_cwd)
                
                # Log execution to scenario history
                log_execution_to_scenario(
                    command=f"Model Execution: {model_filename}",
                    output=result.stdout if result.returncode == 0 else None,
                    error=result.stderr if result.returncode != 0 else None
                )
                
                return {
                    "success": result.returncode == 0,
                    "filename": model_filename,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "execution_time": "completed",
                    "scenario_id": scenario.id if scenario else None
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "filename": model_filename,
                    "error": "Execution timed out after 5 minutes",
                    "stdout": "",
                    "stderr": "Timeout"
                }
            except Exception as e:
                return {
                    "success": False,
                    "filename": model_filename,
                    "error": str(e),
                    "stdout": "",
                    "stderr": str(e)
                }
                
        elif file_ext in ['.bat', '.cmd']:
            # Execute batch file (Windows)
            try:
                result = subprocess.run(
                    [file_path],
                    capture_output=True,
                    text=True,
                    timeout=300,
                    shell=True
                )
                
                # Log execution to scenario history
                log_execution_to_scenario(
                    command=f"Model Execution: {model_filename}",
                    output=result.stdout if result.returncode == 0 else None,
                    error=result.stderr if result.returncode != 0 else None
                )
                
                return {
                    "success": result.returncode == 0,
                    "filename": model_filename,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "execution_time": "completed",
                    "scenario_id": scenario.id if scenario else None
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "filename": model_filename,
                    "error": str(e),
                    "stdout": "",
                    "stderr": str(e)
                }
                
        elif file_ext == '.sh':
            # Execute shell script (Unix/Linux)
            try:
                result = subprocess.run(
                    ['bash', file_path],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                # Log execution to scenario history
                log_execution_to_scenario(
                    command=f"Model Execution: {model_filename}",
                    output=result.stdout if result.returncode == 0 else None,
                    error=result.stderr if result.returncode != 0 else None
                )
                
                return {
                    "success": result.returncode == 0,
                    "filename": model_filename,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "execution_time": "completed",
                    "scenario_id": scenario.id if scenario else None
                }
                
            except Exception as e:
                return {
                    "success": False,
                    "filename": model_filename,
                    "error": str(e),
                    "stdout": "",
                    "stderr": str(e)
                }
        else:
            return {
                "success": False,
                "filename": model_filename,
                "error": f"Unsupported file type: {file_ext}",
                "supported_types": [".py", ".bat", ".cmd", ".sh"]
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "filename": request.model_filename
        }

@app.get("/session/info")
async def get_session_info():
    """Get information about the current session and temp directory structure"""
    try:
        session_info = {
            "current_session_id": current_session_id,
            "eyproject_temp_base": EYPROJECT_TEMP_BASE,
            "current_session_dir": get_current_session_dir() if current_session_id else None,
            "temp_directories": temp_directories
        }
        
        # List all sessions in the EYProject temp directory
        if os.path.exists(EYPROJECT_TEMP_BASE):
            sessions = []
            for item in os.listdir(EYPROJECT_TEMP_BASE):
                item_path = os.path.join(EYPROJECT_TEMP_BASE, item)
                if os.path.isdir(item_path) and item.startswith("session_"):
                    try:
                        creation_time = os.path.getctime(item_path)
                        size = sum(os.path.getsize(os.path.join(dirpath, filename))
                                 for dirpath, dirnames, filenames in os.walk(item_path)
                                 for filename in filenames)
                        sessions.append({
                            "session_id": item,
                            "path": item_path,
                            "creation_time": datetime.fromtimestamp(creation_time).isoformat(),
                            "size_bytes": size,
                            "is_current": item == current_session_id
                        })
                    except Exception as e:
                        sessions.append({
                            "session_id": item,
                            "path": item_path,
                            "error": str(e),
                            "is_current": item == current_session_id
                        })
            
            # Sort by creation time (newest first)
            sessions.sort(key=lambda x: x.get("creation_time", ""), reverse=True)
            session_info["all_sessions"] = sessions
        else:
            session_info["all_sessions"] = []
        
        return session_info
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get session info: {str(e)}")

@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a specific session directory"""
    try:
        session_path = os.path.join(EYPROJECT_TEMP_BASE, session_id)
        
        if not os.path.exists(session_path):
            raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
        if not session_id.startswith("session_"):
            raise HTTPException(status_code=400, detail="Invalid session ID format")
        
        # Don't allow deletion of current session
        if session_id == current_session_id:
            raise HTTPException(status_code=400, detail="Cannot delete current session")
        
        import shutil
        shutil.rmtree(session_path)
        
        return {"message": f"Session {session_id} deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete session: {str(e)}")

@app.delete("/files/{filename:path}")
async def delete_file(filename: str):
    """Delete a specific file from the temporary workspace"""
    global uploaded_files, file_contents, ai_created_files, current_database_path, database_schema
    
    # Normalise slashes so the key matches what the frontend sends
    filename = filename.replace('\\', '/')

    if filename not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = uploaded_files[filename]

    try:
        # Remove the file from disk if it exists
        if os.path.exists(file_path):
            os.remove(file_path)
        # Remove the entry from in-memory tracking structures
        uploaded_files.pop(filename, None)
        file_contents.pop(filename, None)
        ai_created_files.discard(filename)

        # Reset database related globals if the deleted file was the active database
        if current_database_path and os.path.abspath(file_path) == os.path.abspath(current_database_path):
            current_database_path = None
            database_schema = None

        return {"message": f"File {filename} deleted successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

# --- SCENARIO MANAGEMENT IMPORTS ---
# --- SCENARIO MANAGEMENT ENDPOINTS ---
from fastapi import Body

class ScenarioCreateRequest(BaseModel):
    name: Optional[str] = None
    base_scenario_id: Optional[int] = None
    description: Optional[str] = None

class ScenarioUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

@app.post("/scenarios/create")
def create_scenario(request: ScenarioCreateRequest):
    # For branching scenarios, we don't need original_db_path since copy_database will handle it
    # For new scenarios (not branching), use the original upload database
    original_db_path = None
    if request.base_scenario_id is None:
        # This is a new scenario (not branching), use original upload database
        original_db_path = os.path.join(scenario_manager.shared_dir, "original_upload.db")
        if not os.path.exists(original_db_path):
            original_db_path = None
    
    scenario = scenario_manager.create_scenario(
        name=request.name,
        base_scenario_id=request.base_scenario_id,
        description=request.description,
        original_db_path=original_db_path
    )
    return scenario

@app.get("/scenarios/list")
def list_scenarios():
    return scenario_manager.list_scenarios()

@app.get("/scenarios/current")
def get_current_scenario():
    scenario = scenario_manager.get_current_scenario()
    if not scenario:
        raise HTTPException(status_code=404, detail="No active scenario")
    return scenario

@app.get("/scenarios/{id}")
def get_scenario(id: int):
    scenario = scenario_manager.get_scenario(id)
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found")
    return scenario

@app.put("/scenarios/{id}")
def update_scenario(id: int, request: ScenarioUpdateRequest):
    updated = scenario_manager.update_scenario(id, name=request.name, description=request.description)
    if not updated:
        raise HTTPException(status_code=404, detail="Scenario not found or update failed")
    return updated

@app.delete("/scenarios/{id}")
def delete_scenario(id: int):
    deleted = scenario_manager.delete_scenario(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scenario not found or delete failed")
    return {"success": True}

@app.post("/scenarios/{id}/activate")
def activate_scenario(id: int):
    success = scenario_manager.switch_scenario(id)
    if not success:
        raise HTTPException(status_code=404, detail="Scenario not found")
    
    # Get the activated scenario
    scenario = scenario_manager.get_current_scenario()
    if not scenario:
        raise HTTPException(status_code=404, detail="Failed to get activated scenario")
    
    # Update global database path for backward compatibility
    global current_database_path
    current_database_path = scenario.database_path
    
    return scenario

# --- ANALYSIS FILES ENDPOINTS ---
class AnalysisFileCreateRequest(BaseModel):
    filename: str
    file_type: str
    content: str
    is_global: bool = True
    created_by_scenario_id: Optional[int] = None

class AnalysisFileUpdateRequest(BaseModel):
    filename: Optional[str] = None
    file_type: Optional[str] = None
    content: Optional[str] = None
    is_global: Optional[bool] = None

@app.get("/analysis-files/list")
def list_analysis_files():
    return scenario_manager.list_analysis_files()

@app.post("/analysis-files/create")
def create_analysis_file(request: AnalysisFileCreateRequest):
    file = scenario_manager.create_analysis_file(
        filename=request.filename,
        file_type=request.file_type,
        content=request.content,
        is_global=request.is_global,
        created_by_scenario_id=request.created_by_scenario_id
    )
    return file

@app.put("/analysis-files/{id}")
def update_analysis_file(id: int, request: AnalysisFileUpdateRequest):
    updated = scenario_manager.update_analysis_file(
        id,
        filename=request.filename,
        file_type=request.file_type,
        content=request.content,
        is_global=request.is_global
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Analysis file not found or update failed")
    return updated

@app.delete("/analysis-files/{id}")
def delete_analysis_file(id: int):
    deleted = scenario_manager.delete_analysis_file(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Analysis file not found or delete failed")
    return {"success": True}

# --- EXECUTION HISTORY ENDPOINTS ---
@app.get("/scenarios/{id}/execution-history")
def get_execution_history(id: int):
    return scenario_manager.get_execution_history(id)

# --- PATCH EXISTING ENDPOINTS TO BE SCENARIO-AWARE ---
# Helper to get current scenario's database path

def get_active_scenario_database():
    scenario = scenario_manager.get_current_scenario()
    if scenario and scenario.database_path:
        return scenario.database_path
    else:
        return current_database_path  # fallback for backward compatibility

def log_execution_to_scenario(command: str, output: str = None, error: str = None, output_files: list = None):
    """Helper function to log execution to current scenario's history"""
    try:
        scenario = scenario_manager.get_current_scenario()
        if scenario:
            # Convert output_files list to JSON string if provided
            output_files_json = None
            if output_files:
                import json
                output_files_json = json.dumps(output_files)
            
            scenario_manager.add_execution_history(
                scenario_id=scenario.id,
                command=command,
                output=output,
                error=error,
                output_files=output_files_json
            )
    except Exception as e:
        print(f"Warning: Could not log execution to scenario history: {e}")

# --- AGENT VERSION ENDPOINTS ---
@app.post("/switch-agent-version")
async def switch_agent_version(request: dict):
    """Switch between agent v1 and v2"""
    global agent_v2
    
    version = request.get("version", "v2")
    
    if version == "v2":
        # Initialize v2 agent
        agent_v2 = None  # Force recreation
        await get_or_create_agent_v2()
        return {"message": "Switched to Agent v2 (Simplified with proper scenario routing)", "version": "v2"}
    else:
        return {"message": "Agent v1 is still available through existing endpoints", "version": "v1"}

@app.get("/agent-version")
async def get_agent_version():
    """Get current agent version info"""
    return {
        "v1_available": True,
        "v2_available": agent_v2 is not None,
        "v2_features": [
            "Proper scenario database routing",
            "Simplified workflow", 
            "Chat without code execution",
            "Always uses current scenario DB",
            "Plotly-only visualizations",
            "Preserved DB modification logic"
        ]
    }

@app.get("/server-startup")
async def get_server_startup_info():
    """Get server startup information for frontend localStorage clearing"""
    return {
        "startup_timestamp": server_startup_timestamp,
        "server_restarted": True
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        reload=False  # Disable auto-reload to prevent restarts when files are created
    ) 