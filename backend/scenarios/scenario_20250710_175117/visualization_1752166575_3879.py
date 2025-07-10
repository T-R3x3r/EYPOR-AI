# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def create_pie_chart():
    try:
        # Connect to the SQLite database
        conn = sqlite3.connect('database.db')
        
        # Query to get total demand per hub
        query = """
        SELECT HubID, SUM(Demand) as TotalDemand
        FROM inputs_destinations
        GROUP BY HubID
        """
        
        # Read the data into a pandas DataFrame
        df = pd.read_sql_query(query, conn)
        
        # Close the database connection
        conn.close()
        
        # Sort the DataFrame by TotalDemand in descending order
        df = df.sort_values(by='TotalDemand', ascending=False).reset_index(drop=True)
        
        # Calculate cumulative demand percentage
        df['CumulativeDemand'] = df['TotalDemand'].cumsum()
        total_demand = df['TotalDemand'].sum()
        df['CumulativePercentage'] = df['CumulativeDemand'] / total_demand
        
        # Filter the DataFrame to include only the top 50% of total demand
        df_top_50 = df[df['CumulativePercentage'] <= 0.5]
        
        # Extract data for plotting
        labels = df_top_50['HubID'].tolist()
        values = df_top_50['TotalDemand'].tolist()
        
        # Create a pie chart with a red color scheme
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=0.3,
                                     marker=dict(colors=['#FF9999', '#FF6666', '#FF3333', '#FF0000', '#CC0000']),
                                     hoverinfo='label+percent')])
        
        # Update layout for the pie chart
        fig.update_layout(
            title='Top 50% Hubs by Total Demand',
            annotations=[dict(text='Top 50%', x=0.5, y=0.5, font_size=20, showarrow=False)],
            showlegend=True
        )
        
        # Generate a dynamic file name with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        html_file_path = f'pie_chart_top_50_percent_{timestamp}.html'
        
        # Save the figure as an interactive HTML file
        fig.write_html(html_file_path)
        
        print(f"Interactive pie chart saved as {html_file_path}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

# Call the function to create the pie chart
create_pie_chart()