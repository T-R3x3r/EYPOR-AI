"""
Scenario Management System for EYProject

This module provides the core functionality for managing multiple scenarios
in the EYProject application. Each scenario maintains its own database state
while sharing uploaded files and analysis templates.
"""

import os
import sqlite3
import shutil
import json
from datetime import datetime
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import tempfile


@dataclass
class Scenario:
    """Represents a scenario with its metadata and state"""
    id: Optional[int]
    name: str
    created_at: datetime
    modified_at: datetime
    database_path: str
    parent_scenario_id: Optional[int]
    is_base_scenario: bool
    description: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert scenario to dictionary for JSON serialization"""
        return {
            'id': self.id,
            'name': self.name,
            'created_at': self.created_at.isoformat(),
            'modified_at': self.modified_at.isoformat(),
            'database_path': self.database_path,
            'parent_scenario_id': self.parent_scenario_id,
            'is_base_scenario': self.is_base_scenario,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Scenario':
        """Create scenario from dictionary"""
        return cls(
            id=data.get('id'),
            name=data['name'],
            created_at=datetime.fromisoformat(data['created_at']),
            modified_at=datetime.fromisoformat(data['modified_at']),
            database_path=data['database_path'],
            parent_scenario_id=data.get('parent_scenario_id'),
            is_base_scenario=data.get('is_base_scenario', False),
            description=data.get('description')
        )


@dataclass
class AnalysisFile:
    """Represents an analysis file (SQL query, visualization template, etc.)"""
    id: Optional[int]
    filename: str
    file_type: str  # 'sql_query', 'visualization_template', etc.
    content: str
    created_at: datetime
    created_by_scenario_id: Optional[int]
    is_global: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis file to dictionary"""
        return {
            'id': self.id,
            'filename': self.filename,
            'file_type': self.file_type,
            'content': self.content,
            'created_at': self.created_at.isoformat(),
            'created_by_scenario_id': self.created_by_scenario_id,
            'is_global': self.is_global
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AnalysisFile':
        """Create analysis file from dictionary"""
        return cls(
            id=data.get('id'),
            filename=data['filename'],
            file_type=data['file_type'],
            content=data['content'],
            created_at=datetime.fromisoformat(data['created_at']),
            created_by_scenario_id=data.get('created_by_scenario_id'),
            is_global=data.get('is_global', True)
        )


@dataclass
class ExecutionHistory:
    """Represents execution history for a scenario"""
    id: Optional[int]
    scenario_id: int
    command: str
    output: Optional[str]
    error: Optional[str]
    timestamp: datetime
    execution_time_ms: Optional[int]
    output_files: Optional[str] = None  # JSON string of output files
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert execution history to dictionary"""
        return {
            'id': self.id,
            'scenario_id': self.scenario_id,
            'command': self.command,
            'output': self.output,
            'error': self.error,
            'timestamp': self.timestamp.isoformat(),
            'execution_time_ms': self.execution_time_ms,
            'output_files': self.output_files
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExecutionHistory':
        """Create execution history from dictionary"""
        return cls(
            id=data.get('id'),
            scenario_id=data['scenario_id'],
            command=data['command'],
            output=data.get('output'),
            error=data.get('error'),
            timestamp=datetime.fromisoformat(data['timestamp']),
            execution_time_ms=data.get('execution_time_ms'),
            output_files=data.get('output_files')
        )


class ScenarioState:
    """Tracks the current active scenario state"""
    
    def __init__(self):
        self._current_scenario_id: Optional[int] = None
        self._scenarios_dir: Optional[str] = None
        self._metadata_db_path: Optional[str] = None
    
    @property
    def current_scenario_id(self) -> Optional[int]:
        return self._current_scenario_id
    
    @current_scenario_id.setter
    def current_scenario_id(self, value: Optional[int]):
        self._current_scenario_id = value
    
    @property
    def scenarios_dir(self) -> Optional[str]:
        return self._scenarios_dir
    
    @scenarios_dir.setter
    def scenarios_dir(self, value: Optional[str]):
        self._scenarios_dir = value
    
    @property
    def metadata_db_path(self) -> Optional[str]:
        return self._metadata_db_path
    
    @metadata_db_path.setter
    def metadata_db_path(self, value: Optional[str]):
        self._metadata_db_path = value


class ScenarioManager:
    """Manages scenarios and their associated databases"""
    
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.scenarios_dir = os.path.join(project_root, "scenarios")
        self.shared_dir = os.path.join(project_root, "shared")
        self.metadata_db_path = os.path.join(project_root, "metadata.db")
        self.state = ScenarioState()
        
        # Initialize directories
        self._ensure_directories()
        
        # Initialize metadata database
        self._init_metadata_db()
    
    def _ensure_directories(self):
        """Ensure required directories exist"""
        os.makedirs(self.scenarios_dir, exist_ok=True)
        os.makedirs(self.shared_dir, exist_ok=True)
        os.makedirs(os.path.join(self.shared_dir, "uploaded_files"), exist_ok=True)
        os.makedirs(os.path.join(self.shared_dir, "analysis_files"), exist_ok=True)
    
    def _init_metadata_db(self):
        """Initialize the metadata database with required tables"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        # Create scenarios table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                modified_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                database_path TEXT NOT NULL,
                parent_scenario_id INTEGER,
                is_base_scenario BOOLEAN DEFAULT FALSE,
                description TEXT,
                FOREIGN KEY (parent_scenario_id) REFERENCES scenarios(id)
            )
        ''')
        
        # Create analysis_files table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                filename TEXT NOT NULL,
                file_type TEXT NOT NULL,
                content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by_scenario_id INTEGER,
                is_global BOOLEAN DEFAULT TRUE,
                FOREIGN KEY (created_by_scenario_id) REFERENCES scenarios(id)
            )
        ''')
        
        # Create execution_history table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS execution_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id INTEGER NOT NULL,
                command TEXT NOT NULL,
                output TEXT,
                error TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                execution_time_ms INTEGER,
                output_files TEXT,
                FOREIGN KEY (scenario_id) REFERENCES scenarios(id)
            )
        ''')
        
        # Add output_files column if it doesn't exist (for existing databases)
        try:
            cursor.execute('ALTER TABLE execution_history ADD COLUMN output_files TEXT')
        except sqlite3.OperationalError:
            # Column already exists
            pass
        
        # Create indexes for better performance
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_name ON scenarios(name)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_scenarios_parent ON scenarios(parent_scenario_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_scenario ON execution_history(scenario_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_execution_timestamp ON execution_history(timestamp)')
        
        conn.commit()
        conn.close()
    
    def create_scenario(self, name: str, base_scenario_id: Optional[int] = None, description: Optional[str] = None, original_db_path: Optional[str] = None) -> Scenario:
        """Create a new scenario"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            # Generate unique scenario directory name
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            scenario_dir_name = f"scenario_{timestamp}"
            scenario_dir = os.path.join(self.scenarios_dir, scenario_dir_name)
            os.makedirs(scenario_dir, exist_ok=True)
            
            # Create database path
            database_path = os.path.join(scenario_dir, "database.db")
            
            # Check if this is the very first scenario (only the first one should be base)
            cursor.execute('SELECT COUNT(*) FROM scenarios')
            existing_count = cursor.fetchone()[0]
            is_base_scenario = existing_count == 0
            
            # Insert scenario record
            cursor.execute('''
                INSERT INTO scenarios (name, database_path, parent_scenario_id, is_base_scenario, description)
                VALUES (?, ?, ?, ?, ?)
            ''', (name, database_path, base_scenario_id, is_base_scenario, description))
            
            scenario_id = cursor.lastrowid
            
            # Commit the scenario record first so it's available for copying
            conn.commit()
            
            # If branching from another scenario, copy the database from parent
            if base_scenario_id is not None:
                print(f"\n=== DEBUG: Creating branch scenario ===")
                print(f"DEBUG: Scenario ID: {scenario_id}")
                print(f"DEBUG: Base scenario ID: {base_scenario_id}")
                print(f"DEBUG: Database path: {database_path}")
                
                # Check if base scenario exists before copying
                base_scenario = self.get_scenario(base_scenario_id)
                if base_scenario:
                    print(f"DEBUG: Base scenario found: {base_scenario.name}")
                    print(f"DEBUG: Base scenario database: {base_scenario.database_path}")
                    print(f"DEBUG: Base scenario database exists: {os.path.exists(base_scenario.database_path)}")
                else:
                    print(f"ERROR: Base scenario {base_scenario_id} not found!")
                
                success = self.copy_database(base_scenario_id, scenario_id)
                if not success:
                    print(f"ERROR: Failed to copy database for scenario {scenario_id}")
                    # Create empty database as fallback
                    self._create_empty_database(database_path)
                else:
                    print(f"DEBUG: Database copy successful for scenario {scenario_id}")
            else:
                # For base and all new scenarios, copy from original_db_path if provided
                print(f"\n=== DEBUG: Creating new scenario (not branching) ===")
                print(f"DEBUG: Scenario ID: {scenario_id}")
                print(f"DEBUG: Original DB path: {original_db_path}")
                print(f"DEBUG: Original DB exists: {original_db_path and os.path.exists(original_db_path)}")
                
                if original_db_path and os.path.exists(original_db_path):
                    print(f"DEBUG: Copying original upload database to scenario: {database_path}")
                    shutil.copy2(original_db_path, database_path)
                else:
                    print(f"DEBUG: Creating empty database as fallback")
                    # Create empty database as fallback
                    self._create_empty_database(database_path)
            
            # Get the created scenario
            cursor.execute('SELECT * FROM scenarios WHERE id = ?', (scenario_id,))
            row = cursor.fetchone()
            
            scenario = self._row_to_scenario(row)
            
            # Set as current scenario if it's the first one
            if self.list_scenarios() == [scenario]:
                self.state.current_scenario_id = scenario_id
            
            return scenario
            
        finally:
            conn.close()
    
    def switch_scenario(self, scenario_id: int) -> bool:
        """Switch to the specified scenario"""
        scenarios = self.list_scenarios()
        scenario = next((s for s in scenarios if s.id == scenario_id), None)
        
        if scenario is None:
            return False
        
        self.state.current_scenario_id = scenario_id
        return True
    
    def get_current_scenario(self) -> Optional[Scenario]:
        """Get the currently active scenario"""
        if self.state.current_scenario_id is None:
            return None
        
        scenarios = self.list_scenarios()
        return next((s for s in scenarios if s.id == self.state.current_scenario_id), None)
    
    def copy_database(self, source_scenario_id: int, target_scenario_id: int) -> bool:
        """Copy database from source scenario to target scenario"""
        print(f"\n=== DEBUG: copy_database called ===")
        print(f"DEBUG: Source scenario ID: {source_scenario_id}")
        print(f"DEBUG: Target scenario ID: {target_scenario_id}")
        
        scenarios = self.list_scenarios()
        print(f"DEBUG: All scenarios in database: {[(s.id, s.name, s.database_path) for s in scenarios]}")
        
        source_scenario = next((s for s in scenarios if s.id == source_scenario_id), None)
        target_scenario = next((s for s in scenarios if s.id == target_scenario_id), None)
        
        if source_scenario is None:
            print(f"ERROR: Source scenario {source_scenario_id} not found in scenarios list!")
            print(f"DEBUG: Available scenario IDs: {[s.id for s in scenarios]}")
            return False
            
        if target_scenario is None:
            print(f"ERROR: Target scenario {target_scenario_id} not found in scenarios list!")
            print(f"DEBUG: Available scenario IDs: {[s.id for s in scenarios]}")
            return False
        
        print(f"DEBUG: Source scenario found: {source_scenario.name} (ID: {source_scenario.id})")
        print(f"DEBUG: Target scenario found: {target_scenario.name} (ID: {target_scenario.id})")
        print(f"DEBUG: Source database path: {source_scenario.database_path}")
        print(f"DEBUG: Target database path: {target_scenario.database_path}")
        print(f"DEBUG: Source database exists: {os.path.exists(source_scenario.database_path)}")
        
        # Don't copy if source and target are the same
        if source_scenario_id == target_scenario_id:
            print(f"DEBUG: Source and target are the same, skipping copy")
            return True
        
        try:
            # Ensure target directory exists
            target_dir = os.path.dirname(target_scenario.database_path)
            os.makedirs(target_dir, exist_ok=True)
            print(f"DEBUG: Target directory created/verified: {target_dir}")
            
            # Copy the database file
            if os.path.exists(source_scenario.database_path):
                print(f"DEBUG: Source database exists, copying...")
                print(f"DEBUG: From: {source_scenario.database_path}")
                print(f"DEBUG: To: {target_scenario.database_path}")
                
                # Get file size before copy
                source_size = os.path.getsize(source_scenario.database_path)
                print(f"DEBUG: Source file size: {source_size} bytes")
                
                shutil.copy2(source_scenario.database_path, target_scenario.database_path)
                
                # Verify the copy was successful
                if os.path.exists(target_scenario.database_path):
                    target_size = os.path.getsize(target_scenario.database_path)
                    print(f"DEBUG: Target file size: {target_size} bytes")
                    print(f"DEBUG: Copy successful! Sizes match: {source_size == target_size}")
                    return True
                else:
                    print(f"ERROR: Database copy failed - target file not found")
                    return False
            else:
                print(f"ERROR: Source database {source_scenario.database_path} does not exist!")
                print(f"DEBUG: Current working directory: {os.getcwd()}")
                print(f"DEBUG: Source directory exists: {os.path.exists(os.path.dirname(source_scenario.database_path))}")
                # Create empty database as fallback
                print(f"DEBUG: Creating empty database as fallback")
                self._create_empty_database(target_scenario.database_path)
                return True
        except Exception as e:
            print(f"ERROR copying database: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def list_scenarios(self) -> List[Scenario]:
        """List all scenarios"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('SELECT * FROM scenarios ORDER BY created_at ASC')
            rows = cursor.fetchall()
            
            scenarios = []
            for row in rows:
                scenario = self._row_to_scenario(row)
                scenarios.append(scenario)
            
            return scenarios
        finally:
            conn.close()
    
    def delete_scenario(self, scenario_id: int) -> bool:
        """Delete a scenario and its associated data"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            # Get scenario details
            cursor.execute('SELECT * FROM scenarios WHERE id = ?', (scenario_id,))
            row = cursor.fetchone()
            
            if row is None:
                return False
            
            scenario = self._row_to_scenario(row)
            
            # Delete execution history
            cursor.execute('DELETE FROM execution_history WHERE scenario_id = ?', (scenario_id,))
            
            # Delete scenario record
            cursor.execute('DELETE FROM scenarios WHERE id = ?', (scenario_id,))
            
            # Delete scenario directory and database
            scenario_dir = os.path.dirname(scenario.database_path)
            if os.path.exists(scenario_dir):
                shutil.rmtree(scenario_dir)
            
            conn.commit()
            
            # If this was the current scenario, switch to another one
            if self.state.current_scenario_id == scenario_id:
                scenarios = self.list_scenarios()
                if scenarios:
                    self.state.current_scenario_id = scenarios[0].id
                else:
                    self.state.current_scenario_id = None
            
            return True
        finally:
            conn.close()
    
    def get_scenario(self, scenario_id: int) -> Optional[Scenario]:
        """Get a specific scenario by ID"""
        scenarios = self.list_scenarios()
        return next((s for s in scenarios if s.id == scenario_id), None)
    
    def update_scenario(self, scenario_id: int, name: Optional[str] = None, description: Optional[str] = None) -> bool:
        """Update scenario metadata"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            updates = []
            params = []
            
            if name is not None:
                updates.append('name = ?')
                params.append(name)
            
            if description is not None:
                updates.append('description = ?')
                params.append(description)
            
            if not updates:
                return False
            
            updates.append('modified_at = CURRENT_TIMESTAMP')
            params.append(scenario_id)
            
            query = f'UPDATE scenarios SET {", ".join(updates)} WHERE id = ?'
            cursor.execute(query, params)
            
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
    
    def add_execution_history(self, scenario_id: int, command: str, output: Optional[str] = None, 
                            error: Optional[str] = None, execution_time_ms: Optional[int] = None, 
                            output_files: Optional[str] = None) -> bool:
        """Add execution history entry for a scenario"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO execution_history (scenario_id, command, output, error, execution_time_ms, output_files)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (scenario_id, command, output, error, execution_time_ms, output_files))
            
            conn.commit()
            return True
        finally:
            conn.close()
    
    def get_execution_history(self, scenario_id: int, limit: Optional[int] = None) -> List[ExecutionHistory]:
        """Get execution history for a scenario"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            query = 'SELECT * FROM execution_history WHERE scenario_id = ? ORDER BY timestamp DESC'
            params = [scenario_id]
            
            if limit:
                query += f' LIMIT {limit}'
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            
            history = []
            for row in rows:
                history.append(self._row_to_execution_history(row))
            
            return history
        finally:
            conn.close()
    
    def add_analysis_file(self, filename: str, file_type: str, content: str, 
                         created_by_scenario_id: Optional[int] = None, is_global: bool = True) -> AnalysisFile:
        """Add an analysis file"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                INSERT INTO analysis_files (filename, file_type, content, created_by_scenario_id, is_global)
                VALUES (?, ?, ?, ?, ?)
            ''', (filename, file_type, content, created_by_scenario_id, is_global))
            
            file_id = cursor.lastrowid
            
            cursor.execute('SELECT * FROM analysis_files WHERE id = ?', (file_id,))
            row = cursor.fetchone()
            
            conn.commit()
            
            return self._row_to_analysis_file(row)
        finally:
            conn.close()
    
    def get_analysis_files(self, scenario_id: Optional[int] = None) -> List[AnalysisFile]:
        """Get analysis files (global or scenario-specific)"""
        conn = sqlite3.connect(self.metadata_db_path)
        cursor = conn.cursor()
        
        try:
            if scenario_id is None:
                # Get global files only
                cursor.execute('SELECT * FROM analysis_files WHERE is_global = TRUE ORDER BY created_at DESC')
            else:
                # Get both global and scenario-specific files
                cursor.execute('''
                    SELECT * FROM analysis_files 
                    WHERE is_global = TRUE OR created_by_scenario_id = ?
                    ORDER BY created_at DESC
                ''', (scenario_id,))
            
            rows = cursor.fetchall()
            
            files = []
            for row in rows:
                files.append(self._row_to_analysis_file(row))
            
            return files
        finally:
            conn.close()
    
    def _create_empty_database(self, database_path: str):
        """Create an empty SQLite database with basic structure"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(database_path), exist_ok=True)
            
            # Create the database file
            conn = sqlite3.connect(database_path)
            
            # Create a simple table to ensure the database is properly initialized
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scenario_info (
                    id INTEGER PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    scenario_type TEXT DEFAULT 'empty'
                )
            ''')
            
            # Insert a record to mark this as an empty scenario database
            cursor.execute('''
                INSERT OR REPLACE INTO scenario_info (id, scenario_type) 
                VALUES (1, 'empty')
            ''')
            
            conn.commit()
            conn.close()
            
            print(f"Created empty database at: {database_path}")
            
        except Exception as e:
            print(f"Error creating empty database at {database_path}: {e}")
            # Fallback: create minimal database
            try:
                conn = sqlite3.connect(database_path)
                conn.close()
                print(f"Created minimal database at: {database_path}")
            except Exception as e2:
                print(f"Failed to create even minimal database: {e2}")
    
    def _row_to_scenario(self, row) -> Scenario:
        """Convert database row to Scenario object"""
        return Scenario(
            id=row[0],
            name=row[1],
            created_at=datetime.fromisoformat(row[2]),
            modified_at=datetime.fromisoformat(row[3]),
            database_path=row[4],
            parent_scenario_id=row[5],
            is_base_scenario=bool(row[6]),
            description=row[7]
        )
    
    def _row_to_analysis_file(self, row) -> AnalysisFile:
        """Convert database row to AnalysisFile object"""
        return AnalysisFile(
            id=row[0],
            filename=row[1],
            file_type=row[2],
            content=row[3],
            created_at=datetime.fromisoformat(row[4]),
            created_by_scenario_id=row[5],
            is_global=bool(row[6])
        )
    
    def _row_to_execution_history(self, row) -> ExecutionHistory:
        """Convert database row to ExecutionHistory object"""
        return ExecutionHistory(
            id=row[0],
            scenario_id=row[1],
            command=row[2],
            output=row[3],
            error=row[4],
            timestamp=datetime.fromisoformat(row[5]),
            execution_time_ms=row[6],
            output_files=row[7] if len(row) > 7 else None
        )


# Global scenario manager instance
_scenario_manager: Optional[ScenarioManager] = None


def get_scenario_manager(project_root: Optional[str] = None) -> ScenarioManager:
    """Get or create the global scenario manager instance"""
    global _scenario_manager
    
    if _scenario_manager is None:
        if project_root is None:
            # Use current session directory as project root
            import tempfile
            project_root = os.path.join(tempfile.gettempdir(), "EYProject", "scenarios_project")
        
        _scenario_manager = ScenarioManager(project_root)
    
    return _scenario_manager


def set_scenario_manager(manager: ScenarioManager):
    """Set the global scenario manager instance"""
    global _scenario_manager
    _scenario_manager = manager 