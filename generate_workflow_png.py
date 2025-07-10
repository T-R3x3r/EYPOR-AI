#!/usr/bin/env python3
"""
Generate PNG workflow diagram from Mermaid code.
This script uses the Mermaid Live Editor API to convert the .mmd file to PNG.
"""

import requests
import json
import base64
from pathlib import Path

def generate_png_from_mermaid(mermaid_file: Path, output_png: Path):
    """Generate PNG from Mermaid code using the Mermaid Live Editor API"""
    
    # Read the Mermaid code
    with open(mermaid_file, 'r', encoding='utf-8') as f:
        mermaid_code = f.read()
    
    # Prepare the request for Mermaid Live Editor API
    # The API expects the Mermaid code to be base64 encoded
    mermaid_b64 = base64.b64encode(mermaid_code.encode('utf-8')).decode('utf-8')
    
    # Mermaid Live Editor API endpoint
    url = "https://mermaid.ink/img/"
    
    # Create the full URL with the encoded Mermaid code
    full_url = f"{url}{mermaid_b64}"
    
    print(f"Generating PNG from Mermaid code...")
    print(f"Input file: {mermaid_file}")
    print(f"Output file: {output_png}")
    
    try:
        # Download the PNG
        response = requests.get(full_url)
        response.raise_for_status()
        
        # Save the PNG
        with open(output_png, 'wb') as f:
            f.write(response.content)
        
        print(f"✅ PNG generated successfully: {output_png}")
        return True
        
    except Exception as e:
        print(f"❌ Error generating PNG: {e}")
        return False

def main():
    """Main function to generate the workflow PNG"""
    
    # File paths
    mermaid_file = Path("docs/images/simplified_agent_v2_workflow.mmd")
    output_png = Path("docs/images/data_analyst_workflow.png")
    
    # Ensure output directory exists
    output_png.parent.mkdir(parents=True, exist_ok=True)
    
    if not mermaid_file.exists():
        print(f"❌ Mermaid file not found: {mermaid_file}")
        return
    
    # Generate PNG
    success = generate_png_from_mermaid(mermaid_file, output_png)
    
    if success:
        print(f"\n✅ Workflow diagram saved to: {output_png}")
        print(f"   View the diagram at: file://{output_png.absolute()}")
        
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
    else:
        print("\n❌ Failed to generate PNG diagram")

if __name__ == "__main__":
    main() 