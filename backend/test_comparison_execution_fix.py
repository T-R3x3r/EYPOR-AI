#!/usr/bin/env python3
"""
Test script to verify that comparison files are executed in the correct directory
and output files are saved in the right location.
"""

import os
import sys
import tempfile
import shutil
import time

# Add the current directory to the path so we can import the agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_agent_v2 import SimplifiedAgent
from scenario_manager import ScenarioManager

def test_comparison_execution_directory():
    """Test that comparison files are executed in the correct directory"""
    print("🧪 Testing Comparison Execution Directory Fix")
    print("=" * 50)
    
    # Create a temporary project directory
    temp_dir = tempfile.mkdtemp()
    project_root = temp_dir
    
    try:
        # Create scenario manager
        scenario_manager = ScenarioManager(project_root)
        
        # Create test scenarios
        print("📁 Creating test scenarios...")
        
        # Create Base Scenario
        base_scenario = scenario_manager.create_scenario("Base Scenario", "Base scenario for testing")
        print(f"✅ Created Base Scenario with ID: {base_scenario.id}")
        
        # Create test1 scenario
        test1_scenario = scenario_manager.create_scenario("test1", "Test scenario 1")
        print(f"✅ Created test1 scenario with ID: {test1_scenario.id}")
        
        # Create agent
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test the execution directory logic
        print("\n🔍 Testing execution directory logic...")
        
        # Create a test comparison file
        test_comparison_content = '''# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

# Define the database paths (these should NOT be replaced by the run endpoint)
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_214112_306/database.db"
test_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_214512_849/database.db"

# This is a comparison file - it should NOT have database paths injected
print("Testing comparison file execution...")
print(f"Base scenario database: {base_scenario_db}")
print(f"Test scenario database: {test_scenario_db}")

# Create a simple visualization
fig = go.Figure()
fig.add_trace(go.Bar(x=['Base Scenario', 'Test Scenario'], y=[100, 150], name='Comparison'))
fig.update_layout(title='Test Comparison Chart')

# Save the chart in the current directory
timestamp = int(time.time())
html_file = f"test_comparison_chart_{timestamp}.html"
fig.write_html(html_file)
print(f"Chart saved as {html_file}")

# Also save a test file to verify the execution directory
test_file = f"test_execution_dir_{timestamp}.txt"
with open(test_file, 'w') as f:
    f.write(f"Executed in directory: {os.getcwd()}")
    f.write(f"\\nTimestamp: {timestamp}")
print(f"Test file saved as {test_file}")
'''
        
        # Create the comparison file in the Base Scenario directory
        base_scenario_dir = os.path.dirname(base_scenario.database_path)
        comparison_filename = "comparison_analysis_Base_Scenario_vs_test1_20250710_230555.py"
        comparison_file_path = os.path.join(base_scenario_dir, comparison_filename)
        
        with open(comparison_file_path, 'w', encoding='utf-8') as f:
            f.write(test_comparison_content)
        
        print(f"📝 Created comparison file: {comparison_file_path}")
        
        # Test the execution directory logic by simulating the _execute_code method
        print(f"\n🔍 Testing execution directory logic...")
        
        # Simulate the state that would be passed to _execute_code
        from langgraph_agent_v2 import AgentState, DatabaseContext
        
        # Create a database context for the current scenario
        db_context = agent._get_database_context()
        
        # Create state
        state = {
            "messages": [],
            "user_request": "test",
            "request_type": "scenario_comparison",
            "db_context": db_context,
            "generated_files": [comparison_filename],
            "execution_output": "",
            "execution_error": "",
            "modification_request": None,
            "db_modification_result": None,
            "comparison_scenarios": ["Base Scenario", "test1"],
            "comparison_data": {},
            "comparison_type": "analysis",
            "scenario_name_mapping": {"Base Scenario": 0, "test1": 1}
        }
        
        # Test the execution directory logic
        filename = state["generated_files"][-1]
        file_path = os.path.join(db_context.temp_dir, filename)
        
        print(f"🔍 DEBUG: Filename: {filename}")
        print(f"🔍 DEBUG: File path: {file_path}")
        print(f"🔍 DEBUG: DB context temp_dir: {db_context.temp_dir}")
        
        # Check if the file is a comparison file
        is_comparison_file = filename and ('comparison' in filename.lower() or 'vs_' in filename.lower())
        print(f"🔍 DEBUG: Is comparison file: {is_comparison_file}")
        
        # Determine execution directory
        if db_context.comparison_mode and db_context.multi_database_contexts:
            # In comparison mode, use the primary scenario's directory
            primary_context = db_context.get_primary_context()
            if primary_context and primary_context.database_path:
                db_dir = os.path.dirname(primary_context.database_path)
            else:
                # Fallback to temp_dir if available
                db_dir = db_context.temp_dir or os.getcwd()
        else:
            # Single scenario mode
            db_dir = os.path.dirname(db_context.database_path)
        
        # For comparison files, ensure we're executing in the correct directory
        if is_comparison_file:
            # For comparison files, use the directory where the file is located
            file_dir = os.path.dirname(file_path)
            if file_dir and os.path.exists(file_dir):
                db_dir = file_dir
                print(f"🔍 DEBUG: Using comparison file's directory for execution: {db_dir}")
        
        print(f"🔍 DEBUG: Final execution directory: {db_dir}")
        
        # Verify that the execution directory is correct
        expected_dir = base_scenario_dir
        if db_dir == expected_dir:
            print(f"✅ SUCCESS: Execution directory is correct: {db_dir}")
        else:
            print(f"❌ FAILED: Expected {expected_dir}, got {db_dir}")
        
        # Test actual execution
        print(f"\n🚀 Testing actual execution...")
        try:
            import subprocess
            
            # Record existing files before execution
            existing_files = set()
            if os.path.exists(db_dir):
                for file in os.listdir(db_dir):
                    if file.endswith('.html') or file.endswith('.txt'):
                        existing_files.add(file)
            print(f"🔍 DEBUG: Existing files before execution: {existing_files}")
            
            # Execute the comparison file
            result = subprocess.run(
                [sys.executable, comparison_file_path],
                cwd=db_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=30
            )
            
            print(f"🔍 DEBUG: Execution completed with return code: {result.returncode}")
            print(f"🔍 DEBUG: STDOUT: {result.stdout[:200]}...")
            print(f"🔍 DEBUG: STDERR: {result.stderr[:200]}...")
            
            if result.returncode == 0:
                # Check for newly generated files
                output_files = []
                if os.path.exists(db_dir):
                    for file in os.listdir(db_dir):
                        if file.endswith('.html') or file.endswith('.txt'):
                            if file not in existing_files:
                                output_files.append(file)
                
                print(f"🔍 DEBUG: Newly generated files: {output_files}")
                
                if output_files:
                    print(f"✅ SUCCESS: Files generated in correct directory: {output_files}")
                    
                    # Verify files are in the expected directory
                    for file in output_files:
                        file_path = os.path.join(db_dir, file)
                        if os.path.exists(file_path):
                            print(f"✅ File exists: {file_path}")
                        else:
                            print(f"❌ File missing: {file_path}")
                else:
                    print(f"⚠️ No new files generated")
            else:
                print(f"❌ Execution failed: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Execution error: {e}")
        
        print("\n" + "=" * 50)
        print("✅ Test completed!")
        
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        print("🧹 Cleaned up temporary files")

if __name__ == "__main__":
    test_comparison_execution_directory() 