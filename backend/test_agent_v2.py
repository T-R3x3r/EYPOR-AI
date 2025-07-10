"""
Test script for the new simplified agent v2 with proper scenario database routing
"""

import os
import sys
from langgraph_agent_v2 import SimplifiedAgent, DatabaseContext
from scenario_manager import ScenarioManager

def test_database_routing():
    """Test that the agent properly uses scenario-specific databases"""
    
    # Initialize scenario manager
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root)
    
    # Create agent
    agent = SimplifiedAgent(ai_model="openai", scenario_manager=scenario_manager)
    
    # Get current scenario (should be the base scenario)
    current_scenario = scenario_manager.get_current_scenario()
    if not current_scenario:
        print("❌ No current scenario found")
        return
    
    print(f"✅ Current scenario: {current_scenario.name} (ID: {current_scenario.id})")
    print(f"✅ Database path: {current_scenario.database_path}")
    
    # Test database context creation
    db_context = agent._get_database_context()
    print(f"✅ Database context valid: {db_context.is_valid()}")
    print(f"✅ Context database path: {db_context.database_path}")
    print(f"✅ Context scenario ID: {db_context.scenario_id}")
    
    # Test different request types
    test_requests = [
        ("What is this model about?", "chat"),
        ("Show me all the hubs", "sql_query"), 
        ("Create a chart of demand by location", "visualization"),
        ("Change the maximum hub demand to 5000", "db_modification")
    ]
    
    for request, expected_type in test_requests:
        print(f"\n🧪 Testing request: '{request}'")
        
        # Test classification
        state = {
            "messages": [],
            "user_request": request,
            "request_type": "",
            "db_context": db_context,
            "generated_files": [],
            "execution_output": "",
            "execution_error": "",
            "modification_request": None,
            "db_modification_result": None
        }
        
        # Run classification
        classified_state = agent._classify_request(state)
        actual_type = classified_state.get("request_type", "")
        
        if actual_type == expected_type:
            print(f"✅ Classification correct: {actual_type}")
        else:
            print(f"❌ Classification incorrect: expected {expected_type}, got {actual_type}")
        
        # Test routing
        route = agent._route_request(classified_state)
        print(f"✅ Route: {route}")

def test_schema_context():
    """Test schema context building"""
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root)
    agent = SimplifiedAgent(scenario_manager=scenario_manager)
    
    # Get database context
    db_context = agent._get_database_context()
    
    if db_context.schema_info:
        schema_context = agent._build_schema_context(db_context.schema_info)
        print(f"✅ Schema context generated ({len(schema_context)} chars)")
        print("📋 Schema preview:")
        print(schema_context[:500] + "..." if len(schema_context) > 500 else schema_context)
    else:
        print("❌ No schema info available")

def test_chat_request():
    """Test simple chat request"""
    
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root)
    agent = SimplifiedAgent(scenario_manager=scenario_manager)
    
    response, files = agent.run("What is hub location optimization?")
    print(f"✅ Chat response: {response[:200]}...")
    print(f"✅ Generated files: {files}")

if __name__ == "__main__":
    print("🧪 Testing new simplified agent v2...")
    
    try:
        print("\n" + "="*50)
        print("Testing database routing...")
        test_database_routing()
        
        print("\n" + "="*50)
        print("Testing schema context...")
        test_schema_context()
        
        print("\n" + "="*50)
        print("Testing chat request...")
        test_chat_request()
        
        print("\n✅ All tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc() 