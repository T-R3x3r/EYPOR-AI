#!/usr/bin/env python3
"""
Test script to verify that the improved scenario extraction works correctly
for complex requests like "compare the demand for birmingham in base and test1".
"""

import os
import sys
import tempfile
import shutil

# Add the current directory to the path so we can import the agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_agent_v2 import SimplifiedAgent
from scenario_manager import ScenarioManager

def test_improved_scenario_extraction():
    """Test the improved scenario extraction with complex requests"""
    print("🧪 Testing Improved Scenario Extraction")
    print("=" * 50)
    
    # Create a temporary project directory
    temp_dir = tempfile.mkdtemp()
    project_root = temp_dir
    
    try:
        # Create scenario manager
        scenario_manager = ScenarioManager(project_root)
        
        # Create test scenarios
        print("📁 Creating test scenarios...")
        
        # Create Base Scenario
        base_scenario = scenario_manager.create_scenario("Base Scenario", "Base scenario for testing")
        print(f"✅ Created Base Scenario with ID: {base_scenario.id}")
        
        # Create test1 scenario
        test1_scenario = scenario_manager.create_scenario("test1", "Test scenario 1")
        print(f"✅ Created test1 scenario with ID: {test1_scenario.id}")
        
        # Create agent
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test cases
        test_cases = [
            {
                "request": "compare the demand for birmingham in base and test1",
                "expected_scenarios": ["Base Scenario", "test1"],
                "description": "Complex request with extra context"
            },
            {
                "request": "compare base and test1",
                "expected_scenarios": ["Base Scenario", "test1"],
                "description": "Simple compare request"
            },
            {
                "request": "compare the top 10 hubs by demand across base and test1",
                "expected_scenarios": ["Base Scenario", "test1"],
                "description": "Complex request with additional context"
            },
            {
                "request": "base vs test1",
                "expected_scenarios": ["Base Scenario", "test1"],
                "description": "Simple vs comparison"
            },
            {
                "request": "compare demand between base scenario and test1",
                "expected_scenarios": ["Base Scenario", "test1"],
                "description": "Between comparison"
            }
        ]
        
        print("\n🔍 Testing scenario extraction...")
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n{i}. Testing: {test_case['description']}")
            print(f"   Request: '{test_case['request']}'")
            print(f"   Expected: {test_case['expected_scenarios']}")
            
            # Test the extraction by running the agent workflow
            try:
                # Initialize state
                initial_state = {
                    "messages": [],
                    "user_request": test_case['request'],
                    "request_type": "",
                    "db_context": agent._get_database_context(),
                    "generated_files": [],
                    "execution_output": "",
                    "execution_error": "",
                    "modification_request": None,
                    "db_modification_result": None,
                    "comparison_scenarios": [],
                    "comparison_data": {},
                    "comparison_type": "",
                    "scenario_name_mapping": {}
                }
                
                # Run classification
                classified_state = agent._classify_request(initial_state)
                print(f"   Classification result: {classified_state.get('request_type', 'unknown')}")
                
                if classified_state.get('request_type') == 'scenario_comparison':
                    # Run scenario extraction
                    extracted_state = agent._extract_scenarios(classified_state)
                    extracted_scenarios = extracted_state.get('comparison_scenarios', [])
                    
                    print(f"   Extracted scenarios: {extracted_scenarios}")
                    
                    # Check if extraction was successful
                    if len(extracted_scenarios) >= 2:
                        # Check if all expected scenarios are present
                        missing_scenarios = [s for s in test_case['expected_scenarios'] if s not in extracted_scenarios]
                        if not missing_scenarios:
                            print(f"   ✅ SUCCESS: All expected scenarios found")
                        else:
                            print(f"   ❌ FAILED: Missing scenarios: {missing_scenarios}")
                    else:
                        print(f"   ❌ FAILED: Not enough scenarios extracted ({len(extracted_scenarios)})")
                else:
                    print(f"   ❌ FAILED: Request not classified as scenario_comparison")
                    
            except Exception as e:
                print(f"   ❌ ERROR: {e}")
        
        print("\n" + "=" * 50)
        print("✅ Test completed!")
        
    finally:
        # Clean up
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        print("🧹 Cleaned up temporary files")

if __name__ == "__main__":
    test_improved_scenario_extraction() 