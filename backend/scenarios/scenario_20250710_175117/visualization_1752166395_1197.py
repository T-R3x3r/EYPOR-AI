# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Connect to the database
db_file = 'database.db'
conn = sqlite3.connect(db_file)

try:
    # Query data from inputs_destinations
    query_destinations = """
    SELECT d.DestinationID, d.Location, d.Demand, h.CostFactor_Opening, h.CostFactor_Closing
    FROM inputs_destinations d
    JOIN inputs_hubs h ON d.LocationID = h.LocationID
    ORDER BY d.Demand DESC
    LIMIT 10
    """
    df_destinations = pd.read_sql_query(query_destinations, conn)

    # Reset index
    df_destinations.reset_index(drop=True, inplace=True)

    # Extract data for plotting
    locations = df_destinations['Location'].tolist()
    demands = df_destinations['Demand'].tolist()
    cost_factor_opening = df_destinations['CostFactor_Opening'].tolist()
    cost_factor_closing = df_destinations['CostFactor_Closing'].tolist()

    # Create hover text
    hover_text = [
        f"Location: {loc}<br>Cost Factor Opening: {cfo}<br>Cost Factor Closing: {cfc}"
        for loc, cfo, cfc in zip(locations, cost_factor_opening, cost_factor_closing)
    ]

    # Create a bar chart
    fig = go.Figure(data=[
        go.Bar(
            x=locations,
            y=demands,
            text=hover_text,
            hoverinfo='text',
            marker=dict(color='royalblue')
        )
    ])

    # Update layout
    fig.update_layout(
        title='Top 10 Hubs with Highest Demand',
        xaxis_title='Location',
        yaxis_title='Demand',
        template='plotly',
        xaxis_tickangle=-45
    )

    # Save the figure as an HTML file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    html_file_path = f"top_10_hubs_demand_{timestamp}.html"
    fig.write_html(html_file_path)

    print(f"Interactive chart saved as {html_file_path}")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    # Close the database connection
    conn.close()