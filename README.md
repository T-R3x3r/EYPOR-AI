# EYPOR-AI – AI-Powered Operations Research Platform

## Overview
EYPOR-AI is an end-to-end, AI-powered environment for data-driven decision making and optimisation. The platform features a **Simplified Agent v2** architecture that intelligently routes user requests through specialized handlers, all accessible through a natural language interface.

The system comprises:
- A Python/FastAPI backend with LangGraph-based agent orchestration
- An Angular frontend providing an intuitive chat interface
- A Simplified Agent v2 with specialized request handlers including **file editing capabilities**
- Integrated database and scenario management capabilities

---

## Key Capabilities
• **Intelligent Request Classification**: Automatic analysis and routing of user requests to specialized handlers  
• **SQL Operations**: Natural-language queries with automatic schema discovery and Plotly table generation  
• **Dynamic Visualization**: Automated generation and execution of Python/Plotly visualization code  
• **Database Management**: Parameter updates with scenario-aware database context and percentage calculations  
• **Scenario Management**: Multi-scenario support with isolated databases and file directories  
• **File Editing**: **NEW** - Edit existing Python files with modification tracking and validation  
• **Enhanced File Management**: Automatic cleanup of empty query groups and organized file structure  
• **Built-in Chat Capability**: Q&A support without code execution for general questions  
• **Error Handling**: Comprehensive execution error capture and user-friendly reporting  
• **Persistent Memory**: Browser-side conversation storage with context retention

---

## High-Level Agent Workflow

The system employs a **Simplified Agent v2** architecture that intelligently routes and processes user requests through specialized handlers:

### **Simplified Agent v2 Workflow (Updated with Edit Feature)**

![Simplified Agent v2 Workflow](docs/images/data_analyst_workflow.png)

The workflow features intelligent request classification and specialized processing:

### **Core Workflow Nodes**

1. **Request Classification** (`classify_request`):
   - Analyzes user input to determine request type using keyword patterns and LLM fallback
   - Routes to appropriate specialized handler
   - Supports: `chat`, `sql_query`, `visualization`, `db_modification`, `scenario_comparison`, `file_edit`
   - **Edit Mode Detection**: Automatically detects when frontend sets edit mode for file editing

2. **Scenario Extraction** (`extract_scenarios`):
   - **NEW** - Extracts scenario names from comparison requests using regex patterns
   - Supports fuzzy matching for scenario name resolution
   - Handles natural language comparison requests (e.g., "compare Base and Test")
   - Creates multi-database context for comparison operations

3. **Specialized Handlers**:
   - **`handle_chat`**: General Q&A without code execution, provides context about current scenario
   - **`handle_sql_query`**: SQL query generation with Plotly table output and schema validation
   - **`handle_visualization`**: Chart/graph generation with Plotly (single scenario)
   - **`handle_file_edit`**: **NEW** - File editing with modification tracking and validation
   - **`handle_scenario_comparison`**: **NEW** - Multi-scenario comparison analysis and visualization
   - **`prepare_db_modification`**: Database parameter change preparation with percentage calculations

4. **Code Execution** (`execute_code`):
   - Executes generated Python scripts for SQL, visualization, and **file editing** requests
   - Captures outputs, errors, and generated files
   - Supports interactive HTML charts and data exports
   - **Enhanced**: Now handles modified files from edit operations

5. **Database Modification** (`execute_db_modification`):
   - Performs parameter updates with validation and percentage calculations
   - Maintains data integrity across scenarios
   - Supports model re-execution capabilities
   - **Enhanced**: Supports percentage-based modifications (e.g., "increase by 10%")

6. **Response Generation** (`respond`):
   - Formats final responses with context and file information
   - Includes generated files and execution results
   - Provides user-friendly output formatting
   - **Enhanced**: Includes modification history and query tracking information

### **Workflow Paths**

