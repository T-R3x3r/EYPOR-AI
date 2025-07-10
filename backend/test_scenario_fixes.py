#!/usr/bin/env python3
"""
Test script to verify scenario creation and database handling fixes
"""

import os
import shutil
import sqlite3
from scenario_manager import get_scenario_manager

def test_scenario_creation():
    """Test scenario creation with proper base/branch logic and database handling"""
    
    # Use a fixed test directory
    test_dir = "test_scenarios"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    print(f"Testing in directory: {test_dir}")
    
    try:
        # Initialize scenario manager
        scenario_manager = get_scenario_manager(test_dir)
        
        # Test 1: Create first scenario (should be base)
        print("\n=== Test 1: Creating first scenario (should be base) ===")
        scenario1 = scenario_manager.create_scenario(
            name="Test Scenario 1",
            description="First scenario test"
        )
        
        print(f"Scenario 1: {scenario1.name}")
        print(f"Is base: {scenario1.is_base_scenario}")
        print(f"Database path: {scenario1.database_path}")
        print(f"Database exists: {os.path.exists(scenario1.database_path)}")
        
        # Verify it's marked as base
        assert scenario1.is_base_scenario, "First scenario should be marked as base"
        assert os.path.exists(scenario1.database_path), "Database should exist"
        
        # Test 2: Create second scenario from scratch (should NOT be base)
        print("\n=== Test 2: Creating second scenario from scratch (should NOT be base) ===")
        scenario2 = scenario_manager.create_scenario(
            name="Test Scenario 2",
            description="Second scenario test"
        )
        
        print(f"Scenario 2: {scenario2.name}")
        print(f"Is base: {scenario2.is_base_scenario}")
        print(f"Database path: {scenario2.database_path}")
        print(f"Database exists: {os.path.exists(scenario2.database_path)}")
        
        # Verify it's NOT marked as base
        assert not scenario2.is_base_scenario, "Second scenario should NOT be marked as base"
        assert os.path.exists(scenario2.database_path), "Database should exist"
        
        # Test 3: Create third scenario by branching from first
        print("\n=== Test 3: Creating third scenario by branching from first ===")
        scenario3 = scenario_manager.create_scenario(
            name="Test Scenario 3",
            base_scenario_id=scenario1.id,
            description="Branched scenario test"
        )
        
        print(f"Scenario 3: {scenario3.name}")
        print(f"Is base: {scenario3.is_base_scenario}")
        print(f"Parent: {scenario3.parent_scenario_id}")
        print(f"Database path: {scenario3.database_path}")
        print(f"Database exists: {os.path.exists(scenario3.database_path)}")
        
        # Verify it's NOT marked as base and has parent
        assert not scenario3.is_base_scenario, "Branched scenario should NOT be marked as base"
        assert scenario3.parent_scenario_id == scenario1.id, "Should have correct parent"
        assert os.path.exists(scenario3.database_path), "Database should exist"
        
        # Test 4: List all scenarios
        print("\n=== Test 4: Listing all scenarios ===")
        scenarios = scenario_manager.list_scenarios()
        print(f"Total scenarios: {len(scenarios)}")
        
        base_count = sum(1 for s in scenarios if s.is_base_scenario)
        print(f"Base scenarios: {base_count}")
        
        assert base_count == 1, "Should have exactly one base scenario"
        assert len(scenarios) == 3, "Should have exactly 3 scenarios"
        
        # Test 5: Test scenario switching
        print("\n=== Test 5: Testing scenario switching ===")
        
        # Switch to scenario 2
        success = scenario_manager.switch_scenario(scenario2.id)
        assert success, "Should be able to switch to scenario 2"
        
        current = scenario_manager.get_current_scenario()
        assert current.id == scenario2.id, "Current scenario should be scenario 2"
        print(f"Current scenario: {current.name}")
        
        # Switch to scenario 3
        success = scenario_manager.switch_scenario(scenario3.id)
        assert success, "Should be able to switch to scenario 3"
        
        current = scenario_manager.get_current_scenario()
        assert current.id == scenario3.id, "Current scenario should be scenario 3"
        print(f"Current scenario: {current.name}")
        
        print("\n✅ All tests passed! Scenario creation and database handling is working correctly.")
        
    finally:
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

def test_database_creation():
    """Test that databases are created properly"""
    
    test_dir = "test_db_creation"
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    
    print(f"\n=== Testing database creation ===")
    
    try:
        scenario_manager = get_scenario_manager(test_dir)
        
        # Create a scenario
        scenario = scenario_manager.create_scenario(
            name="Database Test Scenario",
            description="Testing database creation"
        )
        
        # Check that database exists and has basic structure
        assert os.path.exists(scenario.database_path), "Database file should exist"
        
        # Try to connect to the database
        conn = sqlite3.connect(scenario.database_path)
        cursor = conn.cursor()
        
        # Check if scenario_info table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scenario_info'")
        tables = cursor.fetchall()
        
        assert len(tables) > 0, "scenario_info table should exist"
        
        # Check the content
        cursor.execute("SELECT * FROM scenario_info")
        rows = cursor.fetchall()
        assert len(rows) > 0, "scenario_info table should have data"
        
        conn.close()
        print("✅ Database creation test passed!")
        
    finally:
        # Clean up
        if os.path.exists(test_dir):
            shutil.rmtree(test_dir)

if __name__ == "__main__":
    print("Testing Scenario Creation and Database Handling Fixes")
    print("=" * 60)
    
    try:
        test_scenario_creation()
        test_database_creation()
        print("\n🎉 All tests passed! The scenario system is working correctly.")
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc() 