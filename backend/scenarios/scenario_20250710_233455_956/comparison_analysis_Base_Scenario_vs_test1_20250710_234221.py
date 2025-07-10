# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Define the database paths
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233455_956/database.db"
test1_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233510_140/database.db"

# Function to connect to a database and retrieve data
def get_data_from_db(db_path, query):
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error connecting to database {db_path}: {e}")
        return None

# Query to retrieve demand data for Birmingham
query = """
SELECT Location, Demand FROM outputs_destinations_basecase
WHERE Location = 'Birmingham'
"""

# Retrieve data from both scenarios
base_scenario_data = get_data_from_db(base_scenario_db, query)
test1_scenario_data = get_data_from_db(test1_scenario_db, query)

# Check if data retrieval was successful
if base_scenario_data is None or test1_scenario_data is None:
    print("Failed to retrieve data from one or more databases.")
else:
    # Reset index and convert to lists for plotting
    base_scenario_data = base_scenario_data.reset_index(drop=True)
    test1_scenario_data = test1_scenario_data.reset_index(drop=True)

    base_demand = base_scenario_data['Demand'].tolist()
    test1_demand = test1_scenario_data['Demand'].tolist()

    # Create a bar chart to compare demands
    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=['Birmingham'],
        y=base_demand,
        name='Base Scenario',
        marker_color='indigo'
    ))

    fig.add_trace(go.Bar(
        x=['Birmingham'],
        y=test1_demand,
        name='Test1 Scenario',
        marker_color='orange'
    ))

    # Update layout
    fig.update_layout(
        title='Demand Comparison for Birmingham',
        xaxis_title='Location',
        yaxis_title='Demand',
        barmode='group',
        hovermode='x unified'
    )

    # Save the figure as an HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file_path = f"scenario_comparison_{timestamp}.html"
    fig.write_html(html_file_path)

    print(f"Analysis saved to {html_file_path}")