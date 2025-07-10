# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Define database paths
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233455_956/database.db"
test1_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233510_140/database.db"

# Function to fetch data from a database
def fetch_data(db_path, query):
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error fetching data from {db_path}: {e}")
        return pd.DataFrame()

# Query to get demand for Birmingham
query_birmingham_demand = """
SELECT Location, Demand FROM inputs_destinations WHERE Location = 'Birmingham'
"""

# Fetch data for each scenario
base_scenario_data = fetch_data(base_scenario_db, query_birmingham_demand)
test1_scenario_data = fetch_data(test1_scenario_db, query_birmingham_demand)

# Add scenario names
base_scenario_data['Scenario'] = 'Base Scenario'
test1_scenario_data['Scenario'] = 'Test1'

# Combine data
combined_data = pd.concat([base_scenario_data, test1_scenario_data], ignore_index=True)

# Reset index
combined_data.reset_index(drop=True, inplace=True)

# Convert data to lists for plotting
locations = combined_data['Location'].tolist()
demands = combined_data['Demand'].tolist()
scenarios = combined_data['Scenario'].tolist()

# Create a bar chart
fig = go.Figure()

fig.add_trace(go.Bar(
    x=scenarios,
    y=demands,
    text=locations,
    hoverinfo='text+y',
    name='Demand'
))

# Update layout
fig.update_layout(
    title='Demand Comparison for Birmingham',
    xaxis_title='Scenario',
    yaxis_title='Demand',
    barmode='group'
)

# Save the figure as an interactive HTML file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
html_file_path = f"scenario_comparison_{timestamp}.html"
fig.write_html(html_file_path)

print(f"Analysis saved to {html_file_path}")