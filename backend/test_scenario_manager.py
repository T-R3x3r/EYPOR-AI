#!/usr/bin/env python3
"""
Test script for ScenarioManager implementation
"""

import os
import tempfile
import shutil
from scenario_manager import ScenarioManager, Scenario, AnalysisFile, ExecutionHistory

def test_scenario_manager():
    """Test the scenario manager functionality"""
    
    # Create a temporary directory for testing
    test_dir = tempfile.mkdtemp(prefix="scenario_test_")
    print(f"Testing in directory: {test_dir}")
    
    try:
        # Initialize scenario manager
        manager = ScenarioManager(test_dir)
        print("✓ ScenarioManager initialized successfully")
        
        # Test creating scenarios
        print("\n--- Testing Scenario Creation ---")
        
        # Create base scenario
        base_scenario = manager.create_scenario("Base Scenario", description="Original scenario")
        print(f"✓ Created base scenario: {base_scenario.name} (ID: {base_scenario.id})")
        
        # Create scenario branching from base
        branch_scenario = manager.create_scenario("Branch Scenario", base_scenario_id=base_scenario.id, description="Branch from base")
        print(f"✓ Created branch scenario: {branch_scenario.name} (ID: {branch_scenario.id})")
        
        # Create scenario from scratch
        scratch_scenario = manager.create_scenario("Scratch Scenario", description="Created from scratch")
        print(f"✓ Created scratch scenario: {scratch_scenario.name} (ID: {scratch_scenario.id})")
        
        # Test listing scenarios
        print("\n--- Testing Scenario Listing ---")
        scenarios = manager.list_scenarios()
        print(f"✓ Found {len(scenarios)} scenarios:")
        for scenario in scenarios:
            print(f"  - {scenario.name} (ID: {scenario.id}, Base: {scenario.is_base_scenario})")
        
        # Test scenario switching
        print("\n--- Testing Scenario Switching ---")
        current = manager.get_current_scenario()
        print(f"✓ Current scenario: {current.name if current else 'None'}")
        
        # Switch to branch scenario
        success = manager.switch_scenario(branch_scenario.id)
        print(f"✓ Switched to branch scenario: {success}")
        
        current = manager.get_current_scenario()
        print(f"✓ Current scenario: {current.name if current else 'None'}")
        
        # Test execution history
        print("\n--- Testing Execution History ---")
        
        # Add some execution history
        manager.add_execution_history(
            base_scenario.id, 
            "python test.py", 
            "Test output", 
            None, 
            1500
        )
        
        manager.add_execution_history(
            base_scenario.id, 
            "python model.py", 
            "Model output", 
            "Error occurred", 
            3000
        )
        
        # Get execution history
        history = manager.get_execution_history(base_scenario.id)
        print(f"✓ Found {len(history)} execution history entries for base scenario")
        for entry in history:
            print(f"  - {entry.command} ({entry.timestamp})")
        
        # Test analysis files
        print("\n--- Testing Analysis Files ---")
        
        # Add analysis files
        sql_file = manager.add_analysis_file(
            "test_query.sql",
            "sql_query",
            "SELECT * FROM test_table WHERE value > 10",
            base_scenario.id,
            True
        )
        print(f"✓ Created analysis file: {sql_file.filename}")
        
        viz_file = manager.add_analysis_file(
            "chart_template.py",
            "visualization_template",
            "import plotly.express as px\nfig = px.bar(data, x='x', y='y')",
            None,
            True
        )
        print(f"✓ Created global analysis file: {viz_file.filename}")
        
        # Get analysis files
        files = manager.get_analysis_files()
        print(f"✓ Found {len(files)} analysis files (global)")
        
        scenario_files = manager.get_analysis_files(base_scenario.id)
        print(f"✓ Found {len(scenario_files)} analysis files (scenario-specific)")
        
        # Test scenario updates
        print("\n--- Testing Scenario Updates ---")
        success = manager.update_scenario(base_scenario.id, name="Updated Base Scenario", description="Updated description")
        print(f"✓ Updated scenario: {success}")
        
        updated_scenario = manager.get_scenario(base_scenario.id)
        print(f"✓ Updated name: {updated_scenario.name}")
        print(f"✓ Updated description: {updated_scenario.description}")
        
        # Test database copying
        print("\n--- Testing Database Copying ---")
        # Create a new scenario to copy to
        copy_target = manager.create_scenario("Copy Target", description="Target for copying")
        success = manager.copy_database(base_scenario.id, copy_target.id)
        print(f"✓ Copied database: {success}")
        
        # Test scenario deletion
        print("\n--- Testing Scenario Deletion ---")
        # Create a scenario to delete
        delete_scenario = manager.create_scenario("Delete Me", description="Will be deleted")
        print(f"✓ Created scenario to delete: {delete_scenario.name}")
        
        success = manager.delete_scenario(delete_scenario.id)
        print(f"✓ Deleted scenario: {success}")
        
        # Verify deletion
        scenarios_after = manager.list_scenarios()
        print(f"✓ Scenarios after deletion: {len(scenarios_after)}")
        
        print("\n--- All Tests Passed! ---")
        
    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Clean up test directory
        shutil.rmtree(test_dir)
        print(f"\nCleaned up test directory: {test_dir}")

if __name__ == "__main__":
    test_scenario_manager() 