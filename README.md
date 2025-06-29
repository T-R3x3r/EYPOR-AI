# EYPOR-AI – AI-Powered Operations Research Platform

## Overview
EYPOR-AI is an end-to-end, AI-powered environment for data-driven decision making and optimisation. The platform features a multi-agent architecture with specialized agents handling different aspects of the workflow, all accessible through a natural language interface.

The system comprises:
- A Python/FastAPI backend with LangGraph-based agent orchestration
- An Angular frontend providing an intuitive chat interface
- Multiple specialized AI agents working in concert
- Integrated database and model management capabilities

---

## Key Capabilities
• **Intelligent Request Analysis**: Automatic classification and routing of user requests to specialized agents  
• **SQL Operations**: Natural-language queries with automatic schema discovery and validation  
• **Dynamic Visualization**: Automated generation and execution of Python/Plotly visualization code  
• **Database Management**: Parameter updates with automatic model re-execution capabilities  
• **Model Integration**: Intelligent discovery and execution of optimization models  
• **Error Recovery**: Self-healing code execution with automated fixes  
• **Human-in-the-Loop**: User-controlled model selection after database modifications  
• **Persistent Memory**: Browser-side conversation storage with context retention

---

## High-Level Agent Workflow

The system employs two specialized agents working in concert:

1. **Data Analyst Agent** (Primary Intelligence):
   - Request analysis and classification
   - SQL query generation and execution
   - Visualization script creation
   - Database modification preparation
   - Model discovery and execution
   - Response generation

2. **Code Fixer Agent** (Error Recovery):
   - Execution error analysis
   - Automated code fixes
   - Syntax and import corrections
   - Major code restructuring
   - Re-execution management

![Data Analyst Workflow](docs/images/data_analyst_workflow.png)

The workflow intelligently routes requests through:
- SQL query path for data retrieval and analysis
- Visualization path for creating charts and graphs
- Database modification path with model selection
- Error recovery path when execution issues occur

All paths converge to a response node, ensuring complete interaction cycles.

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

