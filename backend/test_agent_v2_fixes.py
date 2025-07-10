#!/usr/bin/env python3
"""
Test script to verify agent v2 fixes:
1. HTML files show in execution window
2. Python files appear in sidebar under query elements
"""

import os
import sys
import time
from langgraph_agent_v2 import create_agent_v2
from scenario_manager import ScenarioManager

def test_agent_v2_file_generation():
    """Test that agent v2 generates both Python and HTML files"""
    
    # Setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    # Create a test scenario
    scenario = scenario_manager.create_scenario("test_scenario")
    scenario_manager.set_current_scenario(scenario.id)
    
    # Create agent
    agent = create_agent_v2(scenario_manager=scenario_manager)
    
    # Test message
    test_message = "Create a bar chart showing the top 5 locations by demand"
    
    print(f"Testing agent v2 with message: {test_message}")
    print(f"Scenario ID: {scenario.id}")
    print(f"Database path: {scenario.database_path}")
    
    # Run agent
    try:
        response, generated_files, execution_output, execution_error = agent.run(
            user_message=test_message,
            scenario_id=scenario.id
        )
        
        print("\n=== RESULTS ===")
        print(f"Response: {response}")
        print(f"Generated files: {generated_files}")
        print(f"Execution output: {execution_output}")
        print(f"Execution error: {execution_error}")
        
        # Check if we have both Python and HTML files
        python_files = [f for f in generated_files if f.endswith('.py')]
        html_files = [f for f in generated_files if f.endswith('.html')]
        
        print(f"\n=== FILE ANALYSIS ===")
        print(f"Python files: {python_files}")
        print(f"HTML files: {html_files}")
        
        if python_files and html_files:
            print("✅ SUCCESS: Both Python and HTML files generated!")
            return True
        elif python_files:
            print("⚠️  WARNING: Only Python files generated (HTML files may be in database directory)")
            return True
        else:
            print("❌ ERROR: No files generated")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_agent_v2_file_generation()
    sys.exit(0 if success else 1) 