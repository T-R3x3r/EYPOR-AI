"""
Create test scenarios for comparison testing
"""

import os
import sqlite3
import shutil
from datetime import datetime
from scenario_manager import ScenarioManager

def create_test_scenarios():
    """Create test scenarios with different data"""
    print("🔧 Creating test scenarios...")
    
    # Initialize scenario manager
    project_root = os.path.dirname(os.path.dirname(__file__))
    scenario_manager = ScenarioManager(project_root)
    
    # Create Base Scenario
    print("📁 Creating Base Scenario...")
    base_scenario = scenario_manager.create_scenario(
        name="Base Scenario",
        description="Base scenario with standard parameters"
    )
    print(f"✅ Created Base Scenario with ID: {base_scenario.id}")
    
    # Create Scenario1
    print("📁 Creating Scenario1...")
    scenario1 = scenario_manager.create_scenario(
        name="Scenario1", 
        description="Scenario with modified demand parameters"
    )
    print(f"✅ Created Scenario1 with ID: {scenario1.id}")
    
    # Add test data to both scenarios
    print("📊 Adding test data to scenarios...")
    
    # Base Scenario data
    base_data = {
        'inputs_destinations': [
            ('Birmingham', 5000, 100),
            ('London', 8000, 150),
            ('Manchester', 6000, 120),
            ('Leeds', 4000, 80),
            ('Liverpool', 3500, 70)
        ],
        'inputs_hubs': [
            ('Hub1', 10000, 200),
            ('Hub2', 12000, 250),
            ('Hub3', 8000, 150)
        ]
    }
    
    # Scenario1 data (modified demand)
    scenario1_data = {
        'inputs_destinations': [
            ('Birmingham', 7000, 140),  # Increased demand
            ('London', 10000, 200),     # Increased demand
            ('Manchester', 7500, 150),   # Increased demand
            ('Leeds', 5000, 100),       # Increased demand
            ('Liverpool', 4500, 90)     # Increased demand
        ],
        'inputs_hubs': [
            ('Hub1', 12000, 240),       # Increased capacity
            ('Hub2', 15000, 300),       # Increased capacity
            ('Hub3', 10000, 200)        # Increased capacity
        ]
    }
    
    # Insert data into Base Scenario
    print("📊 Inserting data into Base Scenario...")
    insert_test_data(base_scenario.database_path, base_data)
    
    # Insert data into Scenario1
    print("📊 Inserting data into Scenario1...")
    insert_test_data(scenario1.database_path, scenario1_data)
    
    # List all scenarios
    all_scenarios = scenario_manager.list_scenarios()
    print(f"\n✅ Created {len(all_scenarios)} scenarios:")
    for scenario in all_scenarios:
        print(f"  - {scenario.name} (ID: {scenario.id})")
    
    return scenario_manager

def insert_test_data(database_path, data):
    """Insert test data into a scenario database"""
    conn = sqlite3.connect(database_path)
    cursor = conn.cursor()
    
    try:
        # Create tables if they don't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inputs_destinations (
                Location TEXT PRIMARY KEY,
                Demand INTEGER,
                Distance REAL
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inputs_hubs (
                Hub TEXT PRIMARY KEY,
                Capacity INTEGER,
                Cost REAL
            )
        ''')
        
        # Insert destinations data
        cursor.executemany(
            'INSERT OR REPLACE INTO inputs_destinations (Location, Demand, Distance) VALUES (?, ?, ?)',
            data['inputs_destinations']
        )
        
        # Insert hubs data
        cursor.executemany(
            'INSERT OR REPLACE INTO inputs_hubs (Hub, Capacity, Cost) VALUES (?, ?, ?)',
            data['inputs_hubs']
        )
        
        conn.commit()
        print(f"✅ Inserted {len(data['inputs_destinations'])} destinations and {len(data['inputs_hubs'])} hubs")
        
    except Exception as e:
        print(f"❌ Error inserting data: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    create_test_scenarios() 