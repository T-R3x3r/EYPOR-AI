# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def main():
    try:
        # Connect to the database
        conn = sqlite3.connect('database.db')
        
        # Define the SQL query to get the top 10 hubs by demand
        query = """
        SELECT h.HubID, h.Location, SUM(d.Demand) as TotalDemand
        FROM inputs_hubs h
        JOIN inputs_destinations d ON h.LocationID = d.LocationID
        GROUP BY h.HubID, h.Location
        ORDER BY TotalDemand DESC
        LIMIT 10;
        """
        
        # Execute the query and load the results into a DataFrame
        df = pd.read_sql_query(query, conn)
        
        # Close the database connection
        conn.close()
        
        # Reset DataFrame index
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
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_file_path = f"top_10_hubs_by_demand_{timestamp}.html"
        
        # Save the figure as an HTML file
        fig.write_html(html_file_path)
        
        # Print a summary of the query results
        print("Query executed successfully. Top 10 hubs by demand:")
        print(df)
        print(f"Interactive table saved as {html_file_path}")
        
    except sqlite3.Error as e:
        print(f"An error occurred while accessing the database: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()