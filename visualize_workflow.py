"""
LangGraph Workflow Visualization
Generates and displays the complete Data Analyst Agent workflow
"""

import os
import sys
from pathlib import Path
import graphviz

# Ensure backend package is on path
BACKEND_DIR = Path(__file__).parent / "backend"
sys.path.append(str(BACKEND_DIR))

from backend.langgraph_agent import create_agent  # type: ignore

OUTPUT_DIR = Path(__file__).parent / "docs" / "images"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def export_agent_graph(agent_type: str, filename: str) -> None:
    """Create a PNG diagram of the compiled LangGraph for the given agent."""
    agent = create_agent(ai_model="openai", temp_dir="", agent_type=agent_type)
    nx_graph = agent.graph.get_graph()  # networkx.DiGraph

    dot = graphviz.Digraph(name=agent_type, format="png")
    dot.attr(rankdir="LR", splines="line", nodesep="0.5", ranksep="0.75")

    # Add nodes
    for node in nx_graph.nodes:
        dot.node(node, shape="box", style="rounded,filled", fillcolor="#FFFFEE")

    # Add edges
    for src, dst in nx_graph.edges:
        dot.edge(src, dst)

    output_path = OUTPUT_DIR / filename
    dot.render(str(output_path), cleanup=True)
    print(f"✅ Generated {output_path.with_suffix('.png').relative_to(Path.cwd())}")


def main():
    export_agent_graph("data_analyst", "data_analyst_workflow")
    # Uncomment if you wish to visualise the specialist agent as well
    # export_agent_graph("database_modifier", "database_modifier_workflow")


if __name__ == "__main__":
    main() 