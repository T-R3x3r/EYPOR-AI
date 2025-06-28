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
    model_selection_required: bool
    pending_model_selection: Dict[str, any]
    interrupt_reason: str

def create_data_analyst_workflow():
    """Create the Data Analyst Agent workflow for visualization"""
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("analyze_request", lambda state: state)
    workflow.add_node("execute_sql_query", lambda state: state)
    workflow.add_node("create_visualization", lambda state: state)
    workflow.add_node("prepare_db_modification", lambda state: state)
    workflow.add_node("execute_db_modification", lambda state: state)
    workflow.add_node("find_and_run_models", lambda state: state)
    workflow.add_node("request_model_selection", lambda state: state)
    workflow.add_node("execute_selected_models", lambda state: state)
    workflow.add_node("execute_file", lambda state: state)
    workflow.add_node("code_fixer", lambda state: state)
    workflow.add_node("respond", lambda state: state)
    
    # Add edges
    workflow.add_edge(START, "analyze_request")
    
    # Routing edges
    workflow.add_edge("analyze_request", "execute_sql_query")
    workflow.add_edge("analyze_request", "create_visualization")
    workflow.add_edge("analyze_request", "prepare_db_modification")
    
    # SQL query path
    workflow.add_edge("execute_sql_query", "execute_file")
    
    # Visualization path
    workflow.add_edge("create_visualization", "execute_file")
    
    # Database modification path - direct execution with model selection
    workflow.add_edge("prepare_db_modification", "execute_db_modification")
    workflow.add_edge("execute_db_modification", "find_and_run_models")
    workflow.add_edge("find_and_run_models", "request_model_selection")
    workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
    workflow.add_edge("execute_selected_models", "respond")
    
    # File execution and error handling
    workflow.add_edge("execute_file", "respond")
    workflow.add_edge("code_fixer", "execute_file")
    workflow.add_edge("respond", END)
    
    return workflow

def create_database_modifier_workflow():
    """Create the Database Modifier Agent workflow for visualization"""
    workflow = StateGraph(AgentState)
    
    # Add nodes
    workflow.add_node("analyze_modification", lambda state: state)
    workflow.add_node("prepare_modification", lambda state: state)
    workflow.add_node("execute_modification", lambda state: state)
    workflow.add_node("find_models", lambda state: state)
    workflow.add_node("request_model_selection", lambda state: state)
    workflow.add_node("execute_models", lambda state: state)
    workflow.add_node("respond", lambda state: state)
    
    # Add edges
    workflow.add_edge(START, "analyze_modification")
    workflow.add_edge("analyze_modification", "prepare_modification")
    workflow.add_edge("prepare_modification", "execute_modification")
    workflow.add_edge("execute_modification", "find_models")
    workflow.add_edge("find_models", "request_model_selection")
    workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
    workflow.add_edge("execute_models", "respond")
    workflow.add_edge("respond", END)
    
    return workflow

def visualize_workflows():
    """Print the workflow structure"""
    print("# LangGraph Workflow Visualization\n")
    
    # Data Analyst workflow
    data_analyst_graph = create_data_analyst_workflow()
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
    print("START → analyze_request → execute_sql_query → execute_file → respond → END\n")
    
    print("### 2. Visualization Path:")
    print("START → analyze_request → create_visualization → execute_file → respond → END\n")
    
    print("### 3. Database Modification Path:")
    print("START → analyze_request → prepare_db_modification → execute_db_modification → find_and_run_models → request_model_selection → END")
    print("(Model Selection) → execute_selected_models → respond → END\n")
    
    print("### 4. Model Selection Interrupts:")
    print("- **Model Selection**: request_model_selection → END")
    print("- **Continuation**: User provides model selection → execute_selected_models → Continue workflow\n")

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
    print("- Direct database modifications without approval")
    print("- Exact SQL UPDATE statement execution")
    print("- Transaction-safe database operations")
    print("- Automatic model discovery and execution after changes\n")
    
    print("### 🔄 **Workflow Interrupts (Model Selection)**")
    print("The workflow includes strategic interrupts for:")
    print("- **Model Selection**: User chooses which Python models to run after modifications")
    print("- **State Preservation**: LangGraph memory maintains conversation context across interrupts\n")
    
    print("### ⚡ **Execution Paths**")
    print("**1. Simple Queries**: Direct SQL execution with formatted results")
    print("**2. Visualizations**: Python script creation and execution with error handling")
    print("**3. Database Changes**: Multi-step process with modification and model execution")
    print("**4. Error Recovery**: Automatic code fixing for failed visualizations\n")

if __name__ == "__main__":
    print("=" * 80)
    print("LANGGRAPH WORKFLOW VISUALIZATION")
    print("=" * 80)
    print()
    
    # Create workflow graphs
    data_analyst_graph = create_data_analyst_workflow()
    database_modifier_graph = create_database_modifier_workflow()
    
    # Visualize workflows
    visualize_workflows()
    
    # Print detailed explanation
    print_workflow_explanation()
    
    print("=" * 80)
    print("END OF WORKFLOW VISUALIZATION")
    print("=" * 80) 