- **Chat Path**: `START → classify_request → handle_chat → respond → END`
- **SQL Path**: `START → classify_request → handle_sql_query → execute_code → respond → END`
- **Visualization Path**: `START → classify_request → handle_visualization → execute_code → respond → END`
- **File Edit Path**: `START → classify_request → handle_file_edit → execute_code → respond → END`
- **Scenario Comparison Path**: `START → classify_request → extract_scenarios → handle_scenario_comparison → execute_code → respond → END`
- **DB Modification Path**: `START → classify_request → prepare_db_modification → execute_db_modification → respond → END`

---

## **NEW: File Editing Feature**

The agent now supports **file editing capabilities** that allow users to modify existing Python files through natural language requests.

### **File Editing Workflow**

1. **Edit Mode Detection**: Frontend can set edit mode with specific file path
2. **File Loading**: Agent loads original file content and modification history
3. **Context Building**: Creates modification context with file history and database context
4. **LLM Modification**: Uses LLM to generate modified content based on user request
5. **Validation**: Validates modifications before saving
6. **Execution**: Modified file is executed through standard code execution pipeline
7. **Tracking**: Maintains modification history and query-file mappings

### **File Editing Features**

- **Context Preservation**: Maintains original file content and modification history
- **Validation**: Validates file modifications before execution
- **Query Tracking**: Maps queries to modified files for future reference
- **Execution Integration**: Modified files are executed through the standard execute_code node
- **Database Context**: Uses current scenario's database context for file operations
- **Error Handling**: Comprehensive error handling for file operations
- **History Tracking**: Maintains modification history with timestamps and query IDs

### **State Information Flow for File Editing**

The `AgentState` contains specialized fields for file editing:

```python
# Edit mode specific fields
edit_mode: bool = False
editing_file_path: Optional[str] = None
original_file_content: Optional[str] = None
file_modification_history: List[Dict[str, Any]] = []

# Enhanced query tracking
query_file_mappings: Dict[str, List[str]] = {}  # query_id -> [file_paths]
current_query_context: Optional[Dict[str, Any]] = None
```

### **File Editing Methods**

- **`_handle_file_edit`**: Main handler for file editing requests
- **`_load_file_for_editing`**: Loads file content with proper path resolution
- **`_save_file_modification`**: Saves modified content with validation
- **`_get_file_modification_context`**: Builds context for modification requests
- **`_validate_file_modification`**: Validates modifications before saving
- **`_track_file_modification`**: Tracks modification history and metadata
- **`_get_file_modification_history`**: Retrieves modification history for context

---

## **Enhanced Database Context System**

The agent uses a sophisticated `DatabaseContext` system that provides scenario-aware database routing:

### **DatabaseContext Features**

- **Scenario-Aware Routing**: Always uses current scenario's database and file directory
- **Multi-Scenario Support**: Supports comparison operations across multiple scenarios
- **Schema Information**: Provides database schema information for query generation
- **Validation**: Validates database context before operations
- **Path Resolution**: Handles absolute and relative path resolution

### **DatabaseContext Methods**

- **`is_valid()`**: Checks if database context is valid and usable
- **`get_primary_context()`**: Gets primary context for comparison operations
- **`get_all_database_paths()`**: Gets all database paths in comparison mode
- **`get_scenario_names()`**: Gets all scenario names in comparison mode

---

## **Multi-Scenario Comparison System**

The agent supports sophisticated multi-scenario comparison operations:

### **Comparison Workflow**

1. **Scenario Extraction**: Uses regex patterns to extract scenario names from requests
2. **Context Creation**: Creates multi-database context for comparison operations
3. **Data Aggregation**: Aggregates data from multiple scenarios with consistent structure
4. **Visualization**: Generates comparison charts and tables
5. **Analysis**: Performs statistical analysis across scenarios

### **Comparison Features**

- **Fuzzy Matching**: Supports fuzzy matching for scenario name resolution
- **Natural Language**: Handles natural language comparison requests
- **Multiple Chart Types**: Supports side-by-side bars, faceted plots, heatmaps, etc.
- **Statistical Analysis**: Provides statistical summaries and differences
- **Interactive Visualizations**: Creates interactive comparison charts

