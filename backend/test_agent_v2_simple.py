"""
Simple test script for the new simplified agent v2 (no API keys required)
"""

import os
import sys
from langgraph_agent_v2 import SimplifiedAgent, DatabaseContext
from scenario_manager import ScenarioManager

def test_agent_structure():
    """Test that the agent v2 structure is correct"""
    
    print("🧪 Testing Agent v2 Structure...")
    print("=" * 50)
    
    # Initialize scenario manager
    project_root = os.path.dirname(os.path.abspath(__file__))
    scenario_manager = ScenarioManager(project_root)
    
    print("✅ Scenario manager initialized")
    
    # Test DatabaseContext class
    try:
        db_context = DatabaseContext(
            scenario_id=1,
            database_path="/test/path/database.db",
            schema_info={"tables": []},
            temp_dir="/test/temp"
        )
        print("✅ DatabaseContext class works")
    except Exception as e:
        print(f"❌ DatabaseContext failed: {e}")
        return False
    
    # Test agent creation (without LLM)
    try:
        # Create agent without LLM for testing
        agent = SimplifiedAgent.__new__(SimplifiedAgent)
        agent.scenario_manager = scenario_manager
        agent.ai_model = "test"
        print("✅ Agent structure is valid")
    except Exception as e:
        print(f"❌ Agent creation failed: {e}")
        return False
    
    # Test workflow structure
    try:
        # Check if workflow methods exist
        required_methods = [
            '_classify_request',
            '_handle_sql_query', 
            '_handle_visualization',
            '_prepare_db_modification',
            '_execute_code',
            '_execute_db_modification'
        ]
        
        for method_name in required_methods:
            if hasattr(agent, method_name):
                print(f"✅ Method {method_name} exists")
            else:
                print(f"❌ Method {method_name} missing")
                return False
                
        print("✅ All required methods exist")
        
    except Exception as e:
        print(f"❌ Workflow structure test failed: {e}")
        return False
    
    print("\n🎉 Agent v2 structure test passed!")
    return True

def test_scenario_routing():
    """Test scenario database routing logic"""
    
    print("\n🧪 Testing Scenario Database Routing...")
    print("=" * 50)
    
    try:
        # Initialize scenario manager
        project_root = os.path.dirname(os.path.abspath(__file__))
        print("✅ Project root determined")
        scenario_manager = ScenarioManager(project_root)
        print("✅ Scenario manager created")
        
        # Test database path routing
        print("Creating test scenario...")
        scenario = scenario_manager.create_scenario(
            name="Test Scenario",
            description="Test scenario for routing"
        )
        
        print(f"✅ Created test scenario: {scenario.id}")
        print(f"✅ Database path: {scenario.database_path}")
        
        # Test that the path is scenario-specific
        if "scenario_" in scenario.database_path:
            print("✅ Database path is scenario-specific")
        else:
            print("❌ Database path is not scenario-specific")
            return False
            
        print("\n🎉 Scenario routing test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Scenario routing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_endpoint_integration():
    """Test that the new endpoints are properly integrated"""
    
    print("\n🧪 Testing Endpoint Integration...")
    print("=" * 50)
    
    # Check if main.py has the new endpoints
    try:
        with open('main.py', 'r', encoding='utf-8') as f:
            content = f.read()
            
        required_endpoints = [
            '/langgraph-chat-v2',
            '/action-chat-v2', 
            '/switch-agent-version',
            '/agent-version'
        ]
        
        for endpoint in required_endpoints:
            if endpoint in content:
                print(f"✅ Endpoint {endpoint} found in main.py")
            else:
                print(f"❌ Endpoint {endpoint} missing from main.py")
                return False
                
        print("✅ All new endpoints are integrated")
        
    except Exception as e:
        print(f"❌ Endpoint integration test failed: {e}")
        return False
    
    print("\n🎉 Endpoint integration test passed!")
    return True

if __name__ == "__main__":
    print("🧪 Testing new simplified agent v2 (Simple Version)...")
    print("=" * 60)
    
    tests = [
        test_agent_structure,
        test_scenario_routing,
        test_endpoint_integration
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
        print("🎉 All tests passed! Agent v2 is ready for use.")
    else:
        print("⚠️  Some tests failed. Please check the implementation.") 