# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
import os
from datetime import datetime

def connect_to_database(db_file):
    """Connect to the SQLite database and return the connection object."""
    try:
        conn = sqlite3.connect(db_file)
        return conn
    except sqlite3.Error as e:
        print(f"Error connecting to database {db_file}: {e}")
        return None

def query_data(conn, table_name):
    """Query data from a specified table in the database."""
    try:
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        return df
    except Exception as e:
        print(f"Error querying data from table {table_name}: {e}")
        return pd.DataFrame()

def analyze_scenarios():
    # Define the scenarios and their corresponding database files
    scenarios = {
        "Base Scenario": "database.db",
        "Scenario1": "database.db"
    }

    # Initialize a dictionary to store data from each scenario
    scenario_data = {}

    # Connect to each database and query the necessary data
    for scenario_name, db_file in scenarios.items():
        conn = connect_to_database(db_file)
        if conn:
            inputs_destinations_df = query_data(conn, "inputs_destinations")
            scenario_data[scenario_name] = inputs_destinations_df
            conn.close()

    # Perform analysis and create visualizations
    fig = go.Figure()

    for scenario_name, df in scenario_data.items():
        # Filter data for Birmingham
        birmingham_data = df[df['Location'] == 'Birmingham'].reset_index(drop=True)

        # Extract data for plotting
        demand = birmingham_data['Demand'].tolist()
        distance = birmingham_data['Distance'].tolist()

        # Add trace for each scenario
        fig.add_trace(go.Scatter(
            x=distance,
            y=demand,
            mode='markers+lines',
            name=f"{scenario_name} - Birmingham",
            hoverinfo='text',
            text=[f"Demand: {d}, Distance: {dist}" for d, dist in zip(demand, distance)]
        ))

    # Update layout for better visualization
    fig.update_layout(
        title="Demand vs Distance for Birmingham across Scenarios",
        xaxis_title="Distance",
        yaxis_title="Demand",
        hovermode="closest"
    )

    # Save the figure as an interactive HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file_path = f"scenario_comparison_{timestamp}.html"
    fig.write_html(html_file_path)

    print(f"Analysis saved to {html_file_path}")

if __name__ == "__main__":
    analyze_scenarios()