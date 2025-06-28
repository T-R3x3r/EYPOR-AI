"""
Example Model with Parameter Synchronization

This file demonstrates how to create a model that automatically uses the latest
parameters from the database and includes parameter validation.
"""

import sqlite3
import pandas as pd
import os
from datetime import datetime

# Auto-generated SQL helper functions (added by the system)
def get_db_connection():
    """Get connection to the project database"""
    return sqlite3.connect(r"project_data.db")

def query_table(query, params=None):
    """Execute SQL query and return DataFrame"""
    conn = get_db_connection()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

def execute_sql(query, params=None):
    """Execute SQL command (INSERT, UPDATE, DELETE)"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()

def load_table(table_name):
    """Load a specific table as DataFrame"""
    return query_table(f"SELECT * FROM {table_name}")

def get_table_info():
    """Get information about all available tables"""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        return tables
    finally:
        conn.close()

# Parameter synchronization helpers
def get_latest_parameters(table_name=None):
    """
    Get the latest parameter values from the database.
    This ensures your model always uses the most recent parameter changes.
    """
    # Find the database file
    db_path = None
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                db_path = os.path.join(root, file)
                break
        if db_path:
            break
    
    if not db_path:
        raise FileNotFoundError("No database file found")
    
    conn = sqlite3.connect(db_path)
    try:
        if table_name:
            # Read from specific table
            df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        else:
            # Read from all parameter tables
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            # Find parameter tables
            param_tables = [t for t in tables if 'param' in t.lower() or 'config' in t.lower()]
            
            all_params = {}
            for table in param_tables:
                df = pd.read_sql_query(f"SELECT * FROM {table}", conn)
                if not df.empty:
                    # Convert to parameter dictionary
                    table_params = {}
                    for _, row in df.iterrows():
                        if 'Parameter' in df.columns and 'Value' in df.columns:
                            table_params[row['Parameter']] = row['Value']
                        else:
                            # Handle other formats
                            for col in df.columns:
                                if col.lower() not in ['id', 'index']:
                                    table_params[col] = row[col]
                    all_params[table] = table_params
            
            return all_params
        
        # Convert DataFrame to parameter dictionary
        if not df.empty:
            params = {}
            for _, row in df.iterrows():
                if 'Parameter' in df.columns and 'Value' in df.columns:
                    params[row['Parameter']] = row['Value']
                else:
                    for col in df.columns:
                        if col.lower() not in ['id', 'index']:
                            params[col] = row[col]
            return params
        else:
            return {}
            
    finally:
        conn.close()

def validate_model_parameters(required_params):
    """
    Validate that all required parameters are available in the database.
    """
    current_params = get_latest_parameters()
    
    validation = {
        "all_present": True,
        "missing_params": [],
        "available_params": list(current_params.keys()),
        "parameter_count": len(current_params)
    }
    
    for param in required_params:
        if param not in current_params:
            validation["missing_params"].append(param)
            validation["all_present"] = False
    
    return validation

def log_parameter_usage(parameters_used, model_name="Unknown"):
    """
    Log which parameters were used by the model for tracking purposes.
    """
    timestamp = datetime.now().isoformat()
    
    print(f"📊 Model '{model_name}' executed with parameters:")
    for param, value in parameters_used.items():
        print(f"   {param}: {value}")
    print(f"   Timestamp: {timestamp}")

def main():
    """
    Example Hub Location Optimization Model
    This demonstrates how to use parameter synchronization in a real model.
    """
    print("🚀 Starting Hub Location Optimization Model")
    print("=" * 50)
    
    # Step 1: Get latest parameters from database
    print("\n📋 Loading parameters from database...")
    try:
        # Get parameters from the inputs_params table
        params = get_latest_parameters("inputs_params")
        
        if not params:
            print("❌ No parameters found in inputs_params table")
            return
        
        print(f"✅ Loaded {len(params)} parameters from database")
        
    except Exception as e:
        print(f"❌ Error loading parameters: {e}")
        return
    
    # Step 2: Validate required parameters
    print("\n🔍 Validating required parameters...")
    required_params = [
        "Maximum Hub Demand",
        "Minimum Hub Demand", 
        "Operating Hubs Limit",
        "Opening Cost",
        "Operating Cost (Fixed)",
        "Operating Cost per Unit"
    ]
    
    validation = validate_model_parameters(required_params)
    
    if not validation["all_present"]:
        print(f"❌ Missing required parameters: {validation['missing_params']}")
        print(f"Available parameters: {validation['available_params']}")
        return
    
    print(f"✅ All required parameters validated ({validation['parameter_count']} total)")
    
    # Step 3: Extract parameter values
    print("\n📊 Extracting parameter values...")
    try:
        max_hub_demand = float(params.get("Maximum Hub Demand", 0))
        min_hub_demand = float(params.get("Minimum Hub Demand", 0))
        operating_hubs_limit = int(params.get("Operating Hubs Limit", 0))
        opening_cost = float(params.get("Opening Cost", 0))
        operating_cost_fixed = float(params.get("Operating Cost (Fixed)", 0))
        operating_cost_per_unit = float(params.get("Operating Cost per Unit", 0))
        
        print(f"   Maximum Hub Demand: {max_hub_demand}")
        print(f"   Minimum Hub Demand: {min_hub_demand}")
        print(f"   Operating Hubs Limit: {operating_hubs_limit}")
        print(f"   Opening Cost: {opening_cost}")
        print(f"   Operating Cost (Fixed): {operating_cost_fixed}")
        print(f"   Operating Cost per Unit: {operating_cost_per_unit}")
        
    except (ValueError, KeyError) as e:
        print(f"❌ Error extracting parameter values: {e}")
        return
    
    # Step 4: Load other data from database
    print("\n📈 Loading hub and destination data...")
    try:
        # Load hubs data
        hubs_data = load_table("hubs_data")
        print(f"   Loaded {len(hubs_data)} hub locations")
        
        # Load destinations data  
        destinations_data = load_table("destinations_data")
        print(f"   Loaded {len(destinations_data)} destinations")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return
    
    # Step 5: Run optimization (simplified example)
    print("\n🔧 Running optimization...")
    
    # Simulate optimization process
    import time
    time.sleep(1)  # Simulate computation time
    
    # Example optimization logic (simplified)
    total_cost = opening_cost * min(operating_hubs_limit, len(hubs_data))
    total_cost += operating_cost_fixed * min(operating_hubs_limit, len(hubs_data))
    
    total_demand = destinations_data.get('Demand', [0]).sum() if 'Demand' in destinations_data.columns else 0
    total_cost += operating_cost_per_unit * total_demand
    
    # Step 6: Generate results
    print("\n📊 Optimization Results:")
    print(f"   Total Cost: ${total_cost:,.2f}")
    print(f"   Total Demand: {total_demand:,.0f}")
    print(f"   Hubs Used: {min(operating_hubs_limit, len(hubs_data))}")
    print(f"   Destinations Served: {len(destinations_data)}")
    
    # Step 7: Log parameter usage for tracking
    print("\n📝 Logging parameter usage...")
    log_parameter_usage(params, "Hub Location Optimization Model")
    
    # Step 8: Save results to database
    print("\n💾 Saving results to database...")
    try:
        results_data = pd.DataFrame({
            'Metric': ['Total Cost', 'Total Demand', 'Hubs Used', 'Destinations Served'],
            'Value': [total_cost, total_demand, min(operating_hubs_limit, len(hubs_data)), len(destinations_data)],
            'Timestamp': [datetime.now()] * 4
        })
        
        # Save to database
        conn = get_db_connection()
        results_data.to_sql('optimization_results', conn, if_exists='replace', index=False)
        conn.close()
        
        print("✅ Results saved to optimization_results table")
        
    except Exception as e:
        print(f"❌ Error saving results: {e}")
    
    print("\n🎉 Model execution completed successfully!")
    print("=" * 50)

if __name__ == "__main__":
    main() 