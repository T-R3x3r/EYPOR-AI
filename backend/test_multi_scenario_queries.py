"""
Test script for multi-scenario comparison functionality

This script demonstrates and tests all aspects of the multi-scenario comparison system:
- Scenario detection and resolution
- Multi-database queries
- Comparison visualizations
- File management and tracking
"""

import os
import sys
import tempfile
import shutil
import sqlite3
import json
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario_manager import ScenarioManager
from langgraph_agent_v2 import SimplifiedAgent, DatabaseContext


def setup_test_scenarios(scenario_manager):
    """Create test scenarios with different data for comparison"""
    print("🔧 Setting up test scenarios...")
    
    # Create base scenario
    base_scenario = scenario_manager.create_scenario("Base Scenario", description="Original scenario with baseline data")
    
    # Create test scenario with modified data
    test_scenario = scenario_manager.create_scenario("Test Scenario", base_scenario_id=base_scenario.id, description="Modified scenario with higher demand")
    
    # Create alternative scenario
    alt_scenario = scenario_manager.create_scenario("Alternative Scenario", base_scenario_id=base_scenario.id, description="Different approach with lower costs")
    
    # Populate databases with different data
    populate_scenario_database(base_scenario.database_path, "base")
    populate_scenario_database(test_scenario.database_path, "test") 
    populate_scenario_database(alt_scenario.database_path, "alternative")
    
    print(f"✅ Created scenarios:")
    print(f"   - {base_scenario.name} (ID: {base_scenario.id})")
    print(f"   - {test_scenario.name} (ID: {test_scenario.id})")
    print(f"   - {alt_scenario.name} (ID: {alt_scenario.id})")
    
    return [base_scenario, test_scenario, alt_scenario]


