#!/usr/bin/env python3
"""
Test script to verify scenario file behavior and identify issues.
"""

import os
import sys
from scenario_manager import ScenarioManager

def test_scenario_file_behavior():
    """Test how files are handled across scenarios"""
    
    # Setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    print("=== Testing Scenario File Behavior ===")
    
    # Get current scenarios
    scenarios = scenario_manager.list_scenarios()
    print(f"Found {len(scenarios)} scenarios:")
    
    for scenario in scenarios:
        print(f"  - {scenario.name} (ID: {scenario.id}, Base: {scenario.is_base_scenario})")
        print(f"    Database: {scenario.database_path}")
        print(f"    Created: {scenario.created_at}")
        print()
    
    # Test file listing for each scenario
    for scenario in scenarios:
        print(f"=== Testing files for scenario: {scenario.name} ===")
        
        # Switch to scenario
        scenario_manager.switch_scenario(scenario.id)
        current = scenario_manager.get_current_scenario()
        print(f"Current scenario: {current.name if current else 'None'}")
        
        # List files in scenario directory
        scenario_dir = os.path.join(scenario_manager.scenarios_dir, f"scenario_{scenario.id}")
        if os.path.exists(scenario_dir):
            files = os.listdir(scenario_dir)
            print(f"Files in scenario directory: {files}")
        else:
            print("Scenario directory does not exist")
        
        print()

if __name__ == "__main__":
    test_scenario_file_behavior() 