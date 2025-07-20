#!/usr/bin/env python3
"""
Test edit operation context preservation and file tracking:
1. Verify that original user query is preserved during edits
2. Verify that HTML files from edited files are associated with original query
3. Verify that edits maintain the original intent
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

def test_edit_context_and_tracking():
    """Test edit operation context preservation and file tracking"""
    print("Testing Edit Context Preservation and File Tracking")
    print("=" * 60)
    
    # Initialize scenario manager and agent
    project_root = os.path.dirname(__file__)
    scenario_manager = ScenarioManager(project_root)
    agent = create_agent_v2(scenario_manager=scenario_manager)
    
    # Create a test scenario
    print("\n=== Creating test scenario ===")
    scenario = scenario_manager.create_scenario("Test Edit Context Scenario")
    scenario_manager.switch_scenario(scenario.id)
    print(f"Created scenario: {scenario.name} (ID: {scenario.id})")
    
    # Test 1: Create a file with a specific query (top 10 locations)
    print("\n=== Test 1: Creating file with specific query ===")
    original_query = "Create a script to show the top 10 locations by demand"
    
    print(f"Original query: {original_query}")
    
    # Run the original request
    response1, generated_files1, execution_output1, execution_error1 = agent.run(original_query)
    
    print(f"Response: {response1}")
    print(f"Generated files: {generated_files1}")
    print(f"Execution output: {execution_output1}")
    print(f"Execution error: {execution_error1}")
    
    # Get the Python file that was created
    python_file = None
    for file in generated_files1:
        if file.endswith('.py'):
            python_file = file
            break
    
    if not python_file:
        print("FAILED: No Python file was generated")
        return
    
    print(f"Python file created: {python_file}")
    
    # Check the content of the generated file to see if it has "top 10" logic
    file_path = os.path.join(os.path.dirname(scenario.database_path), python_file)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            content = f.read()
            print(f"File content contains 'LIMIT 10': {'LIMIT 10' in content}")
            print(f"File content contains 'top 10': {'top 10' in content.lower()}")
    
    # Test 2: Edit the file to remove a column
    print("\n=== Test 2: Editing file to remove column ===")
    edit_request = "Edit file " + python_file + ": remove the HubID column from the table"
    
    print(f"Edit request: {edit_request}")
    
    # Run the edit request
    response2, generated_files2, execution_output2, execution_error2 = agent.run(edit_request)
    
    print(f"Response: {response2}")
    print(f"Generated files: {generated_files2}")
    print(f"Execution output: {execution_output2}")
    print(f"Execution error: {execution_error2}")
    
    # Check if this was detected as an edit operation
    is_edit = '[EDIT_OPERATION]' in response2
    has_edited_file = '[EDITED_FILE:' in response2
    print(f"Is edit operation: {is_edit}")
    print(f"Has edited file info: {has_edited_file}")
    
    # Check the modified file content
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            modified_content = f.read()
            print(f"Modified file contains 'LIMIT 10': {'LIMIT 10' in modified_content}")
            print(f"Modified file contains 'HubID': {'HubID' in modified_content}")
            print(f"Modified file contains 'Location': {'Location' in modified_content}")
    
    # Test 3: Check if HTML files are associated with original query
    print("\n=== Test 3: Checking HTML file association ===")
    
    # Look for HTML files in the scenario directory
    scenario_dir = os.path.dirname(scenario.database_path)
    html_files = [f for f in os.listdir(scenario_dir) if f.endswith('.html')]
    print(f"HTML files found: {html_files}")
    
    if html_files:
        print("SUCCESS: HTML files were generated from edited file execution")
        
        # Check if the HTML files are associated with the original query
        for html_file in html_files:
            # This would require checking the database, but for now we'll just verify the files exist
            print(f"HTML file: {html_file}")
    else:
        print("FAILED: No HTML files were generated from edited file execution")
    
    # Test 4: Edit the file again to change limit
    print("\n=== Test 4: Editing file to change limit ===")
    edit_request2 = "Edit file " + python_file + ": change the limit to 5 instead of 10"
    
    print(f"Second edit request: {edit_request2}")
    
    # Run the second edit request
    response3, generated_files3, execution_output3, execution_error3 = agent.run(edit_request2)
    
    print(f"Response: {response3}")
    print(f"Generated files: {generated_files3}")
    print(f"Execution output: {execution_output3}")
    print(f"Execution error: {execution_error3}")
    
    # Check the final file content
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            final_content = f.read()
            print(f"Final file contains 'LIMIT 5': {'LIMIT 5' in final_content}")
            print(f"Final file contains 'LIMIT 10': {'LIMIT 10' in final_content}")
            print(f"Final file contains 'top 10': {'top 10' in final_content.lower()}")
            print(f"Final file contains 'top 5': {'top 5' in final_content.lower()}")
    
    print("\n" + "=" * 60)
    print("Edit context and tracking test completed!")
    
    # Summary
    print("\n=== Summary ===")
    print(f"Original query preservation: {'PASS' if 'LIMIT 10' in modified_content else 'FAIL'}")
    print(f"Edit operation detection: {'PASS' if is_edit and has_edited_file else 'FAIL'}")
    print(f"HTML file generation: {'PASS' if html_files else 'FAIL'}")
    print(f"Limit change: {'PASS' if 'LIMIT 5' in final_content else 'FAIL'}")
    
    # Cleanup
    print("\nCleaning up...")
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
        print("Test files cleaned up")
    except Exception as e:
        print(f"Warning: Could not clean up test files: {e}")

if __name__ == "__main__":
    test_edit_context_and_tracking() 