---

## **Enhanced Database Modification System**

The database modification system now supports percentage-based calculations:

### **Percentage Modification Types**

1. **Absolute Percentage Changes**:
   - "increase by 10%" → Increase current value by 10%
   - "decrease by 15%" → Decrease current value by 15%
   - "reduce by 5%" → Decrease current value by 5%

2. **Relative Percentage Changes**:
   - "increase by 10% of capacity" → Add (10% of capacity_value) to current value
   - "set to 20% of maximum" → Set to (20% of maximum_value)
   - "set demand to twice that of oxford" → Set to (200% of Oxford's demand value)

3. **Natural Language Fractions**:
   - "half" = 50%, "quarter" = 25%, "third" = 33.33%
   - "double" = 200%, "triple" = 300%, "quadruple" = 400%

### **Modification Validation**

- **Whitelist Validation**: Only allows modifications to whitelisted tables
- **Schema Validation**: Validates against database schema
- **Value Validation**: Ensures numeric values are valid
- **Percentage Validation**: Validates percentage calculations

---

## **State Information Flow**

The agent uses a comprehensive state system that tracks all workflow information:

### **AgentState Fields**

```python
# Core workflow fields
messages: List[BaseMessage]  # Conversation history
user_request: str  # Current user request
request_type: str  # Request classification
db_context: DatabaseContext  # Database context

# Execution results
generated_files: List[str]  # Generated file paths
execution_output: str  # Execution output
execution_error: str  # Execution errors

# Database modification specific
modification_request: Optional[Dict[str, Any]]  # Modification details
db_modification_result: Optional[Dict[str, Any]]  # Modification results

# Multi-scenario comparison specific
comparison_scenarios: List[str]  # Scenario names to compare
comparison_data: Dict[str, Any]  # Aggregated comparison data
comparison_type: str  # Type of comparison
scenario_name_mapping: Dict[str, int]  # Scenario name to ID mapping

# Edit mode specific fields
edit_mode: bool  # Whether in edit mode
editing_file_path: Optional[str]  # File being edited
original_file_content: Optional[str]  # Original file content
file_modification_history: List[Dict[str, Any]]  # Modification history

# Enhanced query tracking
query_file_mappings: Dict[str, List[str]]  # Query to file mappings
current_query_context: Optional[Dict[str, Any]]  # Current query context
```

### **Information Flow Between Nodes**

1. **Request Classification**: Analyzes user input and sets request_type
2. **Database Context**: Provides scenario-aware database routing
3. **Handler Execution**: Processes request and updates state
4. **Code Execution**: Executes generated code and captures results
5. **Response Generation**: Formats final response with context

---

## **Key Improvements in v2**

- **Simplified Architecture**: Single agent with specialized handlers instead of multiple agents
- **Scenario-Aware Database Context**: Always uses current scenario's database and file directory
- **Built-in Chat Capability**: Supports Q&A without code execution
- **Enhanced File Management**: Automatic cleanup of empty query groups
- **Improved Error Handling**: Better execution error capture and reporting
- **Multi-Scenario Support**: Architecture supports scenario comparisons
- **File Editing**: **NEW** - Comprehensive file editing with modification tracking
- **Percentage Calculations**: **NEW** - Advanced percentage-based database modifications
- **Enhanced Validation**: Comprehensive validation for all operations

---

## Repository Layout
```text
EYProjectGit/
├── backend/     # Python FastAPI server + Multi-agent LangGraph system
├── frontend/    # Angular SPA with chat interface
├── docs/        # Technical documentation and implementation guides
└── outputs/     # Generated visualizations, files, and execution logs
```

---

## Quick-Start
1. Clone the repo
   ```bash
   git clone <repository-url>
   cd EYProjectGit
   ```
2. Install dependencies
   ```bash
   # Frontend
   cd frontend && npm install && cd ..

   # Backend
   cd backend && pip install -r requirements.txt && cd ..
   ```
3. Copy the environment template and add your keys
   ```bash
   cp EY.env.example EY.env
   # edit EY.env with your API keys
   ```
4. Launch
   ```bash
   # Backend
   cd backend && python main.py &
   # Frontend (second terminal)
   cd frontend && ng serve
   ```
5. Visit http://localhost:4200

---

## Documentation Map
The **docs/** folder contains self-contained guides for every subsystem:

• [SETUP_GUIDE](docs/SETUP_GUIDE.md) – local installation & environment variables  
• [FRONTEND_STARTUP_GUIDE](docs/FRONTEND_STARTUP_GUIDE.md) – developing the Angular client  
• [SQL_INTEGRATION_GUIDE](docs/SQL_INTEGRATION_GUIDE.md) – how the agent builds, validates and runs SQL  
• [PARAMETER_SYNCHRONIZATION_GUIDE](docs/PARAMETER_SYNCHRONIZATION_GUIDE.md) – keeping Excel-originated parameters in sync with the database  
• [NEW_AGENT_WORKFLOW_IMPLEMENTATION](docs/NEW_AGENT_WORKFLOW_IMPLEMENTATION.md) – detailed explanation of the LangGraph workflow  
• [DATABASE_BROWSER_IMPLEMENTATION](docs/DATABASE_BROWSER_IMPLEMENTATION.md) – database browser implementation details  
• [HUMAN_IN_LOOP_IMPLEMENTATION_SUMMARY](docs/HUMAN_IN_LOOP_IMPLEMENTATION_SUMMARY.md) – human-in-the-loop features  
• [TEMP_FILE_MANAGEMENT](docs/TEMP_FILE_MANAGEMENT.md) – temporary file handling and cleanup

All guides focus on *how the feature works* rather than its development history or bug-fix logs.

---

## Recent Updates (v2 Agent)

### **Simplified Agent v2 Implementation**
- **Unified Architecture**: Replaced multi-agent system with single agent and specialized handlers
- **Scenario-Aware Database Context**: Proper routing to current scenario's database and file directory
- **Enhanced File Management**: Automatic cleanup of empty query groups in sidebar
- **Built-in Chat Support**: Q&A capability without code execution for general questions

### **NEW: File Editing Feature**
- **File Modification**: Support for editing existing Python files through natural language
- **Context Preservation**: Maintains original file content and modification history
- **Validation System**: Comprehensive validation of file modifications before execution
- **Query Tracking**: Maps queries to modified files for future reference
- **Execution Integration**: Modified files executed through standard pipeline
- **History Tracking**: Maintains modification history with timestamps and query IDs

### **Enhanced Database Modifications**
- **Percentage Calculations**: Support for percentage-based modifications (e.g., "increase by 10%")
- **Natural Language Fractions**: Support for "half", "quarter", "double", etc.
- **Relative Calculations**: Support for relative percentage calculations (e.g., "twice that of oxford")
- **Enhanced Validation**: Comprehensive validation for all modification types

### **Multi-Scenario Comparison System**
- **Scenario Extraction**: Automatic extraction of scenario names from natural language requests
- **Fuzzy Matching**: Intelligent scenario name resolution with fuzzy matching
- **Comparison Visualizations**: Advanced comparison charts and tables
- **Statistical Analysis**: Statistical summaries and differences across scenarios

### **Key Fixes**
- **Database Routing**: Fixed major issue where agent used wrong database path
- **File Organization**: Improved sidebar query group management with automatic cleanup
- **Error Handling**: Better execution error capture and user feedback
- **Multi-Scenario Support**: Architecture ready for future scenario comparisons

### **Workflow Diagram**
The updated workflow diagram shows the new v2 agent structure with intelligent request classification and specialized processing paths, including the new file editing feature. The diagram is generated from the actual agent code and reflects the current implementation.

---

