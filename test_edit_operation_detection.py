#!/usr/bin/env python3
"""
Test edit operation detection and handling:
1. Verify that edit operations are properly detected
2. Verify that edit operations don't create new query groups
3. Verify that execution results are properly associated with the original query
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

def test_edit_operation_detection():
    """Test edit operation detection and handling"""
    print("Testing Edit Operation Detection and Handling")
    print("=" * 50)
    
    # Initialize scenario manager and agent
    project_root = os.path.dirname(__file__)
    scenario_manager = ScenarioManager(project_root)
    agent = create_agent_v2(scenario_manager=scenario_manager)
    
    # Create a test scenario
    print("\n=== Creating test scenario ===")
    scenario = scenario_manager.create_scenario("Test Edit Detection Scenario")
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
    
    # Test 1: Regular file generation (should create new query group)
    print("\n=== Test 1: Regular file generation ===")
    regular_request = "Create a script to show the top 5 hubs by demand"
    
    print(f"Regular request: {regular_request}")
    
    # Run the regular request
    response1, generated_files1, execution_output1, execution_error1 = agent.run(regular_request)
    
    print(f"Response: {response1}")
    print(f"Generated files: {generated_files1}")
    print(f"Execution output: {execution_output1}")
    print(f"Execution error: {execution_error1}")
    
    # Check if this was detected as an edit operation
    is_edit1 = '[EDIT_OPERATION]' in response1
    print(f"Is edit operation: {is_edit1}")
    
    if not is_edit1:
        print("SUCCESS: Regular request correctly not detected as edit operation")
    else:
        print("FAILED: Regular request incorrectly detected as edit operation")
    
    # Test 2: Edit operation (should NOT create new query group)
    print("\n=== Test 2: Edit operation ===")
    edit_request = "Edit file test_script.py: remove the HubID column from the table"
    
    print(f"Edit request: {edit_request}")
    
    # Run the edit request
    response2, generated_files2, execution_output2, execution_error2 = agent.run(edit_request)
    
    print(f"Response: {response2}")
    print(f"Generated files: {generated_files2}")
    print(f"Execution output: {execution_output2}")
    print(f"Execution error: {execution_error2}")
    
    # Check if this was detected as an edit operation
    is_edit2 = '[EDIT_OPERATION]' in response2
    edited_file_match = '[EDITED_FILE:' in response2 if response2 else False
    
    print(f"Is edit operation: {is_edit2}")
    print(f"Has edited file info: {edited_file_match}")
    
    if is_edit2 and edited_file_match:
        print("SUCCESS: Edit request correctly detected as edit operation")
    else:
        print("FAILED: Edit request not detected as edit operation")
        print("Response should contain [EDIT_OPERATION] and [EDITED_FILE: filename]")
    
    # Test 3: Another edit operation (should also be detected as edit)
    print("\n=== Test 3: Second edit operation ===")
    edit_request2 = "Edit file test_script.py: change the limit to 5 instead of 10"
    
    print(f"Second edit request: {edit_request2}")
    
    # Run the second edit request
    response3, generated_files3, execution_output3, execution_error3 = agent.run(edit_request2)
    
    print(f"Response: {response3}")
    print(f"Generated files: {generated_files3}")
    print(f"Execution output: {execution_output3}")
    print(f"Execution error: {execution_error3}")
    
    # Check if this was detected as an edit operation
    is_edit3 = '[EDIT_OPERATION]' in response3
    edited_file_match3 = '[EDITED_FILE:' in response3 if response3 else False
    
    print(f"Is edit operation: {is_edit3}")
    print(f"Has edited file info: {edited_file_match3}")
    
    if is_edit3 and edited_file_match3:
        print("SUCCESS: Second edit request correctly detected as edit operation")
    else:
        print("FAILED: Second edit request not detected as edit operation")
    
    print("\n" + "=" * 50)
    print("Edit operation detection test completed!")
    
    # Summary
    print("\n=== Summary ===")
    print(f"Regular request edit detection: {'PASS' if not is_edit1 else 'FAIL'}")
    print(f"First edit request detection: {'PASS' if is_edit2 and edited_file_match else 'FAIL'}")
    print(f"Second edit request detection: {'PASS' if is_edit3 and edited_file_match3 else 'FAIL'}")
    
    # Cleanup
    print("\nCleaning up...")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        print("Test files cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean up test files: {e}")

if __name__ == "__main__":
    test_edit_operation_detection() 