"""Generate a PNG diagram of the Data-Analyst LangGraph workflow.
Run:  python visualize_workflow.py
The image is written to docs/images/data_analyst_workflow.png

Note: The diagram shows:
- Data Analyst Agent: All rectangular nodes except code_fixer
- Code Fixer Agent: The code_fixer node
- Control Flow: START/END nodes and dotted edges for conditional routing
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
from backend.langgraph_agent import create_agent  # type: ignore

def main() -> None:
    """Generate and save the workflow diagram using LangGraph's native rendering."""
    try:
        # Create agent and get graph
        agent = create_agent(ai_model="openai", temp_dir="", agent_type="data_analyst")
        graph = agent.graph.get_graph()
        
        # Save main workflow diagram
        graph_png = graph.draw_mermaid_png()
        with open(OUTPUT_FILE, 'wb') as f:
            f.write(graph_png)
            
        # Try to get and save subgraphs showing agent structure
        try:
            subgraphs = agent.graph.get_subgraphs()
            if subgraphs:
                subgraphs_png = subgraphs.draw_mermaid_png()
                with open(OUTPUT_SUBGRAPHS_FILE, 'wb') as f:
                    f.write(subgraphs_png)
                print(f"\n✅ Agent structure diagram saved to {OUTPUT_SUBGRAPHS_FILE.relative_to(Path.cwd())}")
        except Exception as e:
            print(f"\n⚠️ Could not generate agent structure diagram: {e}")
        
        relative_path = OUTPUT_FILE.relative_to(Path.cwd())
        print(f"\n✅ Workflow diagram saved to {relative_path}")
        print(f"   View the diagram at: file://{OUTPUT_FILE.absolute()}")
        
        print("\nDiagram Legend:")
        print("Workflow Diagram shows the task flow:")
        print("- Data Analyst Agent Tasks: analyze_request, execute_sql_query, prepare_db_modification,")
        print("                           execute_db_modification, execute_file, respond")
        print("- Code Fixer Agent Tasks: code_fixer node")
        print("- Control Flow: START/END nodes and dotted edges for conditional routing")
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 