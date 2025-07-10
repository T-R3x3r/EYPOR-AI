# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Define database paths
base_scenario_db = '../scenarios/scenario_20250710_210837_098/database.db'
scenario1_db = '../scenarios/scenario_20250710_210837_120/database.db'

# Function to connect to a database and fetch data
def fetch_data_from_db(db_path, query):
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error fetching data from {db_path}: {e}")
        return pd.DataFrame()

# Query to fetch demand for Birmingham
query_birmingham_demand = """
SELECT Location, Demand
FROM inputs_destinations
WHERE Location = 'Birmingham'
"""

# Fetch data for each scenario
base_scenario_data = fetch_data_from_db(base_scenario_db, query_birmingham_demand)
scenario1_data = fetch_data_from_db(scenario1_db, query_birmingham_demand)

# Add scenario names to the data
base_scenario_data['Scenario'] = 'Base Scenario'
scenario1_data['Scenario'] = 'Scenario1'

# Combine data from both scenarios
combined_data = pd.concat([base_scenario_data, scenario1_data], ignore_index=True)

# Reset index for combined data
combined_data = combined_data.reset_index(drop=True)

# Prepare data for plotting
locations = combined_data['Location'].tolist()
demands = combined_data['Demand'].tolist()
scenarios = combined_data['Scenario'].tolist()

# Create a bar chart comparing demand for Birmingham in both scenarios
fig = go.Figure()

fig.add_trace(go.Bar(
    x=scenarios,
    y=demands,
    text=demands,
    textposition='auto',
    name='Demand',
    hoverinfo='text',
    hovertext=[f"Location: {loc}<br>Demand: {dem}" for loc, dem in zip(locations, demands)]
))

# Update layout for better visualization
fig.update_layout(
    title='Demand Comparison for Birmingham',
    xaxis_title='Scenario',
    yaxis_title='Demand',
    barmode='group',
    template='plotly',
    hovermode='x unified'
)

# Generate a dynamic file name with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
html_file_path = f"scenario_comparison_{timestamp}.html"

# Save the figure as an interactive HTML file
fig.write_html(html_file_path)

print(f"Analysis complete. Results saved to {html_file_path}")