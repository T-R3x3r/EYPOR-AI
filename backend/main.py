from fastapi import FastAPI, UploadFile, File, HTTPException, Form
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
from langgraph_agent import create_agent
import time
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
file_contents = {}
ai_created_files = set()
current_database_path = None
database_schema = None
current_session_id = None
temp_directories = {}
query_start_time = None  # Track when each query starts

# Global variables for execution context
code_output = ""
code_error = ""

# Global LangGraph agent
langgraph_agent = None
current_agent_type = get_default_agent()  # This will now be "data_analyst"
use_langgraph_by_default = True

# Temp directory management
EYPROJECT_TEMP_BASE = os.path.join(tempfile.gettempdir(), "EYProject")

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

def get_or_create_agent():
    """Get or create the LangGraph multi-agent system"""
    global langgraph_agent, database_schema
    temp_dir = temp_directories.get('current', '')
    
    # Use simple schema agent as default (as set in agent_configs.py)
    agent_type = get_default_agent()
    
    if (langgraph_agent is None or 
        langgraph_agent.ai_model != current_ai_model or 
        langgraph_agent.temp_dir != temp_dir or
        langgraph_agent.agent_type != agent_type):
        langgraph_agent = create_agent(ai_model=current_ai_model, temp_dir=temp_dir, agent_type=agent_type)
    
    # Always pass the latest cached schema to the agent
    if database_schema and hasattr(langgraph_agent, 'set_cached_schema'):
        langgraph_agent.set_cached_schema(database_schema)
    
    return langgraph_agent

def refresh_file_list():
    """Refresh the file list to include newly created files and outputs"""
    global uploaded_files, file_contents, ai_created_files, query_start_time
    temp_dir = temp_directories.get('current')
    
    print(f"DEBUG: refresh_file_list called with temp_dir: {temp_dir}")
    print(f"DEBUG: Current query_start_time: {query_start_time}")
    
    if temp_dir:
        # Scan for all files in the temp directory (including outputs)
        for root, dirs, files in os.walk(temp_dir):
            print(f"DEBUG: Scanning directory: {root}")
            print(f"DEBUG: Found files: {files}")
            for fname in files:
                abs_path = os.path.join(root, fname)
                rel_path = os.path.relpath(abs_path, temp_dir)
                # Normalize path for web compatibility (forward slashes)
                rel_path = rel_path.replace('\\', '/')
                print(f"DEBUG: Processing file: {fname} -> {rel_path}")
                
                if rel_path not in uploaded_files:
                    print(f"DEBUG: Adding new file: {rel_path}")
                    uploaded_files[rel_path] = abs_path
                    
                    # Only mark as AI-created if it was created during current query
                    if query_start_time and os.path.exists(abs_path):
                        file_creation_time = os.path.getctime(abs_path)
                        if file_creation_time >= query_start_time:
                            ai_created_files.add(rel_path)  # Mark as AI-created for current query
                            print(f"DEBUG: Marking as AI-created (created during current query): {rel_path} (created: {file_creation_time}, query start: {query_start_time})")
                        else:
                            print(f"DEBUG: Not marking as AI-created (created before current query): {rel_path} (created: {file_creation_time}, query start: {query_start_time})")
                    else:
                        # Fallback: mark as AI-created if we can't determine creation time
                        ai_created_files.add(rel_path)
                        print(f"DEBUG: Marking as AI-created (no time check): {rel_path}")
                    
                    # Load file content for text files
                    if fname.endswith(('.py', '.txt', '.csv', '.html', '.json', '.md')):
                        try:
                            with open(abs_path, 'r', encoding='utf-8') as f:
                                file_contents[rel_path] = f.read()
                        except Exception as e:
                            print(f"Error reading created file {rel_path}: {e}")
                    else:
                        # For binary files (images, etc.), just mark as available
                        file_contents[rel_path] = f"[Binary file: {fname}]"
                else:
                    print(f"DEBUG: File already exists: {rel_path}")
    
    print(f"DEBUG: Final uploaded_files: {list(uploaded_files.keys())}")
    print(f"DEBUG: Final ai_created_files: {list(ai_created_files)}")

