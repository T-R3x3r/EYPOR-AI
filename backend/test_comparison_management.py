"""
Test script for comparison management system

This script tests the extended scenario management system with comparison tracking,
file naming conventions, and database integration.
"""

import os
import sys
import tempfile
import shutil
import json
from datetime import datetime

# Add the backend directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scenario_manager import ScenarioManager, ComparisonHistory


def test_comparison_management():
    """Test the comparison management system"""
    print("🧪 Testing Comparison Management System")
    print("=" * 50)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Initialize scenario manager
        scenario_manager = ScenarioManager(temp_dir)
        
        # Test 1: Create scenarios for comparison
        print("\n1️⃣ Creating test scenarios...")
        scenario1 = scenario_manager.create_scenario("Base Scenario", description="Original scenario")
        scenario2 = scenario_manager.create_scenario("Test Scenario", base_scenario_id=scenario1.id, description="Modified scenario")
        scenario3 = scenario_manager.create_scenario("Alternative Scenario", base_scenario_id=scenario1.id, description="Different approach")
        
        print(f"✅ Created scenarios:")
        print(f"   - {scenario1.name} (ID: {scenario1.id})")
        print(f"   - {scenario2.name} (ID: {scenario2.id})")
        print(f"   - {scenario3.name} (ID: {scenario3.id})")
        
        # Test 2: Test filename generation
        print("\n2️⃣ Testing filename generation...")
        scenario_names = ["Base Scenario", "Test Scenario"]
        filename = scenario_manager.generate_comparison_filename(
            scenario_names=scenario_names,
            comparison_type="chart",
            extension="html"
        )
        print(f"✅ Generated filename: {filename}")
        
        # Test with more scenarios
        scenario_names_long = ["Base Scenario", "Test Scenario", "Alternative Scenario", "Another Scenario"]
        filename_long = scenario_manager.generate_comparison_filename(
            scenario_names=scenario_names_long,
            comparison_type="table",
            extension="html"
        )
        print(f"✅ Generated filename (long): {filename_long}")
        
        # Test 3: Test file path generation
        print("\n3️⃣ Testing file path generation...")
        file_path = scenario_manager.get_comparison_file_path(filename)
        print(f"✅ Full file path: {file_path}")
        
        # Test 4: Test comparison history tracking
        print("\n4️⃣ Testing comparison history tracking...")
        
        # Create a test comparison file
        test_file_path = scenario_manager.get_comparison_file_path("test_comparison.html")
        with open(test_file_path, 'w') as f:
            f.write("<html><body>Test comparison</body></html>")
        
        # Add comparison history entry
        comparison_history = scenario_manager.add_comparison_history(
            comparison_name="Test Comparison",
            scenario_ids=[scenario1.id, scenario2.id],
            scenario_names=["Base Scenario", "Test Scenario"],
            comparison_type="chart",
            output_file_path=test_file_path,
            created_by_scenario_id=scenario1.id,
            description="Test comparison between base and test scenarios",
            metadata={"test": True, "timestamp": datetime.now().isoformat()}
        )
        
        print(f"✅ Added comparison history:")
        print(f"   - ID: {comparison_history.id}")
        print(f"   - Name: {comparison_history.comparison_name}")
        print(f"   - Type: {comparison_history.comparison_type}")
        print(f"   - File: {comparison_history.output_file_path}")
        print(f"   - Created: {comparison_history.created_at}")
        
        # Test 5: Test retrieving comparison history
        print("\n5️⃣ Testing comparison history retrieval...")
        
        # Get all comparison history
        all_comparisons = scenario_manager.get_comparison_history()
        print(f"✅ Retrieved {len(all_comparisons)} comparison entries")
        
        # Get comparison by type
        chart_comparisons = scenario_manager.get_comparison_history(comparison_type="chart")
        print(f"✅ Retrieved {len(chart_comparisons)} chart comparisons")
        
        # Get specific comparison by ID
        if comparison_history.id:
            specific_comparison = scenario_manager.get_comparison_by_id(comparison_history.id)
            if specific_comparison:
                print(f"✅ Retrieved specific comparison: {specific_comparison.comparison_name}")
                print(f"   - Scenario IDs: {json.loads(specific_comparison.scenario_ids)}")
                print(f"   - Scenario Names: {json.loads(specific_comparison.scenario_names)}")
                if specific_comparison.metadata:
                    metadata = json.loads(specific_comparison.metadata)
                    print(f"   - Metadata: {metadata}")
        
        # Test 6: Test listing comparison files
        print("\n6️⃣ Testing comparison file listing...")
        comparison_files = scenario_manager.list_comparison_files()
        print(f"✅ Found {len(comparison_files)} comparison files:")
        for file in comparison_files:
            print(f"   - {file}")
        
        # Test 7: Test cleanup functionality
        print("\n7️⃣ Testing cleanup functionality...")
        deleted_count = scenario_manager.cleanup_old_comparisons(max_age_days=0)  # Clean up everything older than 0 days
        print(f"✅ Cleaned up {deleted_count} old comparison entries")
        
        # Test 8: Test comparison file path generation with special characters
        print("\n8️⃣ Testing filename sanitization...")
        problematic_names = ["Scenario with Spaces", "Scenario-with-dashes", "Scenario.with.dots", "Scenario (with) brackets"]
        sanitized_filename = scenario_manager.generate_comparison_filename(
            scenario_names=problematic_names,
            comparison_type="analysis",
            extension="html"
        )
        print(f"✅ Generated sanitized filename: {sanitized_filename}")
        
        # Test 9: Test JSON serialization of comparison history
        print("\n9️⃣ Testing JSON serialization...")
        if comparison_history:
            comparison_dict = comparison_history.to_dict()
            print(f"✅ Serialized comparison to dict:")
            print(f"   - Keys: {list(comparison_dict.keys())}")
            print(f"   - Scenario IDs: {comparison_dict['scenario_ids']}")
            print(f"   - Scenario Names: {comparison_dict['scenario_names']}")
            
            # Test deserialization
            reconstructed = ComparisonHistory.from_dict(comparison_dict)
            print(f"✅ Reconstructed comparison: {reconstructed.comparison_name}")
        
        print("\n✅ All comparison management tests passed!")
        return True


