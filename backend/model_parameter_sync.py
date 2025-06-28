"""
Model Parameter Synchronization Module

This module ensures that when parameters are modified in the database (representing Excel data),
the models always run with the latest parameter values and provides validation to ensure
parameter changes are properly applied.
"""

import sqlite3
import pandas as pd
import os
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class ModelParameterSync:
    """
    Handles synchronization between database parameter changes and model execution
    to ensure models always use the latest parameter values.
    """
    
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.parameter_tables = [
            'inputs_params', 'params', 'parameters', 'config', 'settings'
        ]
        
    def get_db_connection(self):
        """Get connection to the project database"""
        return sqlite3.connect(self.database_path)
    
    def query_table(self, query: str, params: Optional[List] = None) -> pd.DataFrame:
        """Execute SQL query and return DataFrame"""
        conn = self.get_db_connection()
        try:
            return pd.read_sql_query(query, conn, params=params)
        finally:
            conn.close()
    
    def execute_sql(self, query: str, params: Optional[List] = None) -> int:
        """Execute SQL command (INSERT, UPDATE, DELETE)"""
        conn = self.get_db_connection()
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
    
    def get_parameter_tables(self) -> List[str]:
        """Get all tables that contain model parameters"""
        conn = self.get_db_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            all_tables = [row[0] for row in cursor.fetchall()]
            
            # Find tables that match parameter patterns
            param_tables = []
            for table in all_tables:
                table_lower = table.lower()
                if any(pattern in table_lower for pattern in ['param', 'config', 'setting', 'input']):
                    param_tables.append(table)
            
            return param_tables
        finally:
            conn.close()
    
    def get_current_parameters(self) -> Dict[str, Any]:
        """Get all current parameter values from the database"""
        param_tables = self.get_parameter_tables()
        all_params = {}
        
        for table in param_tables:
            try:
                df = self.query_table(f"SELECT * FROM {table}")
                if not df.empty:
                    # Convert DataFrame to dictionary format
                    table_params = {}
                    for _, row in df.iterrows():
                        # Handle different parameter table formats
                        if 'Parameter' in df.columns and 'Value' in df.columns:
                            # Standard parameter table format
                            param_name = row['Parameter']
                            param_value = row['Value']
                            table_params[param_name] = param_value
                        elif 'parameter' in df.columns and 'value' in df.columns:
                            # Lowercase format
                            param_name = row['parameter']
                            param_value = row['value']
                            table_params[param_name] = param_value
                        else:
                            # Treat all columns as potential parameters
                            for col in df.columns:
                                if col.lower() not in ['id', 'index', 'unnamed']:
                                    table_params[col] = row[col]
                    
                    all_params[table] = table_params
                    
            except Exception as e:
                logger.warning(f"Could not read parameters from table {table}: {e}")
        
        return all_params
    
    def validate_parameter_changes(self, changes: List[Dict]) -> Dict[str, Any]:
        """
        Validate that parameter changes have been properly applied to the database
        
        Args:
            changes: List of changes made to parameters
            
        Returns:
            Validation results with success status and details
        """
        validation_results = {
            "success": True,
            "validated_changes": [],
            "errors": [],
            "warnings": []
        }
        
        for change in changes:
            try:
                table = change.get('table')
                column = change.get('column')
                new_value = change.get('new_value')
                where_condition = change.get('where_condition', '')
                
                # Helper function to properly quote identifiers with special characters
                def quote_identifier(name):
                    # Remove any existing quotes
                    name = name.strip('`"\'')
                    # Quote if it contains special characters or starts with a number
                    if ':' in name or ' ' in name or name.startswith('Unnamed') or name[0].isdigit():
                        return f'"{name}"'
                    return name
                
                # Clean and quote column and table names
                quoted_column = quote_identifier(column)
                quoted_table = quote_identifier(table)
                
                # Parse and quote the where condition if it exists
                formatted_where = where_condition
                if where_condition:
                    # Handle cases like: Unnamed: 2 = 'Base Cost per Unit'
                    where_parts = where_condition.split('=', 1)
                    if len(where_parts) == 2:
                        left_part = where_parts[0].strip()
                        right_part = where_parts[1].strip()
                        quoted_left = quote_identifier(left_part)
                        formatted_where = f"{quoted_left} = {right_part}"
                
                # Query the database to verify the change
                if formatted_where:
                    query = f"SELECT {quoted_column} FROM {quoted_table} WHERE {formatted_where}"
                else:
                    query = f"SELECT {quoted_column} FROM {quoted_table}"
                
                df = self.query_table(query)
                
                if df.empty:
                    validation_results["errors"].append(
                        f"No data found for change in {table}.{column}"
                    )
                    validation_results["success"] = False
                else:
                    # Check if the change was applied
                    # Use the original column name (without quotes) to access DataFrame
                    actual_value = df.iloc[0][column.strip('`"\'')]
                    
                    # Handle type conversion for comparison
                    try:
                        if isinstance(new_value, (int, float)):
                            actual_value = float(actual_value)
                            new_value = float(new_value)
                        elif isinstance(new_value, str):
                            actual_value = str(actual_value)
                            new_value = str(new_value)
                    except (ValueError, TypeError):
                        pass
                    
                    if actual_value == new_value:
                        validation_results["validated_changes"].append({
                            "table": table,
                            "column": column,
                            "expected": new_value,
                            "actual": actual_value,
                            "status": "✅ Applied"
                        })
                    else:
                        validation_results["errors"].append({
                            "table": table,
                            "column": column,
                            "expected": new_value,
                            "actual": actual_value,
                            "status": "❌ Not Applied"
                        })
                        validation_results["success"] = False
                        
            except Exception as e:
                validation_results["errors"].append(
                    f"Error validating change in {change.get('table', 'unknown')}: {str(e)}"
                )
                validation_results["success"] = False
        
        return validation_results
    
    def create_parameter_snapshot(self) -> Dict[str, Any]:
        """Create a snapshot of current parameter values for comparison"""
        current_params = self.get_current_parameters()
        return {
            "timestamp": datetime.now().isoformat(),
            "parameters": current_params,
            "database_path": self.database_path
        }
    
    def compare_parameter_snapshots(self, before: Dict, after: Dict) -> Dict[str, Any]:
        """Compare two parameter snapshots to identify changes"""
        comparison = {
            "changes": [],
            "unchanged": [],
            "added": [],
            "removed": []
        }
        
        before_params = before.get("parameters", {})
        after_params = after.get("parameters", {})
        
        # Find all unique tables
        all_tables = set(before_params.keys()) | set(after_params.keys())
        
        for table in all_tables:
            before_table = before_params.get(table, {})
            after_table = after_params.get(table, {})
            
            # Find all unique parameters in this table
            all_params = set(before_table.keys()) | set(after_table.keys())
            
            for param in all_params:
                before_value = before_table.get(param)
                after_value = after_table.get(param)
                
                if param not in before_table:
                    comparison["added"].append({
                        "table": table,
                        "parameter": param,
                        "value": after_value
                    })
                elif param not in after_table:
                    comparison["removed"].append({
                        "table": table,
                        "parameter": param,
                        "value": before_value
                    })
                elif before_value != after_value:
                    comparison["changes"].append({
                        "table": table,
                        "parameter": param,
                        "before": before_value,
                        "after": after_value
                    })
                else:
                    comparison["unchanged"].append({
                        "table": table,
                        "parameter": param,
                        "value": before_value
                    })
        
        return comparison
    
    def ensure_model_reads_latest_params(self, model_file_path: str) -> Dict[str, Any]:
        """
        Ensure a model file is properly configured to read from the database
        and will use the latest parameter values.
        
        Args:
            model_file_path: Path to the model file to check
            
        Returns:
            Analysis results with recommendations
        """
        analysis = {
            "file_path": model_file_path,
            "uses_database": False,
            "uses_file_operations": False,
            "recommendations": [],
            "sql_helpers_present": False,
            "file_operations_found": []
        }
        
        try:
            with open(model_file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Check for SQL helper functions
            sql_helpers = ['query_table', 'load_table', 'get_db_connection']
            for helper in sql_helpers:
                if helper in content:
                    analysis["sql_helpers_present"] = True
                    analysis["uses_database"] = True
            
            # Check for file operations that should be replaced
            file_operations = [
                'pd.read_csv', 'pd.read_excel', 'open(', 'read_csv', 'read_excel'
            ]
            
            for operation in file_operations:
                if operation in content:
                    analysis["uses_file_operations"] = True
                    analysis["file_operations_found"].append(operation)
            
            # Generate recommendations
            if not analysis["uses_database"]:
                analysis["recommendations"].append(
                    "Model should use SQL helper functions (query_table, load_table) instead of file operations"
                )
            
            if analysis["uses_file_operations"]:
                analysis["recommendations"].append(
                    "File operations detected - these should be replaced with database queries"
                )
            
            if not analysis["sql_helpers_present"]:
                analysis["recommendations"].append(
                    "Add SQL helper functions to ensure database connectivity"
                )
            
        except Exception as e:
            analysis["error"] = str(e)
        
        return analysis
    
    def generate_model_execution_summary(self, model_file_path: str, execution_output: str) -> Dict[str, Any]:
        """
        Generate a summary of model execution with parameter validation
        
        Args:
            model_file_path: Path to the executed model
            execution_output: Output from model execution
            
        Returns:
            Summary with parameter validation and execution status
        """
        summary = {
            "model_file": model_file_path,
            "execution_timestamp": datetime.now().isoformat(),
            "current_parameters": self.get_current_parameters(),
            "execution_output": execution_output,
            "parameter_validation": {
                "parameter_tables_found": len(self.get_parameter_tables()),
                "total_parameters": 0,
                "validation_status": "✅ Ready"
            }
        }
        
        # Count total parameters
        current_params = summary["current_parameters"]
        total_params = sum(len(table_params) for table_params in current_params.values())
        summary["parameter_validation"]["total_parameters"] = total_params
        
        # Check if execution output indicates any parameter-related issues
        if "error" in execution_output.lower() or "exception" in execution_output.lower():
            summary["parameter_validation"]["validation_status"] = "⚠️ Execution Issues"
        
        return summary

def create_parameter_sync_helpers():
    """
    Create helper functions that can be added to model files to ensure
    they always read the latest parameters from the database.
    """
    helpers = '''
# Parameter Synchronization Helpers
# Add these functions to your model files to ensure they always use the latest parameters

import sqlite3
import pandas as pd
import os
from typing import Dict, Any, Optional

def get_latest_parameters(table_name: str = None) -> Dict[str, Any]:
    """
    Get the latest parameter values from the database.
    This ensures your model always uses the most recent parameter changes.
    
    Args:
        table_name: Specific table to read from (optional)
    
    Returns:
        Dictionary of parameter values
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

def validate_model_parameters(required_params: List[str]) -> Dict[str, Any]:
    """
    Validate that all required parameters are available in the database.
    
    Args:
        required_params: List of parameter names that the model requires
    
    Returns:
        Validation results
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

def log_parameter_usage(parameters_used: Dict[str, Any], model_name: str = "Unknown"):
    """
    Log which parameters were used by the model for tracking purposes.
    
    Args:
        parameters_used: Dictionary of parameters and their values
        model_name: Name of the model for logging
    """
    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "model": model_name,
        "parameters": parameters_used
    }
    
    print(f"📊 Model '{model_name}' executed with parameters:")
    for param, value in parameters_used.items():
        print(f"   {param}: {value}")
    print(f"   Timestamp: {timestamp}")
'''
    
    return helpers

if __name__ == "__main__":
    # Example usage
    db_path = "project_data.db"
    if os.path.exists(db_path):
        sync = ModelParameterSync(db_path)
        
        print("🔍 Current Parameters:")
        params = sync.get_current_parameters()
        for table, table_params in params.items():
            print(f"\n📋 Table: {table}")
            for param, value in table_params.items():
                print(f"   {param}: {value}")
        
        print(f"\n✅ Parameter tables found: {len(sync.get_parameter_tables())}")
    else:
        print("❌ Database file not found") 