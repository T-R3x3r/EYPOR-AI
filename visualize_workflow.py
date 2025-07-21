"""Generate a PNG diagram of the Simplified LangGraph Agent v2 workflow.
Run:  python visualize_workflow.py
The image is written to docs/images/data_analyst_workflow.png

Note: The diagram shows:
- Simplified Agent v2: All nodes in the workflow including the new edit feature
- Request Classification: classify_request node routes to different handlers
- Specialized Handlers: handle_chat, handle_sql_query, handle_visualization, handle_file_edit, prepare_db_modification
- Scenario Extraction: extract_scenarios for multi-scenario comparisons
- Code Execution: execute_code for SQL, visualization, and file editing requests
- Database Modification: prepare_db_modification → execute_db_modification
- Control Flow: START/END nodes and conditional routing based on request type
"""

from pathlib import Path
import os
import sys

# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------
BACKEND_DIR = Path(__file__).parent / "backend"
OUTPUT_FILE = Path(__file__).parent / "docs" / "images" / "data_analyst_workflow.png"
OUTPUT_SUBGRAPHS_FILE = Path(__file__).parent / "docs" / "images" / "data_analyst_subgraphs.png"

# Ensure output directory exists
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

# Add backend to Python path
sys.path.append(str(BACKEND_DIR))

# Set dummy OpenAI key (no actual API calls made)
os.environ.setdefault("OPENAI_API_KEY", "dummy")

# Import after environment setup
from backend.langgraph_agent_v2 import create_agent_v2  # type: ignore

def _create_text_diagram(graph_obj, output_file):
    """Create a simple text representation of the workflow"""
    diagram_text = """Simplified Agent v2 Workflow Diagram (Updated with Edit Feature)
===============================================================

START
  |
classify_request (Request Classification)
  |
+-----------------+-----------------+-----------------+-----------------+-----------------+
|     chat        |   sql_query     | visualization   | file_edit       | db_modification |
|     Path        |     Path        |     Path        |     Path        |     Path        |
+-----------------+-----------------+-----------------+-----------------+-----------------+
  |                 |                 |                 |                 |
handle_chat    handle_sql_query  handle_visualization  handle_file_edit  prepare_db_modification
  |                 |                 |                 |                 |
respond         execute_code      execute_code          execute_code      execute_db_modification
  |                 |                 |                 |                 |
END              respond           respond              respond           respond
                 |                 |                    |                 |
                END               END                  END              END

Scenario Comparison Path:
START → classify_request → extract_scenarios → handle_scenario_comparison → execute_code → respond → END

Node Descriptions:
=================
* classify_request: Analyzes user input and routes to appropriate handler
* extract_scenarios: Extracts scenario names from comparison requests using regex patterns
* handle_chat: Processes general Q&A without code execution
* handle_sql_query: Generates SQL query scripts with Plotly table output
* handle_visualization: Creates chart/graph generation scripts (single scenario)
* handle_file_edit: Handles file editing requests with modification tracking
* handle_scenario_comparison: Generates multi-scenario comparison analysis
* prepare_db_modification: Prepares database parameter changes with validation
* execute_code: Executes generated Python scripts for SQL, visualization, and file editing
* execute_db_modification: Performs database modifications with percentage calculations
* respond: Generates final response to user with context and file information

Workflow Paths:
==============
1. Chat Path: START → classify_request → handle_chat → respond → END
2. SQL Path: START → classify_request → handle_sql_query → execute_code → respond → END
3. Visualization Path: START → classify_request → handle_visualization → execute_code → respond → END
4. File Edit Path: START → classify_request → handle_file_edit → execute_code → respond → END
5. Scenario Comparison Path: START → classify_request → extract_scenarios → handle_scenario_comparison → execute_code → respond → END
6. DB Modification Path: START → classify_request → prepare_db_modification → execute_db_modification → respond → END

New Edit Feature Details:
========================
* File Editing: Supports editing existing Python files with modification tracking
* Context Preservation: Maintains original file content and modification history
* Validation: Validates file modifications before execution
* Query Tracking: Maps queries to modified files for future reference
* Execution Integration: Modified files are executed through the standard execute_code node
* Database Context: Uses current scenario's database context for file operations
* Error Handling: Comprehensive error handling for file operations
* History Tracking: Maintains modification history with timestamps and query IDs

State Information Flow:
======================
* AgentState: Contains all workflow state including edit mode, file paths, and modification history
* DatabaseContext: Provides scenario-aware database routing and schema information
* Edit Mode Fields: edit_mode, editing_file_path, original_file_content, file_modification_history
* Query Tracking: query_file_mappings, current_query_context for linking queries to files
* Comparison Fields: comparison_scenarios, comparison_data, comparison_type for multi-scenario operations
"""
    
    # Save as text file
    text_file = output_file.with_suffix('.txt')
    with open(text_file, 'w', encoding='utf-8') as f:
        f.write(diagram_text)
    print(f"Saved text diagram to {text_file}")

