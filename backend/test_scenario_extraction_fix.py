#!/usr/bin/env python3
"""
Test script to verify that the scenario extraction fix works correctly
for various comparison requests.
"""

import sys
import os

# Add the current directory to the path so we can import the agent
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from langgraph_agent_v2 import SimplifiedAgent
from scenario_manager import ScenarioManager

def test_scenario_extraction():
    """Test scenario extraction with various comparison requests"""
    print("🧪 Testing Scenario Extraction Fix")
    print("=" * 50)
    
    # Create scenario manager
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scenario_manager = ScenarioManager(project_root)
    
    # Create agent
    agent = SimplifiedAgent(scenario_manager=scenario_manager)
    
    # Test cases
    test_cases = [
        {
            "request": "compare Base and Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Simple compare with 'and'"
        },
        {
            "request": "compare the top 10 hubs by demand across Base and Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Complex request with additional context"
        },
        {
            "request": "Base vs Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Simple vs comparison"
        },
        {
            "request": "compare Base Scenario and Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Full scenario names"
        },
        {
            "request": "compare Base Scenario, Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Comma separated"
        },
        {
            "request": "between Base Scenario and Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Between keyword"
        },
        {
            "request": "across Base Scenario, Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Across keyword"
        },
        {
            "request": "show me the differences between Base Scenario and Scenario1",
            "expected_scenarios": ["Base Scenario", "Scenario1"],
            "description": "Complex request with 'differences'"
        }
    ]
    
    print(f"📋 Testing {len(test_cases)} comparison requests...")
    print()
    
    passed = 0
    failed = 0
    
    for i, test_case in enumerate(test_cases, 1):
        request = test_case["request"]
        expected = test_case["expected_scenarios"]
        description = test_case["description"]
        
        print(f"📝 Test {i}: {description}")
        print(f"   Request: '{request}'")
        print(f"   Expected: {expected}")
        
        # Extract scenarios
        extracted_scenarios = agent._extract_comparison_scenarios(request)
        print(f"   Extracted: {extracted_scenarios}")
        
        # Check if we got the expected scenarios
        if set(extracted_scenarios) == set(expected):
            print("   ✅ PASS")
            passed += 1
        else:
            print("   ❌ FAIL")
            failed += 1
        
        print()
    
    print("📊 Results:")
    print(f"   ✅ Passed: {passed}")
    print(f"   ❌ Failed: {failed}")
    print(f"   📈 Success Rate: {passed/(passed+failed)*100:.1f}%")
    
    if failed == 0:
        print("\n🎉 All tests passed! Scenario extraction is working correctly.")
    else:
        print(f"\n⚠️ {failed} test(s) failed. Scenario extraction needs improvement.")
    
    return failed == 0

if __name__ == "__main__":
    success = test_scenario_extraction()
    sys.exit(0 if success else 1) 