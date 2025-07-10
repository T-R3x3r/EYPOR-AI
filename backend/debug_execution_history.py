#!/usr/bin/env python3
"""
Debug script to test execution history functionality
"""

import os
import sys
import json
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scenario_manager import ScenarioManager

def debug_execution_history():
    """Debug the execution history functionality"""
    
    # Initialize scenario manager
    SCENARIO_BASE_DIR = os.path.join(os.getcwd(), 'scenarios')
    scenario_manager = ScenarioManager(SCENARIO_BASE_DIR)
    
    print("=== DEBUG: Execution History Functionality ===")
    
    # List all scenarios
    scenarios = scenario_manager.list_scenarios()
    print(f"DEBUG: Total scenarios: {len(scenarios)}")
    
    for scenario in scenarios:
        print(f"DEBUG: Scenario {scenario.id}: {scenario.name}")
        print(f"DEBUG:   Database path: {scenario.database_path}")
        print(f"DEBUG:   Is base scenario: {scenario.is_base_scenario}")
        print(f"DEBUG:   Parent scenario ID: {scenario.parent_scenario_id}")
        
        # Get execution history for this scenario
        history = scenario_manager.get_execution_history(scenario.id)
        print(f"DEBUG:   Execution history entries: {len(history)}")
        
        for i, entry in enumerate(history):
            print(f"DEBUG:     Entry {i+1}:")
            print(f"DEBUG:       Command: {entry.command}")
            print(f"DEBUG:       Output files: {entry.output_files}")
            print(f"DEBUG:       Timestamp: {entry.timestamp}")
        
        print()
    
    # Check current scenario
    current_scenario = scenario_manager.get_current_scenario()
    print(f"DEBUG: Current scenario ID: {scenario_manager.state.current_scenario_id}")
    
    if current_scenario:
        print(f"DEBUG: Current scenario: {current_scenario.name} (ID: {current_scenario.id})")
        
        # Test switching to another scenario
        if len(scenarios) > 1:
            other_scenario = scenarios[1] if scenarios[0].id == current_scenario.id else scenarios[0]
            print(f"DEBUG: Testing switch to scenario: {other_scenario.name} (ID: {other_scenario.id})")
            
            # Switch scenario
            success = scenario_manager.switch_scenario(other_scenario.id)
            print(f"DEBUG: Switch successful: {success}")
            
            # Check new current scenario
            new_current = scenario_manager.get_current_scenario()
            print(f"DEBUG: New current scenario: {new_current.name if new_current else 'None'} (ID: {new_current.id if new_current else 'None'})")
            
            # Get execution history for new scenario
            new_history = scenario_manager.get_execution_history(new_current.id)
            print(f"DEBUG: New scenario execution history entries: {len(new_history)}")
            
            for i, entry in enumerate(new_history):
                print(f"DEBUG:     Entry {i+1}:")
                print(f"DEBUG:       Command: {entry.command}")
                print(f"DEBUG:       Output files: {entry.output_files}")
                print(f"DEBUG:       Timestamp: {entry.timestamp}")
    else:
        print("DEBUG: No current scenario found!")

if __name__ == "__main__":
    debug_execution_history() 