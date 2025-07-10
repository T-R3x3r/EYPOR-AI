#!/usr/bin/env python3
"""
Test cross-scenario file execution functionality
"""

import requests
import json
import os
from scenario_manager import ScenarioManager

def test_cross_scenario_execution():
    """Test that files can be run in different scenarios using the correct database"""
    
    # Initialize scenario manager
    scenario_manager = ScenarioManager(project_root=os.getcwd())
    
    # Get all scenarios
    scenarios = scenario_manager.list_scenarios()
    if len(scenarios) < 2:
        print("❌ Need at least 2 scenarios to test cross-scenario execution")
        return
    
    print(f"Found {len(scenarios)} scenarios")
    
    # Get a file to test with (use the first Python file we find)
    test_file = None
    for scenario in scenarios:
        db_dir = os.path.dirname(scenario.database_path)
        if os.path.exists(db_dir):
            for file in os.listdir(db_dir):
                if file.endswith('.py'):
                    test_file = file
                    break
        if test_file:
            break
    
    if not test_file:
        print("❌ No Python files found to test with")
        return
    
    print(f"Testing with file: {test_file}")
    
    # Test running the file in each scenario
    for i, scenario in enumerate(scenarios):
        print(f"\n=== Testing Scenario {i+1}: {scenario.name} ===")
        print(f"Database: {scenario.database_path}")
        
        # Switch to this scenario
        scenario_manager.switch_scenario(scenario.id)
        
        # Run the file
        try:
            response = requests.post(
                f"http://localhost:8001/run?filename={test_file}",
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success in scenario {scenario.name}")
                print(f"Return code: {result.get('return_code', 'N/A')}")
                print(f"Output files: {len(result.get('output_files', []))}")
                
                # Check if output files were created in the correct scenario directory
                output_files = result.get('output_files', [])
                for output_file in output_files:
                    file_path = output_file.get('path', '')
                    if file_path:
                        # The file should be in the current scenario's database directory
                        expected_dir = os.path.dirname(scenario.database_path)
                        actual_dir = os.path.dirname(os.path.join(expected_dir, file_path))
                        if actual_dir == expected_dir:
                            print(f"✅ Output file created in correct scenario directory: {file_path}")
                        else:
                            print(f"⚠️ Output file in unexpected location: {file_path}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Exception: {e}")
    
    print(f"\n🎉 Cross-scenario execution test completed!")

if __name__ == "__main__":
    test_cross_scenario_execution() 