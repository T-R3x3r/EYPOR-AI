"""Generate a PNG diagram of the Simplified LangGraph Agent v2 workflow.
Run:  python visualize_workflow.py
The image is written to docs/images/data_analyst_workflow.png

Note: The diagram shows:
- Simplified Agent v2: All nodes in the workflow
- Request Classification: classify_request node routes to different handlers
- Specialized Handlers: handle_chat, handle_sql_query, handle_visualization, prepare_db_modification
- Code Execution: execute_code for SQL and visualization requests
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
    diagram_text = """Simplified Agent v2 Workflow Diagram
===============================================

START
  |
classify_request (Request Classification)
  |
+-----------------+-----------------+-----------------+-----------------+
|     chat        |   sql_query     | visualization   | db_modification |
|     Path        |     Path        |     Path        |     Path        |
+-----------------+-----------------+-----------------+-----------------+
  |                 |                 |                 |
handle_chat    handle_sql_query  handle_visualization  prepare_db_modification
  |                 |                 |                 |
respond         execute_code      execute_code          execute_db_modification
  |                 |                 |                 |
END              respond           respond              respond
                 |                 |                    |
                END               END                  END

Node Descriptions:
=================
* classify_request: Analyzes user input and routes to appropriate handler
* handle_chat: Processes general Q&A without code execution
* handle_sql_query: Generates SQL query scripts
* handle_visualization: Creates chart/graph generation scripts
* prepare_db_modification: Prepares database parameter changes
* execute_code: Executes generated Python scripts
* execute_db_modification: Performs database modifications
* respond: Generates final response to user

Workflow Paths:
==============
1. Chat Path: START -> classify_request -> handle_chat -> respond -> END
2. SQL Path: START -> classify_request -> handle_sql_query -> execute_code -> respond -> END
3. Visualization Path: START -> classify_request -> handle_visualization -> execute_code -> respond -> END
4. DB Modification Path: START -> classify_request -> prepare_db_modification -> execute_db_modification -> respond -> END
"""
    
    # Save as text file
    text_file = output_file.with_suffix('.txt')
    with open(text_file, 'w') as f:
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
                with open(mermaid_file, 'w') as f:
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
        print("Simplified Agent v2 Workflow:")
        print("- Request Classification: classify_request (routes based on request type)")
        print("- Specialized Handlers:")
        print("  • handle_chat: General Q&A without code execution")
        print("  • handle_sql_query: SQL query generation")
        print("  • handle_visualization: Chart/graph generation")
        print("  • prepare_db_modification: Database parameter changes")
        print("- Code Execution: execute_code (for SQL and visualization)")
        print("- Database Modification: execute_db_modification")
        print("- Response: respond (final response generation)")
        print("- Control Flow: START/END with conditional routing")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 