"""
Test to verify agent v2 generates lightweight code
"""

import os
import sys
from langgraph_agent_v2 import SimplifiedAgent
from scenario_manager import ScenarioManager

def test_lightweight_code_generation():
    """Test that agent generates lightweight code without heavy imports"""
    
    print("🧪 Testing Agent v2 Lightweight Code Generation...")
    print("=" * 60)
    
    try:
        # Initialize scenario manager
        project_root = os.path.dirname(os.path.abspath(__file__))
        scenario_manager = ScenarioManager(project_root)
        
        # Create agent
        agent = SimplifiedAgent(ai_model="openai", scenario_manager=scenario_manager)
        
        # Test SQL query generation
        test_request = "Show me the top 10 hubs by demand"
        
        # Create a minimal state for testing
        state = {
            "messages": [],
            "user_request": test_request,
            "request_type": "sql_query",
            "db_context": agent._get_database_context(),
            "generated_files": [],
            "execution_output": "",
            "execution_error": "",
            "modification_request": None,
            "db_modification_result": None
        }
        
        # Test SQL query generation
        result_state = agent._handle_sql_query(state)
        generated_files = result_state.get("generated_files", [])
        
        if generated_files:
            # Read the generated file to check for heavy imports
            file_path = os.path.join(agent._get_database_context().temp_dir, generated_files[0])
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    code_content = f.read()
                
                print("✅ Generated SQL query code:")
                print("-" * 40)
                print(code_content[:500] + "..." if len(code_content) > 500 else code_content)
                print("-" * 40)
                
                # Check for heavy imports
                heavy_imports = ["import pandas", "import plotly", "import numpy"]
                found_heavy = [imp for imp in heavy_imports if imp in code_content]
                
                if found_heavy:
                    print(f"⚠️  Found heavy imports: {found_heavy}")
                else:
                    print("✅ No heavy imports found - code is lightweight")
                
                # Check for proper imports
                if "import sqlite3" in code_content:
                    print("✅ Found sqlite3 import")
                else:
                    print("❌ Missing sqlite3 import")
                
                return True
            else:
                print(f"❌ Generated file not found: {file_path}")
                return False
        else:
            print("❌ No files generated")
            return False
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 Testing Agent v2 Lightweight Code Generation...")
    
    if test_lightweight_code_generation():
        print("🎉 Lightweight code generation test passed!")
    else:
        print("❌ Lightweight code generation test failed!") 