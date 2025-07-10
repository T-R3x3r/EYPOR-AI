#!/usr/bin/env python3
"""
Debug script to test scenario branching functionality
"""

import os
import sys
import sqlite3
from scenario_manager import get_scenario_manager

def test_scenario_branching():
    """Test the scenario branching functionality"""
    
    # Get the scenario manager
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = get_scenario_manager(project_root)
    
    print("=== Testing Scenario Branching ===")
    
    # List current scenarios
    scenarios = scenario_manager.list_scenarios()
    print(f"Current scenarios: {len(scenarios)}")
    for scenario in scenarios:
        print(f"  - Scenario {scenario.id}: {scenario.name} (base: {scenario.is_base_scenario})")
        print(f"    Database: {scenario.database_path}")
        print(f"    Exists: {os.path.exists(scenario.database_path)}")
        
        # Check database content
        if os.path.exists(scenario.database_path):
            try:
                conn = sqlite3.connect(scenario.database_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                print(f"    Tables: {[t[0] for t in tables]}")
                
                # Check table contents
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    print(f"      {table_name}: {count} rows")
                
                conn.close()
            except Exception as e:
                print(f"    Error reading database: {e}")
        print()
    
    # Get current scenario
    current_scenario = scenario_manager.get_current_scenario()
    if current_scenario:
        print(f"Current scenario: {current_scenario.id} - {current_scenario.name}")
        
        # Try to create a branch
        print("\n=== Creating Branch Scenario ===")
        try:
            branch_scenario = scenario_manager.create_scenario(
                name="Test Branch",
                base_scenario_id=current_scenario.id,
                description="Test branch from current scenario"
            )
            print(f"Created branch scenario: {branch_scenario.id} - {branch_scenario.name}")
            print(f"Branch database: {branch_scenario.database_path}")
            print(f"Branch database exists: {os.path.exists(branch_scenario.database_path)}")
            
            # Check branch database content
            if os.path.exists(branch_scenario.database_path):
                conn = sqlite3.connect(branch_scenario.database_path)
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = cursor.fetchall()
                print(f"Branch tables: {[t[0] for t in tables]}")
                
                # Check table contents
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cursor.fetchone()[0]
                    print(f"  {table_name}: {count} rows")
                
                conn.close()
            else:
                print("ERROR: Branch database was not created!")
                
        except Exception as e:
            print(f"Error creating branch scenario: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("No current scenario found")

if __name__ == "__main__":
    test_scenario_branching() 