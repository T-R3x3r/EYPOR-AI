"""
LangGraph Workflow Visualization
Generates and displays the complete Data Analyst Agent workflow
"""

import os
import sys
from typing import Dict, List, Tuple, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage
from typing_extensions import TypedDict

# Add the backend directory to path to import agent modules
sys.path.append('backend')

# Define the AgentState (simplified version for visualization)
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    request_type: str
    modification_request: Dict[str, any]
    available_models: List[str]
    selected_models: List[str]
    approval_required: bool
    pending_approval: Dict[str, any]

def create_data_analyst_workflow():
    """Create the Data Analyst workflow for visualization"""
    workflow = StateGraph(AgentState)
    
    # Core workflow nodes
    workflow.add_node("analyze_request", lambda state: state)
    workflow.add_node("execute_sql_query", lambda state: state)
    workflow.add_node("create_visualization", lambda state: state)
    workflow.add_node("prepare_db_modification", lambda state: state)
    workflow.add_node("request_approval", lambda state: state)
    workflow.add_node("process_approval", lambda state: state)
    workflow.add_node("execute_db_modification", lambda state: state)
    workflow.add_node("find_and_run_models", lambda state: state)
    workflow.add_node("request_model_selection", lambda state: state)
    workflow.add_node("execute_selected_models", lambda state: state)
    workflow.add_node("execute_file", lambda state: state)
    workflow.add_node("code_fixer", lambda state: state)
    workflow.add_node("respond", lambda state: state)
    
    # Start with request analysis
    workflow.add_edge(START, "analyze_request")
    
    # Route based on request type
    workflow.add_conditional_edges(
        "analyze_request",
        lambda state: "sql_query",  # Simplified for visualization
        {
            "sql_query": "execute_sql_query",
            "visualization": "create_visualization",
            "db_modification": "prepare_db_modification",
            "respond": "respond"
        }
    )
    
    # SQL query path
    workflow.add_edge("execute_sql_query", "respond")
    
    # Visualization path
    workflow.add_edge("create_visualization", "execute_file")
    
    # Database modification path
    workflow.add_edge("prepare_db_modification", "request_approval")
    workflow.add_edge("request_approval", END)  # Interrupt for human approval
    workflow.add_edge("process_approval", "execute_db_modification")
    workflow.add_edge("execute_db_modification", "find_and_run_models")
    
    # Model execution path
    workflow.add_conditional_edges(
        "find_and_run_models",
        lambda state: "run_all",  # Simplified for visualization
        {
            "run_all": "execute_selected_models",
            "select_models": "request_model_selection",
            "no_models": "respond"
        }
    )
    workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
    workflow.add_edge("execute_selected_models", "respond")
    
    # File execution and error handling
    workflow.add_conditional_edges(
        "execute_file",
        lambda state: "success",  # Simplified for visualization
        {
            "success": "respond",
            "retry": "code_fixer",
            "error": "respond"
        }
    )
    
    workflow.add_conditional_edges(
        "code_fixer",
        lambda state: "execute",  # Simplified for visualization
        {
            "execute": "execute_file",
            "major_fix": "create_visualization",
            "respond": "respond"
        }
    )
    
    workflow.add_edge("respond", END)
    
    return workflow

def create_database_modifier_workflow():
    """Create the Database Modifier workflow for visualization"""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("analyze_modification", lambda state: state)
    workflow.add_node("prepare_modification", lambda state: state)
    workflow.add_node("request_approval", lambda state: state)
    workflow.add_node("process_approval", lambda state: state)
    workflow.add_node("execute_modification", lambda state: state)
    workflow.add_node("find_models", lambda state: state)
    workflow.add_node("request_model_selection", lambda state: state)
    workflow.add_node("execute_models", lambda state: state)
    workflow.add_node("respond", lambda state: state)
    
    workflow.add_edge(START, "analyze_modification")
    workflow.add_edge("analyze_modification", "prepare_modification")
    workflow.add_edge("prepare_modification", "request_approval")
    workflow.add_edge("request_approval", END)  # Interrupt for approval
    workflow.add_edge("process_approval", "execute_modification")
    workflow.add_edge("execute_modification", "find_models")
    
    workflow.add_conditional_edges(
        "find_models",
        lambda state: "run_all",  # Simplified for visualization
        {
            "run_all": "execute_models",
            "select_models": "request_model_selection",
            "no_models": "respond"
        }
    )
    workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
    workflow.add_edge("execute_models", "respond")
    workflow.add_edge("respond", END)
    
    return workflow

