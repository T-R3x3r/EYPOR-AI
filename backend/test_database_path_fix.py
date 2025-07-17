#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify the database path fix works correctly
"""

import os
import time
import requests
import json

def create_test_file_with_database_reference():
    """Create a test file that references database.db"""
    test_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime
import os

def main():
    try:
        # Print current working directory
        print(f"Current working directory: {os.getcwd()}")
        
        # Connect to the database using relative path
        print("Attempting to connect to database.db...")
        conn = sqlite3.connect('database.db')
        print("Successfully connected to database.db")
        
        # Simple query that should execute quickly
        query = """
        SELECT h.HubID, h.Location, SUM(d.Demand) as TotalDemand
        FROM inputs_hubs h
        JOIN inputs_destinations d ON h.LocationID = d.LocationID
        GROUP BY h.HubID, h.Location
        ORDER BY TotalDemand DESC
        LIMIT 3;
        """
        
        # Execute the query and load the results into a DataFrame
        df = pd.read_sql_query(query, conn)
        
        # Close the database connection
        conn.close()
        
        # Reset the DataFrame index
        df.reset_index(drop=True, inplace=True)
        
        # Convert DataFrame columns to lists for Plotly
        hub_ids = df['HubID'].tolist()
        locations = df['Location'].tolist()
        total_demand = df['TotalDemand'].tolist()
        
        # Create a Plotly table
        fig = go.Figure(data=[go.Table(
            header=dict(values=['HubID', 'Location', 'Total Demand'],
                        fill_color='paleturquoise',
                        align='left'),
            cells=dict(values=[hub_ids, locations, total_demand],
                       fill_color='lavender',
                       align='left'))
        ])
        
        # Generate a dynamic filename with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file_path = f'database_path_test_{timestamp}.html'
        
        # Save the figure as an HTML file
        fig.write_html(html_file_path)
        
        # Print a summary of the query results
        print("Database path test completed successfully!")
        print("Top 3 hubs by demand:")
        print(df)
        print(f"Interactive table saved as {html_file_path}")
        print(f"File saved in: {os.path.abspath(html_file_path)}")
        
    except sqlite3.Error as e:
        print(f"An error occurred while connecting to the database: {e}")
        print(f"Current working directory: {os.getcwd()}")
        print(f"Files in current directory: {os.listdir('.')}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
'''
    
    # Find a scenario directory
    scenarios_dir = "scenarios"
    if not os.path.exists(scenarios_dir):
        print("No scenarios directory found")
        return None
    
    # Find the first scenario directory
    for item in os.listdir(scenarios_dir):
        if item.startswith("scenario_"):
            scenario_path = os.path.join(scenarios_dir, item)
            if os.path.isdir(scenario_path):
                # Create test file in this scenario
                test_file_path = os.path.join(scenario_path, "database_path_test.py")
                with open(test_file_path, 'w', encoding='utf-8') as f:
                    f.write(test_content)
                
                print(f"Created test file: {test_file_path}")
                return test_file_path
    
    print("No scenario directories found")
    return None

def test_database_path_fix():
    """Test that database path injection works correctly"""
    # Create test file
    test_file = create_test_file_with_database_reference()
    if not test_file:
        print("Could not create test file")
        return
    
    # Get just the filename for the API call
    filename = os.path.basename(test_file)
    
    print(f"Testing database path fix with: {filename}")
    print(f"File location: {test_file}")
    
    # Test the /run endpoint
    url = "http://localhost:8000/run"
    
    try:
        response = requests.post(url, params={'filename': filename})
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Return code: {result.get('return_code', 'N/A')}")
            print(f"Output files: {result.get('output_files', [])}")
            print(f"Stdout: {result.get('stdout', '')}")
            if result.get('stderr'):
                print(f"Stderr: {result.get('stderr', '')}")
            
            # Check if the execution was successful
            if result.get('return_code') == 0:
                print("✓ Database path fix successful - file executed without SQL errors")
            else:
                print("✗ Database path fix failed - SQL errors occurred")
                
        else:
            print(f"Error response: {response.text}")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    print("Testing database path fix...")
    test_database_path_fix() 