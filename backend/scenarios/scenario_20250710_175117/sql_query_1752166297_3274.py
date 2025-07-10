# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def main():
    # Connect to the database
    try:
        conn = sqlite3.connect('database.db')
    except sqlite3.Error as e:
        print(f"Error connecting to database: {e}")
        return

    # Define the SQL query to get the top 3 hubs by demand
    query = """
    SELECT h.HubID, h.Location, SUM(d.Demand) as TotalDemand
    FROM inputs_hubs h
    JOIN inputs_destinations d ON h.LocationID = d.LocationID
    GROUP BY h.HubID, h.Location
    ORDER BY TotalDemand DESC
    LIMIT 3;
    """

    # Execute the query and fetch the results
    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError as e:
        print(f"Error executing query: {e}")
        return
    finally:
        conn.close()

    # Reset index and convert DataFrame to lists for Plotly
    df.reset_index(drop=True, inplace=True)
    hub_ids = df['HubID'].tolist()
    locations = df['Location'].tolist()
    total_demands = df['TotalDemand'].tolist()

    # Create a Plotly table
    fig = go.Figure(data=[go.Table(
        header=dict(values=['HubID', 'Location', 'Total Demand'],
                    fill_color='paleturquoise',
                    align='left'),
        cells=dict(values=[hub_ids, locations, total_demands],
                   fill_color='lavender',
                   align='left'))
    ])

    # Generate a dynamic filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file_path = f"top_3_hubs_by_demand_{timestamp}.html"

    # Save the figure as an HTML file
    try:
        fig.write_html(html_file_path)
        print(f"Interactive table saved as {html_file_path}")
    except Exception as e:
        print(f"Error saving HTML file: {e}")

    # Print a summary of the query results
    print("Query Results Summary:")
    print(df)

if __name__ == "__main__":
    main()