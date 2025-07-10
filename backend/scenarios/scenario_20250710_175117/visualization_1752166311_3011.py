# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def create_bar_chart_top_10_hubs_by_demand():
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('database.db')
        
        # Query data from the inputs_hubs table
        query = """
        SELECT HubID, Location, Initial_Active
        FROM inputs_hubs
        """
        df_hubs = pd.read_sql_query(query, conn)
        
        # Close the database connection
        conn.close()
        
        # Ensure the DataFrame is reset
        df_hubs.reset_index(drop=True, inplace=True)
        
        # Sort the hubs by demand (Initial_Active) in descending order and select the top 10
        df_top_10_hubs = df_hubs.sort_values(by='Initial_Active', ascending=False).head(10)
        
        # Convert DataFrame columns to lists for plotting
        hub_ids = df_top_10_hubs['HubID'].tolist()
        locations = df_top_10_hubs['Location'].tolist()
        demands = df_top_10_hubs['Initial_Active'].tolist()
        
        # Create a bar chart using Plotly
        fig = go.Figure(data=[
            go.Bar(
                x=locations,
                y=demands,
                text=hub_ids,
                hoverinfo='text+y',
                marker=dict(color='royalblue')
            )
        ])
        
        # Update layout for the chart
        fig.update_layout(
            title='Top 10 Hubs by Demand',
            xaxis_title='Location',
            yaxis_title='Demand',
            template='plotly_white',
            xaxis_tickangle=-45
        )
        
        # Generate a timestamp for the file name
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file_path = f'top_10_hubs_by_demand_{timestamp}.html'
        
        # Save the figure as an interactive HTML file
        fig.write_html(html_file_path)
        
        print(f"Interactive bar chart saved as {html_file_path}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

# Call the function to create the chart
create_bar_chart_top_10_hubs_by_demand()