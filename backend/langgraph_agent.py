import os
import time
from typing import Dict, List, Tuple, Literal, Annotated
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from typing_extensions import TypedDict
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv
# Fallback agent configuration
class AgentConfig:
    def __init__(self, system_prompt="", max_execution_time=60):
        self.system_prompt = system_prompt
        self.max_execution_time = max_execution_time

def get_default_agent():
    return "data_analyst"

def get_agent_config(agent_type):
    configs = {
        "data_analyst": AgentConfig("You are a data analyst.", 60),
        "code_fixer": AgentConfig("""You are an intelligent code fixer. Analyze execution errors and fix the code.

IMPORTANT: You must respond in one of these exact formats:

For simple fixes (syntax errors, missing imports, etc.):
FIX_AND_EXECUTE: [filename]
[fixed code content]

For complex fixes (logic errors, major restructuring):
MAJOR_FIX_NEEDED: [filename]
[fixed code content]

For legacy compatibility:
CREATE_FILE: [filename]
[fixed code content]

DO NOT explain the problem in chat - fix the code directly using one of the above formats.
Always provide the complete fixed code, not just explanations.""", 60),
        "database_modifier": AgentConfig("You are a database modifier.", 60)
    }
    return configs.get(agent_type, AgentConfig())
import re
import sqlite3
import glob
import pandas as pd
import uuid

# LangGraph memory imports
try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.checkpoint.sqlite import SqliteSaver
    CHECKPOINTER_AVAILABLE = True
except ImportError:
    print("Warning: LangGraph checkpointers not available. Using manual memory.")
    CHECKPOINTER_AVAILABLE = False

# Load environment variables
load_dotenv("../EY.env")

class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    files: Dict[str, str]
    temp_dir: str
    execution_output: str
    execution_error: str
    created_files: List[str]
    retry_count: int
    current_file: str
    has_execution_error: bool
    last_error_type: str
    # New fields for planning workflow
    execution_plan: str
    required_files: List[str]
    analysis_type: str
    selected_file_contents: Dict[str, str]
    # New fields for SQL integration
    database_schema: Dict[str, any]
    database_path: str
    # New fields for action-based routing
    action_type: str
    action_result: str
    db_modification_result: Dict[str, any]
    # User feedback field (kept for model selection)
    user_feedback: str
    # New fields for SQL Query Pipeline
    generated_sql: str
    sql_validation_result: Dict[str, any]
    query_execution_result: Dict[str, any]
    interpretation_response: str
    # New fields for enhanced data analyst workflow
    request_type: str
    sql_query_result: str
    visualization_request: str
    modification_request: Dict[str, any]
    identified_tables: List[str]
    identified_columns: List[str]
    current_values: Dict[str, any]
    new_values: Dict[str, any]
    modification_sql: str
    available_models: List[str]
    selected_models: List[str]
    model_execution_results: List[str]