@app.post("/upload")
async def upload_files(file: UploadFile = File(...)):
    """Upload a zip file and extract its contents - preserves all files without conversion"""
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
        
        # Build file paths
        file_paths = {}
        db_files = []  # Track .db files
        
        for root, dirs, files in os.walk(temp_dir):
            for fname in files:
                rel_path = os.path.relpath(os.path.join(root, fname), temp_dir)
                # Normalize path for web compatibility (forward slashes)
                rel_path = rel_path.replace('\\', '/')
                file_paths[rel_path] = os.path.join(root, fname)
                
                # Track database files
                if fname.lower().endswith('.db'):
                    db_files.append((rel_path, os.path.join(root, fname)))
        
        uploaded_files = file_paths
        ai_created_files = set()  # Clear AI-created files when uploading new project
        
        # Check if there's a database file and set up database access
        db_info = {"tables": [], "total_tables": 0}
        table_names_message = ""
        
        if db_files:
            # Use the first .db file found
            current_database_path = db_files[0][1]  # abs_path
            print(f"DEBUG: Found database file: {current_database_path}")
            
            # Get database information
            try:
                db_info = get_database_info(current_database_path)
                print(f"DEBUG: Database has {len(db_info.get('tables', []))} tables")
                
                # Cache the schema globally for immediate agent access
                database_schema = db_info
                
                # Create table names message for chat
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
            if not rel_path.endswith(('.db', '.png', '.jpg', '.jpeg', '.gif', '.pdf')):  # Skip binary files
                file_contents[rel_path] = read_file_content(abs_path)
        
        # Create summary message
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
            "database_info": db_info
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to process upload: {str(e)}")

@app.get("/files")
async def get_files():
    """Get list of uploaded files"""
    uploaded_list = [f for f in uploaded_files.keys() if f not in ai_created_files]
    ai_created_list = [f for f in uploaded_files.keys() if f in ai_created_files]
    
    return {
        "files": list(uploaded_files.keys()),
        "uploaded_files": uploaded_list,
        "ai_created_files": ai_created_list,
        "file_contents": file_contents
    }

@app.get("/files/{filename}")
async def get_file_content(filename: str):
    """Get content of a specific file"""
    if filename not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    content = read_file_content(uploaded_files[filename])
    return {"filename": filename, "content": content}

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
        
        if filename not in uploaded_files:
            print(f"DEBUG: File not found in uploaded_files: {filename}")
            print(f"DEBUG: Available keys: {list(uploaded_files.keys())}")
            raise HTTPException(status_code=404, detail="File not found")
        
        file_path = uploaded_files[filename]
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
    """Run a Python file"""
    global code_output, code_error
    
    if filename not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not filename.endswith('.py'):
        raise HTTPException(status_code=400, detail="Only Python files can be executed")
    
    try:
        abs_path = uploaded_files[filename]
        temp_dir = temp_directories.get('current')
        
        result = subprocess.run(
            [sys.executable, abs_path],
            cwd=temp_dir,
            capture_output=True,
            text=True,
            timeout=300
        )
        
        code_output = result.stdout
        code_error = result.stderr
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Execution timed out")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution failed: {str(e)}")

