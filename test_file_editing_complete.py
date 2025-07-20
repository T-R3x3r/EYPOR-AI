#!/usr/bin/env python3
"""
Test file editing functionality:
1. File editing should update existing files, not create new ones
2. File editing should not create new sidebar entries
3. File editing should execute the modified file
"""

import os
import sys
import time
import sqlite3
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.langgraph_agent_v2 import create_agent_v2
from backend.scenario_manager import ScenarioManager

def test_file_editing_complete():
    """Test complete file editing workflow"""
    print("Testing Complete File Editing Workflow")
    print("=" * 50)
    
    # Initialize scenario manager and agent
    project_root = os.path.dirname(__file__)
    scenario_manager = ScenarioManager(project_root)
    agent = create_agent_v2(scenario_manager=scenario_manager)
    
    # Create a test scenario
    print("\n=== Creating test scenario ===")
    scenario = scenario_manager.create_scenario("Test File Editing Scenario")
    scenario_manager.switch_scenario(scenario.id)
    print(f"Created scenario: {scenario.name} (ID: {scenario.id})")
    
    # Create a test file first
    print("\n=== Creating initial test file ===")
    test_file_content = '''import pandas as pd
import sqlite3

# Connect to database
conn = sqlite3.connect('database.db')

# Query to get top 10 hubs by demand
query = """
SELECT HubID, Location, TotalDemand
FROM hubs 
ORDER BY TotalDemand DESC 
LIMIT 10
"""

# Execute query
df = pd.read_sql_query(query, conn)
print("Top 10 hubs by demand:")
print(df)

# Save as HTML
df.to_html('top_10_hubs_by_demand.html', index=False)
print("Generated files: top_10_hubs_by_demand.html")

conn.close()
'''
    
    # Save the initial file
    file_path = os.path.join(os.path.dirname(scenario.database_path), 'test_script.py')
    with open(file_path, 'w') as f:
        f.write(test_file_content)
    
    print(f"Created initial file: {file_path}")
    
    # Test 1: Edit the file to remove HubID column
    print("\n=== Test 1: Editing file to remove HubID column ===")
    edit_request = "Edit file test_script.py: remove the HubID column from the table"
    
    print(f"Edit request: {edit_request}")
    
    # Run the edit request
    response, generated_files, execution_output, execution_error = agent.run(edit_request)
    
    print(f"Response: {response}")
    print(f"Generated files: {generated_files}")
    print(f"Execution output: {execution_output}")
    print(f"Execution error: {execution_error}")
    
    # Check that the file was modified (not created new)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            modified_content = f.read()
        
        # Check if HubID was removed
        if 'HubID' not in modified_content:
            print("SUCCESS: HubID column was successfully removed from the query")
        else:
            print("FAILED: HubID column was not removed")
            print("Modified content:")
            print(modified_content)
    else:
        print("FAILED: Modified file not found")
    
    # Test 2: Verify no new files were created
    print("\n=== Test 2: Verifying no new files were created ===")
    scenario_dir = os.path.dirname(scenario.database_path)
    files_before = set(os.listdir(scenario_dir))
    
    # Run another edit request
    edit_request2 = "Edit file test_script.py: change the limit to 5 instead of 10"
    print(f"Second edit request: {edit_request2}")
    
    response2, generated_files2, execution_output2, execution_error2 = agent.run(edit_request2)
    
    files_after = set(os.listdir(scenario_dir))
    new_files = files_after - files_before
    
    print(f"Files before: {files_before}")
    print(f"Files after: {files_after}")
    print(f"New files created: {new_files}")
    
    if not new_files:
        print("SUCCESS: No new files were created during editing")
    else:
        print("FAILED: New files were created during editing")
    
    # Test 3: Verify the file was executed after editing
    print("\n=== Test 3: Verifying file execution after editing ===")
    
    # Check if HTML output was generated
    html_files = [f for f in os.listdir(scenario_dir) if f.endswith('.html')]
    print(f"HTML files found: {html_files}")
    
    if html_files:
        print("SUCCESS: File was executed and generated HTML output")
    else:
        print("FAILED: File was not executed or no HTML output generated")
    
    # Test 4: Check file content after second edit
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            final_content = f.read()
        
        if 'LIMIT 5' in final_content:
            print("SUCCESS: File was successfully modified to use LIMIT 5")
        else:
            print("FAILED: File was not modified to use LIMIT 5")
            print("Final content:")
            print(final_content)
    
    print("\n" + "=" * 50)
    print("Complete file editing test completed!")
    
    # Cleanup
    print("\nCleaning up...")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        print("Test files cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean up test files: {e}")

if __name__ == "__main__":
    test_file_editing_complete() 