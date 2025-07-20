#!/usr/bin/env python3
"""
Test script for file editing fixes
"""

import requests
import json
import time
import os

# Test configuration
BASE_URL = "http://localhost:8001"

def test_file_editing_fixes():
    """Test the file editing fixes"""
    
    print("🧪 Testing File Editing Fixes")
    print("=" * 50)
    
    # Test 1: Check if server is running
    print("\n1. Testing server connectivity...")
    try:
        response = requests.get(f"{BASE_URL}/status")
        if response.status_code == 200:
            print("✅ Server is running")
        else:
            print(f"❌ Server returned status: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Server not accessible: {e}")
        return
    
    # Test 2: Get scenarios to understand file locations
    print("\n2. Getting scenarios...")
    try:
        response = requests.get(f"{BASE_URL}/scenarios/list")
        if response.status_code == 200:
            scenarios = response.json()
            print(f"✅ Found {len(scenarios)} scenarios")
            for scenario in scenarios:
                print(f"   - {scenario['name']}: {scenario['database_path']}")
        else:
            print(f"❌ Failed to get scenarios: {response.status_code}")
            return
    except Exception as e:
        print(f"❌ Error getting scenarios: {e}")
        return
    
    # Test 3: Create a test file in a scenario directory
    print("\n3. Creating test file in scenario directory...")
    test_file_content = """
import pandas as pd
import sqlite3

# Test script for editing
def analyze_data():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM your_table LIMIT 10", conn)
    print("Data analysis complete")
    return df

if __name__ == "__main__":
    analyze_data()
"""
    
    # Try to find a scenario directory
    try:
        response = requests.get(f"{BASE_URL}/scenarios/list")
        if response.status_code == 200:
            scenarios = response.json()
            if scenarios:
                # Use the first scenario
                scenario = scenarios[0]
                scenario_dir = os.path.dirname(scenario['database_path'])
                test_file_path = os.path.join(scenario_dir, "test_editing_script.py")
                
                with open(test_file_path, 'w') as f:
                    f.write(test_file_content)
                print(f"✅ Test file created: {test_file_path}")
                
                # Test 4: Test file content retrieval via /files endpoint
                print("\n4. Testing file content retrieval via /files endpoint...")
                try:
                    response = requests.get(f"{BASE_URL}/files/test_editing_script.py")
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✅ File content retrieved via /files: {len(data['content'])} characters")
                    else:
                        print(f"❌ File content retrieval via /files failed: {response.status_code}")
                except Exception as e:
                    print(f"❌ Error testing file content retrieval via /files: {e}")
                
                # Test 5: Test file content retrieval via /api/files endpoint
                print("\n5. Testing file content retrieval via /api/files endpoint...")
                try:
                    response = requests.get(f"{BASE_URL}/api/files/test_editing_script.py/content")
                    if response.status_code == 200:
                        data = response.json()
                        print(f"✅ File content retrieved via /api/files: {len(data['content'])} characters")
                    else:
                        print(f"❌ File content retrieval via /api/files failed: {response.status_code}")
                except Exception as e:
                    print(f"❌ Error testing file content retrieval via /api/files: {e}")
                
                # Test 6: Test file modification
                print("\n6. Testing file modification...")
                modified_content = test_file_content + "\n# Modified by test script\n"
                try:
                    response = requests.put(f"{BASE_URL}/api/files/test_editing_script.py/content", 
                                          json={
                                              "content": modified_content,
                                              "modification_query": "Add comment to test file",
                                              "query_id": "test_query_456"
                                          })
                    if response.status_code == 200:
                        print("✅ File modification successful")
                    else:
                        print(f"❌ File modification failed: {response.status_code}")
                except Exception as e:
                    print(f"❌ Error testing file modification: {e}")
                
                # Test 7: Test file download endpoint
                print("\n7. Testing file download endpoint...")
                try:
                    response = requests.get(f"{BASE_URL}/files/test_editing_script.py/download")
                    if response.status_code == 200:
                        print(f"✅ File download successful: {len(response.content)} bytes")
                    else:
                        print(f"❌ File download failed: {response.status_code}")
                except Exception as e:
                    print(f"❌ Error testing file download: {e}")
                
                # Cleanup
                print("\n8. Cleaning up...")
                try:
                    if os.path.exists(test_file_path):
                        os.remove(test_file_path)
                    if os.path.exists(f"{test_file_path}.backup"):
                        os.remove(f"{test_file_path}.backup")
                    print("✅ Test files cleaned up")
                except Exception as e:
                    print(f"❌ Error cleaning up: {e}")
            else:
                print("❌ No scenarios available for testing")
        else:
            print(f"❌ Failed to get scenarios: {response.status_code}")
    except Exception as e:
        print(f"❌ Error accessing scenarios: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 File editing fixes test completed!")

if __name__ == "__main__":
    test_file_editing_fixes() 