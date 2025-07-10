#!/usr/bin/env python3
"""
Test to verify that database modification requests don't create empty query groups.
This test ensures that when a request doesn't generate any files, no query group
is created in the sidebar.
"""

import requests
import json
import time
import os

def test_db_modification_no_query_group():
    """Test that DB modification requests don't create empty query groups"""
    
    base_url = "http://localhost:8000"
    
    # Test message that should trigger a database modification (no file generation)
    test_message = "Change the demand for location 'New York' to 500"
    
    print(f"Testing DB modification request: {test_message}")
    
    # Send the request
    response = requests.post(
        f"{base_url}/langgraph-chat",
        json={
            "message": test_message,
            "thread_id": f"test_db_mod_{int(time.time())}"
        },
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    print(f"✅ Response received")
    print(f"Generated files: {result.get('generated_files', [])}")
    print(f"User query: {result.get('user_query', 'None')}")
    
    # Check that no files were generated
    generated_files = result.get('generated_files', [])
    if len(generated_files) == 0:
        print("✅ No files generated - this is correct for DB modification")
        return True
    else:
        print(f"❌ Unexpected files generated: {generated_files}")
        return False

def test_visualization_creates_query_group():
    """Test that visualization requests do create query groups with files"""
    
    base_url = "http://localhost:8000"
    
    # Test message that should trigger a visualization (file generation)
    test_message = "Create a bar chart showing the top 5 locations by demand"
    
    print(f"\nTesting visualization request: {test_message}")
    
    # Send the request
    response = requests.post(
        f"{base_url}/langgraph-chat",
        json={
            "message": test_message,
            "thread_id": f"test_viz_{int(time.time())}"
        },
        headers={"Content-Type": "application/json"}
    )
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        print(response.text)
        return False
    
    result = response.json()
    print(f"✅ Response received")
    print(f"Generated files: {result.get('generated_files', [])}")
    print(f"User query: {result.get('user_query', 'None')}")
    
    # Check that files were generated
    generated_files = result.get('generated_files', [])
    if len(generated_files) > 0:
        print("✅ Files generated - this is correct for visualization")
        return True
    else:
        print("❌ No files generated - this is unexpected for visualization")
        return False

if __name__ == "__main__":
    print("Testing query group creation behavior...")
    
    # Test 1: DB modification should not create query group
    success1 = test_db_modification_no_query_group()
    
    # Test 2: Visualization should create query group
    success2 = test_visualization_creates_query_group()
    
    if success1 and success2:
        print("\n✅ All tests passed! Query group behavior is correct.")
    else:
        print("\n❌ Some tests failed. Check the output above.") 