def main() -> None:
    """Generate and save the workflow diagram using LangGraph's native rendering."""
    try:
        # Create agent and get graph
        agent = create_agent_v2(ai_model="openai")
        graph = agent.workflow
        
        # Try different methods to generate the workflow diagram
        try:
            # Method 1: Try get_graph() method
            if hasattr(graph, 'get_graph'):
                graph_obj = graph.get_graph()
                print("Using get_graph() method")
            else:
                graph_obj = graph
                print("Using graph object directly")
            
            # Method 2: Try to get Mermaid representation
            if hasattr(graph_obj, 'draw_mermaid_png'):
                graph_png = graph_obj.draw_mermaid_png()
                with open(OUTPUT_FILE, 'wb') as f:
                    f.write(graph_png)
                print("Generated PNG using draw_mermaid_png()")
            elif hasattr(graph_obj, 'get_mermaid'):
                mermaid_code = graph_obj.get_mermaid()
                print("Generated Mermaid code using get_mermaid()")
                # Save Mermaid code to file
                mermaid_file = OUTPUT_FILE.with_suffix('.mmd')
                with open(mermaid_file, 'w', encoding='utf-8') as f:
                    f.write(mermaid_code)
                print(f"Saved Mermaid code to {mermaid_file}")
            else:
                # Fallback: Create a simple text representation
                print("No diagram generation method found, creating text representation")
                _create_text_diagram(graph_obj, OUTPUT_FILE)
        except Exception as e:
            print(f"Error generating diagram: {e}")
            # Create a simple text representation as fallback
            _create_text_diagram(graph, OUTPUT_FILE)
            
        relative_path = OUTPUT_FILE.relative_to(Path.cwd())
        print(f"\n✅ Workflow diagram saved to {relative_path}")
        print(f"   View the diagram at: file://{OUTPUT_FILE.absolute()}")
        
        print("\nDiagram Legend:")
        print("Simplified Agent v2 Workflow (Updated with Edit Feature):")
        print("- Request Classification: classify_request (routes based on request type)")
        print("- Scenario Extraction: extract_scenarios (for multi-scenario comparisons)")
        print("- Specialized Handlers:")
        print("  • handle_chat: General Q&A without code execution")
        print("  • handle_sql_query: SQL query generation with Plotly tables")
        print("  • handle_visualization: Chart/graph generation (single scenario)")
        print("  • handle_file_edit: File editing with modification tracking")
        print("  • handle_scenario_comparison: Multi-scenario comparison analysis")
        print("  • prepare_db_modification: Database parameter changes")
        print("- Code Execution: execute_code (for SQL, visualization, and file editing)")
        print("- Database Modification: execute_db_modification (with percentage calculations)")
        print("- Response: respond (final response generation)")
        print("- Control Flow: START/END with conditional routing")
        print("\nNew Edit Feature:")
        print("- File Editing: Supports editing existing Python files")
        print("- Context Preservation: Maintains original content and modification history")
        print("- Validation: Validates modifications before execution")
        print("- Query Tracking: Maps queries to modified files")
        print("- Execution Integration: Modified files executed through standard pipeline")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 