#!/usr/bin/env python3
"""
Test script to verify that comparison files can be executed properly
from the run endpoint without database path injection errors.
"""

import os
import sys
import tempfile
import requests
import time

def test_comparison_file_execution():
    """Test that comparison files can be executed without path injection errors"""
    print("🧪 Testing Comparison File Execution Fix")
    print("=" * 50)
    
    # Create a test comparison file
    test_comparison_content = '''# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Define the database paths (these should NOT be replaced by the run endpoint)
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_214112_306/database.db"
test_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_214512_849/database.db"

# This is a comparison file - it should NOT have database paths injected
print("Testing comparison file execution...")
print(f"Base scenario database: {base_scenario_db}")
print(f"Test scenario database: {test_scenario_db}")

# Create a simple visualization
fig = go.Figure()
fig.add_trace(go.Bar(x=['Base Scenario', 'Test Scenario'], y=[100, 150], name='Comparison'))
fig.update_layout(title='Test Comparison Chart')

# Save the chart
timestamp = int(time.time())
html_file = f"test_comparison_chart_{timestamp}.html"
fig.write_html(html_file)
print(f"Chart saved as {html_file}")
'''

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the test file
        test_file = os.path.join(temp_dir, "comparison_analysis_Base_Scenario_vs_Test_20250710_214555.py")
        with open(test_file, 'w', encoding='utf-8') as f:
            f.write(test_comparison_content)
        
        print(f"📝 Created test comparison file: {test_file}")
        print(f"📄 File content preview:")
        print(test_comparison_content[:200] + "...")
        
        # Test the run endpoint
        try:
            print(f"\n🚀 Testing run endpoint...")
            response = requests.post(
                "http://localhost:8001/run",
                params={"filename": "comparison_analysis_Base_Scenario_vs_Test_20250710_214555.py"},
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Success!")
                print(f"Return code: {result.get('return_code')}")
                print(f"Output: {result.get('stdout', '')[:200]}...")
                print(f"Error: {result.get('stderr', '')[:200]}...")
                print(f"Output files: {result.get('output_files', [])}")
                
                # Check if the database paths were preserved (not injected)
                stdout = result.get('stdout', '')
                if 'base_scenario_db' in stdout and 'test_scenario_db' in stdout:
                    print(f"✅ Database paths preserved correctly")
                else:
                    print(f"⚠️ Database paths may have been modified")
                    
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    test_comparison_file_execution() 