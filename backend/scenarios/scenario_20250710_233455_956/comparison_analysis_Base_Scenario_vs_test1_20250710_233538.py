# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

# Define database paths
base_scenario_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233455_956/database.db"
test1_db = "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233510_140/database.db"

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
        return pd.DataFrame()

# Retrieve data from both scenarios
base_scenario_destinations = get_data_from_db(base_scenario_db, "inputs_destinations")
test1_destinations = get_data_from_db(test1_db, "inputs_destinations")

# Add scenario names to distinguish data sources
base_scenario_destinations['Scenario'] = 'Base Scenario'
test1_destinations['Scenario'] = 'Test1'

# Combine data from both scenarios
combined_data = pd.concat([base_scenario_destinations, test1_destinations], ignore_index=True)

# Reset index
combined_data.reset_index(drop=True, inplace=True)

# Prepare data for plotting
locations = combined_data['Location'].tolist()
demands = combined_data['Demand'].tolist()
scenarios = combined_data['Scenario'].tolist()

# Create a bar chart to compare demands across scenarios
fig = go.Figure()

# Add traces for each scenario
fig.add_trace(go.Bar(
    x=locations,
    y=demands,
    name='Demand',
    text=scenarios,
    hoverinfo='text+y',
    marker=dict(color='blue')
))

# Update layout
fig.update_layout(
    title='Demand Comparison Across Scenarios',
    xaxis_title='Location',
    yaxis_title='Demand',
    barmode='group',
    hovermode='closest'
)

# Generate dynamic file name with timestamp
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
html_file_path = f"scenario_comparison_{timestamp}.html"

# Save the figure as an interactive HTML file
fig.write_html(html_file_path)

print(f"Analysis saved to {html_file_path}")