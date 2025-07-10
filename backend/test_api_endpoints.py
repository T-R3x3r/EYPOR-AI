#!/usr/bin/env python3
"""
Test script to verify API endpoints work with scenario files.
"""

import os
import sys
import requests
import json
from scenario_manager import ScenarioManager

def test_api_endpoints():
    """Test API endpoints with scenario files"""
    
    # Setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    # Get current scenario
    current_scenario = scenario_manager.get_current_scenario()
    if not current_scenario:
        print("No current scenario found")
        return
    
    print(f"Testing with scenario: {current_scenario.name}")
    print(f"Database path: {current_scenario.database_path}")
    
    # Create a test Python file in the scenario directory
    scenario_dir = os.path.dirname(current_scenario.database_path)
    test_file = "test_api_endpoint.py"
    test_file_path = os.path.join(scenario_dir, test_file)
    
    # Create test file content
    test_content = '''#!/usr/bin/env python3
import os
print("Hello from test API endpoint!")
print(f"Current working directory: {os.getcwd()}")
print("Test completed successfully!")
'''
    
    # Write test file
    with open(test_file_path, 'w') as f:
        f.write(test_content)
    
    print(f"Created test file: {test_file_path}")
    
    # Test API endpoints
    base_url = "http://localhost:8001"
    
    # Test 1: Check if file is listed in /files
    print("\n=== Test 1: /files endpoint ===")
    try:
        response = requests.get(f"{base_url}/files")
        if response.status_code == 200:
            data = response.json()
            files = data.get('files', [])
            if test_file in files:
                print(f"✅ File {test_file} found in /files response")
            else:
                print(f"❌ File {test_file} NOT found in /files response")
                print(f"Available files: {files}")
        else:
            print(f"❌ /files endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing /files endpoint: {e}")
    
    # Test 2: Get file content
    print("\n=== Test 2: /files/{filename} endpoint ===")
    try:
        response = requests.get(f"{base_url}/files/{test_file}")
        if response.status_code == 200:
            data = response.json()
            content = data.get('content', '')
            if 'Hello from test API endpoint!' in content:
                print(f"✅ File content retrieved successfully")
            else:
                print(f"❌ File content not as expected")
        else:
            print(f"❌ /files/{test_file} endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing /files/{test_file} endpoint: {e}")
    
    # Test 3: Run file
    print("\n=== Test 3: /run endpoint ===")
    try:
        response = requests.post(f"{base_url}/run?filename={test_file}")
        if response.status_code == 200:
            data = response.json()
            stdout = data.get('stdout', '')
            if 'Hello from test API endpoint!' in stdout:
                print(f"✅ File executed successfully")
            else:
                print(f"❌ File execution output not as expected")
                print(f"Output: {stdout}")
        else:
            print(f"❌ /run endpoint failed: {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Error testing /run endpoint: {e}")
    
    # Clean up
    if os.path.exists(test_file_path):
        os.remove(test_file_path)
        print(f"\nCleaned up test file: {test_file_path}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_api_endpoints() 