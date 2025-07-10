#!/usr/bin/env python3
"""
Test script to verify upload and scenario system fixes
"""

import requests
import json
import os
import tempfile
import zipfile
import sqlite3

# Test configuration
BASE_URL = "http://localhost:8001"

def test_status():
    """Test that the server is running"""
    print("Testing server status...")
    response = requests.get(f"{BASE_URL}/status")
    if response.status_code == 200:
        print("✅ Server is running")
        return True
    else:
        print(f"❌ Server error: {response.status_code}")
        return False

def test_database_info_no_db():
    """Test database info endpoint when no database is uploaded"""
    print("Testing database info (no database)...")
    response = requests.get(f"{BASE_URL}/database/info")
    if response.status_code == 400:
        print("✅ Correctly returns 400 when no database is available")
        return True
    else:
        print(f"❌ Unexpected response: {response.status_code}")
        return False

def create_test_zip():
    """Create a test zip file with a simple database"""
    print("Creating test zip file...")
    
    # Create a temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a simple SQLite database
        db_path = os.path.join(temp_dir, "test.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create a test table
        cursor.execute("""
            CREATE TABLE test_table (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value REAL
            )
        """)
        
        # Insert some test data
        cursor.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("Test1", 10.5))
        cursor.execute("INSERT INTO test_table (name, value) VALUES (?, ?)", ("Test2", 20.7))
        conn.commit()
        conn.close()
        
        # Create a test Python file
        py_path = os.path.join(temp_dir, "test.py")
        with open(py_path, 'w') as f:
            f.write("""
import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect('test.db')
df = pd.read_sql_query("SELECT * FROM test_table", conn)
print("Database contents:")
print(df)
conn.close()
""")
        
        # Create zip file
        zip_path = "test_upload.zip"
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            zipf.write(db_path, "test.db")
            zipf.write(py_path, "test.py")
        
        print(f"✅ Created test zip file: {zip_path}")
        return zip_path

def test_upload():
    """Test file upload"""
    print("Testing file upload...")
    
    zip_path = create_test_zip()
    
    try:
        with open(zip_path, 'rb') as f:
            files = {'file': ('test_upload.zip', f, 'application/zip')}
            response = requests.post(f"{BASE_URL}/upload", files=files)
        
        if response.status_code == 200:
            result = response.json()
            print("✅ Upload successful")
            print(f"   Files: {result.get('files', [])}")
            print(f"   Database info: {result.get('database_info', {})}")
            print(f"   Scenario: {result.get('scenario', {})}")
            return True
        else:
            print(f"❌ Upload failed: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
    finally:
        # Clean up
        if os.path.exists(zip_path):
            os.remove(zip_path)

def test_database_info_with_db():
    """Test database info endpoint after upload"""
    print("Testing database info (with database)...")
    response = requests.get(f"{BASE_URL}/database/info")
    if response.status_code == 200:
        result = response.json()
        print("✅ Database info retrieved")
        print(f"   Tables: {result.get('tables', [])}")
        print(f"   Total tables: {result.get('total_tables', 0)}")
        return True
    else:
        print(f"❌ Database info failed: {response.status_code}")
        return False

def test_langgraph_chat():
    """Test LangGraph chat endpoint"""
    print("Testing LangGraph chat...")
    
    message = {
        "role": "user",
        "content": "What tables are in the database?",
        "thread_id": "test"
    }
    
    response = requests.post(f"{BASE_URL}/langgraph-chat", json=message)
    if response.status_code == 200:
        result = response.json()
        print("✅ LangGraph chat successful")
        print(f"   Response: {result.get('response', '')[:100]}...")
        return True
    else:
        print(f"❌ LangGraph chat failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def test_run_file():
    """Test running a Python file"""
    print("Testing file execution...")
    
    response = requests.post(f"{BASE_URL}/run?filename=test.py")
    if response.status_code == 200:
        result = response.json()
        print("✅ File execution successful")
        print(f"   Output: {result.get('stdout', '')[:100]}...")
        return True
    else:
        print(f"❌ File execution failed: {response.status_code}")
        print(f"   Response: {response.text}")
        return False

def main():
    """Run all tests"""
    print("=" * 50)
    print("Testing Upload and Scenario System Fixes")
    print("=" * 50)
    
    tests = [
        test_status,
        test_database_info_no_db,
        test_upload,
        test_database_info_with_db,
        test_langgraph_chat,
        test_run_file
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"❌ Test failed with exception: {e}")
        print()
    
    print("=" * 50)
    print(f"Test Results: {passed}/{total} tests passed")
    print("=" * 50)
    
    if passed == total:
        print("🎉 All tests passed! The upload and scenario system is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the issues above.")

if __name__ == "__main__":
    main() 