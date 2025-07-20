#!/usr/bin/env python3
"""
Test script for file editing functionality
"""

import requests
import json
import time

# Test configuration
BASE_URL = "http://localhost:8001"

def test_file_editing_endpoints():
    """Test the file editing API endpoints"""
    
    print("🧪 Testing File Editing Functionality")
    print("=" * 50)
    
    # Test 1: Check if database tables were created
    print("\n1. Testing database initialization...")
    try:
        response = requests.get(f"{BASE_URL}/api/query-file-mappings")
        if response.status_code == 200:
            print("✅ Query file mappings endpoint working")
        else:
            print(f"❌ Query file mappings endpoint failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing query file mappings: {e}")
    
    # Test 2: Create a test file
    print("\n2. Creating test file...")
    test_file_content = """
import pandas as pd
import sqlite3

# Test script
def analyze_data():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM your_table LIMIT 10", conn)
    print("Data analysis complete")
    return df

if __name__ == "__main__":
    analyze_data()
"""
    
    test_file_path = "test_script.py"
    try:
        with open(test_file_path, 'w') as f:
            f.write(test_file_content)
        print("✅ Test file created")
    except Exception as e:
        print(f"❌ Error creating test file: {e}")
        return
    
    # Test 3: Test file content retrieval
    print("\n3. Testing file content retrieval...")
    try:
        response = requests.get(f"{BASE_URL}/api/files/{test_file_path}/content")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ File content retrieved: {len(data['content'])} characters")
        else:
            print(f"❌ File content retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing file content retrieval: {e}")
    
    # Test 4: Test file modification
    print("\n4. Testing file modification...")
    modified_content = test_file_content + "\n# Modified by test script\n"
    try:
        response = requests.put(f"{BASE_URL}/api/files/{test_file_path}/content", 
                              json={
                                  "content": modified_content,
                                  "modification_query": "Add comment to test file",
                                  "query_id": "test_query_123"
                              })
        if response.status_code == 200:
            print("✅ File modification successful")
        else:
            print(f"❌ File modification failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing file modification: {e}")
    
    # Test 5: Test file modification history
    print("\n5. Testing file modification history...")
    try:
        response = requests.get(f"{BASE_URL}/api/files/{test_file_path}/history")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ File history retrieved: {len(data['history'])} modifications")
        else:
            print(f"❌ File history retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing file history: {e}")
    
    # Test 6: Test query files endpoint
    print("\n6. Testing query files endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/api/query/test_query_123/files")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Query files retrieved: {len(data['files'])} files")
        else:
            print(f"❌ Query files retrieval failed: {response.status_code}")
    except Exception as e:
        print(f"❌ Error testing query files: {e}")
    
    # Cleanup
    print("\n7. Cleaning up...")
    try:
        import os
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
        if os.path.exists(f"{test_file_path}.backup"):
            os.remove(f"{test_file_path}.backup")
        print("✅ Test files cleaned up")
    except Exception as e:
        print(f"❌ Error cleaning up: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 File editing functionality test completed!")

if __name__ == "__main__":
    test_file_editing_endpoints() 