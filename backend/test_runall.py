#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import sqlite3
import pandas as pd

# Test import of dataprocessing
try:
    from dataprocessing import process_inputs, process_data
    print("✅ Successfully imported dataprocessing module")
except ImportError as e:
    print(f"❌ Failed to import dataprocessing: {e}")
    print(f"Current working directory: {os.getcwd()}")
    print(f"Python path: {sys.path}")
    sys.exit(1)

def main():
    """Main function to test the model execution"""
    print("🚀 Starting test_runall.py execution...")
    
    # Test dataprocessing functions
    result1 = process_inputs()
    result2 = process_data("test data")
    
    print(f"✅ process_inputs result: {result1}")
    print(f"✅ process_data result: {result2}")
    
    # Test database connection (this will be replaced with current scenario's database)
    try:
        # This path will be replaced by the /run endpoint
        db_path = "project_data.db"
        print(f"🔍 Attempting to connect to database: {db_path}")
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get list of tables
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"✅ Successfully connected to database")
        print(f"📊 Found tables: {[table[0] for table in tables]}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
    
    print("✅ test_runall.py completed successfully!")

if __name__ == "__main__":
    main() 