class CodeExecutorAgent:
    def __init__(self, ai_model: str = "openai", temp_dir: str = "", agent_type: str = None):
        self.ai_model = ai_model
        self.temp_dir = temp_dir
        self.agent_type = agent_type or "data_analyst"
        self.config = get_agent_config(self.agent_type)
        
        # Initialize LLM
        if ai_model == "openai":
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=4000
            )
        else:
            # Fallback to default
            self.llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=4000
            )
        
        # Initialize memory system
        self.checkpointer = self._initialize_memory()
        
        # Build and compile the graph
        self.graph = self._build_graph()
        
        # Compile the graph
        if self.checkpointer:
            self.graph = self.graph.compile(checkpointer=self.checkpointer)
            print("DEBUG: Graph compiled with memory checkpointer")
        else:
            # TEMPORARILY DISABLED: Memory system causing duplicate executions
            self.graph = self.graph.compile()
            print("DEBUG: Graph compiled WITHOUT memory checkpointer")
        
        # Execution tracking
        self.execution_counter = 0
        self.last_request_hash = None
        
        # Initialize execution output tracking for the execution window
        self.last_execution_output = ""
        self.last_execution_error = ""
        self.last_action_type = ""
        
        # Cache for database schema (set externally)
        self.cached_database_schema = None
    
    def _initialize_memory(self):
        """Initialize memory system for conversation persistence"""
        # TEMPORARILY DISABLED: Memory system causing duplicate executions
        print("DEBUG: Memory system temporarily disabled to prevent duplicates")
        self.checkpointer = None
        return
        
        # Original memory initialization (commented out)
        # try:
        #     # Try to initialize in-memory checkpointer for session-based memory
        #     from langgraph.checkpoint.memory import MemorySaver
        #     self.checkpointer = MemorySaver()
        #     print("DEBUG: Initialized in-memory checkpointer (session-based)")
        # except Exception as e:
        #     print(f"DEBUG: Failed to initialize memory system: {e}")
        #     self.checkpointer = None
    
    def _build_graph(self):
        """Build the LangGraph workflow based on agent type"""
        workflow = StateGraph(AgentState)
        
        # Main Data Analyst workflow - handles all database-related requests
        if self.agent_type == "data_analyst":
            # Core workflow nodes
            workflow.add_node("analyze_request", self._analyze_data_request)
            workflow.add_node("execute_sql_query", self._execute_sql_query_node)
            workflow.add_node("create_visualization", self._create_visualization_node)
            workflow.add_node("prepare_db_modification", self._prepare_db_modification_node)
            workflow.add_node("database_modifier", self._database_modifier_node)
            workflow.add_node("execute_db_modification", self._execute_db_modification_node)
            workflow.add_node("find_and_run_models", self._find_and_run_models_node)
            workflow.add_node("request_model_selection", self._request_model_selection_node)
            workflow.add_node("execute_selected_models", self._execute_selected_models_node)
            workflow.add_node("execute_file", self._execute_file)
            workflow.add_node("code_fixer", self._code_fixer_node)
            workflow.add_node("respond", self._respond)
            
            # Start with request analysis
            workflow.add_edge(START, "analyze_request")
            
            # Route based on request type
            workflow.add_conditional_edges(
                "analyze_request",
                self._route_data_request,
                {
                    "sql_query": "execute_sql_query",
                    "visualization": "create_visualization",
                    "db_modification": "prepare_db_modification",
                    "respond": "respond"
                }
            )
            
            # SQL query path - now creates and executes a Python file
            workflow.add_edge("execute_sql_query", "execute_file")
            
            # Visualization path
            workflow.add_edge("create_visualization", "execute_file")
            
            # Database modification path - direct execution without approval, no automatic model run
            workflow.add_edge("prepare_db_modification", "execute_db_modification")
            workflow.add_edge("execute_db_modification", "respond")
            
            # Model execution path
            workflow.add_conditional_edges(
                "find_and_run_models",
                self._route_model_execution,
                {
                    "run_all": "execute_selected_models",
                    "select_models": "request_model_selection",
                    "no_models": "respond"
                }
            )
            workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
            workflow.add_edge("execute_selected_models", "respond")
            
            # File execution and error handling
            workflow.add_conditional_edges(
                "execute_file",
                self._execution_router,
                {
                    "success": "respond",
                    "retry": "code_fixer",
                    "error": "respond"
                }
            )
            
            workflow.add_conditional_edges(
                "code_fixer",
                self._code_fixer_router,
                {
                    "execute": "execute_file",
                    "major_fix": "create_visualization",
                    "respond": "respond"
                }
            )
            
            workflow.add_edge("respond", END)
            
        # Database Modifier workflow - handles the actual database modifications (no approval needed)
        elif self.agent_type == "database_modifier":
            workflow.add_node("analyze_modification", self._analyze_modification_request)
            workflow.add_node("prepare_modification", self._prepare_modification_node)
            workflow.add_node("execute_modification", self._execute_modification_node)
            workflow.add_node("find_models", self._find_models_node)
            workflow.add_node("request_model_selection", self._request_model_selection_node)
            workflow.add_node("execute_models", self._execute_models_node)
            workflow.add_node("respond", self._respond)
            
            workflow.add_edge(START, "analyze_modification")
            workflow.add_edge("analyze_modification", "prepare_modification")
            workflow.add_edge("prepare_modification", "execute_modification")
            workflow.add_edge("execute_modification", "find_models")
            
            workflow.add_conditional_edges(
                "find_models",
                self._route_model_execution,
                {
                    "run_all": "execute_models",
                    "select_models": "request_model_selection",
                    "no_models": "respond"
                }
            )
            workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
            workflow.add_edge("execute_models", "respond")
            workflow.add_edge("respond", END)

        else:
            # For unsupported agent types, create a simple error workflow
            workflow.add_node("respond", self._respond)
            workflow.add_edge(START, "respond")
            workflow.add_edge("respond", END)
            
        return workflow



    def _query_gen_node(self, state: AgentState) -> AgentState:
        """Step 1: Generate SQL query from user question"""
        last_message = state["messages"][-1].content if state["messages"] else ""
        
        print(f"DEBUG: Query Generation - Processing: {last_message}")
        
        # Get cached database schema
        schema_info = self._get_cached_database_schema()
        
        if not schema_info:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="No Database Available")]
            }
        
        # Build schema context
        schema_context = self._build_schema_context(schema_info)
        
        system_prompt = f"""You are in the QUERY GENERATION step of the SQL pipeline.

DATABASE SCHEMA:
{schema_context}

USER QUESTION: {last_message}

Your task: Convert the user's question into a valid SQL query.

RULES:
1. Generate ONLY the SQL query, no explanations
2. Use proper table and column names from the schema
3. Include appropriate JOINs when combining tables
4. Use LIMIT clauses for large result sets (default LIMIT 100)
5. Handle aggregations (COUNT, SUM, AVG) when appropriate
6. Ensure proper WHERE clauses for filtering

RESPONSE FORMAT:
Return only the SQL query, nothing else."""
        
        try:
            response = self.llm.invoke([HumanMessage(content=system_prompt)])
            generated_sql = response.content.strip()
            
            # Clean up the SQL (remove markdown formatting if present)
            if generated_sql.startswith("```sql"):
                generated_sql = generated_sql.replace("```sql", "").replace("```", "").strip()
            elif generated_sql.startswith("```"):
                generated_sql = generated_sql.replace("```", "").strip()
            
            print(f"DEBUG: Generated SQL: {generated_sql}")
            
            return {
                **state,
                "generated_sql": generated_sql,
                "database_schema": schema_info
            }
            
        except Exception as e:
            print(f"DEBUG: Query generation error: {e}")
            return {
                **state,
                "generated_sql": "",
                "messages": state["messages"] + [AIMessage(content=f"❌ **Query Generation Error**: {str(e)}")]
            }

    def _query_check_node(self, state: AgentState) -> AgentState:
        """Step 2: Validate the generated SQL query"""
        generated_sql = state.get("generated_sql", "")
        
        print(f"DEBUG: Query Validation - Checking: {generated_sql}")
        
        if not generated_sql:
            return {
                **state,
                "sql_validation_result": {"valid": False, "error": "No SQL query to validate"},
                "messages": state["messages"] + [AIMessage(content="❌ **Validation Error**: No SQL query was generated")]
            }
        
        # Get schema for validation
        schema_info = state.get("database_schema", {})
        schema_context = self._build_schema_context(schema_info)
        
        system_prompt = f"""You are in the QUERY VALIDATION step of the SQL pipeline.

DATABASE SCHEMA:
{schema_context}

SQL QUERY TO VALIDATE:
{generated_sql}

Your task: Validate this SQL query for syntax and logical correctness.

CHECK FOR:
1. SQL syntax correctness
2. Table names exist in schema
3. Column names exist in tables
4. JOIN conditions are logical
5. WHERE clause logic is sound
6. Aggregation usage is appropriate

RESPONSE FORMAT:
Return ONLY one of:
- "VALID" if query is correct
- "INVALID: [specific reason]" if query has issues"""
        
        try:
            response = self.llm.invoke([HumanMessage(content=system_prompt)])
            validation_response = response.content.strip()
            
            # Remove quotes if present
            if validation_response.startswith('"') and validation_response.endswith('"'):
                validation_response = validation_response[1:-1]
            
            is_valid = validation_response.upper().startswith("VALID")
            error_msg = validation_response if not is_valid else ""
            
            print(f"DEBUG: Validation result: {validation_response}, is_valid: {is_valid}")
            
            return {
                **state,
                "sql_validation_result": {
                    "valid": is_valid,
                    "error": error_msg,
                    "response": validation_response
                }
            }
            
        except Exception as e:
            print(f"DEBUG: Query validation error: {e}")
            return {
                **state,
                "sql_validation_result": {"valid": False, "error": f"Validation failed: {str(e)}"},
                "messages": state["messages"] + [AIMessage(content=f"❌ **Validation Error**: {str(e)}")]
            }

    def _query_execute_node(self, state: AgentState) -> AgentState:
        """Step 3: Execute the validated SQL query"""
        generated_sql = state.get("generated_sql", "")
        validation_result = state.get("sql_validation_result", {})
        
        print(f"DEBUG: Query Execution - SQL: {generated_sql}")
        
        # Check if query is valid
        is_valid = validation_result.get("valid", False)
        print(f"DEBUG: Query execution - validation_result: {validation_result}")
        print(f"DEBUG: Query execution - is_valid: {is_valid}")
        
        if not is_valid:
            error_msg = validation_result.get("error", "Query validation failed")
            return {
                **state,
                "query_execution_result": {"success": False, "error": error_msg},
                "messages": state["messages"] + [AIMessage(content=f"❌ **Cannot Execute**: {error_msg}")]
            }
        
        # Execute the SQL query
        try:
            schema_info = state.get("database_schema", {})
            db_path = schema_info.get("database_path", "")
            
            if not db_path or not os.path.exists(db_path):
                return {
                    **state,
                    "query_execution_result": {"success": False, "error": "Database file not found"},
                    "messages": state["messages"] + [AIMessage(content="❌ **Database Error**: Database file not accessible")]
                }
            
            # Connect and execute query
            import sqlite3
            import pandas as pd
            
            conn = sqlite3.connect(db_path)
            
            # Execute query and get results
            if generated_sql.strip().upper().startswith(('SELECT', 'WITH')):
                # For SELECT queries, return data
                df = pd.read_sql_query(generated_sql, conn)
                result_data = df.to_dict('records')
                columns = list(df.columns)
                row_count = len(df)
                
                execution_result = {
                    "success": True,
                    "data": result_data,
                    "columns": columns,
                    "row_count": row_count,
                    "query": generated_sql
                }
            else:
                # For other queries (INSERT, UPDATE, DELETE)
                cursor = conn.cursor()
                cursor.execute(generated_sql)
                conn.commit()
                rows_affected = cursor.rowcount
                
                execution_result = {
                    "success": True,
                    "rows_affected": rows_affected,
                    "query": generated_sql,
                    "operation_type": "modification"
                }
            
            conn.close()
            
            print(f"DEBUG: Query executed successfully - {execution_result.get('row_count', execution_result.get('rows_affected', 0))} rows")
            
            return {
                **state,
                "query_execution_result": execution_result
            }
            
        except Exception as e:
            print(f"DEBUG: Query execution error: {e}")
            return {
                **state,
                "query_execution_result": {"success": False, "error": str(e)},
                "messages": state["messages"] + [AIMessage(content=f"❌ **Execution Error**: {str(e)}")]
            }

    def _result_interpret_node(self, state: AgentState) -> AgentState:
        """Step 4: Interpret raw query results into human-friendly response"""
        execution_result = state.get("query_execution_result", {})
        generated_sql = state.get("generated_sql", "")
        last_message = state["messages"][-1].content if state["messages"] else ""
        
        print(f"DEBUG: Result Interpretation - Processing results")
        
        if not execution_result.get("success", False):
            error_msg = execution_result.get("error", "Query execution failed")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"❌ **Failed to get results**: {error_msg}")]
            }
        
        # Get schema for context
        schema_info = state.get("database_schema", {})
        schema_context = self._build_schema_context(schema_info)
        
        # Prepare results summary for LLM
        if "data" in execution_result:
            # SELECT query results
            data = execution_result["data"]
            columns = execution_result["columns"]
            row_count = execution_result["row_count"]
            
            # Create summary of results (first 10 rows max)
            results_preview = data[:10] if len(data) > 10 else data
            results_summary = f"""
QUERY RESULTS SUMMARY:
- Total rows: {row_count}
- Columns: {', '.join(columns)}
- Sample data (first {len(results_preview)} rows):
{results_preview}
"""
        else:
            # Modification query results
            rows_affected = execution_result.get("rows_affected", 0)
            operation_type = execution_result.get("operation_type", "modification")
            results_summary = f"""
QUERY EXECUTION SUMMARY:
- Operation: {operation_type}
- Rows affected: {rows_affected}
"""
        
        system_prompt = f"""You are in the RESULT INTERPRETATION step of the SQL pipeline.

ORIGINAL USER QUESTION: {last_message}

SQL QUERY EXECUTED:
{generated_sql}

{results_summary}

DATABASE SCHEMA CONTEXT:
{schema_context}

Your task: Convert these raw results into a clear, human-friendly response.

GUIDELINES:
1. Explain what the query did in plain English
2. Summarize the key findings from the results
3. Provide meaningful insights based on the data
4. Format numbers and text appropriately
5. Suggest follow-up questions if relevant
6. Use markdown formatting for better readability

Be helpful, clear, and educational in your response."""
        
        try:
            response = self.llm.invoke([HumanMessage(content=system_prompt)])
            
            return {
                **state,
                "interpretation_response": response.content,
                "messages": state["messages"] + [response]
            }
            
        except Exception as e:
            print(f"DEBUG: Result interpretation error: {e}")
            # Fallback to basic result display
            fallback_response = self._create_fallback_response(execution_result, generated_sql)
            return {
                **state,
                "interpretation_response": fallback_response,
                "messages": state["messages"] + [AIMessage(content=fallback_response)]
            }

    def _create_fallback_response(self, execution_result: Dict, sql_query: str) -> str:
        """Create a basic response when interpretation fails"""
        if "data" in execution_result:
            row_count = execution_result.get("row_count", 0)
            columns = execution_result.get("columns", [])
            return f"""✅ **Query Executed Successfully**

**SQL Query:** `{sql_query}`

**Results:**
- Found {row_count} rows
- Columns: {', '.join(columns)}

The query completed successfully. Here are the raw results from your database."""
        else:
            rows_affected = execution_result.get("rows_affected", 0)
            return f"""✅ **Query Executed Successfully**

**SQL Query:** `{sql_query}`

**Result:** {rows_affected} rows were affected by this operation."""

    def _build_schema_context(self, schema_info: Dict[str, any]) -> str:
        """Build a formatted context string from schema information"""
        if not schema_info or not schema_info.get("tables"):
            return "No tables found in database."
        
        context_lines = []
        context_lines.append(f"DATABASE OVERVIEW:")
        context_lines.append(f"- Total tables: {schema_info.get('total_tables', 0)}")
        context_lines.append(f"- Database file: {os.path.basename(schema_info.get('database_path', 'unknown'))}")
        context_lines.append("")
        
        # tables is a list, not a dictionary
        tables_list = schema_info["tables"]
        for table_info in tables_list:
            table_name = table_info.get("name", "Unknown")
            context_lines.append(f"TABLE: {table_name}")
            context_lines.append(f"- Row count: {table_info.get('row_count', 0)}")
            
            columns = table_info.get("columns", [])
            context_lines.append(f"- Columns ({len(columns)}):")
            
            for col_info in columns:
                col_name = col_info.get("name", "unknown")
                col_type = col_info.get("type", "UNKNOWN")
                context_lines.append(f"  * {col_name} ({col_type})")
            
            # Add sample data if available
            sample_data = table_info.get("sample_data", [])
            if sample_data:
                # For parameter tables, show more data to help identify specific parameters
                if 'param' in table_name.lower() or 'config' in table_name.lower() or 'setting' in table_name.lower():
                    context_lines.append(f"- ALL data in {table_name} ({len(sample_data)} rows):")
                    for i, row in enumerate(sample_data):  # Show all rows for parameter tables
                        row_str = ", ".join([f"{k}={v}" for k, v in row.items()])
                        context_lines.append(f"  Row {i+1}: {row_str}")
                else:
                    context_lines.append(f"- Sample data ({len(sample_data)} rows):")
                    for i, row in enumerate(sample_data[:3]):  # Show max 3 sample rows for regular tables
                        row_str = ", ".join([f"{k}={v}" for k, v in list(row.items())[:3]])  # Show max 3 columns
                        context_lines.append(f"  Row {i+1}: {row_str}...")
            
            context_lines.append("")
        
        return "\n".join(context_lines)

    def set_cached_schema(self, schema: Dict[str, any]):
        """Set the cached database schema"""
        self.cached_database_schema = schema
        print(f"DEBUG: Cached database schema set with {schema.get('total_tables', 0)} tables")

    def _get_cached_database_schema(self) -> Dict[str, any]:
        """Get cached database schema"""
        return self.cached_database_schema



    def _code_fixer_node(self, state: AgentState) -> AgentState:
        """Intelligent code fixer agent - analyzes and fixes execution errors"""
        # Get the current file that had errors
        current_file = state.get("current_file", "")
        if not current_file or current_file not in state["files"]:
            return {**state, "messages": state["messages"] + [AIMessage(content="❌ No file to fix")]}
        
        # Read the current file content
        file_path = state["files"][current_file]
        try:
            with open(file_path, 'r') as f:
                file_content = f.read()
        except Exception as e:
            return {**state, "messages": state["messages"] + [AIMessage(content=f"❌ Could not read file: {str(e)}")]}
        
        # Use intelligent code fixer configuration
        code_fixer_config = get_agent_config("code_fixer")
        system_prompt = f"""{code_fixer_config.system_prompt}
        
        FILE TO FIX: {current_file}
        RETRY COUNT: {state.get("retry_count", 0)}
        
        CURRENT FILE CONTENT:
{file_content}

        EXECUTION ERROR:
{state.get("execution_error", "No error details")}

        ERROR TYPE: {state.get("last_error_type", "Unknown")}
        
        TASK: Fix the code error and provide the corrected version using the required format.
        
        IMPORTANT: 
        - If you see markdown artifacts (```) in the code, remove them completely
        - If there are syntax errors, fix the Python syntax
        - If there are missing imports, add them
        - Provide the complete fixed code, not just explanations
        
        Respond with either FIX_AND_EXECUTE: or MAJOR_FIX_NEEDED: followed by the filename and complete fixed code.
        """
        
        response = self.llm.invoke([HumanMessage(content=system_prompt)])
        
        # Process the response with the new code_fixer logic
        return self._process_code_fixer_response(state, response)

    def _process_code_fixer_response(self, state: AgentState, response: AIMessage) -> AgentState:
        """Process intelligent code fixer response with new routing logic"""
        response_content = response.content
        
        print(f"DEBUG: Processing code_fixer response: {response_content[:300]}...")
        
        # Extract fix type and code
        filename = None
        code_content = ""
        fix_type = "unknown"
        
        # Check for FIX_AND_EXECUTE format
        if "FIX_AND_EXECUTE:" in response_content:
            fix_type = "simple"
            fix_idx = response_content.find("FIX_AND_EXECUTE:")
            file_section = response_content[fix_idx:]
            lines = file_section.split("\n", 1)
            filename = lines[0].replace("FIX_AND_EXECUTE:", "").strip()
            code_content = lines[1] if len(lines) > 1 else ""
            print(f"DEBUG: Simple fix detected - Filename: {filename}")
            
        # Check for MAJOR_FIX_NEEDED format
        elif "MAJOR_FIX_NEEDED:" in response_content:
            fix_type = "major"
            fix_idx = response_content.find("MAJOR_FIX_NEEDED:")
            file_section = response_content[fix_idx:]
            lines = file_section.split("\n", 1)
            filename = lines[0].replace("MAJOR_FIX_NEEDED:", "").strip()
            code_content = lines[1] if len(lines) > 1 else ""
            print(f"DEBUG: Major fix detected - Filename: {filename}")
            
        # Fallback: look for CREATE_FILE (old format)
        elif "CREATE_FILE:" in response_content:
            fix_type = "legacy"
            create_file_idx = response_content.find("CREATE_FILE:")
            file_section = response_content[create_file_idx:]
            lines = file_section.split("\n", 1)
            filename = lines[0].replace("CREATE_FILE:", "").strip()
            code_content = lines[1] if len(lines) > 1 else ""
            print(f"DEBUG: Legacy CREATE_FILE format - Filename: {filename}")
        
        if filename and code_content:
            print(f"DEBUG: Code fixer processing - Fix type: {fix_type}, Filename: {filename}")
            
            # Clean filename
            if not filename.endswith('.py'):
                filename += '.py'
            
            # Write the fixed file
            file_path = os.path.join(state["temp_dir"], filename)
            try:
                # Clean up any markdown artifacts and backticks
                code_content = self._clean_markdown_artifacts(code_content)
                
                # Auto-fix common issues before writing
                code_content = self._fix_gui_code(code_content)
                code_content = self._fix_file_paths(code_content)
                
                print(f"DEBUG: Writing fixed file to: {file_path}")
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code_content)
                
                # Update state
                new_created_files = state["created_files"] if filename in state["created_files"] else state["created_files"] + [filename]
                new_files = {**state["files"], filename: file_path}
                
                # Increment retry count
                new_retry_count = state.get("retry_count", 0) + 1
                
                # Create appropriate message based on fix type
                if fix_type == "simple":
                    success_message = f"🔧 Quick fix applied to {filename} (attempt {new_retry_count})"
                elif fix_type == "major":
                    success_message = f"🛠️ Major fix applied to {filename} (attempt {new_retry_count}) - please review output"
                else:
                    success_message = f"🔧 Fixed {filename} (attempt {new_retry_count})"
                
                new_messages = state["messages"] + [AIMessage(content=success_message)]
                
                print(f"DEBUG: Code fixer completed successfully: {filename}, fix type: {fix_type}")
                
                return {
                    **state,
                    "created_files": new_created_files,
                    "files": new_files,
                    "messages": new_messages,
                    "current_file": filename,
                    "retry_count": new_retry_count,
                    "has_execution_error": False,  # Reset error flag
                    "last_error_type": ""  # Clear error type
                }
                
            except Exception as e:
                print(f"DEBUG: Error writing fixed file: {str(e)}")
                new_messages = state["messages"] + [AIMessage(content=f"❌ Error writing fixed file {filename}: {str(e)}")]
                return {**state, "messages": new_messages}
        
        print(f"DEBUG: Code fixer - No valid fix found in response")
        
        # Fallback: Try to automatically fix common markdown issues
        if state.get("last_error_type") == "SyntaxError" and "```" in state.get("execution_error", ""):
            print(f"DEBUG: Attempting automatic markdown cleanup for {current_file}")
            try:
                # Read the current file
                file_path = state["files"][current_file]
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_content = f.read()
                
                # Clean up markdown artifacts
                cleaned_content = self._clean_markdown_artifacts(current_content)
                
                # Write the cleaned file
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_content)
                
                print(f"DEBUG: Automatic markdown cleanup completed for {current_file}")
                
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=f"🔧 Automatic fix applied: Removed markdown artifacts from {current_file}")],
                    "has_execution_error": False,
                    "last_error_type": ""
                }
            except Exception as e:
                print(f"DEBUG: Automatic cleanup failed: {str(e)}")
        
        # If no code was extracted, just add the response as a message
        return {**state, "messages": state["messages"] + [response]}

    def _process_agent_response(self, state: AgentState, response: AIMessage, agent_type: str) -> AgentState:
        """Process agent response and create/update files"""
        response_content = response.content
        
        print(f"DEBUG: Processing {agent_type} response: {response_content[:300]}...")
        
        # Enhanced extraction for different formats (reusing existing logic)
        filename = None
        code_content = ""
        
        # Method 1: Look for CREATE_FILE directive
        create_file_idx = response_content.find("CREATE_FILE:")
        if create_file_idx != -1:
            file_section = response_content[create_file_idx:]
            lines = file_section.split("\n", 1)
            filename = lines[0].replace("CREATE_FILE:", "").strip()
            code_content = lines[1] if len(lines) > 1 else ""
            print(f"DEBUG: Found CREATE_FILE directive - Filename: {filename}")
        
        # Method 2: Extract from markdown blocks for data_analyst
        elif agent_type == "data_analyst" and "```" in response_content:
            print("DEBUG: Data analyst - extracting from markdown blocks")
            if "```python" in response_content:
                start_idx = response_content.find("```python") + len("```python")
                end_idx = response_content.find("```", start_idx)
                if end_idx != -1:
                    code_content = response_content[start_idx:end_idx].strip()
            elif "```" in response_content:
                start_idx = response_content.find("```") + 3
                end_idx = response_content.find("```", start_idx)
                if end_idx != -1:
                    code_content = response_content[start_idx:end_idx].strip()
            
            import time
            filename = f"data_analysis_{int(time.time())}.py"
            print(f"DEBUG: Generated filename: {filename}")
        
        print(f"DEBUG: Extracted filename: {filename}")
        print(f"DEBUG: Extracted code length: {len(code_content)}")
        
        if filename and code_content:
            print(f"DEBUG: {agent_type} processing file - Filename: {filename}, Content length: {len(code_content)}")
            
            # Clean filename
            if not filename.endswith('.py'):
                filename += '.py'
            
            # Write file to project directory
            file_path = os.path.join(state["temp_dir"], filename)
            print(f"DEBUG: Writing file to: {file_path}")
            try:
                # Clean up any markdown artifacts and backticks
                code_content = self._clean_markdown_artifacts(code_content)
                
                # Auto-fix common issues before writing
                code_content = self._fix_gui_code(code_content)
                code_content = self._fix_file_paths(code_content)
                
                print(f"DEBUG: Writing file to: {file_path}")
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code_content)
                
                print(f"DEBUG: File written successfully: {file_path}")
                
                # Update state
                new_created_files = state["created_files"] + [filename] if filename not in state["created_files"] else state["created_files"]
                new_files = {**state["files"], filename: file_path}
                
                # IMPORTANT: Only add a brief success message to chat, NOT the full response with code
                success_message = f"📄 Created: {filename}"
                if agent_type == "code_fixer":
                    success_message = f"🔧 Fixed: {filename}"
                
                new_messages = state["messages"] + [AIMessage(content=success_message)]
                
                print(f"DEBUG: File created/updated successfully by {agent_type}: {filename}")
                
                return {
                    **state,
                    "created_files": new_created_files,
                    "files": new_files,
                    "messages": new_messages,
                    "current_file": filename
                }
                
            except Exception as e:
                print(f"DEBUG: Error creating/updating file: {str(e)}")
                new_messages = state["messages"] + [AIMessage(content=f"❌ Error creating file {filename}: {str(e)}")]
                return {**state, "messages": new_messages}
        
        print(f"DEBUG: {agent_type} - No valid code content found in response")
        # Only show the response in chat if no code was found (this means it's a regular text response)
        return {**state, "messages": state["messages"] + [response]}

    def _analyst_router(self, state: AgentState) -> Literal["execute", "respond"]:
        """Route based on analyst response"""
        if state.get("analysis_type") == "impossible_request":
            print("DEBUG: Impossible request - skipping to response")
            return "respond"
        else:
            print("DEBUG: Normal request - proceeding to execution")
            return "execute"

    def _execution_router(self, state: AgentState) -> str:
        """Route after file execution with human-in-the-loop checks"""
        print(f"DEBUG: Execution router - has_execution_error: {state.get('has_execution_error')}")
        print(f"DEBUG: Execution router - retry_count: {state.get('retry_count', 0)}")
        print(f"DEBUG: Execution router - last_error_type: {state.get('last_error_type', 'None')}")
        
        # Check if execution was successful
        if not state.get("has_execution_error"):
            print("DEBUG: Execution router - No error, routing to success")
            return "success"
        
        # Handle special cases that should not trigger retries
        last_error_type = state.get("last_error_type", "")
        if last_error_type in ["DuplicateRequest", "AlreadyProcessed", "FileNotFound"]:
            print(f"DEBUG: Execution router - Special error type '{last_error_type}', routing to success")
            return "success"
        
        # Check for dangerous operations that need approval
        current_file = state.get("current_file", "")
        if any(keyword in current_file.lower() for keyword in ["delete", "remove", "drop", "truncate"]):
            print("DEBUG: Execution router - Dangerous operation, requesting approval")
            return "request_approval"
        
        # Check retry count
        retry_count = state.get("retry_count", 0)
        if retry_count >= 2:  # Max 2 retries
            print("DEBUG: Execution router - Max retries reached, routing to error")
            return "error"
        else:
            print("DEBUG: Execution router - Retry count < 2, routing to retry")
            return "retry"

    def _code_fixer_router(self, state: AgentState) -> Literal["execute", "major_fix", "respond"]:
        """Route based on code_fixer response"""
        last_response = state["messages"][-1].content if state["messages"] else ""
        
        print(f"DEBUG: Code fixer router - Last response: {last_response[:200]}...")
        print(f"DEBUG: Code fixer router - Contains FIX_AND_EXECUTE: {'FIX_AND_EXECUTE:' in last_response}")
        print(f"DEBUG: Code fixer router - Contains MAJOR_FIX_NEEDED: {'MAJOR_FIX_NEEDED:' in last_response}")
        
        if "FIX_AND_EXECUTE:" in last_response:
            print("DEBUG: Simple fix completed - routing directly to execution")
            return "execute"
        elif "MAJOR_FIX_NEEDED:" in last_response:
            print("DEBUG: Major fix completed - routing to respond with explanation")
            return "major_fix"
        else:
            print("DEBUG: Code fixer didn't use expected format - routing to respond")
            return "respond"

    def _analyze_request(self, state: AgentState) -> AgentState:
        """Analyze the user request to determine what action to take"""
        last_message = state["messages"][-1].content
        
        # Get list of available files in the working directory
        available_files = []
        if state["temp_dir"] and os.path.exists(state["temp_dir"]):
            try:
                available_files = [f for f in os.listdir(state["temp_dir"]) 
                                 if os.path.isfile(os.path.join(state["temp_dir"], f))]
            except Exception:
                available_files = []
        
        # Build file context
        files_context = ""
        if available_files:
            files_context = f"\nAVAILABLE FILES IN PROJECT DIRECTORY:\n" + "\n".join(f"- {f}" for f in available_files)
        else:
            files_context = "\nNo files currently available in project directory."
        
        # Use the configured system prompt for this agent type
        system_prompt = f"""{self.config.system_prompt}
        
        PROJECT CONTEXT:
        Working directory: {state["temp_dir"] or "Not set"}
        {files_context}
        
        Current execution output context:
        STDOUT: {state["execution_output"]}
        STDERR: {state["execution_error"]}
        
        User request: {last_message}
        """
        
        response = self.llm.invoke([HumanMessage(content=system_prompt)])
        return {**state, "messages": state["messages"] + [response]}
    
    def _should_create_file(self, state: AgentState) -> Literal["create", "execute", "respond"]:
        """Decision function to route based on agent analysis"""
        last_response = state["messages"][-1].content
        
        print(f"DEBUG: Agent response analysis: {last_response[:300]}...")  # Debug logging
        
        # For data_analyst, if response contains code or data analysis terms, force file creation
        if (self.agent_type == "data_analyst" and 
            ("import " in last_response or "pandas" in last_response or "matplotlib" in last_response or 
             "plt." in last_response or "DataFrame" in last_response or "```" in last_response)):
            print("DEBUG: Data analyst detected code - forcing file creation")
            return "create"
        elif "CREATE_FILE:" in last_response:
            print("DEBUG: Routing to create_file")
            return "create"
        elif "EXECUTE_FILE:" in last_response:
            print("DEBUG: Routing to execute_file")
            return "execute"
        else:
            print("DEBUG: Routing to respond")
            return "respond"
    
    def _create_file(self, state: AgentState) -> AgentState:
        """Create a new Python file"""
        last_response = state["messages"][-1].content
        
        # Enhanced extraction for different formats
        filename = None
        code_content = ""
        
        # Method 1: Look for CREATE_FILE directive
        create_file_idx = last_response.find("CREATE_FILE:")
        if create_file_idx != -1:
            file_section = last_response[create_file_idx:]
            lines = file_section.split("\n", 1)
            filename = lines[0].replace("CREATE_FILE:", "").strip()
            code_content = lines[1] if len(lines) > 1 else ""
            print(f"DEBUG: Found CREATE_FILE directive - Filename: {filename}")
        
        # Method 2: If no CREATE_FILE, but it's data_analyst with code, extract from markdown
        elif self.agent_type == "data_analyst" and "```" in last_response:
            print("DEBUG: Data analyst - extracting from markdown blocks")
            # Extract code from first markdown block
            if "```python" in last_response:
                start_idx = last_response.find("```python") + len("```python")
                end_idx = last_response.find("```", start_idx)
                if end_idx != -1:
                    code_content = last_response[start_idx:end_idx].strip()
            elif "```" in last_response:
                start_idx = last_response.find("```") + 3
                end_idx = last_response.find("```", start_idx)
                if end_idx != -1:
                    code_content = last_response[start_idx:end_idx].strip()
            
            # Generate filename
            import time
            filename = f"data_analysis_{int(time.time())}.py"
            print(f"DEBUG: Generated filename: {filename}")
        
        # Method 3: If still no code but contains imports, extract raw text
        elif (self.agent_type == "data_analyst" and 
              ("import " in last_response or "pandas" in last_response)):
            print("DEBUG: Data analyst - extracting raw code from response")
            # Try to extract Python code from the response
            lines = last_response.split('\n')
            code_lines = []
            in_code = False
            
            for line in lines:
                if line.strip().startswith(('import ', 'from ', '#', 'def ', 'class ', 'if ', 'for ', 'while ', 'try:')):
                    in_code = True
                if in_code and line.strip():
                    code_lines.append(line)
                elif in_code and not line.strip():
                    code_lines.append('')  # Keep blank lines in code
                elif in_code and not line.strip() and not any(c.isalnum() for c in line):
                    break  # Stop at non-code content
            
            code_content = '\n'.join(code_lines)
            import time
            filename = f"data_analysis_{int(time.time())}.py"
            print(f"DEBUG: Extracted raw code, filename: {filename}")
        
        if filename and code_content:
            print(f"DEBUG: Processing file - Filename: {filename}, Content length: {len(code_content)}")
            
            # Clean filename
            if not filename.endswith('.py'):
                filename += '.py'
            
            # Generate default filename if needed
            if not filename or filename == '.py':
                import time
                filename = f"data_analysis_{int(time.time())}.py"
            
            # Write file to project directory
            file_path = os.path.join(state["temp_dir"], filename)
            try:
                # Clean up any markdown artifacts and backticks
                code_content = self._clean_markdown_artifacts(code_content)
                
                # Auto-fix common issues before writing
                code_content = self._fix_gui_code(code_content)
                code_content = self._fix_file_paths(code_content)
                
                print(f"DEBUG: Writing file to: {file_path}")
                print(f"DEBUG: Code content preview: {code_content[:200]}...")
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(code_content)
                
                # Update state
                new_created_files = state["created_files"] + [filename]
                new_files = {**state["files"], filename: file_path}
                new_messages = state["messages"] + [AIMessage(content=f"📁 Created file: {filename}")]
                
                print(f"DEBUG: File created successfully: {filename}")
                
                return {
                    **state,
                    "created_files": new_created_files,
                    "files": new_files,
                    "messages": new_messages
                }
                
            except Exception as e:
                print(f"DEBUG: Error creating file: {str(e)}")
                new_messages = state["messages"] + [AIMessage(content=f"❌ Error creating file {filename}: {str(e)}")]
                return {**state, "messages": new_messages}
        
        print("DEBUG: No valid code content found in response")
        return state
    
    def _execute_file(self, state: AgentState) -> AgentState:
        """Execute a Python file and determine next action"""
        # Get the current file to execute
        filename = state.get("current_file")
        if not filename:
            filename = state["created_files"][-1] if state["created_files"] else None
        
        print(f"DEBUG: _execute_file called")
        print(f"DEBUG: current_file: {state.get('current_file')}")
        print(f"DEBUG: created_files: {state.get('created_files')}")
        print(f"DEBUG: files dict keys: {list(state.get('files', {}).keys())}")
        print(f"DEBUG: filename to execute: {filename}")
        
        if not filename or filename not in state["files"]:
            print(f"DEBUG: No file to execute. Filename: {filename}, Available files: {list(state['files'].keys())}")
            
            # Check if this is due to duplicate detection
            last_error_type = state.get("last_error_type", "")
            if last_error_type in ["DuplicateRequest", "AlreadyProcessed"]:
                # Return a friendly message for duplicates
                return {
                    **state,
                    "has_execution_error": False,
                    "last_error_type": last_error_type,
                    "messages": state["messages"] + [AIMessage(content="🔄 This request was already processed. No new execution needed.")]
                }
            else:
                # Return error for actual missing files
                return {
                    **state,
                    "has_execution_error": True,
                    "last_error_type": "FileNotFound",
                    "messages": state["messages"] + [AIMessage(content="❌ No file found to execute")]
                }

        file_path = state["files"][filename]
        print(f"DEBUG: Executing file: {filename} at {file_path}")
        
        # Execute the file
        result = self._run_python_file(file_path, state["temp_dir"])
        
        # Store execution output for the execution window
        self.last_execution_output = result.stdout
        self.last_execution_error = result.stderr
        
        print(f"DEBUG: Execution completed - Return code: {result.returncode}")
        print(f"DEBUG: STDOUT: {result.stdout[:200]}...")
        print(f"DEBUG: STDERR: {result.stderr[:200]}...")
        
        # Determine error type and status
        has_error = result.returncode != 0
        error_type = "Unknown"
        
        if has_error:
            if "ModuleNotFoundError" in result.stderr:
                error_type = "ModuleNotFoundError"
            elif "SyntaxError" in result.stderr:
                error_type = "SyntaxError"
            elif "FileNotFoundError" in result.stderr:
                error_type = "FileNotFoundError"
            elif "ImportError" in result.stderr:
                error_type = "ImportError"
        
        # Check for any newly created output files (visualizations, reports, etc.)
        output_files = []
        if state["temp_dir"]:
            try:
                current_files = set(os.listdir(state["temp_dir"]))
                previous_files = set(state["files"].keys())
                new_files = current_files - previous_files
                output_files = [f for f in new_files if f.endswith(('.png', '.html', '.csv', '.txt', '.pdf', '.jpg', '.jpeg', '.svg'))]
                
                # Add new output files to the state for frontend access
                for output_file in output_files:
                    output_path = os.path.join(state["temp_dir"], output_file)
                    new_files = {**state.get("files", {}), output_file: output_path}
                    state = {**state, "files": new_files}
                    
            except Exception as e:
                print(f"DEBUG: Error checking for output files: {e}")
        
        # Create execution summary for chat (keep minimal)
        if not has_error:
            execution_summary = f"✅ Executed: {filename}"
            if output_files:
                execution_summary += f" → Generated {len(output_files)} file(s)"
        else:
            retry_count = state.get("retry_count", 0)
            execution_summary = f"❌ Execution failed ({error_type}) - Attempt #{retry_count + 1}"
        
        # Store execution results for frontend access
        # The execution results will be sent to frontend through the API response
        
        # Update state with execution results and error status
        new_state = {
            **state,
            "execution_output": result.stdout,
            "execution_error": result.stderr,
            "has_execution_error": has_error,
            "last_error_type": error_type,
            "retry_count": state.get("retry_count", 0) + 1 if has_error else 0,
            "current_file": filename,
            "messages": state["messages"] + [AIMessage(content=execution_summary)]
        }
        
        return new_state
    
    def _run_python_file(self, file_path: str, cwd: str):
        """Run a Python file and return the result"""
        try:
            return subprocess.run(
                [sys.executable, file_path],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=self.config.max_execution_time
            )
        except subprocess.TimeoutExpired:
            # Create a mock result for timeout
            class TimeoutResult:
                def __init__(self):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = "Execution timed out after 60 seconds"
            return TimeoutResult()
        except Exception as e:
            # Create a mock result for other errors
            class ErrorResult:
                def __init__(self, error):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = f"Execution error: {str(error)}"
            return ErrorResult(e)
    
    def _extract_missing_modules(self, stderr: str) -> List[str]:
        """Extract missing module names from error output"""
        modules = []
        
        # Pattern for "No module named 'module_name'"
        pattern = r"No module named ['\"]([^'\"]+)['\"]"
        matches = re.findall(pattern, stderr)
        
        for match in matches:
            # Handle common module name mappings
            module_name = self._map_module_name(match)
            if module_name and module_name not in modules:
                modules.append(module_name)
        
        return modules
    
    def _map_module_name(self, import_name: str) -> str:
        """Map import names to pip package names"""
        # Common mappings between import names and pip package names
        mappings = {
            'PIL': 'Pillow',
            'cv2': 'opencv-python',
            'sklearn': 'scikit-learn',
            'skimage': 'scikit-image',
            'matplotlib': 'matplotlib',
            'numpy': 'numpy',
            'pandas': 'pandas',
            'scipy': 'scipy',
            'seaborn': 'seaborn',
            'plotly': 'plotly',
            'requests': 'requests',
            'beautifulsoup4': 'beautifulsoup4',
            'bs4': 'beautifulsoup4',
            'openpyxl': 'openpyxl',
            'xlrd': 'xlrd',
            'xlsxwriter': 'XlsxWriter',
            'psycopg2': 'psycopg2-binary',
            'pymongo': 'pymongo',
            'sqlalchemy': 'SQLAlchemy',
            'flask': 'Flask',
            'django': 'Django',
            'fastapi': 'fastapi',
            'uvicorn': 'uvicorn',
            'streamlit': 'streamlit',
            'dash': 'dash',
            'jupyter': 'jupyter',
            'ipython': 'ipython',
            'tensorflow': 'tensorflow',
            'torch': 'torch',
            'transformers': 'transformers',
            'openai': 'openai',
            'langchain': 'langchain'
        }
        
        return mappings.get(import_name, import_name)
    
    def _install_module(self, module_name: str):
        """Install a Python module using pip"""
        try:
            return subprocess.run(
                [sys.executable, "-m", "pip", "install", module_name],
                capture_output=True,
                text=True,
                timeout=120  # 2 minutes timeout for installation
            )
        except subprocess.TimeoutExpired:
            # Create a mock result for timeout
            class TimeoutResult:
                def __init__(self):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = "Installation timed out after 120 seconds"
            return TimeoutResult()
        except Exception as e:
            # Create a mock result for other errors
            class ErrorResult:
                def __init__(self, error):
                    self.returncode = -1
                    self.stdout = ""
                    self.stderr = f"Installation error: {str(error)}"
            return ErrorResult(e)
    
    def _fix_gui_code(self, code_content: str) -> str:
        """Fix common GUI-related issues in code to make it headless-friendly"""
        import re
        
        # Fix matplotlib show() calls
        if 'matplotlib' in code_content or 'plt.' in code_content:
            # Replace plt.show() with unique plt.savefig() and plt.close()
            import time
            timestamp = int(time.time())
            unique_filename = f"plot_{timestamp}.png"
            code_content = re.sub(
                r'plt\.show\(\)',
                f"plt.savefig('{unique_filename}', dpi=150, bbox_inches='tight')\nprint('Plot saved as {unique_filename}')\nplt.close()",
                code_content
            )
            
            # Add matplotlib backend setting at the top if not present
            if 'matplotlib.use(' not in code_content:
                # Find the first matplotlib import and add backend setting
                matplotlib_import_pattern = r'(import matplotlib\.pyplot|from matplotlib)'
                if re.search(matplotlib_import_pattern, code_content):
                    code_content = re.sub(
                        matplotlib_import_pattern,
                        r'import matplotlib\nmatplotlib.use("Agg")  # Use non-GUI backend\n\1',
                        code_content,
                        count=1
                    )
        
        # Fix plotly show() calls
        if 'plotly' in code_content:
            # Replace fig.show() with fig.write_html()
            code_content = re.sub(
                r'fig\.show\(\)',
                "fig.write_html('plot.html')\nprint('Interactive plot saved as plot.html')",
                code_content
            )
        
        # Fix seaborn/matplotlib combination
        if 'seaborn' in code_content and 'show()' in code_content:
            import time
            timestamp = int(time.time())
            unique_seaborn_filename = f"seaborn_plot_{timestamp}.png"
            code_content = re.sub(
                r'plt\.show\(\)|show\(\)',
                f"plt.savefig('{unique_seaborn_filename}', dpi=150, bbox_inches='tight')\nprint('Seaborn plot saved as {unique_seaborn_filename}')\nplt.close()",
                code_content
            )
        
        # Add a comment explaining the modifications
        if 'plt.savefig(' in code_content or 'write_html(' in code_content:
            code_content = f"# Note: GUI display calls have been automatically converted to file saves for headless execution\n\n{code_content}"
        
        return code_content
    
    def _clean_markdown_artifacts(self, code_content: str) -> str:
        """Clean up markdown artifacts and backticks from generated code"""
        import re
        
        # Strip whitespace
        code_content = code_content.strip()
        
        # Remove ```python at the beginning of lines
        code_content = re.sub(r'^```python\s*$', '', code_content, flags=re.MULTILINE)
        code_content = re.sub(r'^```py\s*$', '', code_content, flags=re.MULTILINE)
        # Remove standalone ``` lines
        code_content = re.sub(r'^```\s*$', '', code_content, flags=re.MULTILINE)
        # Remove any remaining ``` patterns at line start
        code_content = re.sub(r'^```.*?$', '', code_content, flags=re.MULTILINE)
        
        # Remove any remaining ``` patterns anywhere in the code
        code_content = re.sub(r'```', '', code_content)
        
        # Remove trailing backticks
        while code_content.endswith('`'):
            code_content = code_content[:-1].strip()
        
        # Remove any lines that are just backticks or markdown artifacts
        lines = code_content.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped_line = line.strip()
            # Skip lines that are just markdown artifacts
            if stripped_line in ['```', '```python', '```py', '`', '``']:
                continue
            # Skip lines that start with markdown artifacts
            if stripped_line.startswith('```'):
                continue
            cleaned_lines.append(line)
        
        code_content = '\n'.join(cleaned_lines)
        
        # Clean up multiple empty lines
        code_content = re.sub(r'\n\s*\n\s*\n', '\n\n', code_content)
        
        # Final strip
        return code_content.strip()

    def _fix_file_paths(self, code_content: str) -> str:
        """Fix absolute file paths and remove hardcoded file references"""
        import re
        
        # Remove absolute Windows paths and replace with relative paths
        # Pattern for Windows absolute paths
        windows_path_pattern = r'r?"[C-Z]:[^"]*"'
        code_content = re.sub(windows_path_pattern, '"./"', code_content)
        
        # Pattern for temp directory paths
        temp_path_pattern = r'r?"[^"]*[Tt]emp[^"]*"'
        code_content = re.sub(temp_path_pattern, '"./"', code_content)
        
        # Replace specific common absolute path patterns
        code_content = code_content.replace('OUTPUT_DIR = r"', 'OUTPUT_DIR = "./')
        code_content = code_content.replace('OUTPUT_DIR = "', 'OUTPUT_DIR = "./')
        code_content = code_content.replace('os.path.join(OUTPUT_DIR,', 'os.path.join("./",')
        
        # Remove ALL hardcoded file names - AI models often hallucinate common names
        # This is a comprehensive list of commonly assumed file names
        hardcoded_files = [
            # Basic data files
            'data.csv', 'dataset.csv', 'input.csv', 'output.csv', 'file.csv',
            # Results and solutions  
            'results.csv', 'solution.csv', 'solutions.csv', 'result.csv',
            'solution_tables.csv', 'model_results.csv', 'output_data.csv',
            # Cost and financial
            'costs.csv', 'cost_data.csv', 'cost_analysis.csv', 'pricing.csv', 
            'budget.csv', 'expenses.csv', 'revenue.csv', 'financial_data.csv',
            'sales_data.csv', 'financial.csv', 'money.csv',
            # Operations research specific
            'constraints.csv', 'constraint_data.csv', 'parameters.csv', 'variables.csv',
            'objective.csv', 'optimization_results.csv', 'solver_output.csv', 
            'decision_variables.csv', 'model_output.csv', 'optimization.csv',
            # Location and logistics
            'locations.csv', 'warehouse_data.csv', 'location_data.csv', 'warehouses.csv',
            'routes.csv', 'route_data.csv', 'distance.csv', 'distances.csv',
            'coordinates.csv', 'facilities.csv', 'sites.csv',
            # Supply chain
            'supply.csv', 'demand.csv', 'capacity.csv', 'inventory.csv',
            'supply_data.csv', 'demand_data.csv', 'capacity_data.csv',
            # Generic analysis
            'analysis.csv', 'summary.csv', 'report.csv', 'stats.csv',
            'statistics.csv', 'metrics.csv', 'kpis.csv', 'performance.csv',
            # With directory paths (also commonly hallucinated)
            'Inputs/data.csv', 'Inputs/costs.csv', 'Inputs/parameters.csv',
            'Inputs/cost_data.csv', 'Inputs/input.csv', 'Inputs/dataset.csv',
            'Outputs/results.csv', 'Outputs/output.csv', 'Outputs/solution.csv',
            'Outputs/constraint_data.csv', 'Outputs/analysis.csv',
            'Data/data.csv', 'data/input.csv', 'files/data.csv'
        ]
        
        for hardcoded_file in hardcoded_files:
            # Replace direct references to these files with file discovery
            if hardcoded_file in code_content:
                print(f"DEBUG: Removing hardcoded file reference: {hardcoded_file}")
                # Replace the hardcoded file with discovery pattern
                discovery_pattern = f"""
# Discover available CSV files recursively instead of using hardcoded '{hardcoded_file}'
csv_files = []
excluded_dirs = {{'__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules', '.pytest_cache'}}
for root, dirs, files in os.walk('.'):
    # Skip excluded directories
    dirs[:] = [d for d in dirs if d not in excluded_dirs]
    # Skip hidden directories and common non-data directories
    if any(part.startswith('.') and part not in {'.', '..'} for part in root.split(os.sep)):
        continue
    
    for file in files:
        if file.endswith('.csv'):
            csv_path = os.path.join(root, file).replace('\\\\', '/')
            csv_files.append(csv_path)

print(f"Available CSV files: {{csv_files}}")
if csv_files:
    # Use the first available CSV file
    data_file = csv_files[0]
    print(f"Using discovered file: {{data_file}}")
    
    # MANDATORY: Inspect the data structure before using it
    temp_df = pd.read_csv(data_file)
    print(f"Data shape: {{temp_df.shape}}")
    print(f"Columns: {{temp_df.columns.tolist()}}")
    print(f"Data types: {{temp_df.dtypes}}")
    print("First 3 rows:")
    print(temp_df.head(3))
    available_columns = temp_df.columns.tolist()
    numeric_columns = temp_df.select_dtypes(include=['number']).columns.tolist()
    print(f"Numeric columns: {{numeric_columns}}")
else:
    print("No CSV files found in any directory")
    data_file = None
"""
                # Replace the hardcoded file reference
                code_content = code_content.replace(f"'{hardcoded_file}'", "data_file")
                code_content = code_content.replace(f'"{hardcoded_file}"', "data_file")
                
                # Add discovery code at the beginning
                if "csv_files = [f for f in os.listdir" not in code_content:
                    # Insert discovery after imports
                    import_end = 0
                    lines = code_content.split('\n')
                    for i, line in enumerate(lines):
                        if line.strip().startswith(('import ', 'from ')) or line.strip().startswith('#'):
                            import_end = i + 1
                        elif line.strip() and not line.strip().startswith(('import ', 'from ', '#')):
                            break
                    
                    if import_end > 0:
                        lines.insert(import_end, discovery_pattern)
                        code_content = '\n'.join(lines)
        
        # Add automatic file discovery if no files are specified and no discovery exists
        if ("# Find data files" not in code_content and 
            "os.listdir" not in code_content and 
            "csv_files = [f for f in os.listdir" not in code_content and
            "for root, dirs, files in os.walk" not in code_content):
            file_discovery = """
# Find data files recursively in all directories
data_files = []
excluded_dirs = {'__pycache__', '.git', '.venv', 'venv', 'env', 'node_modules', '.pytest_cache'}
for root, dirs, files in os.walk('.'):
    # Skip excluded directories
    dirs[:] = [d for d in dirs if d not in excluded_dirs]
    # Skip hidden directories
    if any(part.startswith('.') and part not in {'.', '..'} for part in root.split(os.sep)):
        continue
        
    for file in files:
        if file.endswith(('.csv', '.xlsx', '.xls', '.json')):
            file_path = os.path.join(root, file).replace('\\\\', '/')
            data_files.append(file_path)
print(f"Found data files: {data_files}")

"""
            # Insert after imports
            import_end = 0
            lines = code_content.split('\n')
            for i, line in enumerate(lines):
                if line.strip().startswith(('import ', 'from ')) or line.strip().startswith('#'):
                    import_end = i + 1
                elif line.strip() and not line.strip().startswith(('import ', 'from ', '#')):
                    break
            
            if import_end > 0:
                lines.insert(import_end, file_discovery)
                code_content = '\n'.join(lines)
        
        return code_content
    
    def _respond(self, state: AgentState) -> AgentState:
        """Generate final response to user"""
        last_response = state["messages"][-1].content
        
        if last_response.startswith("RESPOND:"):
            response_content = last_response.replace("RESPOND:", "").strip()
            return {**state, "messages": state["messages"] + [AIMessage(content=response_content)]}
        
        return state
    
    def run(self, user_message: str, execution_output: str = "", execution_error: str = "", thread_id: str = "default", user_feedback: str = "") -> Tuple[str, List[str]]:
        """Run the multi-agent workflow with conversation memory and human-in-the-loop"""
        print(f"DEBUG: Starting run with agent_type: {self.agent_type}")
        print(f"DEBUG: User message: {user_message}")
        print(f"DEBUG: Thread ID: {thread_id}")
        
        # Reset request hash tracking for new request
        self.last_request_hash = None
        self.execution_counter = 0
        
        initial_state: AgentState = {
            "messages": [HumanMessage(content=user_message)],
            "files": {},
            "temp_dir": self.temp_dir,
            "execution_output": execution_output,
            "execution_error": execution_error,
            "created_files": [],
            "retry_count": 0,
            "current_file": "",
            "has_execution_error": False,
            "last_error_type": "",
            "execution_plan": "",
            "required_files": [],
            "analysis_type": "",
            "selected_file_contents": {},
            "database_schema": {},
            "database_path": "",
            "action_type": "",
            "action_result": "",
            "db_modification_result": {},
            "pending_approval": {},
            "approval_required": False,
            "approval_message": "",
            "user_feedback": user_feedback,
            "interrupt_reason": ""
        }
        
        # Configure thread for conversation memory
        config = {"configurable": {"thread_id": thread_id}}
        
        # Run the multi-agent graph with memory and interrupts
        # TEMPORARILY DISABLED: Memory system causing duplicate executions
        print("DEBUG: Running workflow WITHOUT memory to prevent duplicates")
        final_state = self.graph.invoke(initial_state)
        last_state = final_state
        
        # Extract only the latest response message (avoid accumulating previous responses)
        messages = last_state.get("messages", [])
        latest_ai_message = None
        
        # Find the last AI message in the conversation
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                latest_ai_message = msg
                break
        
        full_response = latest_ai_message.content if latest_ai_message else "No response generated"
        
        # Update stored execution results for frontend access
        self.last_execution_output = last_state.get("execution_output", "")
        self.last_execution_error = last_state.get("execution_error", "")
        
        print(f"DEBUG: Final created_files: {last_state.get('created_files', [])}")
        print(f"DEBUG: Final files dict keys: {list(last_state.get('files', {}).keys())}")
        
        return full_response, last_state.get("created_files", [])



    def get_conversation_history(self, thread_id: str = "default", limit: int = 10) -> List[BaseMessage]:
        """Get conversation history for a specific thread"""
        if not self.checkpointer:
            return []
        
        try:
            config = {"configurable": {"thread_id": thread_id}}
            # Get the latest checkpoint
            checkpoint = self.checkpointer.get(config)
            if checkpoint and "messages" in checkpoint.values:
                messages = checkpoint.values["messages"]
                return messages[-limit:] if limit > 0 else messages
        except Exception as e:
            print(f"DEBUG: Failed to get conversation history: {e}")
        
        return []

    def clear_conversation_history(self, thread_id: str = "default") -> bool:
        """Clear conversation history for a specific thread"""
        if not self.checkpointer:
            return False
        
        try:
            config = {"configurable": {"thread_id": thread_id}}
            # Note: This method depends on the specific checkpointer implementation
            # For now, we'll just note that the conversation can be cleared
            print(f"DEBUG: Conversation history clearing requested for thread: {thread_id}")
            return True
        except Exception as e:
            print(f"DEBUG: Failed to clear conversation history: {e}")
            return False

    def _get_database_schema(self, db_path: str) -> Dict[str, any]:
        """Extract database schema information without accessing actual data"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            schema_info = {
                "tables": {},
                "total_tables": 0,
                "database_path": db_path
            }
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            schema_info["total_tables"] = len(tables)
            
            for table in tables:
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table})")
                columns = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cursor.fetchone()[0]
                
                schema_info["tables"][table] = {
                    "columns": [],
                    "column_types": {},
                    "row_count": row_count
                }
                
                for col in columns:
                    col_name, col_type = col[1], col[2]
                    schema_info["tables"][table]["columns"].append(col_name)
                    schema_info["tables"][table]["column_types"][col_name] = col_type
            
            conn.close()
            return schema_info
            
        except Exception as e:
            print(f"Error getting database schema: {e}")
            return {"tables": {}, "total_tables": 0, "database_path": db_path, "error": str(e)}

    def _classify_user_request(self, message: str) -> str:
        """Classify the user's request to determine the appropriate action type"""
        message_lower = message.lower()
        
        # Database modification patterns
        db_modification_patterns = [
            'change', 'update', 'set', 'modify', 'alter', 'adjust',
            'increase', 'decrease', 'raise', 'lower', 'edit'
        ]
        
        parameter_patterns = [
            'parameter', 'param', 'maximum', 'minimum', 'limit', 'cost',
            'hub demand', 'opening cost', 'route supply'
        ]
        
        # Visualization patterns
        visualization_patterns = [
            'visualiz', 'visual', 'chart', 'graph', 'plot', 'map',
            'display', 'show', 'draw', 'create.*map', 'create.*chart'
        ]
        
        # SQL query patterns
        sql_patterns = [
            'select', 'query', 'find', 'search', 'get', 'retrieve',
            'list', 'count', 'sum', 'average', 'group by', 'order by'
        ]
        
        # Check for database modification
        has_modification = any(pattern in message_lower for pattern in db_modification_patterns)
        has_parameter = any(pattern in message_lower for pattern in parameter_patterns)
        
        if has_modification and has_parameter:
            return "DATABASE_MODIFICATION"
        
        # Check for visualization requests
        import re
        if any(re.search(pattern, message_lower) for pattern in visualization_patterns):
            return "VISUALIZATION"
        
        # Check for explicit SQL requests
        if any(pattern in message_lower for pattern in sql_patterns):
            return "SQL_QUERY"
        
        # Default to SQL query for ambiguous cases
        return "SQL_QUERY"

    def _action_router_node(self, state: AgentState) -> AgentState:
        """Router node that classifies user requests and routes to appropriate handlers"""
        last_message = state["messages"][-1].content if state["messages"] else ""
        
        # Classify the request
        action_type = self._classify_user_request(last_message)
        print(f"DEBUG: Classified request as: {action_type}")
        
        # Track action type for external access
        self.last_action_type = action_type
        
        # Store the action type in state for routing
        return {
            **state,
            "action_type": action_type,
            "messages": state["messages"] + [AIMessage(content=f"🎯 Action Type: {action_type.replace('_', ' ').title()}")]
        }

    def _database_modification_agent(self, state: AgentState) -> AgentState:
        """Handle database modification requests (parameter changes, data updates)"""
        last_message = state["messages"][-1].content if state["messages"] else ""
        
        print(f"DEBUG: Database modification agent processing: {last_message}")
        
        # Find database file
        db_path = None
        if state["temp_dir"]:
            db_files = glob.glob(os.path.join(state["temp_dir"], "*.db"))
            if db_files:
                db_path = db_files[0]
        
        if not db_path:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No database file found. Please upload a database first.")]
            }
        
        # This functionality is now handled by the database_modifier agent
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content="❌ Database modification requests should be handled by the database_modifier agent through the workflow.")],
            "action_result": "ERROR"
        }

    def _action_type_router(self, state: AgentState) -> Literal["sql_query", "visualization", "database_modification"]:
        """Route based on detected action type"""
        action_type = state.get("action_type", "SQL_QUERY")
        
        if action_type == "DATABASE_MODIFICATION":
            print("DEBUG: Routing to database modification")
            return "database_modification"
        elif action_type == "VISUALIZATION":
            print("DEBUG: Routing to visualization")
            return "visualization"
        else:  # SQL_QUERY or default
            print("DEBUG: Routing to SQL query")
            return "sql_query"

    def _database_modification_router(self, state: AgentState) -> str:
        """Route database modification results"""
        if state.get("db_modification_result"):
            result = state["db_modification_result"]
            
            # High-risk operations need approval
            if result.get("requires_approval", False) or "python_code" in result:
                return "request_approval"
            elif result.get("success") and "python_code" in result:
                return "execute_file"
            elif result.get("success"):
                return "success"
            else:
                return "error"
        else:
            return "error"



    def _human_feedback_node(self, state: AgentState) -> AgentState:
        """Process human feedback and adjust approach"""
        feedback = state.get("user_feedback", "")
        
        feedback_message = f"📝 **Incorporating your feedback**: {feedback}\n\n"
        feedback_message += "Adjusting the approach based on your input..."
        
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content=feedback_message)],
            "user_feedback": ""  # Clear feedback after processing
        }

    def _visualization_router(self, state: AgentState) -> str:
        """Route visualization results"""
        print(f"DEBUG: _visualization_router called")
        print(f"DEBUG: current_file: {state.get('current_file')}")
        print(f"DEBUG: created_files: {state.get('created_files')}")
        print(f"DEBUG: execution_error: {state.get('execution_error')}")
        
        # Check if we just created a visualization file
        if state.get("current_file") and state.get("current_file").endswith('.py'):
            print(f"DEBUG: Routing to execute_file for: {state.get('current_file')}")
            return "execute_file"
        elif state.get("vanna_result_type") == "PYTHON_CREATED":
            return "execute_file"
        elif state.get("execution_error"):
            return "error"
        else:
            return "success"

    def _analyze_data_request(self, state: AgentState) -> AgentState:
        """Analyze user request to determine if it's SQL query, visualization, or database modification"""
        last_message = state["messages"][-1].content if state["messages"] else ""
        print(f"DEBUG: _analyze_data_request called with message: {last_message}")
        
        # Get database schema context
        schema_context = ""
        if state.get("database_schema"):
            schema_context = self._build_schema_context(state["database_schema"])
        elif self.cached_database_schema:
            schema_context = self._build_schema_context(self.cached_database_schema)
        
        system_prompt = """You are analyzing a user request to determine how to handle it. You have three options:

1. **SQL_QUERY** - For straightforward data requests that need simple SQL execution
   Examples: "Show top 10 hubs", "What is total demand?", "List all routes", "give me the top 10 hubs with highest demand", "show me hubs with least demand", "find hubs with cost factors"

2. **VISUALIZATION** - For requests that need charts, graphs, or visual representations  
   Examples: "Create a chart", "Show a graph", "Visualize the data", "Plot distribution", "draw a map", "create a scatter plot"

3. **DATABASE_MODIFICATION** - For requests to change parameters or data
   Examples: "Change maximum hub demand to X", "Update cost to Y", "Set limit to Z", "modify parameter"

IMPORTANT: 
- If the user asks for data retrieval (like "show me", "give me", "find", "list"), it's usually SQL_QUERY
- If the user asks for visual representation (like "chart", "graph", "plot", "visualize"), it's VISUALIZATION
- If the user asks to change/modify data, it's DATABASE_MODIFICATION

Analyze the request and respond with exactly one word: SQL_QUERY, VISUALIZATION, or DATABASE_MODIFICATION"""

        messages = [
            HumanMessage(content=f"Database Schema:\n{schema_context}\n\nUser Request: {last_message}")
        ]
        
        try:
            response = self.llm.invoke([HumanMessage(content=system_prompt)] + messages)
            request_type = response.content.strip().upper()
            
            if request_type not in ["SQL_QUERY", "VISUALIZATION", "DATABASE_MODIFICATION"]:
                request_type = "SQL_QUERY"  # Default fallback
                
        except Exception as e:
            print(f"Error analyzing request: {e}")
            request_type = "SQL_QUERY"  # Default fallback
        
        return {
            **state,
            "request_type": request_type,
            "messages": state["messages"] + [AIMessage(content=f"Request classified as: {request_type}")]
        }
    
    def _route_data_request(self, state: AgentState) -> str:
        """Route the request based on the analyzed type"""
        request_type = state.get("request_type", "SQL_QUERY")
        print(f"DEBUG: _route_data_request called with request_type: {request_type}")
        
        if request_type == "SQL_QUERY":
            return "sql_query"
        elif request_type == "VISUALIZATION":
            return "visualization"
        elif request_type == "DATABASE_MODIFICATION":
            return "db_modification"
        else:
            return "respond"
    
    def _execute_sql_query_node(self, state: AgentState) -> AgentState:
        """Generate SQL query and create a Python script to execute it"""
        import hashlib
        
        # Get the original user message (not the last message which might be AI classification)
        user_message = ""
        for message in reversed(state["messages"]):
            if isinstance(message, HumanMessage):
                user_message = message.content
                break
        
        if not user_message:
            user_message = state["messages"][-1].content if state["messages"] else ""
        
        # Create a hash of the current request to detect duplicates
        request_hash = hashlib.md5(user_message.encode()).hexdigest()[:8]
        self.execution_counter += 1
        
        print(f"DEBUG: _execute_sql_query_node called - Execution #{self.execution_counter}")
        print(f"DEBUG: Request hash: {request_hash}")
        print(f"DEBUG: Last request hash: {self.last_request_hash}")
        print(f"DEBUG: Original user message: {user_message}")
        print(f"DEBUG: Current created_files: {state.get('created_files', [])}")
        print(f"DEBUG: Current files dict keys: {list(state.get('files', {}).keys())}")
        
        # Check if this is a duplicate request
        if self.last_request_hash == request_hash:
            print(f"DEBUG: DUPLICATE REQUEST DETECTED - Skipping execution")
            # Return state with a message indicating duplicate was detected
            # and set has_execution_error to False to avoid retry loops
            return {
                **state,
                "has_execution_error": False,
                "last_error_type": "DuplicateRequest",
                "messages": state["messages"] + [AIMessage(content="🔄 This request was already processed. No new execution needed.")]
            }
        
        # Update the last request hash
        self.last_request_hash = request_hash
        
        # Check if we've already processed this exact message to prevent duplicates
        if state.get("sql_query_result") and user_message.startswith("Request classified as:"):
            print(f"DEBUG: Skipping duplicate execution - already processed this request")
            return {
                **state,
                "has_execution_error": False,
                "last_error_type": "AlreadyProcessed",
                "messages": state["messages"] + [AIMessage(content="🔄 Request already processed. No new execution needed.")]
            }
        
        # Check if we already have a SQL query result for this session
        if state.get("sql_query_result"):
            print(f"DEBUG: SQL query already generated, skipping duplicate execution")
            return {
                **state,
                "has_execution_error": False,
                "last_error_type": "AlreadyProcessed",
                "messages": state["messages"] + [AIMessage(content="🔄 SQL query already generated. No new execution needed.")]
            }
        
        # Get database schema context
        schema_context = ""
        if state.get("database_schema"):
            schema_context = self._build_schema_context(state["database_schema"])
        elif self.cached_database_schema:
            schema_context = self._build_schema_context(self.cached_database_schema)
        
        system_prompt = f"""You are an expert SQL analyst. Generate a SQL query to answer the user's request.

Database Schema:
{schema_context}

Generate a SQL query that answers the user's question. Consider:
- Use appropriate JOINs for related tables
- Include proper WHERE clauses for filtering
- Use aggregations (COUNT, SUM, AVG) when needed
- Limit results to reasonable sizes (use LIMIT)
- Focus on the specific request - if user asks about "demand", look for demand-related columns
- If user asks about "hubs with least demand", find tables with hub information and demand data
- Look for tables with names like 'hubs', 'demand', 'destinations', 'inputs_hubs', 'inputs_destinations'
- For demand analysis, look for columns like 'Demand', 'demand', 'Hub_Demand', etc.
- For hub analysis, look for columns like 'HubID', 'Location', 'Hub_Location', etc.

CRITICAL RULES FOR UNION ALL OPERATIONS:
- NEVER use UNION ALL unless you are CERTAIN that all tables have EXACTLY the same column structure
- If tables have different columns, use separate queries or JOINs instead
- When using UNION ALL, explicitly list the columns in each SELECT statement to ensure they match
- Example of CORRECT UNION ALL:
  SELECT column1, column2, column3 FROM table1 WHERE condition
  UNION ALL
  SELECT column1, column2, column3 FROM table2 WHERE condition
- If you're unsure about column compatibility, use separate queries or JOINs

BEST PRACTICES:
- Start with a simple query on one table first
- If you need data from multiple similar tables, check their column structures first
- Use JOINs when you need to combine data from different tables with different structures
- Use UNION ALL only when you're combining identical table structures
- Always test your query logic before using UNION ALL

IMPORTANT: Pay attention to ALL requirements in the user's request:
- If user asks for "hubs with highest demand AND CostFactor_Opening", you need to JOIN tables that contain both demand and cost factor data
- If user asks for multiple columns (e.g., demand + cost factors), make sure ALL requested columns are included in the SELECT clause
- Look for cost-related columns like 'CostFactor_Opening', 'Opening_Cost', 'Cost_Opening', etc.
- Use appropriate JOINs to combine data from different tables when needed

EXAMPLES:
- "hubs with least demand" → Look for hub tables and demand columns, use ORDER BY demand ASC
- "hubs with highest demand AND CostFactor_Opening" → JOIN hub table with cost table, include both demand and cost columns
- "show demand by location" → Find location and demand columns, group by location
- "compare hub capacities" → Find hub tables with capacity columns
- "routes with cost > 500" → Query the routes table directly, avoid UNION ALL unless tables are identical

Respond with just the SQL query, no explanations."""

        try:
            response = self.llm.invoke([HumanMessage(content=f"{system_prompt}\n\nUser Question: {user_message}")])
            sql_query = response.content.strip()
            
            # Clean up the SQL query
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.replace("```", "").strip()
            
            # Create a Python script to execute the SQL query
            import time
            import random
            timestamp = int(time.time())
            random_id = random.randint(1000, 9999)
            filename = f"sql_query_{timestamp}_{random_id}.py"
            file_path = os.path.join(state["temp_dir"], filename)
            
            print(f"DEBUG: About to create file: {filename}")
            print(f"DEBUG: File path: {file_path}")
            
            # Check if file already exists (shouldn't happen with unique names)
            if os.path.exists(file_path):
                print(f"DEBUG: WARNING - File already exists: {file_path}")
            
            # Generate Python code to execute the SQL query
            python_code = f'''import os
import time
import random
import sqlite3
import pandas as pd
import glob
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

# Find database file
db_files = glob.glob('*.db')
if not db_files:
    print("No database file found")
    exit(1)

db_path = db_files[0]
print(f"Using database: {{db_path}}")

# Connect to database
conn = sqlite3.connect(db_path)

# Execute SQL query
sql_query = """{sql_query}"""

print("Executing SQL query:")
print(sql_query)
print("\\n" + "="*50 + "\\n")

try:
    # Execute query and get results
    df = pd.read_sql_query(sql_query, conn)
    
    # Display results
    if len(df) == 0:
        print("No results found.")
    else:
        print(f"Query returned {{len(df)}} rows:")
        
        # Create a matplotlib table
        fig, ax = plt.subplots(figsize=(min(20, len(df.columns) * 2), min(1 + 0.5 * len(df), 20)))
        ax.axis('off')

        # Create table
        table = ax.table(
            cellText=df.values,
            colLabels=df.columns,
            loc='center',
            cellLoc='left'
        )

        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.auto_set_column_width(col=list(range(len(df.columns))))

        # Set table style
        for (row, col), cell in table.get_celld().items():
            if row == 0:
                cell.set_fontsize(11)
                cell.set_text_props(weight='bold')
                cell.set_facecolor('#f2f2f2')
            cell.set_edgecolor('gray')

        # Save the table as an image
        timestamp = int(time.time())
        random_id = random.randint(1000, 9999)
        table_filename = f"sql_results_{{timestamp}}_{{random_id}}.png"
        plt.tight_layout()
        plt.savefig(table_filename, dpi=150, bbox_inches='tight', facecolor='white')
        plt.close()

        print(f"\\nResults table saved as: {{table_filename}}")
        print(f"\\nQuery Summary:")
        print(f"- Total rows: {{len(df)}}")
        print(f"- Columns: {{', '.join(df.columns)}}")
        
        # Show first few rows as text for immediate feedback
        if len(df) <= 10:
            print(f"\\nAll results:")
            print(df.to_string(index=False))
        else:
            print(f"\\nFirst 5 rows:")
            print(df.head().to_string(index=False))
            print(f"\\n... and {{len(df) - 5}} more rows")
        
        # Also save as CSV for data export
        # csv_filename = f"sql_results_{{timestamp}}_{{random_id}}.csv"
        # df.to_csv(csv_filename, index=False)
        # print(f"\\nData also saved as CSV: {{csv_filename}}")
    
except Exception as e:
    print(f"Error executing query: {{str(e)}}")

finally:
    conn.close()
    print("\\nDatabase connection closed.")
'''
            
            # Write the Python file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(python_code)
            
            # Add file to state
            files_dict = state.get("files", {})
            files_dict[filename] = file_path
            
            print(f"DEBUG: SQL query script created: {filename}")
            print(f"DEBUG: Final created_files will be: [filename]")
            print(f"DEBUG: Final files dict will have keys: {list(files_dict.keys())}")
            
            return {
                **state,
                "current_file": filename,
                "created_files": [filename],  # Only this file, not appended
                "files": files_dict,
                "sql_query_result": sql_query,
                "messages": state["messages"] + [AIMessage(content=f"📊Created SQL query script: {filename}")]
            }
                
        except Exception as e:
            error_message = f"Error generating SQL query: {str(e)}"
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=error_message)],
                "has_execution_error": True
            }

    def _find_database_file(self):
        # Try to find the database file in common locations
        possible_paths = [
            'project_data.db',
            '../project_data.db',
            '../../project_data.db',
            os.path.join(os.getcwd(), 'project_data.db'),
            os.path.join(os.getcwd(), '..', 'project_data.db')
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return None
    
    def _create_visualization_node(self, state: AgentState) -> AgentState:
        """Create Python script for visualization"""
        last_message = state["messages"][-1].content if state["messages"] else ""
        print(f"DEBUG: _create_visualization_node called with message: {last_message}")
        
        # Get database schema context
        schema_context = ""
        if state.get("database_schema"):
            schema_context = self._build_schema_context(state["database_schema"])
        elif self.cached_database_schema:
            schema_context = self._build_schema_context(self.cached_database_schema)
        
        # Generate timestamp and random ID for unique filenames
        import time
        import random
        timestamp = int(time.time())
        random_id = random.randint(1000, 9999)
        
        system_prompt = f"""Create a Python script for data visualization based on the user's request.

Database Schema:
{schema_context}

ANALYZE THE USER REQUEST FIRST:
- If user asks for "map", "geographic", "location", "hub", "allocation" → Create a COORDINATE-BASED SCATTER PLOT
- If user asks for "trend", "over time", "time series" → Create a LINE PLOT
- If user asks for "distribution", "frequency", "count" → Create a BAR CHART or HISTOGRAM
- If user asks for "correlation", "relationship" → Create a SCATTER PLOT
- If user asks for "comparison" → Create a BAR CHART or BOX PLOT
- If user asks for "heatmap", "matrix" → Create a HEATMAP

FOR COORDINATE-BASED VISUALIZATIONS (instead of HTML maps):
- Use matplotlib to create scatter plots with coordinates
- If user mentions "both model runs" or "comparison", create subplots or use different colors/symbols
- If user mentions "active hubs", query the database for hub status and color them appropriately
- If user mentions "lines to locations", draw lines between hubs and their allocated destinations
- Use different colors: red for active hubs, blue for inactive, green for destinations
- Include legends and annotations for clarity
- Save as PNG files for reliable browser display

FOR COMPARISON VISUALIZATIONS:
- If comparing "both model runs", create subplots or use different colors/symbols
- Show before/after scenarios clearly
- Include legends to distinguish between different runs or states

Requirements:
1. Start with the mandatory imports:
```python
import os
import time
import random
import sqlite3
import matplotlib
matplotlib.use('Agg')
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
```

2. Find and connect to database:
```python
import glob
db_files = glob.glob('*.db')
if db_files:
    conn = sqlite3.connect(db_files[0])
else:
    raise FileNotFoundError("No database file found")
```

3. Query appropriate data using the schema - be specific about what you need:
   - For hub allocations: query hub coordinates, destination coordinates, allocation data
   - For model comparisons: query both initial and final states
   - For active hubs: query hub status and capacity information

4. Create the SPECIFIC visualization type requested by the user
5. Save plot with unique filename: visualization_{timestamp}_{random_id}.png
6. Close database connection

IMPORTANT: 
- Pay attention to specific user requirements (colors, lines, comparisons, etc.)
- Query the database thoroughly to get all needed data
- Create clear and informative visualizations
- Handle multiple model runs or states if requested
- Use coordinate-based plots instead of HTML maps for better compatibility

Respond with: CREATE_FILE: visualization_data_{timestamp}.py
Then provide the complete Python script."""

        try:
            response = self.llm.invoke([HumanMessage(content=f"{system_prompt}\n\nVisualization Request: {last_message}")])
            
            # Process the response to extract filename and code
            content = response.content.strip()
            if "CREATE_FILE:" in content:
                lines = content.split('\n')
                filename_line = [line for line in lines if line.startswith("CREATE_FILE:")][0]
                filename = filename_line.replace("CREATE_FILE:", "").strip()
                
                # Extract code (everything after the filename line)
                code_start_idx = content.find(filename_line) + len(filename_line)
                code_content = content[code_start_idx:].strip()
                
                # Clean up code content - remove any markdown formatting
                if code_content.startswith('```python'):
                    code_content = code_content[9:]  # Remove ```python
                if code_content.startswith('```'):
                    code_content = code_content[3:]  # Remove ``` if no language specified
                if code_content.endswith('```'):
                    code_content = code_content[:-3]  # Remove trailing ```
                
                # Remove any remaining markdown artifacts
                code_content = code_content.replace('```', '')
                
                # Clean up any extra whitespace and ensure proper Python formatting
                code_content = code_content.strip()
                
                # Ensure the code ends properly (no hanging backticks or incomplete blocks)
                lines = code_content.split('\n')
                cleaned_lines = []
                for line in lines:
                    # Skip lines that are just markdown artifacts
                    if line.strip() in ['```', '```python', '```py']:
                        continue
                    cleaned_lines.append(line)
                
                code_content = '\n'.join(cleaned_lines).strip()
                
                print(f"DEBUG: Cleaned code content length: {len(code_content)}")
                print(f"DEBUG: Code content preview: {code_content[:200]}...")
                
                # Create the file
                if state.get("temp_dir") and os.path.exists(state["temp_dir"]):
                    file_path = os.path.join(state["temp_dir"], filename)
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(code_content)
                    
                    print(f"DEBUG: Created visualization file: {filename}")
                    print(f"DEBUG: File path: {file_path}")
                    print(f"DEBUG: Code content length: {len(code_content)}")
                    
                    # Add file to the files dictionary for execution
                    files_dict = state.get("files", {})
                    files_dict[filename] = file_path
                    
                    return {
                        **state,
                        "current_file": filename,
                        "created_files": state.get("created_files", []) + [filename],
                        "files": files_dict,
                        "visualization_request": last_message,
                        "messages": state["messages"] + [AIMessage(content=f"Created visualization script: {filename}")]
                    }
            
            # Fallback if parsing fails
            print(f"DEBUG: Failed to parse CREATE_FILE from response: {content[:200]}...")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="Failed to create visualization script.")]
            }
            
        except Exception as e:
            print(f"DEBUG: Exception in _create_visualization_node: {str(e)}")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"Error creating visualization: {str(e)}")]
            }
    
    def _prepare_db_modification_node(self, state: AgentState) -> AgentState:
        """Prepare database modification by identifying tables and columns"""
        # Get the original user message, not the classification message
        original_user_message = ""
        for msg in reversed(state["messages"]):
            if hasattr(msg, 'content') and not msg.content.startswith("Request classified as:"):
                original_user_message = msg.content
                break
        
        last_message = original_user_message
        
        # Get database schema context
        schema_context = ""
        if state.get("database_schema"):
            schema_context = self._build_schema_context(state["database_schema"])
        elif self.cached_database_schema:
            schema_context = self._build_schema_context(self.cached_database_schema)
        
        def fuzzy_match_parameter(user_input, available_parameters, threshold=0.6):
            """Find the best matching parameter using fuzzy logic"""
            import difflib
            
            # Clean the user input
            user_input = user_input.lower().strip()
            
            # Direct substring matching first
            exact_matches = [p for p in available_parameters if user_input.lower() in p.lower() or p.lower() in user_input.lower()]
            if exact_matches:
                return exact_matches[0]
            
            # Use difflib for fuzzy matching
            matches = difflib.get_close_matches(user_input, [p.lower() for p in available_parameters], n=1, cutoff=threshold)
            if matches:
                # Find the original parameter name (with proper casing)
                for param in available_parameters:
                    if param.lower() == matches[0]:
                        return param
            
            # Try partial word matching
            user_words = user_input.split()
            best_match = None
            best_score = 0
            
            for param in available_parameters:
                param_words = param.lower().split()
                score = 0
                for user_word in user_words:
                    for param_word in param_words:
                        if user_word in param_word or param_word in user_word:
                            score += 1
                        elif difflib.SequenceMatcher(None, user_word, param_word).ratio() > 0.7:
                            score += 0.8
                
                if score > best_score:
                    best_score = score
                    best_match = param
            
            return best_match if best_score > 0 else None

        system_prompt = f"""Analyze the database modification request and identify exactly what needs to be changed.

Database Schema:
{schema_context}

You are analyzing an operations research model with hub location optimization. Common parameters that might be modified include:
- Hub capacity/demand limits
- Cost parameters  
- Distance/route parameters
- Supply/demand values

IMPORTANT: Pay attention to table-specific requests. Examples:
- "Change x in table_name" → Use the specified table_name
- "Update maximum hub demand in params table" → Use params or inputs_params table
- "Set cost to 500 in routes table" → Use routes table
- "Modify capacity in hubs_data" → Use hubs_data table

For general requests without table specification, look for:
- Tables with "hub" in the name or description
- Columns related to capacity, demand, max_capacity, limit, etc.
- Parameters tables that might contain model settings

IMPORTANT: Extract the exact numeric value AND parameter name from the user's request. For example:
- "Change maximum hub demand to 20000" → NEW_VALUE: 20000, Parameter: 'Maximum Hub Demand'
- "Set hub capacity to 15000" → NEW_VALUE: 15000
- "Update Operating Cost (Fixed) to 1000" → NEW_VALUE: 1000, Parameter: 'Operating Cost (Fixed)'
- "Change Operating Cost per Unit to 25.5" → NEW_VALUE: 25.5, Parameter: 'Operating Cost per Unit'
- "Update Opening Cost to 500000" → NEW_VALUE: 500000, Parameter: 'Opening Cost'
- "Change Closing Cost to 150000" → NEW_VALUE: 150000, Parameter: 'Closing Cost'

For parameter tables (like inputs_params), you may need to identify:
- The WHERE condition to target the specific parameter row
- The exact parameter name that needs to be updated

TABLE DETECTION RULES:
1. If user specifies "in [table_name]" → Use that exact table name
2. If user mentions specific table → Use that table
3. Otherwise, search for appropriate table based on column/parameter type

Analyze the request and identify:
1. Which table(s) contain the parameter to be modified (prioritize user-specified tables)
2. Which column(s) need to be updated  
3. What the exact new value should be (extract from user request)
4. Any WHERE conditions needed to target the right row

Respond in this exact format:
TABLE: [table_name]
COLUMN: [column_name] 
NEW_VALUE: [exact_numeric_value_from_request]
WHERE_CONDITION: [if needed, e.g., Parameter = 'Maximum Hub Demand']
DESCRIPTION: [brief description of the change]"""

        try:
            # Enhanced regex to extract numeric value and table name from the request
            import re
            
            # Look for table-specific patterns
            table_patterns = [
                r'in\s+(?:the\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s+table',  # "in table_name table"
                r'in\s+([a-zA-Z_][a-zA-Z0-9_]*)',                     # "in table_name"
                r'from\s+(?:the\s+)?([a-zA-Z_][a-zA-Z0-9_]*)\s+table', # "from table_name table"
                r'from\s+([a-zA-Z_][a-zA-Z0-9_]*)',                   # "from table_name"
                r'(?:table|tab)\s+([a-zA-Z_][a-zA-Z0-9_]*)',          # "table table_name"
            ]
            
            extracted_table = None
            for pattern in table_patterns:
                match = re.search(pattern, last_message, re.IGNORECASE)
                if match:
                    extracted_table = match.group(1).lower()
                    break
            
            # Look for patterns like "to 20000", "= 15000", "with 25000", etc.
            numeric_patterns = [
                r'to\s+(\d+(?:\.\d+)?)',
                r'=\s*(\d+(?:\.\d+)?)',
                r'with\s+(\d+(?:\.\d+)?)',
                r'set.*?(\d+(?:\.\d+)?)',
                r'change.*?(\d+(?:\.\d+)?)',
                r'\b(\d+(?:\.\d+)?)\s*$',  # Number at end of sentence
                r'\b(\d+(?:\.\d+)?)\b'     # Any number
            ]
            
            extracted_value = None
            for pattern in numeric_patterns:
                match = re.search(pattern, last_message, re.IGNORECASE)
                if match:
                    extracted_value = match.group(1)
                    break
            
            print(f"DEBUG: Raw request: '{last_message}'")
            print(f"DEBUG: Extracted numeric value: {extracted_value}")
            print(f"DEBUG: Extracted table name: {extracted_table}")
            
            # Check if user specified a table name
            if extracted_table and extracted_value:
                print(f"DEBUG: User specified table '{extracted_table}' - validating table exists")
                
                # Validate that the table exists in the schema
                available_tables = []
                if state.get("database_schema"):
                    # Extract table names from the "tables" key in the schema (list of table objects)
                    schema_tables = state["database_schema"].get("tables", [])
                    available_tables = [t["name"].lower() for t in schema_tables if isinstance(t, dict) and "name" in t]
                elif self.cached_database_schema:
                    # Extract table names from the "tables" key in the cached schema (list of table objects)
                    schema_tables = self.cached_database_schema.get("tables", [])
                    available_tables = [t["name"].lower() for t in schema_tables if isinstance(t, dict) and "name" in t]
                
                print(f"DEBUG: Available tables in database: {available_tables}")
                print(f"DEBUG: Looking for table: '{extracted_table}'")
                
                # Check if the extracted table exists (case insensitive)
                table_exists = extracted_table in available_tables
                if not table_exists:
                    # Try common variations and partial matches
                    table_variations = {
                        'params': 'inputs_params',
                        'parameters': 'inputs_params', 
                        'param': 'inputs_params',
                        'inputs': 'inputs_params',
                        'hubs': 'hubs_data',
                        'routes': 'routes_data',
                        'data': 'project_data'
                    }
                    
                    # Check for direct mapping
                    if extracted_table in table_variations:
                        mapped_table = table_variations[extracted_table]
                        if mapped_table.lower() in available_tables:
                            extracted_table = mapped_table.lower()
                            table_exists = True
                            print(f"DEBUG: Mapped '{extracted_table}' to '{mapped_table}'")
                    
                    # If still not found, try to find similar table names
                    if not table_exists:
                        # Try fuzzy matching for table names
                        fuzzy_table_match = fuzzy_match_parameter(extracted_table, available_tables)
                        if fuzzy_table_match:
                            print(f"DEBUG: Fuzzy matched table '{extracted_table}' to '{fuzzy_table_match}'")
                            extracted_table = fuzzy_table_match.lower()
                            table_exists = True
                        else:
                            # Try different fuzzy matching strategies
                            similar_tables = []
                            
                            # Strategy 1: Substring matching
                            similar_tables.extend([t for t in available_tables if extracted_table in t or t in extracted_table])
                            
                            # Strategy 2: Look for tables containing key words from the extracted table
                            if 'inputs' in extracted_table:
                                similar_tables.extend([t for t in available_tables if 'inputs' in t or 'params' in t or 'parameters' in t])
                            
                            if 'hublocopti' in extracted_table:
                                similar_tables.extend([t for t in available_tables if 'hub' in t or 'opti' in t])
                            
                            if 'parameters' in extracted_table:
                                similar_tables.extend([t for t in available_tables if 'param' in t or 'inputs' in t])
                            
                            # Remove duplicates and sort by length (prefer shorter, more likely matches)
                            similar_tables = list(set(similar_tables))
                            similar_tables.sort(key=len)
                            
                            if similar_tables:
                                print(f"DEBUG: Table '{extracted_table}' not found, but found similar: {similar_tables}")
                                # Use the first (shortest) similar table
                                extracted_table = similar_tables[0]
                                table_exists = True
                
                if table_exists:
                    print(f"DEBUG: Using validated table '{extracted_table}' - creating direct response")
                    
                    # Pass to LLM to identify the specific column within the specified table
                    enhanced_prompt = f"""{system_prompt}

USER SPECIFIED TABLE: {extracted_table}
EXTRACTED VALUE FROM REQUEST: {extracted_value}

The user has specifically requested to modify the '{extracted_table}' table. Focus ONLY on this table.
You need to identify which column in the '{extracted_table}' table should be updated.

Look at the schema for '{extracted_table}' table and determine the appropriate column name."""

                    response = self.llm.invoke([HumanMessage(content=f"{enhanced_prompt}\n\nModification Request: {last_message}")])
                    content = response.content.strip()
                else:
                    print(f"DEBUG: Table '{extracted_table}' not found in schema")
                    # Provide immediate feedback about available tables
                    available_table_names = []
                    if state.get("database_schema"):
                        schema_tables = state["database_schema"].get("tables", [])
                        available_table_names = [t["name"] for t in schema_tables if isinstance(t, dict) and "name" in t]
                    elif self.cached_database_schema:
                        schema_tables = self.cached_database_schema.get("tables", [])
                        available_table_names = [t["name"] for t in schema_tables if isinstance(t, dict) and "name" in t]
                    
                    error_msg = f"❌ Table '{extracted_table}' not found in database.\n\n"
                    error_msg += f"**Available tables:**\n"
                    for table in available_table_names:
                        error_msg += f"• {table}\n"
                    error_msg += f"\n**Suggestion:** Try one of the available table names above.\n"
                    error_msg += f"**Example:** 'Change maximum demand to {extracted_value} in [table_name]'\n\n"
                    error_msg += f"**Your request:** {last_message}"
                    
                    return {
                        **state,
                        "messages": state["messages"] + [AIMessage(content=error_msg)]
                    }
                
            # For Hub Demand requests (minimum or maximum), provide a direct response
            elif 'hub demand' in last_message.lower() and extracted_value:
                # Determine if it's minimum or maximum hub demand
                if 'minimum' in last_message.lower():
                    parameter_name = 'Minimum Hub Demand'
                    description = 'Update minimum hub demand parameter'
                else:
                    parameter_name = 'Maximum Hub Demand' 
                    description = 'Update maximum hub demand parameter'
                    
                content = f"""TABLE: inputs_params
COLUMN: Value
NEW_VALUE: {extracted_value}
WHERE_CONDITION: Parameter = '{parameter_name}'
DESCRIPTION: {description}"""
                print(f"DEBUG: Using direct response for {parameter_name.lower()} modification")
            
            # Try fuzzy matching for parameter names if we have a specific table (inputs_params)
            elif extracted_table and extracted_table.lower() in ['inputs_params', 'params'] and extracted_value:
                # Get available parameters from inputs_params table
                available_parameters = []
                if database_path and os.path.exists(database_path):
                    try:
                        import sqlite3
                        conn = sqlite3.connect(database_path)
                        cursor = conn.cursor()
                        cursor.execute("SELECT DISTINCT Parameter FROM inputs_params")
                        available_parameters = [row[0] for row in cursor.fetchall()]
                        conn.close()
                        print(f"DEBUG: Available parameters for fuzzy matching: {available_parameters}")
                    except Exception as e:
                        print(f"DEBUG: Could not fetch parameters for fuzzy matching: {e}")
                
                if available_parameters:
                    # Extract potential parameter name from the request
                    parameter_keywords = []
                    
                    # Look for common parameter patterns
                    import re
                    
                    # Pattern: "update X to Y" or "change X to Y" or "set X to Y"
                    patterns = [
                        r'(?:update|change|set|modify)\s+(.+?)\s+(?:to|=)\s+\d+',
                        r'(?:update|change|set|modify)\s+(.+?)\s+(?:to|=)',
                        r'(.+?)\s+(?:to|=)\s+\d+',
                        r'(?:parameter|param)\s+(.+?)(?:\s+to|\s+=|\s+in)',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, last_message, re.IGNORECASE)
                        parameter_keywords.extend(matches)
                    
                    # Also try extracting from common phrases
                    if 'operating cost' in last_message.lower():
                        if 'fixed' in last_message.lower():
                            parameter_keywords.append('Operating Cost (Fixed)')
                        elif 'unit' in last_message.lower():
                            parameter_keywords.append('Operating Cost per Unit')
                        else:
                            parameter_keywords.extend(['Operating Cost (Fixed)', 'Operating Cost per Unit'])
                    
                    if 'opening cost' in last_message.lower():
                        parameter_keywords.append('Opening Cost')
                    
                    if 'closing cost' in last_message.lower():
                        parameter_keywords.append('Closing Cost')
                    
                    if 'km cost' in last_message.lower() or 'km cost per unit' in last_message.lower():
                        parameter_keywords.append('KM Cost per Unit')
                    
                    if 'base cost' in last_message.lower() or 'base cost per unit' in last_message.lower():
                        parameter_keywords.append('Base Cost per Unit')
                    
                    if 'hub demand' in last_message.lower():
                        if 'minimum' in last_message.lower():
                            parameter_keywords.append('Minimum Hub Demand')
                        elif 'maximum' in last_message.lower():
                            parameter_keywords.append('Maximum Hub Demand')
                        else:
                            parameter_keywords.extend(['Minimum Hub Demand', 'Maximum Hub Demand'])
                    
                    print(f"DEBUG: Extracted parameter keywords: {parameter_keywords}")
                    
                    # Try fuzzy matching
                    best_match = None
                    best_confidence = 0
                    
                    for keyword in parameter_keywords:
                        matched_param = fuzzy_match_parameter(keyword, available_parameters)
                        if matched_param:
                            # Calculate confidence based on similarity
                            import difflib
                            confidence = difflib.SequenceMatcher(None, keyword.lower(), matched_param.lower()).ratio()
                            if confidence > best_confidence:
                                best_match = matched_param
                                best_confidence = confidence
                    
                    if best_match:
                        print(f"DEBUG: Fuzzy matched parameter '{best_match}' with confidence {best_confidence:.2f}")
                        content = f"""TABLE: inputs_params
COLUMN: Value
NEW_VALUE: {extracted_value}
WHERE_CONDITION: Parameter = '{best_match}'
DESCRIPTION: Update {best_match.lower()} parameter using fuzzy matching"""
                    else:
                        # Try direct fuzzy matching on the entire message
                        print(f"DEBUG: No direct keywords found, trying fuzzy match on entire message")
                        words_in_message = last_message.lower().split()
                        for param in available_parameters:
                            param_words = param.lower().split()
                            for word in words_in_message:
                                if len(word) > 2:  # Skip very short words
                                    fuzzy_result = fuzzy_match_parameter(word, available_parameters)
                                    if fuzzy_result:
                                        import difflib
                                        confidence = difflib.SequenceMatcher(None, word, fuzzy_result.lower()).ratio()
                                        if confidence > best_confidence and confidence > 0.6:
                                            best_match = fuzzy_result
                                            best_confidence = confidence
                        
                        if best_match:
                            print(f"DEBUG: Fallback fuzzy matched parameter '{best_match}' with confidence {best_confidence:.2f}")
                            content = f"""TABLE: inputs_params
COLUMN: Value
NEW_VALUE: {extracted_value}
WHERE_CONDITION: Parameter = '{best_match}'
DESCRIPTION: Update {best_match.lower()} parameter using fallback fuzzy matching"""
                        else:
                            print(f"DEBUG: No fuzzy match found, falling back to LLM")
                            content = None
                
                # If fuzzy matching didn't work, fall back to LLM
                if content is None:
                    print(f"DEBUG: Fuzzy matching failed, using LLM with enhanced prompts")
                    enhanced_prompt = f"""{system_prompt}

EXTRACTED VALUE FROM REQUEST: {extracted_value if extracted_value else 'NOT_FOUND'}
EXTRACTED TABLE FROM REQUEST: {extracted_table if extracted_table else 'NOT_SPECIFIED'}

Available parameters in inputs_params table for reference:
{available_parameters if 'available_parameters' in locals() and available_parameters else 'Not available'}

The user's exact request was: "{last_message}"

Please identify the closest matching parameter name from the available parameters list above.
Use fuzzy matching if needed - small typos or missing letters should not prevent correct identification."""

                    response = self.llm.invoke([HumanMessage(content=f"{enhanced_prompt}\n\nModification Request: {last_message}")])
                    content = response.content.strip()
            else:
                # Enhanced prompt with the extracted values
                enhanced_prompt = f"""{system_prompt}

EXTRACTED VALUE FROM REQUEST: {extracted_value if extracted_value else 'NOT_FOUND'}
EXTRACTED TABLE FROM REQUEST: {extracted_table if extracted_table else 'NOT_SPECIFIED'}

If EXTRACTED VALUE is NOT_FOUND, you MUST look harder in the request text: "{last_message}"
If EXTRACTED TABLE is specified, prioritize that table for the modification.

For Hub Demand requests, always respond:
TABLE: inputs_params
COLUMN: Value  
NEW_VALUE: {extracted_value if extracted_value else '[EXTRACT_FROM_REQUEST]'}
WHERE_CONDITION: Parameter = 'Minimum Hub Demand' OR Parameter = 'Maximum Hub Demand' (depending on request)
DESCRIPTION: Update minimum or maximum hub demand parameter"""

                response = self.llm.invoke([HumanMessage(content=f"{enhanced_prompt}\n\nModification Request: {last_message}")])
                content = response.content.strip()
            
            # Parse the response and clean backticks/formatting
            modification_data = {}
            for line in content.split('\n'):
                if line.startswith('TABLE:'):
                    modification_data['table'] = line.replace('TABLE:', '').strip('`').strip()
                elif line.startswith('COLUMN:'):
                    modification_data['column'] = line.replace('COLUMN:', '').strip('`').strip()
                elif line.startswith('NEW_VALUE:'):
                    modification_data['new_value'] = line.replace('NEW_VALUE:', '').strip('`').strip()
                elif line.startswith('WHERE_CONDITION:'):
                    modification_data['where_condition'] = line.replace('WHERE_CONDITION:', '').strip('`').strip()
                elif line.startswith('DESCRIPTION:'):
                    modification_data['description'] = line.replace('DESCRIPTION:', '').strip()
            
            # Debug: Log the raw response and parsed data
            print(f"DEBUG: LLM raw response for modification: {content}")
            print(f"DEBUG: Parsed modification data: {modification_data}")
            
            # Get current value if possible
            current_value = "unknown"
            # Try to find the database file
            database_path = None
            if state.get("database_path"):
                database_path = state["database_path"]
            elif state.get("temp_dir"):
                # Look for any .db file in temp_dir
                import glob
                db_files = glob.glob(os.path.join(state["temp_dir"], "*.db"))
                if db_files:
                    database_path = db_files[0]
            
            if database_path and os.path.exists(database_path) and modification_data.get('table') and modification_data.get('column'):
                try:
                    conn = sqlite3.connect(database_path)
                    cursor = conn.cursor()
                    
                    # If there's a WHERE condition, use it to get the specific value
                    where_condition = modification_data.get('where_condition')
                    if where_condition:
                        query = f"SELECT {modification_data['column']} FROM {modification_data['table']} WHERE {where_condition}"
                        cursor.execute(query)
                        result = cursor.fetchone()
                        current_value = result[0] if result else "Not found"
                    else:
                        # Fall back to getting distinct values
                        cursor.execute(f"SELECT DISTINCT {modification_data['column']} FROM {modification_data['table']} LIMIT 5")
                        values = cursor.fetchall()
                        if values:
                            current_value = values[0][0] if len(values) == 1 else f"Multiple values: {[v[0] for v in values]}"
                    
                    conn.close()
                except Exception as e:
                    current_value = f"Error retrieving: {str(e)}"
            
            modification_data['current_value'] = current_value
            
            # Check if we successfully identified table and column  
            if not modification_data.get('table') or not modification_data.get('column') or modification_data.get('table') == 'Unknown':
                # Provide fallback error with schema information
                schema_tables = []
                if state.get("database_schema"):
                    schema_data = state["database_schema"].get("tables", [])
                    schema_tables = [t["name"] for t in schema_data if isinstance(t, dict) and "name" in t]
                elif self.cached_database_schema:
                    schema_data = self.cached_database_schema.get("tables", [])
                    schema_tables = [t["name"] for t in schema_data if isinstance(t, dict) and "name" in t]
                
                error_msg = f"❌ Could not identify which table/column to modify.\n\n"
                error_msg += f"**Available tables in database:** {', '.join(schema_tables)}\n\n"
                error_msg += f"**Please specify the exact table name, for example:**\n"
                error_msg += f"• 'Change maximum hub demand to 20000 in inputs_params'\n"
                error_msg += f"• 'Update cost to 500 in routes table'\n"
                error_msg += f"• 'Set capacity to 15000 in hubs_data'\n"
                error_msg += f"• 'Modify value to 25000 in parameters'\n\n"
                error_msg += f"**Alternative syntax:**\n"
                error_msg += f"• 'Change x in [table_name] to [value]'\n"
                error_msg += f"• 'Update [column] in [table] to [value]'\n\n"
                if extracted_table:
                    error_msg += f"**Note:** I detected you mentioned table '{extracted_table}', but couldn't find it or identify the column. Please check the table name.\n\n"
                error_msg += f"Raw analysis: {content}"
                
                return {
                    **state,
                    "modification_request": {},  # Clear any old modification data when parsing fails
                    "messages": state["messages"] + [AIMessage(content=error_msg)]
                }
            
            # Special handling for inputs_params table - add WHERE condition if not specified
            if modification_data.get('table') == 'inputs_params' and not modification_data.get('where_condition'):
                # Look for hub demand parameters in the request
                if 'hub demand' in last_message.lower():
                    if 'minimum' in last_message.lower():
                        parameter_name = 'Minimum Hub Demand'
                    else:
                        parameter_name = 'Maximum Hub Demand'
                    modification_data['where_condition'] = f"Parameter = '{parameter_name}'"
                    print(f"DEBUG: Added automatic WHERE condition for inputs_params: {modification_data['where_condition']}")
            
            # If we have the correct table but the LLM didn't extract the numeric value, try again
            if (modification_data.get('table') == 'inputs_params' and 
                modification_data.get('new_value') in ['<exact_numeric_value_from_request>', '[EXTRACT_FROM_REQUEST]', None] and
                extracted_value):
                modification_data['new_value'] = extracted_value
                print(f"DEBUG: Fixed new_value using extracted value: {extracted_value}")
            
            # Ensure we have a proper WHERE condition for parameter tables
            if 'param' in modification_data.get('table', '').lower() and not modification_data.get('where_condition'):
                # Default WHERE condition to prevent updating all parameters
                modification_data['where_condition'] = "1=0"  # This will prevent any updates without proper WHERE
                print(f"DEBUG: Added safety WHERE condition to prevent bulk updates")
            
            return {
                **state,
                "modification_request": modification_data,
                "identified_tables": [modification_data.get('table', '')],
                "identified_columns": [modification_data.get('column', '')],
                "current_values": {modification_data.get('column', ''): current_value},
                "new_values": {modification_data.get('column', ''): modification_data.get('new_value', '')},
                "messages": state["messages"] + [AIMessage(content=f"Identified modification: {modification_data}")]
            }
            
        except Exception as e:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"Error analyzing modification request: {str(e)}")]
            }
    
    def _execute_db_modification_node(self, state: AgentState) -> AgentState:
        """Execute the database modification with detailed change tracking and parameter validation"""
        # Clear any old modification data and get fresh data
        state_copy = dict(state)
        if "modification_request" in state_copy and not state_copy["modification_request"]:
            # Remove empty modification request to prevent using stale data
            del state_copy["modification_request"]
            print(f"DEBUG: Cleared empty modification_request from state")
        
        modification_data = state_copy.get("modification_request", {})
        
        # Additional check for stale data
        if modification_data and len(str(state.get("messages", []))) > 0:
            last_message = str(state["messages"][-1].content if state["messages"] else "")
            if modification_data.get("where_condition") and modification_data.get("where_condition") not in last_message:
                print(f"DEBUG: Detected stale modification data, clearing it")
                modification_data = {}
        
        print(f"DEBUG: Execute modification - modification_data: {modification_data}")
        print(f"DEBUG: Execute modification - state keys: {list(state.keys())}")
        
        if not modification_data:
            print(f"DEBUG: No modification data found in state")
            
            # Try to provide helpful information about what went wrong
            error_msg = "❌ **No modification data available.** The preparation step may have failed.\n\n"
            
            # Check if we have database schema information
            if state.get("database_schema") or self.cached_database_schema:
                available_tables = []
                if state.get("database_schema"):
                    schema_data = state["database_schema"].get("tables", [])
                    available_tables = [t["name"] for t in schema_data if isinstance(t, dict) and "name" in t]
                elif self.cached_database_schema:
                    schema_data = self.cached_database_schema.get("tables", [])
                    available_tables = [t["name"] for t in schema_data if isinstance(t, dict) and "name" in t]
                
                error_msg += f"**Available tables in database ({len(available_tables)} total):**\n"
                for table in available_tables:
                    error_msg += f"• {table}\n"
                error_msg += f"\n**Please try again with one of the table names above.**"
            else:
                error_msg += "**Unable to retrieve database schema information.**"
            
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=error_msg)]
            }
        
        # Try to find the database file
        database_path = None
        if state.get("database_path"):
            database_path = state["database_path"]
        elif state.get("temp_dir"):
            # Look for any .db file in temp_dir
            import glob
            db_files = glob.glob(os.path.join(state["temp_dir"], "*.db"))
            if db_files:
                database_path = db_files[0]
        
        if not database_path or not os.path.exists(database_path):
            error_message = "❌ No database file found for modification."
            return {
                **state,
                "db_modification_result": {
                    "success": False,
                    "error": "No database file found"
                },
                "messages": state["messages"] + [AIMessage(content=error_message)]
            }
        
        # Import parameter synchronization module for validation
        try:
            from model_parameter_sync import ModelParameterSync
            param_sync = ModelParameterSync(database_path)
            # Create parameter snapshot before modification
            before_snapshot = param_sync.create_parameter_snapshot()
            print(f"DEBUG: Created parameter snapshot before modification")
        except ImportError:
            print("DEBUG: ModelParameterSync module not available, proceeding without parameter validation")
            param_sync = None
        except Exception as e:
            print(f"DEBUG: Could not initialize parameter synchronization: {e}")
            param_sync = None
        
        try:
            # Extract modification details and clean backticks
            table = modification_data.get('table', '').strip('`').strip()
            column = modification_data.get('column', '').strip('`').strip()
            new_value = modification_data.get('new_value', '').strip('`').strip()
            where_condition = modification_data.get('where_condition', '').strip('`').strip()
            
            # Connect to database
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()
            
            # Helper function to properly quote column/table names with special characters
            def quote_identifier(name):
                if ':' in name or ' ' in name or name.startswith('Unnamed'):
                    return f'"{name}"'
                return name
            
            # Get old value(s) before modification
            old_values = []
            try:
                quoted_column = quote_identifier(column)
                quoted_table = quote_identifier(table)
                
                if where_condition:
                    # Parse where condition to quote column names properly
                    # Handle cases like: Unnamed: 2 = 'Maximum Hub Demand'
                    where_parts = where_condition.split('=', 1)
                    if len(where_parts) == 2:
                        left_part = where_parts[0].strip()
                        right_part = where_parts[1].strip()
                        quoted_left = quote_identifier(left_part)
                        formatted_where = f"{quoted_left} = {right_part}"
                    else:
                        formatted_where = where_condition
                    
                    check_sql = f"SELECT {quoted_column} FROM {quoted_table} WHERE {formatted_where}"
                else:
                    check_sql = f"SELECT {quoted_column} FROM {quoted_table}"
                
                print(f"DEBUG: Executing query: {check_sql}")
                cursor.execute(check_sql)
                results = cursor.fetchall()
                old_values = [str(row[0]) for row in results]
            except Exception as e:
                print(f"DEBUG: Error retrieving old values: {e}")
                old_values = [f"Could not retrieve: {e}"]
            
            # Generate SQL UPDATE statement with proper quoting
            try:
                float(new_value)
                sql = f"UPDATE {quoted_table} SET {quoted_column} = {new_value}"
            except ValueError:
                sql = f"UPDATE {quoted_table} SET {quoted_column} = '{new_value}'"
            
            # Add WHERE condition if specified (use the formatted where condition)
            if where_condition:
                if 'formatted_where' in locals():
                    sql += f" WHERE {formatted_where}"
                else:
                    # Fallback formatting
                    where_parts = where_condition.split('=', 1)
                    if len(where_parts) == 2:
                        left_part = where_parts[0].strip()
                        right_part = where_parts[1].strip()
                        quoted_left = quote_identifier(left_part)
                        sql += f" WHERE {quoted_left} = {right_part}"
                    else:
                        sql += f" WHERE {where_condition}"
            
            # Execute the modification
            cursor.execute(sql)
            rows_affected = cursor.rowcount
            conn.commit()
            
            # Verify the change using the same query structure
            new_values = []
            try:
                # Reconstruct the check query since cursor might be closed
                if where_condition:
                    if 'formatted_where' in locals():
                        verify_sql = f"SELECT {quoted_column} FROM {quoted_table} WHERE {formatted_where}"
                    else:
                        where_parts = where_condition.split('=', 1)
                        if len(where_parts) == 2:
                            left_part = where_parts[0].strip()
                            right_part = where_parts[1].strip()
                            quoted_left = quote_identifier(left_part)
                            verify_sql = f"SELECT {quoted_column} FROM {quoted_table} WHERE {quoted_left} = {right_part}"
                        else:
                            verify_sql = f"SELECT {quoted_column} FROM {quoted_table} WHERE {where_condition}"
                else:
                    verify_sql = f"SELECT {quoted_column} FROM {quoted_table}"
                
                print(f"DEBUG: Verification query: {verify_sql}")
                cursor.execute(verify_sql)
                results = cursor.fetchall()
                new_values = [str(row[0]) for row in results]
            except Exception as e:
                print(f"DEBUG: Error verifying change: {e}")
                new_values = [f"Could not verify: {e}"]
            
            conn.close()
            
            # Validate parameter changes if parameter sync is available
            parameter_validation = None
            if param_sync:
                try:
                    # Create change record for validation
                    change_record = [{
                        'table': table,
                        'column': column,
                        'new_value': new_value,
                        'where_condition': where_condition
                    }]
                    
                    # Validate the changes
                    validation_result = param_sync.validate_parameter_changes(change_record)
                    parameter_validation = validation_result
                    
                    print(f"DEBUG: Parameter validation result: {validation_result}")
                except Exception as e:
                    print(f"DEBUG: Could not validate parameter changes: {e}")
            
            # Format detailed change report
            change_summary = "🔧 **DATABASE MODIFICATION COMPLETED**\n\n"
            change_summary += f"📊 **Table:** `{table}`\n"
            change_summary += f"📝 **Column:** `{column}`\n"
            change_summary += f"🔄 **Change:**\n"
            
            if len(old_values) == 1 and len(new_values) == 1:
                change_summary += f"   - **Before:** {old_values[0]}\n"
                change_summary += f"   - **After:** {new_values[0]}\n"
            else:
                change_summary += f"   - **Rows affected:** {rows_affected}\n"
                change_summary += f"   - **Old values:** {', '.join(old_values[:5])}{'...' if len(old_values) > 5 else ''}\n"
                change_summary += f"   - **New value:** {new_value}\n"
            
            change_summary += f"\n📈 **Rows affected:** {rows_affected}\n"
            change_summary += f"💾 **SQL executed:** `{sql}`\n\n"
            
            # Add parameter validation results if available
            if parameter_validation:
                if parameter_validation["success"]:
                    change_summary += "✅ **Parameter validation:** Changes successfully applied and verified\n"
                else:
                    # Check if the database update was actually successful despite validation issues
                    if len(old_values) == 1 and len(new_values) == 1:
                        old_val = old_values[0]
                        new_val = new_values[0]
                        # If the values actually changed, the update was successful
                        if old_val != new_val:
                            change_summary += "✅ **Parameter validation:** Database update successful (validation had minor issues)\n"
                            change_summary += "   - The parameter value was successfully changed in the database\n"
                            change_summary += "   - Validation encountered some technical issues but the change was applied\n"
                        else:
                            change_summary += "⚠️ **Parameter validation:** Issues detected with parameter changes\n"
                            for error in parameter_validation.get("errors", []):
                                change_summary += f"   - {error}\n"
                    else:
                        change_summary += "⚠️ **Parameter validation:** Some issues detected with parameter changes\n"
                        for error in parameter_validation.get("errors", []):
                            change_summary += f"   - {error}\n"
            
            change_summary += "\n✅ **Database successfully updated.** Models will use the latest parameters when executed."
            
            # Print to console for debugging
            print(f"\n=== DATABASE CHANGE DETAILS ===")
            print(f"Table: {table}")
            print(f"Column: {column}")
            print(f"Old value(s): {old_values}")
            print(f"New value: {new_value}")
            print(f"Rows affected: {rows_affected}")
            print(f"SQL: {sql}")
            if parameter_validation:
                print(f"Parameter validation: {parameter_validation['success']}")
            print("================================\n")
            
            return {
                **state,
                "modification_sql": sql,
                "parameter_validation": parameter_validation,
                "db_modification_result": {
                    "success": True,
                    "rows_affected": rows_affected,
                    "sql": sql,
                    "table": table,
                    "column": column,
                    "old_values": old_values,
                    "new_value": new_value,
                    "parameter_validation": parameter_validation
                },
                "messages": state["messages"] + [AIMessage(content=change_summary)]
            }
            
        except Exception as e:
            error_message = f"❌ Database modification failed: {str(e)}"
            print(f"DEBUG: Database modification error: {e}")
            return {
                **state,
                "db_modification_result": {
                    "success": False,
                    "error": str(e)
                },
                "messages": state["messages"] + [AIMessage(content=error_message)]
            }
    
    def _find_and_run_models_node(self, state: AgentState) -> AgentState:
        """Find available Python model files and determine execution strategy"""
        temp_dir = state.get("temp_dir", ".")
        
        # Find all Python files
        python_files = []
        runall_file = None
        
        try:
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.py'):
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, temp_dir)
                        python_files.append(rel_path)
                        
                        if file.lower() == 'runall.py':
                            runall_file = rel_path
            
            # Store found models
            state_update = {
                **state,
                "available_models": python_files
            }
            
            if runall_file:
                state_update["selected_models"] = [runall_file]
                message = f"Found runall.py - will execute it automatically along with {len(python_files)} total Python files."
            elif python_files:
                message = f"Found {len(python_files)} Python files. Will request user to select which to run."
            else:
                message = "No Python model files found in the project."
            
            state_update["messages"] = state["messages"] + [AIMessage(content=message)]
            return state_update
            
        except Exception as e:
            return {
                **state,
                "available_models": [],
                "messages": state["messages"] + [AIMessage(content=f"Error finding model files: {str(e)}")]
            }
    
    def _route_model_execution(self, state: AgentState) -> str:
        """Route model execution based on available files"""
        available_models = state.get("available_models", [])
        selected_models = state.get("selected_models", [])
        
        if not available_models:
            return "no_models"
        elif selected_models and any(model.lower().endswith('runall.py') for model in selected_models):
            return "run_all"
        else:
            return "select_models"
    
    def _request_model_selection_node(self, state: AgentState) -> AgentState:
        """Request user to select which models to run (human-in-the-loop)"""
        available_models = state.get("available_models", [])
        
        approval_message = "🔧 **Model Selection Required**\n\n"
        approval_message += "The following Python model files were found:\n\n"
        
        for i, model in enumerate(available_models, 1):
            approval_message += f"{i}. {model}\n"
        
        approval_message += "\nWhich models would you like to execute? (provide numbers separated by commas, or 'all' for all models)"
        
        return {
            **state,
            "approval_required": True,
            "approval_message": approval_message,
            "pending_approval": {
                "type": "MODEL_SELECTION",
                "models": available_models,
                "message": approval_message
            },
            "interrupt_reason": "MODEL_SELECTION_REQUIRED",
            "messages": state["messages"] + [AIMessage(content=approval_message)]
        }
    
    def _execute_selected_models_node(self, state: AgentState) -> AgentState:
        """Execute the selected model files with parameter synchronization"""
        selected_models = state.get("selected_models", [])
        temp_dir = state.get("temp_dir", ".")
        
        if not selected_models:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="No models selected for execution.")]
            }
        
        # Import parameter synchronization module
        try:
            from model_parameter_sync import ModelParameterSync
        except ImportError:
            # If module not available, proceed without parameter sync
            print("DEBUG: ModelParameterSync module not available, proceeding without parameter validation")
            ModelParameterSync = None
        
        execution_results = []
        parameter_validation_results = []
        
        # Find database path
        database_path = None
        if state.get("database_path"):
            database_path = state["database_path"]
        else:
            import glob
            db_files = glob.glob(os.path.join(temp_dir, "*.db"))
            if db_files:
                database_path = db_files[0]
        
        # Initialize parameter synchronization if database is available
        param_sync = None
        if ModelParameterSync and database_path and os.path.exists(database_path):
            try:
                param_sync = ModelParameterSync(database_path)
                # Create parameter snapshot before execution
                before_snapshot = param_sync.create_parameter_snapshot()
                print(f"DEBUG: Created parameter snapshot before model execution")
            except Exception as e:
                print(f"DEBUG: Could not initialize parameter synchronization: {e}")
        
        for model_file in selected_models:
            try:
                model_path = os.path.join(temp_dir, model_file)
                if os.path.exists(model_path):
                    # Validate model file for parameter synchronization
                    model_analysis = None
                    if param_sync:
                        try:
                            model_analysis = param_sync.ensure_model_reads_latest_params(model_path)
                            if model_analysis.get("recommendations"):
                                parameter_validation_results.append(f"⚠️ {model_file}: Parameter sync recommendations:")
                                for rec in model_analysis["recommendations"]:
                                    parameter_validation_results.append(f"   - {rec}")
                        except Exception as e:
                            print(f"DEBUG: Could not analyze model {model_file}: {e}")
                    
                    # Execute the model
                    result = self._run_python_file(model_path, temp_dir)
                    
                    if hasattr(result, 'returncode'):
                        if result.returncode == 0:
                            execution_output = result.stdout
                            execution_results.append(f"✅ {model_file}: Success\nOutput: {execution_output}")
                            
                            # Generate parameter validation summary
                            if param_sync:
                                try:
                                    summary = param_sync.generate_model_execution_summary(model_file, execution_output)
                                    param_validation = summary["parameter_validation"]
                                    parameter_validation_results.append(
                                        f"📊 {model_file}: Parameters validated - "
                                        f"{param_validation['total_parameters']} parameters from "
                                        f"{param_validation['parameter_tables_found']} tables - "
                                        f"{param_validation['validation_status']}"
                                    )
                                except Exception as e:
                                    print(f"DEBUG: Could not generate parameter summary for {model_file}: {e}")
                        else:
                            execution_results.append(f"❌ {model_file}: Failed\nError: {result.stderr}")
                    else:
                        execution_results.append(f"⚠️ {model_file}: {str(result)}")
                else:
                    execution_results.append(f"❌ {model_file}: File not found")
                    
            except Exception as e:
                execution_results.append(f"❌ {model_file}: Exception - {str(e)}")
        
        # Create parameter comparison if we have before/after snapshots
        if param_sync and 'before_snapshot' in locals():
            try:
                after_snapshot = param_sync.create_parameter_snapshot()
                comparison = param_sync.compare_parameter_snapshots(before_snapshot, after_snapshot)
                
                if comparison["changes"]:
                    parameter_validation_results.append(f"🔄 Parameter changes detected during model execution:")
                    for change in comparison["changes"]:
                        parameter_validation_results.append(
                            f"   - {change['parameter']}: {change['before']} → {change['after']} "
                            f"(table: {change['table']})"
                        )
                else:
                    parameter_validation_results.append("✅ No parameter changes detected during model execution")
                    
            except Exception as e:
                print(f"DEBUG: Could not compare parameter snapshots: {e}")
        
        result_message = "🔄 **Model Execution Results:**\n\n"
        result_message += "\n\n".join(execution_results)
        
        if parameter_validation_results:
            result_message += "\n\n📊 **Parameter Validation:**\n\n"
            result_message += "\n".join(parameter_validation_results)
        
        # Clean up auto-generated CSV and Excel files since everything should work from the database
        self._cleanup_model_generated_files(temp_dir)
        
        return {
            **state,
            "model_execution_results": execution_results,
            "parameter_validation_results": parameter_validation_results,
            "execution_output": "\n".join(execution_results),
            "messages": state["messages"] + [AIMessage(content=result_message)]
        }
    
    def _database_modifier_node(self, state: AgentState) -> AgentState:
        """Database modifier node - delegates to database_modifier agent"""
        # This node is used when the data_analyst workflow needs database modifications
        # It should switch to the database_modifier agent workflow
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content="🔄 Switching to database modifier agent for parameter changes...")]
        }
    
    # Missing database_modifier workflow methods
    def _analyze_modification_request(self, state: AgentState) -> AgentState:
        """Analyze database modification request (database_modifier agent)"""
        return self._prepare_db_modification_node(state)
    
    def _prepare_modification_node(self, state: AgentState) -> AgentState:
        """Prepare modification (database_modifier agent)"""
        return self._prepare_db_modification_node(state)
    
    def _execute_modification_node(self, state: AgentState) -> AgentState:
        """Execute modification (database_modifier agent)"""
        return self._execute_db_modification_node(state)
    
    def _find_models_node(self, state: AgentState) -> AgentState:
        """Find models (database_modifier agent)"""
        return self._find_and_run_models_node(state)
    
    def _execute_models_node(self, state: AgentState) -> AgentState:
        """Execute models (database_modifier agent)"""
        return self._execute_selected_models_node(state)
    
    def _cleanup_model_generated_files(self, temp_dir: str) -> None:
        """Import generated CSV files back to database, then clean up"""
        try:
            # First, update the database with any newly generated output data
            self._import_model_outputs_to_database(temp_dir)
            
            # Then clean up the CSV/Excel files
            cleanup_patterns = [
                "*.csv",
                "*.xlsx", 
                "*.xls",
                "**/*.csv",
                "**/*.xlsx",
                "**/*.xls"
            ]
            
            files_removed = []
            for pattern in cleanup_patterns:
                for file_path in glob.glob(os.path.join(temp_dir, pattern), recursive=True):
                    # Skip if it's the original database or certain important files
                    filename = os.path.basename(file_path)
                    if filename.lower() in ['project_data.db', 'database_summary.md']:
                        continue
                    
                    try:
                        os.remove(file_path)
                        files_removed.append(os.path.relpath(file_path, temp_dir))
                    except Exception as e:
                        print(f"DEBUG: Could not remove {file_path}: {e}")
            
            if files_removed:
                print(f"DEBUG: Cleaned up {len(files_removed)} auto-generated files after importing to database")
            
        except Exception as e:
            print(f"DEBUG: Error during cleanup: {e}")
    
    def _import_model_outputs_to_database(self, temp_dir: str) -> None:
        """Import generated CSV files back into the database to keep it up-to-date"""
        try:
            # Find the database file
            database_path = None
            db_files = glob.glob(os.path.join(temp_dir, "*.db"))
            if db_files:
                database_path = db_files[0]
            
            if not database_path or not os.path.exists(database_path):
                print("DEBUG: No database file found for importing model outputs")
                return
            
            conn = sqlite3.connect(database_path)
            cursor = conn.cursor()
            
            # Find CSV files that look like model outputs
            csv_files = []
            for root, dirs, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.csv'):
                        csv_files.append(os.path.join(root, file))
            
            tables_updated = []
            
            for csv_file in csv_files:
                try:
                    # Get table name from file path
                    rel_path = os.path.relpath(csv_file, temp_dir)
                    
                    # Generate table name based on file structure
                    if 'Outputs/' in rel_path:
                        # Output files - these contain model results
                        table_name = rel_path.replace('Outputs/', '').replace('.csv', '').replace('/', '_')
                    elif 'Inputs/' in rel_path:
                        # Input files - skip these as they shouldn't overwrite original inputs
                        continue
                    else:
                        # Root level CSV files
                        table_name = os.path.basename(csv_file).replace('.csv', '')
                    
                    # Sanitize table name
                    table_name = re.sub(r'[^a-zA-Z0-9_]', '_', table_name)
                    
                    # Read CSV and import to database
                    df = pd.read_csv(csv_file)
                    
                    if len(df) > 0:
                        # Drop existing table and recreate (for output tables)
                        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                        
                        # Import CSV to database
                        df.to_sql(table_name, conn, index=False, if_exists='replace')
                        tables_updated.append(table_name)
                        
                        print(f"DEBUG: Updated database table '{table_name}' with {len(df)} rows from {rel_path}")
                    
                except Exception as e:
                    print(f"DEBUG: Could not import {csv_file} to database: {e}")
            
            conn.commit()
            conn.close()
            
            if tables_updated:
                print(f"DEBUG: Successfully updated {len(tables_updated)} database tables with model outputs: {tables_updated}")
            else:
                print("DEBUG: No model output files found to import to database")
                
        except Exception as e:
            print(f"DEBUG: Error importing model outputs to database: {e}")

def create_agent(ai_model: str, temp_dir: str, agent_type: str = None) -> CodeExecutorAgent:
    """Factory function to create an agent"""
    return CodeExecutorAgent(ai_model=ai_model, temp_dir=temp_dir, agent_type=agent_type) 
