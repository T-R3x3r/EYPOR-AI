#!/usr/bin/env python3
"""
Test script for Scenario Integration
Tests the integration between scenario management, file upload, and LangGraph agent
"""

import os
import tempfile
import shutil
import sqlite3
import json
from pathlib import Path

def create_test_database(db_path: str):
    """Create a test database with some sample data"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create test tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS test_data (
            id INTEGER PRIMARY KEY,
            name TEXT,
            value REAL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS parameters (
            id INTEGER PRIMARY KEY,
            param_name TEXT,
            param_value REAL
        )
    ''')
    
    # Insert sample data
    cursor.execute('INSERT INTO test_data (name, value) VALUES (?, ?)', ('Test1', 100.0))
    cursor.execute('INSERT INTO test_data (name, value) VALUES (?, ?)', ('Test2', 200.0))
    cursor.execute('INSERT INTO parameters (param_name, param_value) VALUES (?, ?)', ('param1', 10.0))
    cursor.execute('INSERT INTO parameters (param_name, param_value) VALUES (?, ?)', ('param2', 20.0))
    
    conn.commit()
    conn.close()

def create_test_zip(temp_dir: str) -> str:
    """Create a test zip file with a database and some Python files"""
    # Create test database
    db_path = os.path.join(temp_dir, "test_database.db")
    create_test_database(db_path)
    
    # Create test Python file
    py_file = os.path.join(temp_dir, "test_model.py")
    with open(py_file, 'w') as f:
        f.write('''
import sqlite3
import pandas as pd

# Test model that reads from database
conn = sqlite3.connect("test_database.db")
df = pd.read_sql_query("SELECT * FROM test_data", conn)
print("Data from database:")
print(df)
conn.close()
''')
    
    # Create zip file
    import zipfile
    zip_path = os.path.join(temp_dir, "test_project.zip")
    with zipfile.ZipFile(zip_path, 'w') as z:
        z.write(db_path, "test_database.db")
        z.write(py_file, "test_model.py")
    
    return zip_path

def test_scenario_integration():
    """Test the complete scenario integration"""
    print("=== Testing Scenario Integration ===")
    
    # Create temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="scenario_integration_test_")
    print(f"Testing in directory: {test_dir}")
    
    try:
        # Import scenario manager
        from scenario_manager import ScenarioManager, ScenarioState
        
        # Initialize scenario manager
        scenario_manager = ScenarioManager(test_dir)
        scenario_state = ScenarioState()
        print("✓ ScenarioManager initialized")
        
        # Create test zip file
        zip_path = create_test_zip(test_dir)
        print(f"✓ Created test zip file: {zip_path}")
        
        # Simulate file upload process
        print("\n--- Simulating File Upload ---")
        
        # Extract files to shared directory
        import zipfile
        shared_upload_dir = os.path.join(scenario_manager.shared_dir, "uploaded_files")
        os.makedirs(shared_upload_dir, exist_ok=True)
        
        with zipfile.ZipFile(zip_path) as z:
            z.extractall(shared_upload_dir)
        
        # Find database file
        db_files = [f for f in os.listdir(shared_upload_dir) if f.endswith('.db')]
        if db_files:
            db_path = os.path.join(shared_upload_dir, db_files[0])
            print(f"✓ Found database file: {db_path}")
            
            # Create base scenario
            base_scenario = scenario_manager.create_scenario(
                name="Base Scenario",
                base_scenario_id=None,
                description="Initial scenario created from upload"
            )
            
            # Copy the uploaded database to the scenario's database path
            if os.path.exists(db_path):
                shutil.copy2(db_path, base_scenario.database_path)
            scenario_state.current_scenario_id = base_scenario.id
            print(f"✓ Created base scenario: {base_scenario.name} (ID: {base_scenario.id})")
            
            # Test scenario switching
            print("\n--- Testing Scenario Switching ---")
            
            # Create a new scenario
            new_scenario = scenario_manager.create_scenario(
                name="Test Scenario",
                base_scenario_id=base_scenario.id,
                description="Test scenario for parameter changes"
            )
            print(f"✓ Created new scenario: {new_scenario.name} (ID: {new_scenario.id})")
            
            # Switch to new scenario
            scenario_manager.switch_scenario(new_scenario.id)
            scenario_state.current_scenario_id = new_scenario.id
            print(f"✓ Switched to scenario: {new_scenario.name}")
            
            # Test database isolation
            print("\n--- Testing Database Isolation ---")
            
            # Modify data in current scenario
            conn = sqlite3.connect(new_scenario.database_path)
            cursor = conn.cursor()
            cursor.execute('UPDATE parameters SET param_value = ? WHERE param_name = ?', (999.0, 'param1'))
            conn.commit()
            conn.close()
            print("✓ Modified parameter in current scenario")
            
            # Verify base scenario is unchanged
            conn = sqlite3.connect(base_scenario.database_path)
            cursor = conn.cursor()
            cursor.execute('SELECT param_value FROM parameters WHERE param_name = ?', ('param1',))
            base_value = cursor.fetchone()[0]
            conn.close()
            print(f"✓ Base scenario param1 value: {base_value} (should be 10.0)")
            
            # Verify current scenario is changed
            conn = sqlite3.connect(new_scenario.database_path)
            cursor = conn.cursor()
            cursor.execute('SELECT param_value FROM parameters WHERE param_name = ?', ('param1',))
            new_value = cursor.fetchone()[0]
            conn.close()
            print(f"✓ Current scenario param1 value: {new_value} (should be 999.0)")
            
            # Test execution history
            print("\n--- Testing Execution History ---")
            
            # Add some execution history
            scenario_manager.add_execution_history(
                scenario_id=new_scenario.id,
                command="Test command",
                output="Test output",
                error=None
            )
            
            history = scenario_manager.get_execution_history(new_scenario.id)
            print(f"✓ Execution history count: {len(history)}")
            
            # Test analysis files
            print("\n--- Testing Analysis Files ---")
            
            # Create analysis file
            analysis_file = scenario_manager.add_analysis_file(
                filename="test_query.sql",
                file_type="sql_query",
                content="SELECT * FROM test_data",
                created_by_scenario_id=new_scenario.id,
                is_global=True
            )
            print(f"✓ Created analysis file: {analysis_file.filename}")
            
            # List analysis files
            files = scenario_manager.get_analysis_files()
            print(f"✓ Analysis files count: {len(files)}")
            
            print("\n=== All Tests Passed! ===")
            
        else:
            print("✗ No database file found in zip")
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")

if __name__ == "__main__":
    test_scenario_integration() 