def visualize_workflows():
    """Generate and display workflow visualizations"""
    
    print("🔄 **Data Analyst Agent Workflow Visualization**\n")
    
    # Create the workflows
    data_analyst_workflow = create_data_analyst_workflow()
    database_modifier_workflow = create_database_modifier_workflow()
    
    # Compile the workflows
    data_analyst_graph = data_analyst_workflow.compile()
    database_modifier_graph = database_modifier_workflow.compile()
    
    try:
        # Try to generate Mermaid diagrams
        print("## Data Analyst Agent Workflow (Mermaid)")
        data_analyst_mermaid = data_analyst_graph.get_graph().draw_mermaid()
        print("```mermaid")
        print(data_analyst_mermaid)
        print("```\n")
        
        print("## Database Modifier Agent Workflow (Mermaid)")
        database_modifier_mermaid = database_modifier_graph.get_graph().draw_mermaid()
        print("```mermaid")
        print(database_modifier_mermaid)
        print("```\n")
        
    except Exception as e:
        print(f"Mermaid generation failed: {e}")
    
    try:
        # Try to generate ASCII representation
        print("## Data Analyst Agent Workflow (ASCII)")
        data_analyst_ascii = data_analyst_graph.get_graph().draw_ascii()
        print(data_analyst_ascii)
        print("\n")
        
        print("## Database Modifier Agent Workflow (ASCII)")
        database_modifier_ascii = database_modifier_graph.get_graph().draw_ascii()
        print(database_modifier_ascii)
        print("\n")
        
    except Exception as e:
        print(f"ASCII generation failed: {e}")
    
    # Print workflow structure information
    print("## Workflow Structure Summary\n")
    
    # Data Analyst nodes
    da_nodes = list(data_analyst_graph.get_graph().nodes.keys())
    print(f"**Data Analyst Agent Nodes ({len(da_nodes)}):**")
    for i, node in enumerate(da_nodes, 1):
        print(f"{i:2d}. {node}")
    print()
    
    # Database Modifier nodes  
    dm_nodes = list(database_modifier_graph.get_graph().nodes.keys())
    print(f"**Database Modifier Agent Nodes ({len(dm_nodes)}):**")
    for i, node in enumerate(dm_nodes, 1):
        print(f"{i:2d}. {node}")
    print()
    
    # Key workflow paths
    print("## Key Workflow Paths\n")
    
    print("### 1. SQL Query Path:")
    print("START → analyze_request → execute_sql_query → respond → END\n")
    
    print("### 2. Visualization Path:")
    print("START → analyze_request → create_visualization → execute_file → respond → END\n")
    
    print("### 3. Database Modification Path:")
    print("START → analyze_request → prepare_db_modification → request_approval → END")
    print("(Human Approval) → process_approval → execute_db_modification → find_and_run_models → execute_selected_models → respond → END\n")
    
    print("### 4. Human-in-the-Loop Interrupts:")
    print("- **Database Modification Approval**: request_approval → END")
    print("- **Model Selection**: request_model_selection → END")
    print("- **Continuation**: User provides feedback → process_approval → Continue workflow\n")

def print_workflow_explanation():
    """Print detailed explanation of the workflow"""
    print("## Workflow Explanation\n")
    
    print("### 🎯 **Data Analyst Agent (Main Intelligence)**")
    print("The Data Analyst Agent serves as the primary decision-maker that:")
    print("- Analyzes user requests using database schema context")
    print("- Routes intelligently between SQL queries, visualizations, and database modifications")
    print("- Executes SQL queries directly for simple data requests")
    print("- Creates Python visualization scripts for complex visual requests")
    print("- Identifies and prepares database modification requests\n")
    
    print("### 🛠️ **Database Modifier Agent (Specialist)**")
    print("The Database Modifier Agent handles database changes with:")
    print("- Human-in-the-loop approval for all modifications")
    print("- Exact SQL UPDATE statement preview")
    print("- Transaction-safe database operations")
    print("- Automatic model discovery and execution after changes\n")
    
    print("### 🔄 **Workflow Interrupts (Human-in-the-Loop)**")
    print("The workflow includes strategic interrupts for:")
    print("- **Database Modification Approval**: User must approve before any database changes")
    print("- **Model Selection**: User chooses which Python models to run after modifications")
    print("- **State Preservation**: LangGraph memory maintains conversation context across interrupts\n")
    
    print("### ⚡ **Execution Paths**")
    print("**1. Simple Queries**: Direct SQL execution with formatted results")
    print("**2. Visualizations**: Python script creation and execution with error handling")
    print("**3. Database Changes**: Multi-step process with approval, modification, and model execution")
    print("**4. Error Recovery**: Automatic code fixing for failed visualizations\n")

if __name__ == "__main__":
    print("# LangGraph Workflow Visualization\n")
    visualize_workflows()
    print_workflow_explanation() 