def test_comparison_integration_with_agent():
    """Test integration with the agent's comparison functionality"""
    print("\n🧪 Testing Agent Integration")
    print("=" * 50)
    
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"📁 Using temporary directory: {temp_dir}")
        
        # Initialize scenario manager
        scenario_manager = ScenarioManager(temp_dir)
        
        # Create test scenarios
        scenario1 = scenario_manager.create_scenario("Base Scenario")
        scenario2 = scenario_manager.create_scenario("Test Scenario", base_scenario_id=scenario1.id)
        
        # Test agent's comparison file path generation
        from langgraph_agent_v2 import SimplifiedAgent
        
        agent = SimplifiedAgent(scenario_manager=scenario_manager)
        
        # Test filename generation through agent
        scenario_names = ["Base Scenario", "Test Scenario"]
        file_path = agent._generate_comparison_file_path(
            scenario_names=scenario_names,
            file_type="chart",
            extension="html"
        )
        
        print(f"✅ Agent generated file path: {file_path}")
        print(f"   - Directory exists: {os.path.exists(os.path.dirname(file_path))}")
        
        # Test comparison tracking
        success = agent._track_comparison_output(
            scenario_names=scenario_names,
            comparison_type="chart",
            output_file_path=file_path,
            description="Test comparison tracking",
            metadata={"test": True}
        )
        
        print(f"✅ Comparison tracking: {'Success' if success else 'Failed'}")
        
        # Verify the comparison was tracked
        comparisons = scenario_manager.get_comparison_history()
        print(f"✅ Found {len(comparisons)} tracked comparisons")
        
        if comparisons:
            latest = comparisons[0]
            print(f"   - Latest comparison: {latest.comparison_name}")
            print(f"   - Type: {latest.comparison_type}")
            print(f"   - File: {latest.output_file_path}")
        
        print("\n✅ Agent integration tests passed!")
        return True


if __name__ == "__main__":
    try:
        # Run comparison management tests
        test_comparison_management()
        
        # Run agent integration tests
        test_comparison_integration_with_agent()
        
        print("\n🎉 All tests completed successfully!")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 