@app.post("/install")
async def install_requirements(filename: str):
    """Install requirements from a requirements.txt file"""
    if filename not in uploaded_files:
        raise HTTPException(status_code=404, detail="File not found")
    
    if not filename.endswith('requirements.txt'):
        raise HTTPException(status_code=400, detail="Only requirements.txt files can be installed")
    
    try:
        abs_path = uploaded_files[filename]
        
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", abs_path],
            capture_output=True,
            text=True,
            timeout=300
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
async def langgraph_chat(message: ChatMessage):
    """Chat endpoint using LangGraph agent that can create and execute files"""
    global code_output, code_error, query_start_time
    
    try:
        print(f"DEBUG: LangGraph chat started with message: {message.content}")
        
        # Set query start time for file tracking
        query_start_time = time.time()
        print(f"DEBUG: Query start time set to: {query_start_time}")
        
        # Clear execution context for each new request to avoid accumulation
        print(f"DEBUG: Clearing previous execution context")
        print(f"DEBUG: Previous code_output length: {len(code_output) if code_output else 0}")
        print(f"DEBUG: Previous code_error length: {len(code_error) if code_error else 0}")
        
        agent = get_or_create_agent()
        
        # Start with clean execution context for each request
        response, created_files = agent.run(
            user_message=message.content,
            execution_output="",  # Start clean for each request
            execution_error="",   # Start clean for each request
            thread_id=getattr(message, 'thread_id', 'default')  # Use thread ID if provided
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
        
        # Detect output files (visualizations, reports, etc.) - ONLY from current query
        output_files = []
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
                            
                            # Check if file was created during current query
                            if query_start_time and os.path.exists(abs_path):
                                file_creation_time = os.path.getctime(abs_path)
                                if file_creation_time >= query_start_time:
                                    all_files.append((rel_path, abs_path))
                                    print(f"DEBUG: Found output file created during current query: {rel_path} -> {abs_path} (created: {file_creation_time}, query start: {query_start_time})")
                                else:
                                    print(f"DEBUG: Skipping file created before current query: {rel_path} (created: {file_creation_time}, query start: {query_start_time})")
                            else:
                                # Fallback: include file if we can't determine creation time
                                all_files.append((rel_path, abs_path))
                                print(f"DEBUG: Found output file (no time check): {rel_path} -> {abs_path}")
                
                print(f"DEBUG: All output files found (query-specific): {all_files}")
                print(f"DEBUG: Current uploaded_files keys: {list(uploaded_files.keys())}")
                print(f"DEBUG: New AI created files: {list(new_files)}")
                
                # Include output files that are in uploaded_files and were created during current query
                output_files_to_include = []
                for rel_path, abs_path in all_files:
                    # Only include actual output files, not input files
                    # Exclude files that were part of the original upload (not in ai_created_files)
                    if rel_path in uploaded_files and rel_path in ai_created_files:
                        # Only include image files and other output files, exclude input files
                        if rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg', '.html', '.pdf')):
                            output_files_to_include.append((rel_path, abs_path))
                            print(f"DEBUG: Including output file: {rel_path}")
                        else:
                            print(f"DEBUG: Skipping non-output file: {rel_path}")
                    else:
                        print(f"DEBUG: Skipping file not in ai_created_files: {rel_path}")
                
                # Create output file objects for frontend
                for rel_path, abs_path in output_files_to_include:
                    # Determine file type for frontend handling
                    file_type = "file"
                    if rel_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')):
                        file_type = "image"
                    elif rel_path.lower().endswith('.html'):
                        file_type = "html"  # Special type for HTML files (maps, etc.)
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
            
            print(f"DEBUG: Output files for frontend (query-specific): {output_files}")
        except Exception as e:
            print(f"Error detecting output files: {e}")
            import traceback
            traceback.print_exc()
        
        return {
            "response": response,
            "created_files": created_files,
            "current_model": current_ai_model,
            "agent_type": current_agent_type,
            "execution_output": code_output,
            "execution_error": code_error,
            "has_execution_results": bool(code_output or code_error),
            "output_files": output_files
        }
        
    except Exception as e:
        print(f"DEBUG: LangGraph chat error: {str(e)}")
        return {"error": f"LangGraph chat error: {str(e)}", "current_model": current_ai_model}

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
    global current_database_path
    
    if not current_database_path:
        raise HTTPException(status_code=400, detail="No database available. Please upload files first.")
    
    return get_database_info(current_database_path)

@app.get("/database/schema")
async def get_cached_database_schema():
    """Get cached database schema (generated automatically when database is created)"""
    global database_schema
    
    if not database_schema:
        raise HTTPException(status_code=400, detail="No database schema available. Please upload files to create a database first.")
    
    return {
        "schema": database_schema,
        "cached": True,
        "message": "Schema automatically generated when database was created"
    }

@app.post("/sql/execute")
async def execute_raw_sql(sql: str = Form(...)):
    """Execute raw SQL query"""
    global current_database_path
    
    if not current_database_path:
        raise HTTPException(status_code=400, detail="No database available. Please upload files first.")
    
    conn = None
    try:
        conn = connect_to_database(current_database_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        
        if sql.strip().upper().startswith('SELECT'):
            # For SELECT queries, return results
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            result = [dict(zip(columns, row)) for row in rows]
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
    global current_database_path
    
    if not current_database_path:
        raise HTTPException(status_code=400, detail="No database available. Please upload files first.")
    
    conn = None
    try:
        conn = connect_to_database(current_database_path)
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
    global current_database_path, database_schema
    
    return {
        "sql_enabled": current_database_path is not None,
        "database_path": current_database_path,
        "total_tables": database_schema.get("total_tables", 0) if database_schema else 0
    }

@app.get("/database/download")
async def download_database():
    """Download the SQLite database file"""
    global current_database_path
    
    if not current_database_path or not os.path.exists(current_database_path):
        raise HTTPException(status_code=404, detail="No database available for download")
    
    from fastapi.responses import FileResponse
    
    return FileResponse(
        current_database_path,
        filename=os.path.basename(current_database_path),
        media_type="application/x-sqlite3",
        headers={"Content-Disposition": f"attachment; filename={os.path.basename(current_database_path)}"}
    )

@app.get("/database/info/detailed")
async def get_detailed_database_info():
    """Get detailed database information including file stats"""
    global current_database_path
    
    if not current_database_path or not os.path.exists(current_database_path):
        raise HTTPException(status_code=404, detail="No database available")
    
    # Get basic database info
    db_info = get_database_info(current_database_path)
    
    # Add file statistics
    file_stats = os.stat(current_database_path)
    
    return {
        **db_info,
        "database_file": {
            "path": current_database_path,
            "filename": os.path.basename(current_database_path),
            "size_bytes": file_stats.st_size,
            "size_mb": round(file_stats.st_size / (1024 * 1024), 2),
            "created": datetime.fromtimestamp(file_stats.st_ctime).strftime('%Y-%m-%d %H:%M:%S'),
            "modified": datetime.fromtimestamp(file_stats.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        }
    }

@app.get("/database/export/{format}")
async def export_database(format: str):
    """Export database to different formats (sql, csv)"""
    global current_database_path, temp_directories
    
    if not current_database_path or not os.path.exists(current_database_path):
        raise HTTPException(status_code=404, detail="No database available")
    
    if format.lower() not in ['sql', 'csv']:
        raise HTTPException(status_code=400, detail="Supported formats: sql, csv")
    
    conn = None
    try:
        conn = connect_to_database(current_database_path)
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

@app.post("/action-chat")
async def action_chat(request: ActionRequest):
    """Enhanced chat endpoint with action-based routing using LangGraph agent"""
    global code_output, code_error, ai_created_files
    
    try:
        print(f"DEBUG: Action-based chat started with message: {request.message}")
        print(f"DEBUG: Action type: {request.action_type}")
        print(f"DEBUG: Thread ID: {request.thread_id}")
        
        # Get or create the LangGraph agent
        agent = get_or_create_agent()
        
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
                output_files.append({
                    "filename": os.path.basename(file_path),
                    "path": normalized_path,
                    "url": f"/files/{normalized_path}/download",
                    "type": "image" if normalized_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')) else "file"
                })
        
        # Check if this was a database modification that requires human-in-the-loop
        requires_approval = False
        db_modification_detected = False
        
        if ("parameter" in response.lower() and "updated" in response.lower()) or \
           ("database" in response.lower() and ("modified" in response.lower() or "changed" in response.lower())):
            db_modification_detected = True
            print("DEBUG: Database modification detected - triggering human-in-the-loop")
        
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
        agent = get_or_create_agent()
        
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
                output_files.append({
                    "filename": os.path.basename(file_path),
                    "path": normalized_path,
                    "url": f"/files/{normalized_path}/download",
                    "type": "image" if normalized_path.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')) else "file"
                })
        
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
        agent = get_or_create_agent()
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
        agent = get_or_create_agent()
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
        agent = get_or_create_agent()
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
        
        agent = get_or_create_agent()
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
        agent = get_or_create_agent()
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
    """Execute a selected model file"""
    try:
        model_filename = request.model_filename
        parameters = request.parameters or {}
        
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
                
                return {
                    "success": result.returncode == 0,
                    "filename": model_filename,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "execution_time": "completed"
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
                
                return {
                    "success": result.returncode == 0,
                    "filename": model_filename,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "execution_time": "completed"
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
                
                return {
                    "success": result.returncode == 0,
                    "filename": model_filename,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "execution_time": "completed"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 