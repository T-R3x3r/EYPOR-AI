# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Define database paths
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233455_956/database.db"
test1_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233510_140/database.db"

# Function to connect to a database and retrieve data
def get_data_from_db(db_path, table_name):
    try:
        conn = sqlite3.connect(db_path)
        query = f"SELECT * FROM {table_name}"
        df = pd.read_sql_query(query, conn)
        conn.close()
        return df
    except Exception as e:
        print(f"Error connecting to database {db_path}: {e}")
        return None

# Retrieve data from both scenarios
base_destinations = get_data_from_db(base_scenario_db, "outputs_destinations_basecase")
test1_destinations = get_data_from_db(test1_scenario_db, "outputs_destinations_basecase")

# Filter data for Birmingham
base_birmingham = base_destinations[base_destinations['Location'].str.contains("Birmingham", case=False)]
test1_birmingham = test1_destinations[test1_destinations['Location'].str.contains("Birmingham", case=False)]

# Reset index for plotting
base_birmingham = base_birmingham.reset_index(drop=True)
test1_birmingham = test1_birmingham.reset_index(drop=True)

# Prepare data for plotting
base_demand = base_birmingham['Demand'].tolist()
test1_demand = test1_birmingham['Demand'].tolist()
locations = base_birmingham['Location'].tolist()  # Assuming locations are the same in both scenarios

# Create a plotly figure
fig = go.Figure()

# Add traces for each scenario
fig.add_trace(go.Bar(
    x=locations,
    y=base_demand,
    name='Base Scenario',
    hoverinfo='x+y',
    marker=dict(color='blue')
))

fig.add_trace(go.Bar(
    x=locations,
    y=test1_demand,
    name='Test1 Scenario',
    hoverinfo='x+y',
    marker=dict(color='orange')
))

# Update layout
fig.update_layout(
    title='Demand Comparison for Birmingham Across Scenarios',
    xaxis_title='Location',
    yaxis_title='Demand',
    barmode='group',
    hovermode='x unified'
)

# Save the figure as an HTML file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
html_file_path = f"scenario_comparison_{timestamp}.html"
fig.write_html(html_file_path)

print(f"Analysis complete. Results saved to {html_file_path}")