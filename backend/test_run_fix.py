#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import subprocess
import time

def test_run_fix():
    """Test the updated /run endpoint logic"""
    
    # Simulate the file content that would be processed
    original_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
import pandas as pd

# Test import of dataprocessing
try:
    from dataprocessing import process_inputs, process_data
    print("[OK] Successfully imported dataprocessing module")
except ImportError as e:
    print(f"[ERROR] Failed to import dataprocessing: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

def main():
    """Main function to test the model execution"""
    print("[START] Starting test_runall.py execution...")
    
    # Test dataprocessing functions
    result1 = process_inputs()
    result2 = process_data("test data")
    
    print(f"[OK] process_inputs result: {result1}")
    print(f"[OK] process_data result: {result2}")
    
    print("[OK] test_runall.py completed successfully!")

if __name__ == "__main__":
    main()
'''
    
    # Simulate the database path injection
    current_db_path = "C:\\\\Users\\\\Bebob\\\\Dropbox\\\\University\\\\MA425 Project in Operations Research\\\\EYProjectGit\\\\backend\\\\test_database.db"
    
    # Replace database paths (simulating the /run endpoint logic)
    file_content = original_content.replace('"project_data.db"', f'"{current_db_path}"')
    file_content = file_content.replace("'project_data.db'", f"'{current_db_path}'")
    
    # Create temp file in the backend directory (where dependencies are)
    backend_dir = os.path.dirname(os.path.abspath(__file__))
    timestamp = int(time.time() * 1000)
    temp_filename = f"__temp_exec_{timestamp}.py"
    temp_file_path = os.path.join(backend_dir, temp_filename)
    
    print(f"Creating temp file: {temp_file_path}")
    print(f"Backend directory: {backend_dir}")
    print(f"Dependencies available: {os.listdir(backend_dir) if os.path.exists(backend_dir) else 'Directory not found'}")
    
    # Write the modified content to the temp file
    with open(temp_file_path, 'w', encoding='utf-8') as temp_file:
        temp_file.write(file_content)
    
    try:
        # Execute the temp file
        print(f"Executing temp file: {temp_file_path}")
        result = subprocess.run(
            [sys.executable, temp_file_path],
            cwd=backend_dir,  # Execute in backend directory where dependencies are
            capture_output=True,
            text=True,
            timeout=30
        )
        
        print("=== STDOUT ===")
        print(result.stdout)
        print("=== STDERR ===")
        print(result.stderr)
        print("=== RETURN CODE ===")
        print(result.returncode)
        
    finally:
        # Clean up temp file
        try:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                print(f"Cleaned up temp file: {temp_file_path}")
        except Exception as e:
            print(f"Could not clean up temp file: {e}")

if __name__ == "__main__":
    test_run_fix() 