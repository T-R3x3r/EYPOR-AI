"""
Data pre-processing for the hub location model
"""
import logging
import pandas as pd
import sqlite3
from pathlib import Path
from geopy import distance

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

DATABASE_FILE = 'C:\\Users\\Bebob\\Dropbox\\University\\MA425 Project in Operations Research\\EYProjectGit\\backend\\scenarios\\scenario_20250716_190149_237\\database.db'


# Distance calculation method
def get_distance(row)trh:
    hub_coords = (row.Latitude_hub, row.Longitude_hub)
    dest_coords = (row.Latitude_dest, row.Longitude_dest)
    return distance.distance(hub_coords, dest_coords).km


# Main data processing method
def process_inputs(database_file=None):
    """
    Process inputs from the database instead of Excel files
    """
    database_file = DATABASE_FILE if database_file is None else database_file
    
    logger.info(f'Reading data from database: {database_file}')
    
    # Connect to database
    conn = sqlite3.connect(database_file)
    
    try:
        # Read base data from database tables
        df_params = pd.read_sql_query(
            "SELECT Parameter, Value FROM inputs_params", 
            conn, 
            index_col='Parameter'
        )
        df_hubs = pd.read_sql_query(
            "SELECT * FROM inputs_hubs", 
            conn, 
            index_col='HubID'
        )
        df_dests = pd.read_sql_query(
            "SELECT * FROM inputs_destinations", 
            conn, 
            index_col='DestinationID'
        )

        # Create route matrix
        logger.info(f'Creating distance matrix')
        df_hubs_merge = df_hubs[['LocationID', 'Latitude', 'Longitude']].reset_index()
        df_dests_merge = df_dests[['LocationID', 'Latitude', 'Longitude']].reset_index()
        df_routes = df_hubs_merge.merge(df_dests_merge, how='cross', suffixes=('_hub', '_dest'))

        df_routes['Distance'] = df_routes.apply(get_distance, axis=1)
        df_routes = df_routes.drop(['LocationID_hub', 'LocationID_dest', 'Latitude_hub', 'Longitude_hub', 'Latitude_dest', 'Longitude_dest'], axis=1)

        # Update database tables
        logger.info(f'Updating database tables')
        
        # Drop existing tables and recreate them
        cursor = conn.cursor()
        
        # Update params table
        cursor.execute("DELETE FROM inputs_params")
        df_params.to_sql('inputs_params', conn, if_exists='append', index=True)
        
        # Update hubs table  
        cursor.execute("DELETE FROM inputs_hubs")
        df_hubs.to_sql('inputs_hubs', conn, if_exists='append', index=True)
        
        # Update destinations table
        cursor.execute("DELETE FROM inputs_destinations") 
        df_dests.to_sql('inputs_destinations', conn, if_exists='append', index=True)
        
        # Update routes table
        cursor.execute("DELETE FROM inputs_routes")
        df_routes.to_sql('inputs_routes', conn, if_exists='append', index=False)
        
        # Commit changes
        conn.commit()
        
        logger.info('Data processing complete - database updated')
        
    except Exception as e:
        logger.error(f'Error processing inputs: {e}')
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    process_inputs()

