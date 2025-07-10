# EYPOR-AI – AI-Powered Operations Research Platform

## Overview
EYPOR-AI is an end-to-end, AI-powered environment for data-driven decision making and optimisation. The platform features a **Simplified Agent v2** architecture that intelligently routes user requests through specialized handlers, all accessible through a natural language interface.

The system comprises:
- A Python/FastAPI backend with LangGraph-based agent orchestration
- An Angular frontend providing an intuitive chat interface
- A Simplified Agent v2 with specialized request handlers
- Integrated database and scenario management capabilities

---

## Key Capabilities
• **Intelligent Request Classification**: Automatic analysis and routing of user requests to specialized handlers  
• **SQL Operations**: Natural-language queries with automatic schema discovery and Plotly table generation  
• **Dynamic Visualization**: Automated generation and execution of Python/Plotly visualization code  
• **Database Management**: Parameter updates with scenario-aware database context  
• **Scenario Management**: Multi-scenario support with isolated databases and file directories  
• **Enhanced File Management**: Automatic cleanup of empty query groups and organized file structure  
• **Built-in Chat Capability**: Q&A support without code execution for general questions  
• **Error Handling**: Comprehensive execution error capture and user-friendly reporting  
• **Persistent Memory**: Browser-side conversation storage with context retention

---

## High-Level Agent Workflow

The system employs a **Simplified Agent v2** architecture that intelligently routes and processes user requests through specialized handlers:

### **Simplified Agent v2 Workflow**

![Simplified Agent v2 Workflow](docs/images/data_analyst_workflow.png)

The workflow features intelligent request classification and specialized processing:

1. **Request Classification** (`classify_request`):
   - Analyzes user input to determine request type
   - Routes to appropriate specialized handler
   - Supports: `chat`, `sql_query`, `visualization`, `db_modification`

2. **Specialized Handlers**:
   - **`handle_chat`**: General Q&A without code execution
   - **`handle_sql_query`**: SQL query generation and execution
   - **`handle_visualization`**: Chart/graph generation with Plotly
   - **`prepare_db_modification`**: Database parameter change preparation

3. **Code Execution** (`execute_code`):
   - Executes generated Python scripts for SQL and visualization requests
   - Captures outputs, errors, and generated files
   - Supports interactive HTML charts and data exports

4. **Database Modification** (`execute_db_modification`):
   - Performs parameter updates with validation
   - Maintains data integrity across scenarios
   - Supports model re-execution capabilities

5. **Response Generation** (`respond`):
   - Formats final responses with context
   - Includes generated files and execution results
   - Provides user-friendly output formatting

### **Workflow Paths**

- **Chat Path**: `START → classify_request → handle_chat → respond → END`
- **SQL Path**: `START → classify_request → handle_sql_query → execute_code → respond → END`
- **Visualization Path**: `START → classify_request → handle_visualization → execute_code → respond → END`
- **DB Modification Path**: `START → classify_request → prepare_db_modification → execute_db_modification → respond → END`

### **Key Improvements in v2**

- **Simplified Architecture**: Single agent with specialized handlers instead of multiple agents
- **Scenario-Aware Database Context**: Always uses current scenario's database and file directory
- **Built-in Chat Capability**: Supports Q&A without code execution
- **Enhanced File Management**: Automatic cleanup of empty query groups
- **Improved Error Handling**: Better execution error capture and reporting
- **Multi-Scenario Support**: Architecture supports future scenario comparisons

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

### **Key Fixes**
- **Database Routing**: Fixed major issue where agent used wrong database path
- **File Organization**: Improved sidebar query group management with automatic cleanup
- **Error Handling**: Better execution error capture and user feedback
- **Multi-Scenario Support**: Architecture ready for future scenario comparisons

### **Workflow Diagram**
The updated workflow diagram shows the new v2 agent structure with intelligent request classification and specialized processing paths. The diagram is generated from the actual agent code and reflects the current implementation.

---

