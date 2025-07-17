#!/usr/bin/env python3
"""
Test script to verify that scenario files execute correctly and are not added to uploaded_files.
This tests the complete fix for the execution directory issue.
"""

import os
import sys
import time
import requests
import json
from pathlib import Path

# Add the backend directory to the path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

# Import the main module to access global variables
import main

def test_scenario_file_execution():
    """Test that scenario files execute correctly and don't get added to uploaded_files"""
    
    print("=== Testing Scenario File Execution Fix ===")
    
    # Start the server if not already running
    base_url = "http://localhost:8000"
    
    try:
        # Test 1: Check if server is running
        response = requests.get(f"{base_url}/status", timeout=5)
        print("✓ Server is running")
    except requests.exceptions.RequestException:
        print("✗ Server is not running. Please start the server first.")
        return False
    
    # Test 2: Check current scenario
    try:
        response = requests.get(f"{base_url}/scenarios/current")
        current_scenario = response.json()
        print(f"✓ Current scenario: {current_scenario.get('name', 'Unknown')}")
        scenario_id = current_scenario.get('id')
        if not scenario_id:
            print("✗ No current scenario found")
            return False
    except Exception as e:
        print(f"✗ Error getting current scenario: {e}")
        return False
    
    # Test 3: Check uploaded_files before execution
    print("\n--- Before Execution ---")
    print(f"uploaded_files keys: {list(main.uploaded_files.keys())}")
    print(f"ai_created_files: {list(main.ai_created_files)}")
    
    # Test 4: Find a scenario Python file to execute
    scenario_dir = os.path.dirname(current_scenario['database_path'])
    print(f"Scenario directory: {scenario_dir}")
    
    python_files = []
    if os.path.exists(scenario_dir):
        for file in os.listdir(scenario_dir):
            if file.endswith('.py'):
                python_files.append(file)
    
    if not python_files:
        print("✗ No Python files found in scenario directory")
        return False
    
    test_file = python_files[0]
    print(f"✓ Found test file: {test_file}")
    
    # Test 5: Execute the file
    print(f"\n--- Executing {test_file} ---")
    try:
        response = requests.post(f"{base_url}/run", json={"filename": test_file}, timeout=180)
        if response.status_code == 200:
            result = response.json()
            print("✓ File executed successfully")
            print(f"Output: {result.get('output', 'No output')}")
            if result.get('error'):
                print(f"Error: {result['error']}")
        else:
            print(f"✗ Execution failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error executing file: {e}")
        return False
    
    # Test 6: Check uploaded_files after execution
    print("\n--- After Execution ---")
    print(f"uploaded_files keys: {list(main.uploaded_files.keys())}")
    print(f"ai_created_files: {list(main.ai_created_files)}")
    
    # Test 7: Verify the file is NOT in uploaded_files
    if test_file in main.uploaded_files:
        print(f"✗ ERROR: {test_file} is still in uploaded_files after execution")
        return False
    else:
        print(f"✓ {test_file} correctly NOT in uploaded_files")
    
    # Test 8: Execute the same file again
    print(f"\n--- Executing {test_file} again ---")
    try:
        response = requests.post(f"{base_url}/run", json={"filename": test_file}, timeout=180)
        if response.status_code == 200:
            result = response.json()
            print("✓ Second execution successful")
            print(f"Output: {result.get('output', 'No output')}")
            if result.get('error'):
                print(f"Error: {result['error']}")
        else:
            print(f"✗ Second execution failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error in second execution: {e}")
        return False
    
    # Test 9: Check uploaded_files after second execution
    print("\n--- After Second Execution ---")
    print(f"uploaded_files keys: {list(main.uploaded_files.keys())}")
    print(f"ai_created_files: {list(main.ai_created_files)}")
    
    # Test 10: Verify the file is still NOT in uploaded_files
    if test_file in main.uploaded_files:
        print(f"✗ ERROR: {test_file} is in uploaded_files after second execution")
        return False
    else:
        print(f"✓ {test_file} correctly NOT in uploaded_files after second execution")
    
    print("\n=== All Tests Passed ===")
    return True

if __name__ == "__main__":
    success = test_scenario_file_execution()
    if success:
        print("🎉 Scenario file execution fix is working correctly!")
    else:
        print("❌ Scenario file execution fix has issues.")
        sys.exit(1) 