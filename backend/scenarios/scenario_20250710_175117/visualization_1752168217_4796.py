# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def create_pie_chart_for_top_demand_hubs():
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('database.db')
        
        # Query to get total demand per hub
        query = """
        SELECT h.HubID, h.Location, SUM(d.Demand) as TotalDemand
        FROM inputs_hubs h
        JOIN inputs_destinations d ON h.LocationID = d.LocationID
        GROUP BY h.HubID, h.Location
        """
        
        # Load data into a DataFrame
        df = pd.read_sql_query(query, conn)
        
        # Close the database connection
        conn.close()
        
        # Sort the DataFrame by TotalDemand in descending order
        df = df.sort_values(by='TotalDemand', ascending=False).reset_index(drop=True)
        
        # Calculate cumulative demand and find the top 50% hubs
        df['CumulativeDemand'] = df['TotalDemand'].cumsum()
        total_demand = df['TotalDemand'].sum()
        df['CumulativePercentage'] = df['CumulativeDemand'] / total_demand
        
        # Filter hubs that make up the top 50% of total demand
        top_50_percent_hubs = df[df['CumulativePercentage'] <= 0.5]
        
        # Prepare data for the pie chart
        labels = top_50_percent_hubs['Location'].tolist()
        values = top_50_percent_hubs['TotalDemand'].tolist()
        
        # Create a pie chart
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hoverinfo='label+percent', textinfo='value')])
        
        # Update layout for the pie chart
        fig.update_layout(
            title='Hubs Contributing to Top 50% of Total Demand',
            margin=dict(l=20, r=20, t=40, b=20),
            showlegend=True
        )
        
        # Generate a dynamic file name with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file_path = f"top_50_percent_hubs_pie_chart_{timestamp}.html"
        
        # Save the figure as an HTML file
        fig.write_html(html_file_path)
        
        print(f"Interactive pie chart saved as {html_file_path}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

# Run the function to create the pie chart
create_pie_chart_for_top_demand_hubs()