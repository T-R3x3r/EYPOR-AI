#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test script to verify performance optimizations for file execution
"""

import time
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def create_test_file():
    """Create a simple test file that should execute quickly"""
    test_content = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def main():
    try:
        # Connect to the database
        conn = sqlite3.connect('database.db')
        
        # Simple query that should execute quickly
        query = """
        SELECT h.HubID, h.Location, SUM(d.Demand) as TotalDemand
        FROM inputs_hubs h
        JOIN inputs_destinations d ON h.LocationID = d.LocationID
        GROUP BY h.HubID, h.Location
        ORDER BY TotalDemand DESC
        LIMIT 5;
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
        html_file_path = f'performance_test_{timestamp}.html'
        
        # Save the figure as an HTML file
        fig.write_html(html_file_path)
        
        # Print a summary of the query results
        print("Performance test executed successfully!")
        print("Top 5 hubs by demand:")
        print(df)
        print(f"Interactive table saved as {html_file_path}")
        
    except sqlite3.Error as e:
        print(f"An error occurred while connecting to the database: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
'''
    
    with open('performance_test.py', 'w', encoding='utf-8') as f:
        f.write(test_content)
    
    print("Created performance_test.py")

def test_execution_time():
    """Test the execution time of the optimized backend"""
    import requests
    import json
    
    # Test the /run endpoint
    url = "http://localhost:8000/run"
    
    start_time = time.time()
    
    try:
        response = requests.post(url, params={'filename': 'performance_test.py'})
        end_time = time.time()
        
        execution_time = end_time - start_time
        
        print(f"Execution completed in {execution_time:.2f} seconds")
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"Return code: {result.get('return_code', 'N/A')}")
            print(f"Output files: {result.get('output_files', [])}")
            print(f"Stdout: {result.get('stdout', '')[:200]}...")
            if result.get('stderr'):
                print(f"Stderr: {result.get('stderr', '')}")
        else:
            print(f"Error response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("Request timed out - this indicates the optimization didn't work")
    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    print("Creating test file...")
    create_test_file()
    
    print("\\nTesting execution performance...")
    test_execution_time() 