def populate_scenario_database(db_path, scenario_type):
    """Populate a scenario database with test data"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create hubs table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hubs (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            demand INTEGER,
            capacity INTEGER,
            cost REAL
        )
    ''')
    
    # Create routes table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS routes (
            id INTEGER PRIMARY KEY,
            from_hub TEXT,
            to_hub TEXT,
            distance REAL,
            cost REAL
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM hubs')
    cursor.execute('DELETE FROM routes')
    
    # Insert scenario-specific data
    if scenario_type == "base":
        # Base scenario data
        hubs_data = [
            (1, "London", 5000, 8000, 100.0),
            (2, "Manchester", 3000, 6000, 80.0),
            (3, "Birmingham", 4000, 7000, 90.0),
            (4, "Liverpool", 2000, 5000, 70.0)
        ]
        routes_data = [
            (1, "London", "Manchester", 200.0, 50.0),
            (2, "London", "Birmingham", 150.0, 40.0),
            (3, "Manchester", "Liverpool", 50.0, 20.0)
        ]
    elif scenario_type == "test":
        # Test scenario with higher demand
        hubs_data = [
            (1, "London", 7000, 10000, 120.0),
            (2, "Manchester", 4500, 8000, 100.0),
            (3, "Birmingham", 5500, 9000, 110.0),
            (4, "Liverpool", 3000, 7000, 90.0)
        ]
        routes_data = [
            (1, "London", "Manchester", 200.0, 60.0),
            (2, "London", "Birmingham", 150.0, 50.0),
            (3, "Manchester", "Liverpool", 50.0, 25.0)
        ]
    else:  # alternative
        # Alternative scenario with lower costs
        hubs_data = [
            (1, "London", 4500, 7500, 80.0),
            (2, "Manchester", 2500, 5500, 60.0),
            (3, "Birmingham", 3500, 6500, 70.0),
            (4, "Liverpool", 1500, 4500, 50.0)
        ]
        routes_data = [
            (1, "London", "Manchester", 200.0, 40.0),
            (2, "London", "Birmingham", 150.0, 30.0),
            (3, "Manchester", "Liverpool", 50.0, 15.0)
        ]
    
    # Insert data
    cursor.executemany('INSERT INTO hubs (id, name, demand, capacity, cost) VALUES (?, ?, ?, ?, ?)', hubs_data)
    cursor.executemany('INSERT INTO routes (id, from_hub, to_hub, distance, cost) VALUES (?, ?, ?, ?, ?)', routes_data)
    
    conn.commit()
    conn.close()
    
    print(f"   - Populated {scenario_type} scenario with {len(hubs_data)} hubs and {len(routes_data)} routes")


def test_scenario_detection():
    """Test scenario name detection and resolution"""
    print("\n🧪 Testing Scenario Detection")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        scenario_manager = ScenarioManager(temp_dir)
        scenarios = setup_test_scenarios(scenario_manager)
        
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test different comparison request patterns
        test_requests = [
            "compare Base Scenario and Test Scenario",
            "Base Scenario vs Test Scenario",
            "show differences between Base Scenario and Test Scenario",
            "compare demand across Base Scenario, Test Scenario, Alternative Scenario",
            "Base Scenario versus Test Scenario",
            "compare Base and Test scenarios",
            "show me a comparison between Base Scenario and Alternative Scenario"
        ]
        
        for request in test_requests:
            print(f"\n📝 Testing request: '{request}'")
            
            # Test scenario extraction
            detected_scenarios = agent._extract_comparison_scenarios(request)
            print(f"   Detected scenarios: {detected_scenarios}")
            
            # Test scenario resolution
            if detected_scenarios:
                try:
                    resolved_paths = agent._resolve_scenario_names(detected_scenarios)
                    print(f"   Resolved paths: {list(resolved_paths.keys())}")
                except ValueError as e:
                    print(f"   Resolution error: {e}")
            else:
                print("   No scenarios detected")


def test_multi_database_queries():
    """Test multi-database query execution"""
    print("\n🧪 Testing Multi-Database Queries")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        scenario_manager = ScenarioManager(temp_dir)
        scenarios = setup_test_scenarios(scenario_manager)
        
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test different query types
        test_queries = [
            "SELECT name, demand, capacity FROM hubs ORDER BY demand DESC",
            "SELECT from_hub, to_hub, distance, cost FROM routes",
            "SELECT name, demand, (capacity - demand) as available_capacity FROM hubs WHERE demand > 3000"
        ]
        
        for query in test_queries:
            print(f"\n📊 Testing query: '{query}'")
            
            # Create multi-database context
            scenario_names = ["Base Scenario", "Test Scenario"]
            db_context = agent._create_comparison_database_context(scenario_names)
            
            if db_context.is_valid():
                print(f"   ✅ Multi-database context created")
                print(f"   Scenarios: {db_context.get_scenario_names()}")
                print(f"   Database paths: {db_context.get_all_database_paths()}")
                
                # Test query execution
                try:
                    result_df = agent._execute_multi_database_query(query, db_context.multi_database_contexts)
                    print(f"   ✅ Query executed successfully")
                    print(f"   Result shape: {result_df.shape}")
                    print(f"   Columns: {list(result_df.columns)}")
                    print(f"   Sample data:")
                    print(result_df.head().to_string())
                except Exception as e:
                    print(f"   ❌ Query execution failed: {e}")
            else:
                print(f"   ❌ Invalid database context")


def test_comparison_visualization():
    """Test comparison visualization generation"""
    print("\n🧪 Testing Comparison Visualization")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        scenario_manager = ScenarioManager(temp_dir)
        scenarios = setup_test_scenarios(scenario_manager)
        
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test different visualization requests
        test_requests = [
            "create a bar chart comparing demand across scenarios",
            "show me a side-by-side comparison of hub capacities",
            "generate a line chart showing cost differences",
            "create a grouped bar chart comparing all metrics",
            "show me a heatmap of route costs across scenarios"
        ]
        
        for request in test_requests:
            print(f"\n📈 Testing visualization request: '{request}'")
            
            # Create state with comparison context
            scenario_names = ["Base Scenario", "Test Scenario", "Alternative Scenario"]
            
            # Create individual database contexts for each scenario
            multi_contexts = {}
            for scenario_name in scenario_names:
                # Find the scenario
                scenario = None
                for s in scenarios:
                    if s.name == scenario_name:
                        scenario = s
                        break
                
                if scenario:
                    # Create individual context for this scenario
                    individual_context = DatabaseContext(
                        scenario_id=scenario.id,
                        database_path=scenario.database_path,
                        schema_info=agent._get_database_info(scenario.database_path),
                        temp_dir=os.path.dirname(scenario.database_path),
                        comparison_mode=False
                    )
                    multi_contexts[scenario_name] = individual_context
            
            # Create comparison database context
            db_context = DatabaseContext(
                scenario_id=None,
                database_path=None,
                schema_info=None,
                temp_dir=os.path.dirname(scenarios[0].database_path),
                multi_database_contexts=multi_contexts,
                comparison_mode=True,
                primary_scenario=scenario_names[0]
            )
            
            # Create proper state
            state = {
                "user_request": request,
                "db_context": db_context,
                "comparison_scenarios": scenario_names,
                "comparison_type": "chart",
                "comparison_data": {},
                "scenario_name_mapping": {name: i for i, name in enumerate(scenario_names)},
                "generated_files": [],
                "execution_output": "",
                "execution_error": "",
                "modification_request": None,
                "db_modification_result": None,
                "messages": []
            }
            
            try:
                # Test comparison visualization handling
                result_state = agent._handle_comparison_visualization(state)
                
                if "generated_files" in result_state and result_state["generated_files"]:
                    filename = result_state["generated_files"][0]
                    print(f"   ✅ Generated visualization script: {filename}")
                    
                    # Check if file was created
                    file_path = os.path.join(db_context.get_primary_context().temp_dir, filename)
                    if os.path.exists(file_path):
                        print(f"   ✅ File created: {file_path}")
                        
                        # Read and check file content
                        with open(file_path, 'r') as f:
                            content = f.read()
                            print(f"   ✅ File size: {len(content)} characters")
                            print(f"   ✅ Contains plotly import: {'plotly' in content}")
                            print(f"   ✅ Contains scenario names: {all(name in content for name in scenario_names)}")
                    else:
                        print(f"   ❌ File not created: {file_path}")
                else:
                    print(f"   ❌ No files generated")
                    
            except Exception as e:
                print(f"   ❌ Visualization generation failed: {e}")
                import traceback
                traceback.print_exc()


def test_file_management():
    """Test file management and tracking"""
    print("\n🧪 Testing File Management")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        scenario_manager = ScenarioManager(temp_dir)
        scenarios = setup_test_scenarios(scenario_manager)
        
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test filename generation
        scenario_names = ["Base Scenario", "Test Scenario", "Alternative Scenario"]
        
        print(f"\n📁 Testing filename generation...")
        filename = agent._generate_comparison_file_path(
            scenario_names=scenario_names,
            file_type="chart",
            extension="html"
        )
        print(f"   Generated path: {filename}")
        print(f"   Directory exists: {os.path.exists(os.path.dirname(filename))}")
        
        # Test comparison tracking
        print(f"\n📊 Testing comparison tracking...")
        success = agent._track_comparison_output(
            scenario_names=scenario_names,
            comparison_type="chart",
            output_file_path=filename,
            description="Test comparison tracking",
            metadata={"test": True, "scenarios": scenario_names}
        )
        print(f"   Tracking success: {success}")
        
        # Verify tracking in database
        comparisons = scenario_manager.get_comparison_history()
        print(f"   Total comparisons in database: {len(comparisons)}")
        
        if comparisons:
            latest = comparisons[0]
            print(f"   Latest comparison: {latest.comparison_name}")
            print(f"   Type: {latest.comparison_type}")
            print(f"   File: {latest.output_file_path}")
            
            # Parse JSON data
            scenario_ids = json.loads(latest.scenario_ids)
            scenario_names_db = json.loads(latest.scenario_names)
            print(f"   Scenario IDs: {scenario_ids}")
            print(f"   Scenario Names: {scenario_names_db}")
        
        # Test file listing
        print(f"\n📋 Testing file listing...")
        comparison_files = scenario_manager.list_comparison_files()
        print(f"   Found {len(comparison_files)} comparison files:")
        for file in comparison_files:
            print(f"     - {file}")


def test_end_to_end_comparison():
    """Test complete end-to-end comparison workflow"""
    print("\n🧪 Testing End-to-End Comparison")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        scenario_manager = ScenarioManager(temp_dir)
        scenarios = setup_test_scenarios(scenario_manager)
        
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test a complete comparison request
        test_request = "compare Base Scenario and Test Scenario - show me a bar chart of demand differences"
        
        print(f"📝 Testing complete request: '{test_request}'")
        
        try:
            # Run the agent
            response, generated_files, execution_output, execution_error = agent.run(test_request)
            
            print(f"   ✅ Agent response: {response[:200]}...")
            print(f"   ✅ Generated files: {generated_files}")
            print(f"   ✅ Execution output: {execution_output[:200] if execution_output else 'None'}...")
            print(f"   ✅ Execution error: {execution_error if execution_error else 'None'}")
            
            # Check if comparison was tracked
            comparisons = scenario_manager.get_comparison_history()
            print(f"   📊 Comparisons tracked: {len(comparisons)}")
            
            if comparisons:
                latest = comparisons[0]
                print(f"   📊 Latest comparison: {latest.comparison_name}")
                print(f"   📊 Type: {latest.comparison_type}")
                print(f"   📊 File: {latest.output_file_path}")
            
        except Exception as e:
            print(f"   ❌ End-to-end test failed: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    print("🚀 Multi-Scenario Comparison System Test")
    print("=" * 60)
    
    try:
        # Run all tests
        test_scenario_detection()
        test_multi_database_queries()
        test_comparison_visualization()
        test_file_management()
        test_end_to_end_comparison()
        
        print("\n🎉 All multi-scenario comparison tests completed!")
        print("\n📋 Summary of what should be working:")
        print("   ✅ Scenario name detection and resolution")
        print("   ✅ Multi-database query execution")
        print("   ✅ Comparison visualization generation")
        print("   ✅ File management and tracking")
        print("   ✅ End-to-end comparison workflow")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 