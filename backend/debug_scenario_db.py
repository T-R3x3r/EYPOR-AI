#!/usr/bin/env python3
"""
Debug script to test scenario database path resolution
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scenario_manager import ScenarioManager

def debug_scenario_database():
    """Debug the scenario database path resolution"""
    
    # Initialize scenario manager
    SCENARIO_BASE_DIR = os.path.join(os.getcwd(), 'scenarios')
    scenario_manager = ScenarioManager(SCENARIO_BASE_DIR)
    
    print("=== DEBUG: Scenario Database Path Resolution ===")
    
    # List all scenarios
    scenarios = scenario_manager.list_scenarios()
    print(f"DEBUG: Total scenarios: {len(scenarios)}")
    
    for scenario in scenarios:
        print(f"DEBUG: Scenario {scenario.id}: {scenario.name}")
        print(f"DEBUG:   Database path: {scenario.database_path}")
        print(f"DEBUG:   Database exists: {os.path.exists(scenario.database_path)}")
        print(f"DEBUG:   Is base scenario: {scenario.is_base_scenario}")
        print(f"DEBUG:   Parent scenario ID: {scenario.parent_scenario_id}")
        print()
    
    # Check current scenario
    current_scenario = scenario_manager.get_current_scenario()
    print(f"DEBUG: Current scenario ID: {scenario_manager.state.current_scenario_id}")
    
    if current_scenario:
        print(f"DEBUG: Current scenario: {current_scenario.name} (ID: {current_scenario.id})")
        print(f"DEBUG: Current scenario database: {current_scenario.database_path}")
        print(f"DEBUG: Current scenario database exists: {os.path.exists(current_scenario.database_path)}")
    else:
        print("DEBUG: No current scenario found!")
    
    # Test the get_active_scenario_database function logic
    print("\n=== Testing get_active_scenario_database logic ===")
    
    # Simulate the function from main.py
    def get_active_scenario_database():
        scenario = scenario_manager.get_current_scenario()
        if scenario and scenario.database_path:
            print(f"DEBUG: Using scenario database: {scenario.database_path}")
            return scenario.database_path
        else:
            print("DEBUG: Falling back to current_database_path")
            return None  # We don't have access to current_database_path here
    
    active_db = get_active_scenario_database()
    print(f"DEBUG: Active database path: {active_db}")
    
    # Check if the original upload database exists
    original_db_path = os.path.join(scenario_manager.shared_dir, "original_upload.db")
    print(f"DEBUG: Original upload database path: {original_db_path}")
    print(f"DEBUG: Original upload database exists: {os.path.exists(original_db_path)}")

if __name__ == "__main__":
    debug_scenario_database() 