#!/usr/bin/env python3
"""
Test script to verify database access in agent v2.
"""

import os
import sys
from langgraph_agent_v2 import create_agent_v2
from scenario_manager import ScenarioManager

def test_database_access():
    """Test that agent v2 can access the database correctly"""
    
    # Setup
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    # Get current scenario
    current_scenario = scenario_manager.get_current_scenario()
    if not current_scenario:
        print("No current scenario found")
        return
    
    print(f"Testing with scenario: {current_scenario.name}")
    print(f"Database path: {current_scenario.database_path}")
    
    # Create agent
    agent = create_agent_v2(scenario_manager=scenario_manager)
    
    # Test a simple SQL query
    test_query = "Show me the first 5 rows from any table"
    
    print(f"\n=== Testing SQL Query ===")
    print(f"Query: {test_query}")
    
    try:
        response, generated_files, execution_output, execution_error = agent.run(
            user_message=test_query,
            scenario_id=current_scenario.id
        )
        
        print(f"\nResponse: {response}")
        print(f"Generated files: {generated_files}")
        print(f"Execution output: {execution_output}")
        print(f"Execution error: {execution_error}")
        
        if execution_error:
            print(f"❌ Error: {execution_error}")
        elif generated_files:
            print(f"✅ Success! Generated files: {generated_files}")
        else:
            print("⚠️ No files generated")
            
    except Exception as e:
        print(f"❌ Agent error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database_access() 