#!/usr/bin/env python3
"""
Test the full workflow: upload file, create base scenario, create branch scenario
"""

import os
import sys
import sqlite3
import shutil
from scenario_manager import get_scenario_manager

def create_test_database():
    """Create a test database with some data"""
    test_db_path = "test_upload.db"
    
    # Create a test database with multiple tables and data
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    
    # Create some test tables
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT,
            region TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id INTEGER,
            quantity INTEGER,
            order_date TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(id),
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    ''')
    
    # Insert some test data
    cursor.execute('''
        INSERT INTO products (name, price, category) VALUES 
        ('Laptop', 999.99, 'Electronics'),
        ('Mouse', 29.99, 'Electronics'),
        ('Desk', 199.99, 'Furniture'),
        ('Chair', 149.99, 'Furniture')
    ''')
    
    cursor.execute('''
        INSERT INTO customers (name, email, region) VALUES 
        ('John Doe', 'john@example.com', 'North'),
        ('Jane Smith', 'jane@example.com', 'South'),
        ('Bob Johnson', 'bob@example.com', 'East')
    ''')
    
    cursor.execute('''
        INSERT INTO orders (customer_id, product_id, quantity, order_date) VALUES 
        (1, 1, 1, '2024-01-15'),
        (2, 2, 2, '2024-01-16'),
        (3, 3, 1, '2024-01-17')
    ''')
    
    conn.commit()
    conn.close()
    
    return test_db_path

def test_full_workflow():
    """Test the complete workflow"""
    
    print("=== Testing Full Workflow ===")
    
    # Get the scenario manager
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = get_scenario_manager(project_root)
    
    # Step 1: Create a test database (simulating file upload)
    print("\n1. Creating test database (simulating file upload)...")
    test_db_path = create_test_database()
    print(f"Created test database: {test_db_path}")
    
    # Verify test database content
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Test database tables: {[t[0] for t in tables]}")
    for table in tables:
        table_name = table[0]
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]
        print(f"  {table_name}: {count} rows")
    conn.close()
    
    # Step 2: Copy test database to shared directory (simulating upload)
    print("\n2. Copying test database to shared directory...")
    shared_db_path = os.path.join(scenario_manager.shared_dir, "original_upload.db")
    shutil.copy2(test_db_path, shared_db_path)
    print(f"Copied to: {shared_db_path}")
    
    # Step 3: Create base scenario
    print("\n3. Creating base scenario...")
    base_scenario = scenario_manager.create_scenario(
        name="Base Scenario",
        description="Base scenario from uploaded file",
        original_db_path=shared_db_path
    )
    print(f"Created base scenario: {base_scenario.id} - {base_scenario.name}")
    print(f"Base database: {base_scenario.database_path}")
    
    # Verify base scenario database
    if os.path.exists(base_scenario.database_path):
        conn = sqlite3.connect(base_scenario.database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Base scenario tables: {[t[0] for t in tables]}")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} rows")
        conn.close()
    else:
        print("ERROR: Base scenario database was not created!")
    
    # Step 4: Create branch scenario
    print("\n4. Creating branch scenario...")
    branch_scenario = scenario_manager.create_scenario(
        name="Branch Scenario",
        base_scenario_id=base_scenario.id,
        description="Branch from base scenario"
    )
    print(f"Created branch scenario: {branch_scenario.id} - {branch_scenario.name}")
    print(f"Branch database: {branch_scenario.database_path}")
    
    # Verify branch scenario database
    if os.path.exists(branch_scenario.database_path):
        conn = sqlite3.connect(branch_scenario.database_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Branch scenario tables: {[t[0] for t in tables]}")
        for table in tables:
            table_name = table[0]
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"  {table_name}: {count} rows")
        conn.close()
    else:
        print("ERROR: Branch scenario database was not created!")
    
    # Step 5: List all scenarios
    print("\n5. All scenarios:")
    scenarios = scenario_manager.list_scenarios()
    for scenario in scenarios:
        print(f"  - Scenario {scenario.id}: {scenario.name} (base: {scenario.is_base_scenario})")
        print(f"    Database: {scenario.database_path}")
        print(f"    Exists: {os.path.exists(scenario.database_path)}")
    
    # Cleanup
    print("\n6. Cleaning up...")
    if os.path.exists(test_db_path):
        os.remove(test_db_path)
    print("Test completed!")

if __name__ == "__main__":
    test_full_workflow() 