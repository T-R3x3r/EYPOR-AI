"""
Test script to verify that comparison actually accesses different scenario databases
"""

import os
import sqlite3
from scenario_manager import ScenarioManager
from langgraph_agent_v2 import SimplifiedAgent

def modify_scenario_data():
    """Modify data in Scenario1 to test comparison"""
    print("🔧 Modifying Scenario1 data...")
    
    # Initialize scenario manager
    project_root = os.path.dirname(os.path.dirname(__file__))
    scenario_manager = ScenarioManager(project_root)
    
    # Get Scenario1
    scenarios = scenario_manager.list_scenarios()
    scenario1 = None
    for scenario in scenarios:
        if scenario.name == "Scenario1":
            scenario1 = scenario
            break
    
    if not scenario1:
        print("❌ Scenario1 not found")
        return
    
    print(f"📁 Found Scenario1 at: {scenario1.database_path}")
    
    # Modify Birmingham demand in Scenario1
    conn = sqlite3.connect(scenario1.database_path)
    cursor = conn.cursor()
    
    # Update Birmingham demand to a very different value
    cursor.execute("""
        UPDATE inputs_destinations 
        SET Demand = 15000 
        WHERE Location = 'Birmingham'
    """)
    
    # Verify the change
    cursor.execute("SELECT Demand FROM inputs_destinations WHERE Location = 'Birmingham'")
    result = cursor.fetchone()
    print(f"✅ Updated Birmingham demand in Scenario1 to: {result[0]}")
    
    conn.commit()
    conn.close()

def test_comparison():
    """Test the comparison functionality"""
    print("\n🧪 Testing comparison functionality...")
    
    # Initialize agent
    project_root = os.path.dirname(os.path.dirname(__file__))
    scenario_manager = ScenarioManager(project_root)
    agent = SimplifiedAgent(scenario_manager=scenario_manager)
    
    # Run comparison
    response, files, output, error = agent.run('compare the demand for birmingham in Base and Scenario1')
    
    print(f"\n📊 Response: {response}")
    print(f"📁 Files: {files}")
    print(f"📤 Output: {output}")
    print(f"❌ Error: {error}")
    
    return response, files, output, error

if __name__ == "__main__":
    # First modify the data
    modify_scenario_data()
    
    # Then test comparison
    test_comparison() 