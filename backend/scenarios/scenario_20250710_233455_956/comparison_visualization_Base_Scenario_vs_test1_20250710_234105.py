# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime

def _aggregate_scenario_data(db_paths, query):
    """Aggregate data from multiple scenario databases."""
    aggregated_data = []
    for db_path in db_paths:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(query, conn)
        conn.close()
        aggregated_data.append(df)
    return aggregated_data

def main():
    # Database paths
    db_paths = [
        "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233455_956/database.db",
        "C:/Users/Bebob/Dropbox/University/MA425 Project in Operations Research/EYProjectGit/backend/scenarios/scenario_20250710_233510_140/database.db"
    ]

    # SQL query to extract demand for Birmingham and Ashford
    query = """
    SELECT Location, Demand FROM outputs_destinations_basecase
    WHERE Location IN ('Birmingham', 'Ashford')
    """

    # Aggregate data from both scenarios
    aggregated_data = _aggregate_scenario_data(db_paths, query)

    # Extract data for plotting
    scenario_names = ['Base Scenario', 'Test1']
    colors = ['#1f77b4', '#ff7f0e']
    pie_data = []

    for i, df in enumerate(aggregated_data):
        df.reset_index(drop=True, inplace=True)
        locations = df['Location'].tolist()
        demands = df['Demand'].tolist()
        pie_data.append(go.Pie(labels=locations, values=demands, name=scenario_names[i], marker=dict(colors=colors[i:i+2])))

    # Create the pie chart
    fig = go.Figure(data=pie_data)

    # Update layout with scenario legends and annotations
    fig.update_layout(
        title="Demand Comparison for Birmingham and Ashford",
        annotations=[
            dict(text='Base Scenario', x=0.18, y=0.5, font_size=20, showarrow=False),
            dict(text='Test1', x=0.82, y=0.5, font_size=20, showarrow=False)
        ],
        showlegend=True
    )

    # Save the figure as an HTML file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_file_path = f"comparison_pie_chart_{timestamp}.html"
    fig.write_html(html_file_path)

if __name__ == "__main__":
    main()