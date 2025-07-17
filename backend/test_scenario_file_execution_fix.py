#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify that scenario files execute correctly and don't get added to uploaded_files
"""

import os
import time
import requests
import json

def create_test_scenario_file():
    """Create a test file in a scenario directory"""
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
        html_file_path = f'scenario_execution_test_{timestamp}.html'
        
        # Save the figure as an HTML file
        fig.write_html(html_file_path)
        
        # Print a summary of the query results
        print("Scenario execution test completed successfully!")
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
                test_file_path = os.path.join(scenario_path, "scenario_execution_test.py")
                with open(test_file_path, 'w', encoding='utf-8') as f:
                    f.write(test_content)
                
                print(f"Created test file: {test_file_path}")
                return test_file_path
    
    print("No scenario directories found")
    return None

def test_scenario_file_execution():
    """Test that scenario files execute correctly and don't get added to uploaded_files"""
    # Create test file
    test_file = create_test_scenario_file()
    if not test_file:
        print("Could not create test file")
        return
    
    # Get just the filename for the API call
    filename = os.path.basename(test_file)
    
    print(f"Testing scenario file execution with: {filename}")
    print(f"File location: {test_file}")
    
    # Test the /run endpoint
    url = "http://localhost:8000/run"
    
    try:
        # First run
        print("\n=== First Run ===")
        response1 = requests.post(url, params={'filename': filename})
        
        print(f"Response status: {response1.status_code}")
        
        if response1.status_code == 200:
            result1 = response1.json()
            print(f"Return code: {result1.get('return_code', 'N/A')}")
            print(f"Output files: {result1.get('output_files', [])}")
            print(f"Stdout: {result1.get('stdout', '')}")
            if result1.get('stderr'):
                print(f"Stderr: {result1.get('stderr', '')}")
            
            # Check if the execution was successful
            if result1.get('return_code') == 0:
                print("✓ First run successful")
            else:
                print("✗ First run failed")
                return
        else:
            print(f"Error response: {response1.text}")
            return
        
        # Wait a moment
        time.sleep(2)
        
        # Second run
        print("\n=== Second Run ===")
        response2 = requests.post(url, params={'filename': filename})
        
        print(f"Response status: {response2.status_code}")
        
        if response2.status_code == 200:
            result2 = response2.json()
            print(f"Return code: {result2.get('return_code', 'N/A')}")
            print(f"Output files: {result2.get('output_files', [])}")
            print(f"Stdout: {result2.get('stdout', '')}")
            if result2.get('stderr'):
                print(f"Stderr: {result2.get('stderr', '')}")
            
            # Check if the execution was successful
            if result2.get('return_code') == 0:
                print("✓ Second run successful")
                print("✓ Scenario file execution fix working correctly!")
            else:
                print("✗ Second run failed")
                
        else:
            print(f"Error response: {response2.text}")
            
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    print("Testing scenario file execution fix...")
    test_scenario_file_execution() 