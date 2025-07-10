#!/usr/bin/env python3
"""
Test script to verify that the /run endpoint executes scenario files correctly.
"""

import os
import sys
import requests
import json
from scenario_manager import ScenarioManager

def test_run_endpoint():
    """Test that the /run endpoint executes scenario files in the correct directory"""
    
    # Setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    # Get current scenario
    scenarios = scenario_manager.list_scenarios()
    if not scenarios:
        print("No scenarios found")
        return
    
    # Switch to first scenario
    scenario_manager.switch_scenario(scenarios[0].id)
    current_scenario = scenario_manager.get_current_scenario()
    
    print(f"Testing with scenario: {current_scenario.name}")
    print(f"Database path: {current_scenario.database_path}")
    
    # Check if there are any Python files in the scenario directory
    scenario_dir = os.path.dirname(current_scenario.database_path)
    python_files = []
    
    if os.path.exists(scenario_dir):
        for file in os.listdir(scenario_dir):
            if file.endswith('.py'):
                python_files.append(file)
    
    if not python_files:
        print("No Python files found in scenario directory")
        return
    
    print(f"Found Python files: {python_files}")
    
    # Test running the first Python file
    test_file = python_files[0]
    print(f"\n=== Testing /run endpoint with {test_file} ===")
    
    try:
        # Make request to /run endpoint
        response = requests.post(
            "http://localhost:8001/run",
            params={"filename": test_file},
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Success!")
            print(f"Return code: {result.get('return_code')}")
            print(f"Output: {result.get('stdout', '')[:200]}...")
            print(f"Error: {result.get('stderr', '')[:200]}...")
            print(f"Output files: {result.get('output_files', [])}")
        else:
            print(f"❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_run_endpoint() 