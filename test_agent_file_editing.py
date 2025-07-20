#!/usr/bin/env python3
"""
Test script for agent file editing functionality
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from langgraph_agent_v2 import create_agent_v2
from scenario_manager import ScenarioManager

def test_agent_file_editing():
    """Test that the agent can handle file editing requests"""
    
    print("🧪 Testing Agent File Editing")
    print("=" * 50)
    
    # Create scenario manager
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root=project_root)
    
    # Create agent
    agent = create_agent_v2(ai_model="openai", scenario_manager=scenario_manager)
    
    # Create a test scenario
    scenario = scenario_manager.create_scenario("Test File Editing Scenario", "Test scenario for file editing")
    print(f"✅ Created test scenario: {scenario.name} (ID: {scenario.id})")
    
    # Create a test file in the scenario directory
    scenario_dir = os.path.dirname(scenario.database_path)
    test_file_path = os.path.join(scenario_dir, "test_agent_script.py")
    
    test_content = """
import pandas as pd
import sqlite3

def analyze_data():
    conn = sqlite3.connect('database.db')
    df = pd.read_sql_query("SELECT * FROM your_table LIMIT 10", conn)
    print("Data analysis complete")
    return df

if __name__ == "__main__":
    analyze_data()
"""
    
    with open(test_file_path, 'w') as f:
        f.write(test_content)
    
    print(f"✅ Created test file: {test_file_path}")
    
    # Test file editing request
    print("\n🔍 Testing file editing request...")
    
    try:
        # This should not raise the db_context error
        result = agent.run("edit test_agent_script.py to add error handling", scenario_id=scenario.id)
        print("✅ Agent file editing test completed successfully")
        print(f"Output: {result[0]}")
        print(f"Generated files: {result[1]}")
        print(f"Execution output: {result[2]}")
        print(f"Execution error: {result[3]}")
        
    except Exception as e:
        print(f"❌ Agent file editing test failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Cleanup
    print("\n🧹 Cleaning up...")
    try:
        if os.path.exists(test_file_path):
            os.remove(test_file_path)
        if os.path.exists(f"{test_file_path}.backup"):
            os.remove(f"{test_file_path}.backup")
        print("✅ Test files cleaned up")
    except Exception as e:
        print(f"❌ Error cleaning up: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Agent file editing test completed!")

if __name__ == "__main__":
    test_agent_file_editing() 