#!/usr/bin/env python3
"""
Test script to verify scenario switching behavior and file handling.
"""

import os
import sys
from scenario_manager import ScenarioManager

def test_scenario_switching():
    """Test scenario switching and file handling"""
    
    # Setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    print("=== Testing Scenario Switching ===")
    
    # Get scenarios
    scenarios = scenario_manager.list_scenarios()
    print(f"Found {len(scenarios)} scenarios")
    
    # Test switching between scenarios
    for i, scenario in enumerate(scenarios[:3]):  # Test first 3 scenarios
        print(f"\n--- Testing Scenario {i+1}: {scenario.name} ---")
        
        # Switch to scenario
        success = scenario_manager.switch_scenario(scenario.id)
        print(f"Switch success: {success}")
        
        # Get current scenario
        current = scenario_manager.get_current_scenario()
        print(f"Current scenario: {current.name if current else 'None'}")
        
        # Check if scenario directory exists
        scenario_dir = os.path.join(scenario_manager.scenarios_dir, f"scenario_{scenario.id}")
        print(f"Scenario directory exists: {os.path.exists(scenario_dir)}")
        
        if os.path.exists(scenario_dir):
            files = os.listdir(scenario_dir)
            print(f"Files in scenario directory: {files}")
    
    print("\n=== Test Complete ===")

if __name__ == "__main__":
    test_scenario_switching() 