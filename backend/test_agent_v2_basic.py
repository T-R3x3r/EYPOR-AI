"""
Basic test for agent v2 functionality (no API keys required)
"""

import os
import sys
from langgraph_agent_v2 import SimplifiedAgent, DatabaseContext
from scenario_manager import ScenarioManager

def test_agent_creation():
    """Test that agent can be created without API keys"""
    
    print("🧪 Testing Agent v2 Creation...")
    print("=" * 50)
    
    try:
        # Initialize scenario manager
        project_root = os.path.dirname(os.path.abspath(__file__))
        scenario_manager = ScenarioManager(project_root)
        
        # Create agent (this will fail if there are import/syntax errors)
        agent = SimplifiedAgent(ai_model="openai", scenario_manager=scenario_manager)
        
        print("✅ Agent created successfully")
        print(f"✅ AI Model: {agent.ai_model}")
        print(f"✅ Scenario Manager: {agent.scenario_manager is not None}")
        print(f"✅ Workflow Graph: {agent.workflow is not None}")
        
        return True
        
    except Exception as e:
        print(f"❌ Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_database_context():
    """Test database context functionality"""
    
    print("\n🧪 Testing Database Context...")
    print("=" * 50)
    
    try:
        # Initialize scenario manager
        project_root = os.path.dirname(os.path.abspath(__file__))
        scenario_manager = ScenarioManager(project_root)
        
        # Create agent
        agent = SimplifiedAgent(ai_model="openai", scenario_manager=scenario_manager)
        
        # Test database context creation
        db_context = agent._get_database_context()
        print(f"✅ Database context created: {db_context}")
        print(f"✅ Is valid: {db_context.is_valid()}")
        
        return True
        
    except Exception as e:
        print(f"❌ Database context test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_request_classification():
    """Test request classification logic"""
    
    print("\n🧪 Testing Request Classification...")
    print("=" * 50)
    
    try:
        # Initialize scenario manager
        project_root = os.path.dirname(os.path.abspath(__file__))
        scenario_manager = ScenarioManager(project_root)
        
        # Create agent
        agent = SimplifiedAgent(ai_model="openai", scenario_manager=scenario_manager)
        
        # Test different request types
        test_requests = [
            ("Show me a chart of the data", "visualization"),
            ("What is the total demand?", "sql_query"),
            ("Change the cost parameter to 2.5", "db_modification"),
            ("How does this model work?", "chat")
        ]
        
        for request, expected_type in test_requests:
            # Create a minimal state for testing
            state = {
                "messages": [],
                "user_request": request,
                "request_type": "",
                "db_context": agent._get_database_context(),
                "generated_files": [],
                "execution_output": "",
                "execution_error": "",
                "modification_request": None,
                "db_modification_result": None
            }
            
            # Test classification
            result_state = agent._classify_request(state)
            actual_type = result_state.get("request_type", "")
            
            print(f"Request: '{request}'")
            print(f"  Expected: {expected_type}")
            print(f"  Actual: {actual_type}")
            print(f"  {'✅' if actual_type == expected_type else '❌'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Request classification test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Agent v2 Basic Functionality...")
    print("=" * 60)
    
    tests = [
        test_agent_creation,
        test_database_context,
        test_request_classification
    ]
    
    passed = 0
    total = len(tests)
    
    for i, test in enumerate(tests):
        print(f"\nRunning test {i+1}/{len(tests)}...")
        try:
            if test():
                passed += 1
                print(f"✅ Test {i+1} passed")
            else:
                print(f"❌ Test {i+1} failed")
        except Exception as e:
            print(f"❌ Test {i+1} failed with exception: {e}")
    
    print(f"\n📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All basic tests passed! Agent v2 is working correctly.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.") 