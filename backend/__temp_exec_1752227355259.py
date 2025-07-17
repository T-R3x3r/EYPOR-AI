
import sys
import os
# Ensure uploaded files take precedence over backend files
sys.path.insert(0, r"C:\Users\Bebob\AppData\Local\Temp\EYProject\session_20250711_101817")
# Only add backend directory if needed for other dependencies
if r"C:\Users\Bebob\AppData\Local\Temp\EYProject\session_20250711_101817" not in sys.path:
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
"""
Prepared script to run data processing and preset optimisation scenarios
"""
import logging

LOGFILE = 'debug.log'
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOGFILE, mode='w')
    ]
)

from dataprocessing import process_inputs
import model

REFRESH_INPUTS = True
MAX_SOLVER_TIME = 0 # 0 means no time limit, otherwise set in seconds

DATABASE_FILE = 'C:\\Users\\Bebob\\Dropbox\\University\\MA425 Project in Operations Research\\EYProjectGit\\backend\\scenarios\\scenario_20250711_104709_760\\database.db'

# Option - refresh data preprocessing
if REFRESH_INPUTS:
    process_inputs(DATABASE_FILE)

# Get standard inputs from database
inputs = model.ModelInputs(database_file=DATABASE_FILE)
inputs.export_model_inputs(database_file=DATABASE_FILE)

# Run basecase option - fixed hubs
model_basecase = model.Model(inputs, option=model.OPTION_BASECASE)
model_basecase.build_and_solve(timeLimit=MAX_SOLVER_TIME)
model_basecase.create_and_export_solution(database_file=DATABASE_FILE)

# Run standard model
model_standard = model.Model(inputs, option=model.OPTION_STANDARD)
model_standard.build_and_solve(timeLimit=MAX_SOLVER_TIME)
model_standard.create_and_export_solution(database_file=DATABASE_FILE)

""" Uncomment to run greenfield option
# Run greenfield option - no initial hubs
model_greenfield = model.Model(inputs, option=model.OPTION_GREENFIELD)
model_greenfield.build_and_solve(timeLimit=MAX_SOLVER_TIME)
model_greenfield.create_and_export_solution(database_file=DATABASE_FILE)
"""

logger.info('All runs completed - results saved to database')
