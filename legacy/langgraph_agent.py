import os
import time
from typing import Dict, List, Tuple, Literal, Annotated, Optional
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
    }
    return configs.get(agent_type, AgentConfig())
import re
import sqlite3
import glob
import pandas as pd
import uuid
import json

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
    # New field for scenario management
    scenario_id: Optional[int]

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
        self.cached_full_schema = None  # Store original unfiltered schema
        
        # Scenario management
        self.current_scenario_id = None
        self.current_database_path = None
    
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
            workflow.add_node("create_visualization", self._create_visualization_node)
            workflow.add_node("execute_sql_query", self._execute_sql_query_node)
            workflow.add_node("prepare_db_modification", self._prepare_db_modification_node)
            workflow.add_node("execute_db_modification", self._execute_db_modification_node)
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
            
            # Visualization path - creates visualization file then executes it
            workflow.add_edge("create_visualization", "execute_file")
            
            # Database modification path - direct execution without approval
            workflow.add_edge("prepare_db_modification", "execute_db_modification")
            workflow.add_edge("execute_db_modification", "respond")
            
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
                    "respond": "respond"
                }
            )
            
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
        """Set the cached database schema and apply whitelist filtering"""
        self.cached_full_schema = schema  # Store original schema
        self.cached_database_schema = self._filter_schema_by_whitelist(schema)
        print(f"DEBUG: Cached database schema set with {schema.get('total_tables', 0)} total tables, {self.cached_database_schema.get('total_tables', 0)} whitelisted")

    def _filter_schema_by_whitelist(self, schema: Dict[str, any]) -> Dict[str, any]:
        """Filter database schema to only include whitelisted tables"""
        if not schema or not schema.get("tables"):
            return schema
        
        # Get current whitelist
        try:
            import main
            current_whitelist = main.get_table_whitelist()
        except Exception as e:
            print(f"DEBUG: Could not get whitelist for schema filtering: {e}")
            # If we can't get whitelist, return original schema to avoid breaking functionality
            return schema
        
        if not current_whitelist:
            print(f"DEBUG: No whitelist found, returning empty schema to prevent unauthorized modifications")
            return {
                "database_path": schema.get("database_path", ""),
                "total_tables": 0,
                "tables": []
            }
        
        # Filter tables to only include whitelisted ones
        original_tables = schema["tables"]
        filtered_tables = []
        
        for table_info in original_tables:
            table_name = table_info.get("name", "")
            if table_name in current_whitelist:
                filtered_tables.append(table_info)
                print(f"DEBUG: Including whitelisted table: {table_name}")
            else:
                print(f"DEBUG: Excluding non-whitelisted table: {table_name}")
        
        # Create filtered schema
        filtered_schema = {
            "database_path": schema.get("database_path", ""),
            "total_tables": len(filtered_tables),
            "tables": filtered_tables
        }
        
        print(f"DEBUG: Schema filtered: {len(original_tables)} -> {len(filtered_tables)} tables")
        return filtered_schema

    def refresh_schema_whitelist(self):
        """Refresh the cached schema with updated whitelist filtering"""
        if hasattr(self, 'cached_full_schema') and self.cached_full_schema:
            self.cached_database_schema = self._filter_schema_by_whitelist(self.cached_full_schema)
            print(f"DEBUG: Schema whitelist refreshed: {self.cached_database_schema.get('total_tables', 0)} tables available")
        else:
            print(f"DEBUG: No full schema available for refresh")

    def _get_cached_database_schema(self) -> Dict[str, any]:
        """Get cached database schema (filtered by whitelist)"""
        return self.cached_database_schema
    
    def _get_full_database_schema(self) -> Dict[str, any]:
        """Get full database schema (unfiltered) for queries and visualizations"""
        return self.cached_full_schema if hasattr(self, 'cached_full_schema') else self.cached_database_schema



    def _code_fixer_node(self, state: AgentState) -> AgentState:
        """Intelligent code fixer agent - analyzes and fixes execution errors"""
        # Check retry count - stop if max retries reached
        retry_count = state.get("retry_count", 0)
        if retry_count >= 3:  # Max retries reached
            return {
                **state, 
                "messages": state["messages"] + [AIMessage(content=f"❌ Max retries ({retry_count}) reached. Giving up on fixing this code.")]
            }
        
        # Get the current file that had errors
        current_file = state.get("current_file", "")
        if not current_file or current_file not in state["files"]:
            return {**state, "messages": state["messages"] + [AIMessage(content="❌ No file to fix")]}
        
        # Read the current file content
        file_path = state["files"][current_file]
        try:
            # Try UTF-8 first, then fallback to other encodings
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    file_content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='latin-1') as f:
                        file_content = f.read()
                except UnicodeDecodeError:
                    with open(file_path, 'r', encoding='cp1252') as f:
                        file_content = f.read()
        except Exception as e:
            return {**state, "messages": state["messages"] + [AIMessage(content=f"❌ Could not read file: {str(e)}")]}
        
        # Get execution error details
        execution_error = state.get("execution_error", "")
        last_error_type = state.get("last_error_type", "")
        
        # Use intelligent code fixer configuration
        code_fixer_config = get_agent_config("code_fixer")
        system_prompt = f"""{code_fixer_config.system_prompt}
        
        FILE TO FIX: {current_file}
        RETRY COUNT: {state.get("retry_count", 0)}
        
        CURRENT FILE CONTENT:
{file_content}

        EXECUTION ERROR:
{execution_error}

        ERROR TYPE: {last_error_type}
        
        TASK: Fix the code error and provide the corrected version using the required format.
        
        COMMON FIXES NEEDED:
        1. **NameError: name 'python' is not defined** → Remove any standalone "python" lines (markdown artifacts)
        2. **NameError: name 'query' is not defined** → Remove references to undefined 'query' variable, use hardcoded table name
        3. **NameError: name 'col' is not defined** → Fix variable scope issues in loops
        4. **NameError: name 'e' is not defined** → Remove orphaned exception print statements outside try/except blocks
        5. **DatabaseError: no such column** → Check database schema and use correct column names
        6. **SyntaxError** → Fix Python syntax issues
        7. **ImportError** → Add missing imports
        8. **FileNotFoundError** → Fix file path issues
        9. **ensure_numeric_columns not defined** → Add the function definition or remove the call
        
        DATABASE SCHEMA CONTEXT:
        {self._build_schema_context(self.cached_database_schema) if self.cached_database_schema else "No schema available"}
        
        IMPORTANT: 
        - If you see markdown artifacts (```) in the code, remove them completely
        - If there are syntax errors, fix the Python syntax
        - If there are missing imports, add them
        - If there are database column errors, check the schema and use correct column names
        - If you see standalone "python" lines, remove them (they're markdown artifacts)
        - For visualization errors: ensure ensure_numeric_columns function is defined if called
        - For NameError with 'query': replace with hardcoded table name like 'inputs_destinations'
        - For NameError with 'col' or 'e': fix variable scope issues or remove orphaned statements
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
                
                # Add the AI response to messages so the router can see the fix keywords
                new_messages = state["messages"] + [response]
                
                print(f"DEBUG: Code fixer completed successfully: {filename}, fix type: {fix_type}")
                
                return {
                    **state,
                    "created_files": new_created_files,
                    "files": new_files,
                    "messages": new_messages,
                    "current_file": filename,
                    "retry_count": new_retry_count,
                    # Keep error flags so execution continues to test the fix
                    "has_execution_error": True,
                    "last_error_type": "CodeFixApplied"
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
        """Route after file execution with model selection checks"""
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
        
        # Handle code fix applied - continue to execute the fixed code
        if last_error_type == "CodeFixApplied":
            print(f"DEBUG: Execution router - Code fix applied, continuing to execute")
            return "execute"
        
        # Always route to code fixer for any execution error (except special cases)
        execution_error = state.get("execution_error", "")
        if execution_error.strip():  # If there's any error content
            print(f"DEBUG: Execution router - Error detected, routing to code fixer")
            return "retry"
        
        # Check retry count
        retry_count = state.get("retry_count", 0)
        if retry_count >= 3:  # Increased max retries to 3
            print("DEBUG: Execution router - Max retries reached, routing to error")
            return "error"
        else:
            print("DEBUG: Execution router - Retry count < 5, routing to retry")
            return "retry"

    def _code_fixer_router(self, state: AgentState) -> str:
        """Route code fixer output to either execute or respond"""
        # Get the last message content
        last_message = state["messages"][-1].content if state["messages"] else ""
        
        print(f"DEBUG: Code fixer router - Last message: {last_message[:200]}...")
        print(f"DEBUG: Code fixer router - Contains FIX_AND_EXECUTE: {'FIX_AND_EXECUTE:' in last_message}")
        print(f"DEBUG: Code fixer router - Contains MAJOR_FIX_NEEDED: {'MAJOR_FIX_NEEDED:' in last_message}")
        print(f"DEBUG: Code fixer router - Contains CREATE_FILE: {'CREATE_FILE:' in last_message}")
        
        # Check for fix commands in the message
        if "FIX_AND_EXECUTE:" in last_message or "MAJOR_FIX_NEEDED:" in last_message or "CREATE_FILE:" in last_message:
            print("DEBUG: Code fixer routing to execute")
            return "execute"
        
        print("DEBUG: Code fixer routing to respond")
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
             "plotly" in last_response or "plt." in last_response or "px." in last_response or "go." in last_response or
             "DataFrame" in last_response or "```" in last_response)):
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
              ("import " in last_response or "pandas" in last_response or "plotly" in last_response)):
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
        print(f"DEBUG: _execute_file called")
        print(f"DEBUG: Received state keys: {list(state.keys())}")
        print(f"DEBUG: current_file: {state.get('current_file')}")
        print(f"DEBUG: created_files: {state.get('created_files')}")
        print(f"DEBUG: files dict keys: {list(state.get('files', {}).keys())}")
        
        # Get the current file to execute
        filename = state.get("current_file")
        if not filename:
            filename = state["created_files"][-1] if state["created_files"] else None
        
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
            if "NameError: name 'python' is not defined" in result.stderr:
                error_type = "NameError"
            elif "no such column" in result.stderr or "DatabaseError" in result.stderr:
                error_type = "DatabaseError"
            elif "ModuleNotFoundError" in result.stderr:
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
                import time
                execution_start_time = time.time()  # Track when this execution started
                
                current_files = set(os.listdir(state["temp_dir"]))
                previous_files = set(state["files"].keys())
                new_files = current_files - previous_files
                
                # Only include files that were actually created during this execution
                query_specific_files = []
                for f in new_files:
                    if f.endswith(('.png', '.html', '.csv', '.txt', '.pdf', '.jpg', '.jpeg', '.svg')):
                        file_path = os.path.join(state["temp_dir"], f)
                        if os.path.exists(file_path):
                            file_creation_time = os.path.getctime(file_path)
                            if file_creation_time >= execution_start_time:
                                query_specific_files.append(f)
                                print(f"DEBUG: Including file created during execution: {f} (created: {file_creation_time}, execution start: {execution_start_time})")
                            else:
                                print(f"DEBUG: Skipping file created before execution: {f} (created: {file_creation_time}, execution start: {execution_start_time})")
                
                output_files = query_specific_files
                
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
            
            # Add success message for code fixes
            if state.get("last_error_type") == "CodeFixApplied":
                retry_count = state.get("retry_count", 0)
                execution_summary = f"🔧 Fix successful! {filename} now executes correctly (attempt {retry_count})"
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
        
        # Remove any lines that are just markdown artifacts or language indicators
        lines = code_content.split('\n')
        cleaned_lines = []
        for line in lines:
            stripped_line = line.strip()
            # Skip lines that are just markdown artifacts
            if stripped_line in ['```', '```python', '```py', '`', '``', 'python', 'py']:
                continue
            # Skip lines that start with markdown artifacts
            if stripped_line.startswith('```'):
                continue
            # Skip lines that are just language indicators
            if stripped_line in ['python', 'py']:
                continue
            cleaned_lines.append(line)
        
        code_content = '\n'.join(cleaned_lines)
        
        # Clean up multiple empty lines
        code_content = re.sub(r'\n\s*\n\s*\n', '\n\n', code_content)

         # Inject comprehensive DataFrame cleaning after 'df = pd.read_sql' lines
        import re
        lines = code_content.split('\n')
        new_lines = []
        for i, line in enumerate(lines):
            new_lines.append(line)
            if re.match(r"\s*df\s*=\s*pd\.read_sql", line):
                new_lines.append("")
                new_lines.append("# Clean and convert data types for visualization using database schema")
                new_lines.append("df.columns = df.columns.str.strip()")
                new_lines.append("")
                new_lines.append("# Ensure numeric columns are properly converted using database schema")
                new_lines.append("df = ensure_numeric_columns(df)")
                new_lines.append("")
                new_lines.append("# Display data info for debugging")
                new_lines.append("print('DataFrame info:')")
                new_lines.append("print(df.info())")
                new_lines.append("print('\\nData types:')")
                new_lines.append("print(df.dtypes)")
                new_lines.append("print('\\nFirst few rows:')")
                new_lines.append("print(df.head())")
                new_lines.append("")
        code_content = '\n'.join(new_lines)        

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
    
    def run(self, user_message: str, execution_output: str = "", execution_error: str = "", thread_id: str = "default", user_feedback: str = "", scenario_id: Optional[int] = None, database_path: Optional[str] = None) -> Tuple[str, List[str]]:
        """Run the agent with scenario awareness"""
        # Update scenario information
        if scenario_id is not None:
            self.current_scenario_id = scenario_id
        if database_path is not None:
            self.current_database_path = database_path
        
        # Get current scenario info if not provided
        if self.current_scenario_id is None or self.current_database_path is None:
            try:
                from scenario_manager import scenario_state
                current_scenario = scenario_state.get_current_scenario()
                if current_scenario:
                    self.current_scenario_id = current_scenario.id
                    self.current_database_path = current_scenario.database_path
            except ImportError:
                print("Warning: scenario_manager not available, using default database")
        
        # Update database schema for current scenario
        if self.current_database_path and os.path.exists(self.current_database_path):
            try:
                from main import get_database_info
                schema = get_database_info(self.current_database_path)
                self.set_cached_schema(schema)
            except Exception as e:
                print(f"Warning: Could not update schema for scenario {self.current_scenario_id}: {e}")
        
        # Create initial state with scenario information
        initial_state = {
            "messages": [HumanMessage(content=user_message)],
            "files": {},
            "temp_dir": self.temp_dir,
            "execution_output": execution_output,
            "execution_error": execution_error,
            "created_files": [],
            "retry_count": 0,
            "current_file": "",
            "has_execution_error": bool(execution_error),
            "last_error_type": "",
            "execution_plan": "",
            "required_files": [],
            "analysis_type": "",
            "selected_file_contents": {},
            "database_schema": self.cached_database_schema or {},
            "database_path": self.current_database_path or "",
            "action_type": "",
            "action_result": "",
            "db_modification_result": {},
            "user_feedback": user_feedback,
            "generated_sql": "",
            "sql_validation_result": {},
            "query_execution_result": {},
            "interpretation_response": "",
            "request_type": "",
            "sql_query_result": "",
            "visualization_request": "",
            "modification_request": {},
            "identified_tables": [],
            "identified_columns": [],
            "current_values": {},
            "new_values": {},
            "modification_sql": "",
            "available_models": [],
            "selected_models": [],
            "model_execution_results": [],
            "scenario_id": self.current_scenario_id
        }
        
        # Run the graph
        try:
            if self.checkpointer:
                result = self.graph.invoke(initial_state, config={"configurable": {"thread_id": thread_id}})
            else:
                result = self.graph.invoke(initial_state)
            
            # Extract response and created files
            response = ""
            created_files = []
            
            if result and "messages" in result:
                messages = result["messages"]
                if messages:
                    last_message = messages[-1]
                    if hasattr(last_message, 'content'):
                        response = last_message.content
            
            if result and "created_files" in result:
                created_files = result["created_files"]
            
            # Don't log AI Agent messages to execution history - they belong in chat only
            # Only log actual code executions that generate files or have errors
            if self.current_scenario_id and self.current_database_path and (execution_error or created_files):
                try:
                    # Use the global scenario manager instance
                    from scenario_manager import ScenarioManager
                    scenario_manager = ScenarioManager(os.path.join(os.getcwd(), 'scenarios'))
                    scenario_manager.add_execution_history(
                        scenario_id=self.current_scenario_id,
                        command=f"AI Agent Execution: {user_message[:100]}...",
                        output=response[:500] if response else None,
                        error=execution_error if execution_error else None
                    )
                except Exception as e:
                    print(f"Warning: Could not log execution to scenario history: {e}")
            
            return response, created_files
            
        except Exception as e:
            error_msg = f"Error running agent: {str(e)}"
            print(f"DEBUG: {error_msg}")
            
            # Only log actual execution errors to scenario history, not chat errors
            if self.current_scenario_id and "execution" in error_msg.lower():
                try:
                    # Use the global scenario manager instance
                    from scenario_manager import ScenarioManager
                    scenario_manager = ScenarioManager(os.path.join(os.getcwd(), 'scenarios'))
                    scenario_manager.add_execution_history(
                        scenario_id=self.current_scenario_id,
                        command=f"AI Agent Execution Error: {user_message[:100]}...",
                        output=None,
                        error=error_msg
                    )
                except Exception as log_error:
                    print(f"Warning: Could not log error to scenario history: {log_error}")
            
            return error_msg, []



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
        """Get database schema - now uses current scenario's database if available"""
        if self.current_database_path and os.path.exists(self.current_database_path):
            db_path = self.current_database_path
        
        if not db_path or not os.path.exists(db_path):
            return {"tables": [], "total_tables": 0, "error": "Database not found"}
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            schema = {"tables": [], "total_tables": len(tables)}
            
            for table in tables:
                table_name = table[0]
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                table_info = {
                    "name": table_name,
                    "columns": []
                }
                
                for col in columns:
                    column_info = {
                        "name": col[1],
                        "type": col[2],
                        "notnull": bool(col[3]),
                        "default": col[4],
                        "primary_key": bool(col[5])
                    }
                    table_info["columns"].append(column_info)
                
                schema["tables"].append(table_info)
            
            conn.close()
            return schema
            
        except Exception as e:
            return {"tables": [], "total_tables": 0, "error": str(e)}

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
            
            # Check if modification was successful
            if result.get("success") and "python_code" in result:
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
        
        # First determine the request type
        system_prompt = """You are analyzing a user request to determine how to handle it. You have three options:

1. **SQL_QUERY** - For straightforward data requests that need simple SQL execution and return tabular data
   Examples: 
   - "Show top 10 hubs", "What is total demand?", "List all routes"
   - "give me the top 10 hubs with highest demand", "show me hubs with least demand"
   - "find hubs with cost factors", "get all routes with cost > 500"
   - "count total destinations", "sum all demand values"
   - "show me the data", "display the results", "list the information"

2. **VISUALIZATION** - For requests that need charts, graphs, plots, or visual representations
   Examples:
   - "Create a chart", "Show a graph", "Visualize the data", "Plot distribution"
   - "draw a map", "create a scatter plot", "make a bar chart"
   - "show me a visualization", "generate a plot", "create a diagram"
   - "visualize the hubs", "plot the demand", "chart the results"
   - "show me a comparison chart", "create a heatmap", "draw a histogram"
   - "bar chart of [data]", "scatter plot of [data]", "line chart of [data]"
   - "pie chart", "histogram", "box plot", "area chart"
   - "map", "location", "geographic", "allocation", "hub allocation"
   - "which hubs are allocated to which location", "show allocation", "display map"

3. **DATABASE_MODIFICATION** - For requests to change parameters or data
   Examples: "Change maximum hub demand to X", "Update cost to Y", "Set limit to Z", "modify parameter"

IMPORTANT DISTINCTION:
- **SQL_QUERY**: User wants to see raw data in table format (rows and columns)
- **VISUALIZATION**: User wants to see data represented as charts, graphs, plots, or visual diagrams
- **DATABASE_MODIFICATION**: User wants to change values in the database

KEY WORDS TO LOOK FOR:
- SQL_QUERY: "show", "list", "get", "find", "count", "sum", "display", "table", "data"
- VISUALIZATION: "chart", "graph", "plot", "visualize", "draw", "map", "diagram", "scatter", "bar", "line", "heatmap", "pie", "histogram", "box", "area", "location", "geographic", "allocation"
- DATABASE_MODIFICATION: "change", "update", "set", "modify", "alter", "edit"

SPECIFIC CHART TYPE DETECTION:
If the user mentions any of these specific chart types, it's ALWAYS a VISUALIZATION request:
- "bar chart", "scatter plot", "line chart", "pie chart", "histogram", "heatmap", "box plot", "area chart"
- "create a [chart type]", "make a [chart type]", "draw a [chart type]"

MAP AND ALLOCATION DETECTION:
If the user mentions any of these terms, it's ALWAYS a VISUALIZATION request:
- "map", "location", "geographic", "allocation", "hub allocation"
- "which hubs are allocated to which location", "show allocation", "display map"
- "create a map", "draw a map", "show locations"

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

        # If this is a visualization request, just set the request type and continue
        if request_type == "VISUALIZATION":
            return {
                **state,
                "request_type": request_type,
                "messages": state["messages"] + [AIMessage(content="🎨 Request classified as visualization")]
            }
        
        # For non-visualization requests or if visualization creation failed
        return {
            **state,
            "request_type": request_type,
            "messages": state["messages"] + [AIMessage(content=f"Request classified as: {request_type}")]
        }
    
    def _create_visualization_node(self, state: AgentState) -> AgentState:
        """Create visualization Python file"""
        # Get the original user message (not the last message which might be AI classification)
        user_message = ""
        for message in reversed(state["messages"]):
            if isinstance(message, HumanMessage):
                user_message = message.content
                break
        
        if not user_message:
            user_message = state["messages"][-1].content if state["messages"] else ""
        
        print(f"DEBUG: _create_visualization_node called with original message: {user_message}")
        
        # Get database schema context - use FULL schema for visualizations (all tables)
        schema_context = ""
        if state.get("database_schema"):
            schema_context = self._build_schema_context(state["database_schema"])
        elif self.cached_database_schema:
            schema_context = self._build_schema_context(self._get_full_database_schema())
        
        try:
            print(f"DEBUG: About to invoke LLM for visualization code generation")
            
            # Create a template that follows Plotly best practices for bar charts
            simple_template = f"""import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import time
import numpy as np

# Connect to database
conn = sqlite3.connect('project_data.db')
print("Connected to database")

# Get data for top 10 locations by demand
query = '''
SELECT Location, Demand 
FROM inputs_destinations 
ORDER BY Demand DESC 
LIMIT 10
'''

df = pd.read_sql(query, conn)
conn.close()

# CRITICAL: Convert pandas Series to Python lists for Plotly
print("Converting data types and extracting as Python lists...")
try:
    df['Demand'] = pd.to_numeric(df['Demand'], errors='coerce')
    print(f"Demand column type: {{df['Demand'].dtype}}")
    
    # CRITICAL: Extract data as Python lists (NOT pandas Series)
    locations = df['Location'].tolist()
    demands = df['Demand'].tolist()
    
    print(f"Locations (Python list): {{locations}}")
    print(f"Demands (Python list): {{demands}}")
    
except Exception as e:
    print(f"Error converting data: {{e}}")

print(f"Data shape: {{df.shape}}")
print(f"Columns: {{df.columns.tolist()}}")
print("First few rows:")
print(df.head())

# CRITICAL: Choose appropriate chart type based on data characteristics
# For this example (categorical comparison), a bar chart is appropriate
# But consider other chart types based on the actual data and user request

# **BAR CHART (for categorical comparisons):**
fig = go.Figure()
fig.add_trace(go.Bar(
    x=locations,  # Category labels (Python list)
    y=demands,  # Numeric values (Python list)
    text=demands,  # Text labels
    textposition='outside',
    hovertemplate='<b>%{{x}}</b><br>Demand: %{{y:,.0f}}<br><extra></extra>'
))

# Configure layout for bar chart
fig.update_layout(
    title='Top 10 Locations by Demand',
    template='plotly_white',
    font=dict(size=12),
    margin=dict(l=80, r=80, t=80, b=100),  # Standard margins
    showlegend=False,
    hovermode='closest',
    xaxis=dict(
        tickangle=45 if len(locations) > 5 else 0  # Angle labels if many categories
    ),
    yaxis=dict(
        range=[0, max(demands) * 1.15]  # Add padding for text labels
    ),
    height=max(500, len(locations) * 30),  # Dynamic height based on number of bars
    width=800
)

# **ALTERNATIVE CHART TYPES (consider based on data and user request):**
# 
# **LINE CHART (for trends over time/sequence):**
# fig = go.Figure()
# fig.add_trace(go.Scatter(
#     x=locations,  # If locations have a natural order
#     y=demands,
#     mode='lines+markers',
#     hovertemplate='<b>%{{x}}</b><br>Demand: %{{y:,.0f}}<br><extra></extra>'
# ))
# 
# **PIE CHART (for proportions of total):**
# fig = go.Figure()
# fig.add_trace(go.Pie(
#     labels=locations,
#     values=demands,
#     hovertemplate='<b>%{{label}}</b><br>Demand: %{{value:,.0f}}<br>Percentage: %{{percent}}<br><extra></extra>'
# ))
# 
# **HORIZONTAL BAR CHART (for many categories or long names):**
# fig = go.Figure()
# fig.add_trace(go.Bar(
#     x=demands,  # Numeric values (Python list)
#     y=locations,  # Category labels (Python list)
#     orientation='h',  # CRITICAL: Must specify for horizontal bars
#     text=[f'{{v:,.0f}}' for v in demands],  # Formatted text labels
#     textposition='outside',
#     hovertemplate='<b>%{{y}}</b><br>Demand: %{{x:,.0f}}<br><extra></extra>'
# ))
# 
# # Configure layout for horizontal bars
# fig.update_layout(
#     title='Top 10 Locations by Demand',
#     template='plotly_white',
#     font=dict(size=12),
#     margin=dict(l=200, r=120, t=80, b=60),  # Adequate left margin for labels
#     showlegend=False,
#     hovermode='closest',
#     yaxis=dict(
#         autorange='reversed',  # Keeps highest values at top
#         tickmode='array',
#         tickvals=list(range(len(locations))),
#         ticktext=locations
#     ),
#     xaxis=dict(
#         range=[0, max(demands) * 1.15]  # Add padding for text labels
#     ),
#     height=max(600, len(locations) * 40),  # Dynamic height based on number of bars
#     width=800
# )

# Save as interactive HTML with comprehensive export options
filename = 'interactive_chart_' + str(int(time.time())) + '.html'
fig.write_html(filename, include_plotlyjs='cdn', config=dict(
    displayModeBar=True,
    displaylogo=False,
    modeBarButtonsToAdd=[
        'downloadImage',
        'pan2d',
        'select2d',
        'lasso2d',
        'resetScale2d',
        'autoScale2d',
        'hoverClosestCartesian',
        'hoverCompareCartesian',
        'toggleSpikelines'
    ],
    modeBarButtonsToRemove=[
        'sendDataToCloud',
        'editInChartStudio'
    ],
    toImageButtonOptions=dict(
        format='png',
        filename='chart',
        height=800,
        width=1200,
        scale=2
    )
))
print('Interactive chart saved as ' + filename)"""

            # Get the visualization code from the agent
            response = self.llm.invoke([
                HumanMessage(content=f"""You are a data visualization expert. Your task is to analyze the user's request and create Python code to visualize data from the database using Plotly for interactive charts.

Database Schema:
{schema_context}

User Request: {user_message}

Create Python code that:
1. Connects to the SQLite database
2. Retrieves the necessary data using SQL
3. **IMPORTANT**: Ensures numeric columns are properly converted to numeric types (not strings)
4. **CRITICAL**: Converts pandas Series to Python lists before passing to Plotly
5. **ANALYZE** the data and user request to choose the most appropriate chart type
6. Creates an appropriate interactive visualization using Plotly
7. Saves the output as an interactive HTML file

**CHART TYPE ANALYSIS:**
Before creating a chart, analyze:
- **Data structure**: How many columns? What types? Any time/sequence data?
- **User request**: What specific chart type did they ask for?
- **Data characteristics**: Categorical comparisons? Trends? Relationships? Distributions?
- **Number of data points**: Few categories (<8) vs many categories (>8)

**DEFAULT CHART SELECTION LOGIC:**
- **Bar chart**: Categorical comparisons (default for few categories)
- **Line chart**: Time series, trends, or sequential data
- **Scatter plot**: Relationships between two numeric variables
- **Pie chart**: Proportions/percentages (limit to 5-7 categories)
- **Histogram**: Distribution of a single variable
- **Heatmap**: Correlation matrices or 2D data
- **Box plot**: Statistical summaries and outlier detection

**CHART TYPE SELECTION GUIDELINES:**
Choose the most appropriate chart type based on the data and user request:

**BAR CHARTS**: For categorical data comparisons
- **Use VERTICAL bars (default)**: When user doesn't specify orientation, few categories (<8), or short category names
- **Use HORIZONTAL bars**: When user specifically requests "horizontal", many categories (>8), or long category names

**LINE CHARTS**: For time series, trends, or continuous data over a sequence
- Use when data has a natural order (time, sequence, etc.)
- Good for showing trends and patterns over time

**SCATTER PLOTS**: For relationships between two numeric variables
- Use when exploring correlations or relationships
- Good for identifying patterns, clusters, or outliers

**PIE CHARTS**: For parts of a whole (percentages, proportions)
- Use when showing composition or distribution
- Limit to 5-7 categories for readability

**HISTOGRAMS**: For distribution of a single variable
- Use when showing frequency distribution
- Good for understanding data spread and shape

**HEATMAPS**: For correlation matrices or 2D data tables
- Use when showing relationships between multiple variables
- Good for identifying patterns in large datasets

**BOX PLOTS**: For statistical summaries and outlier detection
- Use when comparing distributions across categories
- Good for showing median, quartiles, and outliers

**GENERAL RULES:**
- **ALWAYS** use `.tolist()` to convert pandas Series to Python lists before passing to Plotly
- **ALWAYS** set dynamic height based on data size
- **ALWAYS** use `include_plotlyjs='cdn'` for better compatibility
- Choose chart type based on data characteristics, not just user keywords

**CRITICAL DATA TYPE HANDLING:**
- Only convert columns that are CLEARLY numeric to numeric types after reading from SQL
- NEVER convert text/categorical columns like Location, City, Name, Address, etc. - these MUST remain as strings
- This prevents the issue where bar charts show 0,1,2,3 instead of actual location names
- Only convert columns with names like: Demand, Cost, Capacity, Supply, Value, Amount, Quantity, Price, etc.
- Use database schema information when available to determine column types
- Always preserve text columns to ensure proper visualization

**SELECTIVE NUMERIC CONVERSION FUNCTION:**
```python
def ensure_numeric_columns(df):
    \"\"\"Convert only clearly numeric columns to proper types, preserve text columns\"\"\"
    print(f"Original DataFrame dtypes: {{df.dtypes.to_dict()}}")
    print(f"Original DataFrame shape: {{df.shape}}")
    print(f"Original DataFrame index: {{df.index.tolist()[:5]}}...")  # Show first 5 index values
    
    # List of column patterns that should be converted to numeric
    numeric_patterns = ['DEMAND', 'COST', 'CAPACITY', 'SUPPLY', 'VALUE', 'AMOUNT', 
                       'QUANTITY', 'NUMBER', 'COUNT', 'TOTAL', 'SUM', 'PRICE', 
                       'RATE', 'FACTOR', 'WEIGHT', 'DISTANCE', 'SCORE', 'PERCENT']
    
    for col in df.columns:
        print(f"Processing column '{{col}}': current dtype = {{df[col].dtype}}")
        
        # Only convert if column name suggests it's numeric
        if any(pattern in col.upper() for pattern in numeric_patterns):
            try:
                original_dtype = df[col].dtype
                # Check if already numeric
                if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
                    print(f"[OK] Column '{{col}}' already numeric: {{df[col].dtype}}")
                    print(f"  Sample values: {{df[col].head().tolist()}}")
                else:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
                    if df[col].dtype != original_dtype:
                        print(f"[OK] Converted '{{col}}' to numeric: {{df[col].dtype}}")
                        print(f"  Sample values: {{df[col].head().tolist()}}")
                    else:
                        print(f"[OK] '{{col}}' remains as: {{df[col].dtype}}")
            except Exception as e:
                print(f"[WARNING] Could not convert '{{col}}': {{e}}")
        else:
            print(f"[OK] Preserving text column '{{col}}' as: {{df[col].dtype}}")
            if df[col].dtype == 'object':
                print(f"  Sample values: {{df[col].head().tolist()}}")
    
    print(f"Final DataFrame dtypes: {{df.dtypes.to_dict()}}")
    print(f"Final DataFrame shape: {{df.shape}}")
    
    # Final validation
    print("\\nFinal column validation:")
    for col in df.columns:
        if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
            print(f"[OK] Numeric column '{{col}}': {{df[col].dtype}} - min={{df[col].min()}}, max={{df[col].max()}}")
        else:
            print(f"[OK] Text column '{{col}}': {{df[col].dtype}} - {{len(df[col].unique())}} unique values")
    
    return df
```

Basic template to follow:
```python
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sqlite3
import time
import numpy as np

# Get data
conn = sqlite3.connect('project_data.db')
df = pd.read_sql('YOUR_SQL_QUERY', conn)
conn.close()

# CRITICAL: Ensure numeric columns are properly converted for visualization using database schema
# This prevents the issue where bars show 0,1,2,3 instead of actual values
print("Converting data types for visualization...")
df = ensure_numeric_columns(df)

# CRITICAL FIX: Reset DataFrame index to prevent Plotly from using row indices as values
df = df.reset_index(drop=True)

# Display data info for debugging
print('\\nDataFrame info:')
print(df.info())
print('\\nData types:')
print(df.dtypes)
print('\\nFirst few rows:')
print(df.head())
print('\\nNumeric columns for visualization:')
numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
print(numeric_cols)

# CRITICAL: Data integrity check before visualization
print('\\nData integrity check before plotting:')
for col in df.columns:
    if df[col].dtype in ['int64', 'float64', 'int32', 'float32']:
        print(f"Numeric column '{{col}}': min={{df[col].min()}}, max={{df[col].max()}}, dtype={{df[col].dtype}}")
        print(f"Sample values: {{df[col].head().tolist()}}")
    else:
        print(f"Text column '{{col}}': dtype={{df[col].dtype}}")
        print(f"Sample values: {{df[col].head().tolist()}}")

# Additional data validation for plotting
print('\\nValidating data before Plotly visualization:')
print(f"DataFrame shape: {{df.shape}}")
print(f"DataFrame index: {{df.index.tolist()}}")
print(f"All columns: {{df.columns.tolist()}}")

# Check for potential visualization issues
print('\\nChecking for visualization issues:')
columns_to_check = list(df.columns)
for col in columns_to_check:
    if col in ['Demand', 'Cost', 'Capacity', 'Supply', 'Value', 'Amount', 'Quantity', 'Number']:
        if df[col].dtype == 'object':
                    print(f"WARNING: Column '{{col}}' is object type (string) - this will cause bar charts to show 0,1,2,3 instead of actual values!")
        else:
            print(f"[OK] Column '{{col}}' is properly numeric: {{df[col].dtype}} with values {{df[col].head().tolist()}}")
    else:
        print(f"Column '{{col}}' is {{df[col].dtype}} type")

# Create plotly visualization with explicit data validation
print('\\nCreating Plotly visualization...')

# SAFETY: Create a clean copy of the data for plotting to avoid any reference issues
plot_df = df.copy()
print(f"Plot DataFrame shape: {{plot_df.shape}}")
print(f"Plot DataFrame columns: {{plot_df.columns.tolist()}}")

# Use go.Figure() and go.Bar(), go.Scatter(), go.Pie(), etc. for explicit control
# Always use .tolist() on DataFrame columns to ensure explicit data extraction

# **CHART TYPE SELECTION:**
# Choose the most appropriate chart type based on data characteristics and user request:

# **BAR CHART PATTERNS (for categorical comparisons):**
# Vertical bars (default for few categories):
# fig = go.Figure()
# fig.add_trace(go.Bar(
#     x=plot_df['category_column'].tolist(),  # Category labels
#     y=plot_df['numeric_column'].tolist(),  # Numeric values
#     text=plot_df['numeric_column'].tolist(),
#     textposition='outside',
#     hovertemplate='<b>%{{x}}</b><br>Value: %{{y:,.0f}}<br><extra></extra>'
# ))

# Horizontal bars (for many categories or long names):
# fig = go.Figure()
# fig.add_trace(go.Bar(
#     x=plot_df['numeric_column'].tolist(),  # Numeric values
#     y=plot_df['category_column'].tolist(),  # Category labels
#     orientation='h',  # CRITICAL: Must specify for horizontal bars
#     text=[f'{{v:,.0f}}' for v in plot_df['numeric_column'].tolist()],
#     textposition='outside',
#     hovertemplate='<b>%{{y}}</b><br>Value: %{{x:,.0f}}<br><extra></extra>'
# ))

# **LINE CHART PATTERN (for trends/time series):**
# fig = go.Figure()
# fig.add_trace(go.Scatter(
#     x=plot_df['x_column'].tolist(),  # Time/sequence column
#     y=plot_df['y_column'].tolist(),  # Value column
#     mode='lines+markers',
#     hovertemplate='<b>%{{x}}</b><br>Value: %{{y:,.0f}}<br><extra></extra>'
# ))

# **SCATTER PLOT PATTERN (for relationships):**
# fig = go.Figure()
# fig.add_trace(go.Scatter(
#     x=plot_df['x_column'].tolist(),  # First numeric variable
#     y=plot_df['y_column'].tolist(),  # Second numeric variable
#     mode='markers',
#     hovertemplate='<b>X: %{{x:,.0f}}</b><br>Y: %{{y:,.0f}}<br><extra></extra>'
# ))

# **PIE CHART PATTERN (for proportions):**
# fig = go.Figure()
# fig.add_trace(go.Pie(
#     labels=plot_df['category_column'].tolist(),
#     values=plot_df['numeric_column'].tolist(),
#     hovertemplate='<b>%{{label}}</b><br>Value: %{{value:,.0f}}<br>Percentage: %{{percent}}<br><extra></extra>'
# ))

# **HISTOGRAM PATTERN (for distributions):**
# fig = go.Figure()
# fig.add_trace(go.Histogram(
#     x=plot_df['numeric_column'].tolist(),
#     nbinsx=20,
#     hovertemplate='<b>Range: %{{x}}</b><br>Count: %{{y}}<br><extra></extra>'
# ))

# **HEATMAP PATTERN (for correlations/2D data):**
# fig = go.Figure()
# fig.add_trace(go.Heatmap(
#     z=correlation_matrix.tolist(),  # 2D array
#     x=column_names,
#     y=column_names,
#     colorscale='RdBu',
#     hovertemplate='<b>%{{x}} vs %{{y}}</b><br>Correlation: %{{z:.3f}}<br><extra></extra>'
# ))

# **BOX PLOT PATTERN (for statistical summaries):**
# fig = go.Figure()
# fig.add_trace(go.Box(
#     y=plot_df['numeric_column'].tolist(),
#     x=plot_df['category_column'].tolist() if 'category_column' in plot_df.columns else None,
#     hovertemplate='<b>%{{x}}</b><br>Q1: %{{q1:,.0f}}<br>Median: %{{median:,.0f}}<br>Q3: %{{q3:,.0f}}<br><extra></extra>'
# ))

print(f"[OK] Chart created successfully with data shape: {{plot_df.shape}}")

# Configure for professional appearance with explicit layout control
fig.update_layout(
    template='plotly_white',
    font=dict(size=12),
    margin=dict(l=50, r=50, t=50, b=50),
    showlegend=True,
    hovermode='closest',  # Changed from 'x unified' for better individual hovering
    yaxis=dict(range=[0, plot_df['y_column'].max() * 1.1])  # Explicit y-axis range
)

# Save as interactive HTML with comprehensive export options
filename = 'interactive_chart_' + str(int(time.time())) + '.html'
fig.write_html(filename, include_plotlyjs='cdn', config=dict(
    displayModeBar=True,
    displaylogo=False,
    modeBarButtonsToAdd=[
        'downloadImage',
        'pan2d',
        'select2d',
        'lasso2d',
        'resetScale2d',
        'autoScale2d',
        'hoverClosestCartesian',
        'hoverCompareCartesian',
        'toggleSpikelines'
    ],
    modeBarButtonsToRemove=[
        'sendDataToCloud',
        'editInChartStudio'
    ],
    toImageButtonOptions=dict(
        format='png',
        filename='chart',
        height=800,
        width=1200,
        scale=2
    )
))
print('Interactive chart saved as ' + filename)
```

CHART TYPE SELECTION:
- Bar charts: go.Bar() for categorical data (ensure y-axis column is numeric)
- Line charts: go.Scatter(mode='lines') for time series or trends
- Scatter plots: go.Scatter(mode='markers') for relationships
- Pie charts: go.Pie() for parts of whole
- Histograms: go.Histogram() for distributions
- Box plots: go.Box() for statistical summaries
- Heatmaps: go.Heatmap() for correlation matrices

**CRITICAL IMPLEMENTATION RULES:**
1. Always use .tolist() conversion on DataFrame columns to ensure explicit data extraction
2. Add hover template: hovertemplate='<b>%{{x}}</b><br>MetricName: %{{y:,.0f}}<br><extra></extra>'
3. Include text parameter with y-values to display values on bars
4. Set explicit y-axis range: yaxis=dict(range=[0, df['Column'].max() * 1.1])
5. Use hovermode='closest' for better individual element hovering

**EXAMPLE TEMPLATES:**
```python
# Bar Chart
fig = go.Figure()
fig.add_trace(go.Bar(
    x=df['Category'].tolist(),
    y=df['Value'].tolist(),
    text=df['Value'].tolist(),
    textposition='outside',
    hovertemplate='<b>%{{x}}</b><br>Value: %{{y:,.0f}}<br><extra></extra>'
))

# Line Chart
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df['Time'].tolist(),
    y=df['Value'].tolist(),
    mode='lines+markers',
    hovertemplate='<b>%{{x}}</b><br>Value: %{{y:,.0f}}<br><extra></extra>'
))
```

**IMPORTANT**: Always ensure that columns used for y-axis values (like 'Demand', 'Cost', etc.) are converted to numeric types before creating the visualization. The ensure_numeric_columns(df) function is automatically available and should be used after reading data from SQL.

Respond with:
CREATE_FILE: [filename]
[complete Python visualization code using Plotly]""")
            ])
            
            # Generate timestamp for unique filename
            timestamp = int(time.time())
            filename = f"visualization_data_{timestamp}.py"
            
            # Debug: Print the raw response to see what the AI generated
            print(f"DEBUG: Raw AI response for visualization:")
            print(response.content[:1000])  # First 1000 chars
            print("...")
            
            # Check if the response contains valid code
            if "CREATE_FILE:" not in response.content and "```python" not in response.content:
                print(f"DEBUG: AI response doesn't contain valid code, using fallback template")
                code_content = simple_template
            else:
                print(f"DEBUG: About to clean visualization code")
                # Clean and enhance the code
                try:
                    code_content = self._clean_visualization_code(response.content)
                    print(f"DEBUG: Successfully cleaned visualization code")
                except Exception as e:
                    print(f"DEBUG: Error in _clean_visualization_code: {e}")
                    # Fallback to basic cleaning
                    code_content = response.content
                    # Remove markdown artifacts
                    if "```python" in code_content:
                        start_idx = code_content.find("```python") + len("```python")
                        end_idx = code_content.find("```", start_idx)
                        if end_idx != -1:
                            code_content = code_content[start_idx:end_idx].strip()
                    elif "```" in code_content:
                        start_idx = code_content.find("```") + 3
                        end_idx = code_content.find("```", start_idx)
                        if end_idx != -1:
                            code_content = code_content[start_idx:end_idx].strip()
            
            # Debug: Print the cleaned code to see what we're writing
            print(f"DEBUG: Cleaned visualization code:")
            print(code_content[:1000])  # First 1000 chars
            print("...")
            
            # Create the file
            print(f"DEBUG: About to create visualization file: {filename}")
            if state.get("temp_dir") and os.path.exists(state["temp_dir"]):
                try:
                    file_path = os.path.join(state["temp_dir"], filename)
                    print(f"DEBUG: Writing file to: {file_path}")
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(code_content)
                    print(f"DEBUG: Successfully wrote visualization file")
                    
                    # Add file to the files dictionary for execution
                    files_dict = state.get("files", {})
                    files_dict[filename] = file_path
                    
                    return {
                        **state,
                        "current_file": filename,
                        "created_files": state.get("created_files", []) + [filename],
                        "files": files_dict,
                        "messages": state["messages"] + [AIMessage(content="🎨 Creating visualization...")]
                    }
                except Exception as e:
                    print(f"DEBUG: Error writing visualization file: {e}")
                    return {
                        **state,
                        "has_execution_error": True,
                        "last_error_type": "FileWriteError",
                        "messages": state["messages"] + [AIMessage(content=f"❌ Error writing visualization file: {str(e)}")]
                    }
            else:
                print(f"DEBUG: temp_dir not available or doesn't exist: {state.get('temp_dir')}")
                return {
                    **state,
                    "has_execution_error": True,
                    "last_error_type": "NoTempDir",
                    "messages": state["messages"] + [AIMessage(content="❌ No temporary directory available for visualization")]
                }
        except Exception as e:
            print(f"Error creating visualization: {e}")
            import traceback
            print(f"DEBUG: Full traceback:")
            traceback.print_exc()
            return {
                **state,
                "has_execution_error": True,
                "last_error_type": "VisualizationCreationError",
                "messages": state["messages"] + [AIMessage(content=f"❌ Error creating visualization: {str(e)}")]
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
        """Execute SQL query using current scenario's database"""
        # Check if this is actually a SQL query request
        request_type = state.get("request_type", "SQL_QUERY")
        if request_type == "DATABASE_MODIFICATION":
            print(f"DEBUG: _execute_sql_query_node called for DATABASE_MODIFICATION request - skipping")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="🔄 Database modification requests should not generate SQL query files")]
            }
        
        # Ensure we're using the current scenario's database
        db_path = self.current_database_path or state.get("database_path", "")
        if not db_path or not os.path.exists(db_path):
            state["sql_query_result"] = "Error: No database available for current scenario"
            return state
        
        # Rest of the existing SQL execution logic...
        # (Keep the existing implementation but ensure it uses db_path)
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
        
        # Get database schema context - use FULL schema for SQL queries (all tables)
        schema_context = ""
        if state.get("database_schema"):
            schema_context = self._build_schema_context(state["database_schema"])
        elif self.cached_database_schema:
            schema_context = self._build_schema_context(self._get_full_database_schema())
        
        # Also get the full schema for comprehensive table/column information
        full_schema_context = ""
        if hasattr(self, 'cached_full_schema') and self.cached_full_schema:
            full_schema_context = self._build_schema_context(self.cached_full_schema)
        
        # Use full schema if available, otherwise use filtered schema
        final_schema_context = full_schema_context if full_schema_context else schema_context
        
        system_prompt = f"""You are an expert SQL analyst. Generate a SQL query to answer the user's request.

Database Schema:
{final_schema_context}

Generate a SQL query that answers the user's question. Consider:
- Use appropriate JOINs for related tables
- Include proper WHERE clauses for filtering
- Use aggregations (COUNT, SUM, AVG) when needed
- Limit results to reasonable sizes (use LIMIT)

**CRITICAL SCHEMA VALIDATION RULES:**
- **ALWAYS** check the exact column names in the schema before using them
- **NEVER** assume a column exists - only use columns that are explicitly listed in the schema
- **ALWAYS** verify table names and column names match exactly (case-sensitive)
- If you need a column that doesn't exist, find an alternative or use a different approach
- When joining tables, ensure the join columns exist in both tables

**COLUMN SEARCH STRATEGY:**
- For demand analysis: Look for columns like 'Demand', 'demand', 'Hub_Demand', 'Total_Demand', etc.
- For hub analysis: Look for columns like 'HubID', 'Location', 'Hub_Location', 'Hub_Name', etc.
- For cost analysis: Look for columns like 'CostFactor_Opening', 'Opening_Cost', 'Cost_Opening', etc.
- **ALWAYS** verify the exact column name exists in the target table before using it

**TABLE SEARCH STRATEGY:**
- Look for tables with names like 'hubs', 'demand', 'destinations', 'inputs_hubs', 'inputs_destinations'
- Check both 'inputs_' and 'outputs_' prefixed tables
- Verify table names exist in the schema before using them

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
            print(f"DEBUG: About to invoke LLM for SQL generation")
            response = self.llm.invoke([HumanMessage(content=f"{system_prompt}\n\nUser Question: {user_message}")])
            sql_query = response.content.strip()
            print(f"DEBUG: Raw SQL response: {sql_query}")
            
            # Clean up the SQL query
            if sql_query.startswith("```sql"):
                sql_query = sql_query.replace("```sql", "").replace("```", "").strip()
            elif sql_query.startswith("```"):
                sql_query = sql_query.replace("```", "").strip()
            
            print(f"DEBUG: Cleaned SQL query: {sql_query}")
            
            # Validate the SQL query against the schema
            validation_result = self._validate_sql_against_schema(sql_query, final_schema_context)
            if not validation_result["valid"]:
                error_msg = f"❌ **SQL Query Validation Failed**\n\n"
                error_msg += f"**Generated Query:**\n```sql\n{sql_query}\n```\n\n"
                error_msg += f"**Validation Error:**\n{validation_result['error']}\n\n"
                error_msg += f"**Available Tables and Columns:**\n{final_schema_context}\n\n"
                error_msg += "Please try rephrasing your request with more specific details about which tables and columns you want to query."
                
                return {
                    **state,
                    "has_execution_error": True,
                    "last_error_type": "SQLValidationError",
                    "sql_validation_result": validation_result,
                    "messages": state["messages"] + [AIMessage(content=error_msg)]
                }
            
            print(f"DEBUG: SQL query validation passed")
            
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
            
            print(f"DEBUG: About to generate Python code")
            
            # Simple Python code template to avoid complex string formatting issues
            python_code = f'''import os
import time
import random
import sqlite3
import pandas as pd
import glob
import plotly.graph_objects as go
import plotly.io as pio
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
        
        # Create a plotly table
        pio.templates.default = "plotly_white"
        
        # Create interactive plotly table
        fig = go.Figure(data=[go.Table(
            columnwidth=[200] * len(df.columns),
            header=dict(
                values=list(df.columns),
                fill_color='#f2f2f2',
                align='left',
                font=dict(color='#000000', size=12, family='Arial'),
                line_color='#d3d3d3',
                height=30
            ),
            cells=dict(
                values=[df[col].tolist() for col in df.columns],
                fill_color='#ffffff',
                align='left',
                font=dict(color='#000000', size=11, family='Arial'),
                line_color='#d3d3d3',
                height=25
            )
        )])
        
        # Update layout
        fig.update_layout(
            title=dict(
                text='SQL Query Results',
                x=0.5,
                xanchor='center',
                font=dict(size=16, family='Arial, sans-serif')
            ),
            template='plotly_white',
            font=dict(size=12, family='Arial'),
            margin=dict(l=20, r=20, t=60, b=20),
            height=min(800, 100 + len(df) * 30)
        )

        # Save as interactive HTML
        timestamp = int(time.time())
        random_id = random.randint(1000, 9999)
        table_filename = f"sql_results_{{timestamp}}_{{random_id}}.html"
        
        fig.write_html(table_filename, include_plotlyjs=True, config=dict(
            displayModeBar=True,
            displaylogo=False,
            modeBarButtonsToAdd=['downloadImage'],
            modeBarButtonsToRemove=['sendDataToCloud', 'editInChartStudio'],
            toImageButtonOptions=dict(
                format='png',
                filename='sql_results_table',
                height=800,
                width=1200,
                scale=2
            )
        ))

        print(f"\\nInteractive results table saved as: {{table_filename}}")
        print(f"\\nQuery Summary:")
        print(f"- Total rows: {{len(df)}}")
        print(f"- Columns: {{', '.join(df.columns)}}")
        
        # Show first few rows
        if len(df) <= 10:
            print(f"\\nAll results:")
            print(df.to_string(index=False))
        else:
            print(f"\\nFirst 5 rows:")
            print(df.head().to_string(index=False))
            print(f"\\n... and {{len(df) - 5}} more rows")
        
        # Save as CSV
        csv_filename = f"sql_results_{{timestamp}}_{{random_id}}.csv"
        df.to_csv(csv_filename, index=False)
        print(f"\\nData also saved as CSV: {{csv_filename}}")
    
except Exception as e:
    print(f"Error executing query: {{str(e)}}")

finally:
    conn.close()
    print("\\nDatabase connection closed.")
'''
            
            print(f"DEBUG: Python code generated successfully")
            
            # Write the Python file
            print(f"DEBUG: About to write file: {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(python_code)
            print(f"DEBUG: File written successfully")
            
            # Add file to state
            files_dict = state.get("files", {})
            files_dict[filename] = file_path
            
            print(f"DEBUG: SQL query script created: {filename}")
            print(f"DEBUG: Final created_files will be: [filename]")
            print(f"DEBUG: Final files dict will have keys: {list(files_dict.keys())}")
            
            updated_state = {
                **state,
                "current_file": filename,
                "created_files": [filename],  # Only this file, not appended
                "files": files_dict,
                "sql_query_result": sql_query,
                "messages": state["messages"] + [AIMessage(content=f"📊Created SQL query script: {filename}")]
            }
            
            print(f"DEBUG: Returning state with current_file: {updated_state.get('current_file')}")
            print(f"DEBUG: Returning state with created_files: {updated_state.get('created_files')}")
            print(f"DEBUG: Returning state with files keys: {list(updated_state.get('files', {}).keys())}")
            
            return updated_state
                
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
        
        try:
            # Enhanced extraction for both absolute values and percentage patterns
            import re
            
            # First, check for percentage patterns
            percentage_info = self._extract_percentage_patterns(last_message)
            
            # Extract numeric value from the request (for non-percentage cases)
            value_patterns = [
                r'to\s+(\d+(?:\.\d+)?)',  # matches "to 2000" or "to 2000.5"
                r'=\s*(\d+(?:\.\d+)?)',    # matches "= 2000" or "=2000.5"
                r'(\d+(?:\.\d+)?)\s*$'     # matches number at end of string
            ]
            
            extracted_value = None
            for pattern in value_patterns:
                matches = re.findall(pattern, last_message)
                if matches:
                    extracted_value = matches[0]
                    break
            
            # Extract table name if specified
            table_patterns = [
                r'in\s+(\w+(?:_\w+)*)\s',  # matches "in table_name "
                r'from\s+(\w+(?:_\w+)*)\s', # matches "from table_name "
                r'to\s+(\w+(?:_\w+)*)\s',   # matches "to table_name "
                r'update\s+(\w+(?:_\w+)*)\s', # matches "update table_name "
                r'in\s+(\w+(?:_\w+)*)$',  # matches "in table_name" at end of string
                r'from\s+(\w+(?:_\w+)*)$', # matches "from table_name" at end of string
                r'to\s+(\w+(?:_\w+)*)$',   # matches "to table_name" at end of string
                r'update\s+(\w+(?:_\w+)*)$', # matches "update table_name" at end of string
            ]
            
            extracted_table = None
            for pattern in table_patterns:
                matches = re.findall(pattern, last_message.lower())
                if matches:
                    extracted_table = matches[0]
                    break
            
            print(f"DEBUG: Extracted value: {extracted_value}")
            print(f"DEBUG: Extracted table: {extracted_table}")
            print(f"DEBUG: Percentage info: {percentage_info}")
            
            # Check if table exists in schema
            table_exists = False
            if extracted_table:
                if state.get("database_schema"):
                    schema_tables = state["database_schema"].get("tables", [])
                    table_exists = any(t.get("name", "").lower() == extracted_table.lower() for t in schema_tables if isinstance(t, dict))
                elif self.cached_database_schema:
                    schema_tables = self.cached_database_schema.get("tables", [])
                    table_exists = any(t.get("name", "").lower() == extracted_table.lower() for t in schema_tables if isinstance(t, dict))
                
                if not table_exists:
                    # Try fuzzy matching for similar table names
                    available_tables = []
                    if state.get("database_schema"):
                        schema_tables = state["database_schema"].get("tables", [])
                        available_tables = [t["name"] for t in schema_tables if isinstance(t, dict) and "name" in t]
                    elif self.cached_database_schema:
                        schema_tables = self.cached_database_schema.get("tables", [])
                        available_tables = [t["name"] for t in schema_tables if isinstance(t, dict) and "name" in t]
                    
                    # Find similar table names
                    import difflib
                    similar_tables = []
                    for table in available_tables:
                        ratio = difflib.SequenceMatcher(None, extracted_table.lower(), table.lower()).ratio()
                        if ratio > 0.6:  # Adjust threshold as needed
                            similar_tables.append(table)
                    
                    if similar_tables:
                        print(f"DEBUG: Table '{extracted_table}' not found, but found similar: {similar_tables}")
                        # Use the first (shortest) similar table
                        extracted_table = similar_tables[0]
                        table_exists = True
            
            # For inputs_destinations table, we need special handling
            if extracted_table == "inputs_destinations":
                # Check if inputs_destinations is whitelisted
                try:
                    import main
                    current_whitelist = main.get_table_whitelist()
                    
                    if "inputs_destinations" not in current_whitelist:
                        error_message = f"❌ Table 'inputs_destinations' is not whitelisted for modifications. Please enable it in the SQL Database tab."
                        print(f"DEBUG: Table 'inputs_destinations' not in whitelist: {current_whitelist}")
                        return {
                            **state,
                            "messages": state["messages"] + [AIMessage(content=error_message)]
                        }
                except Exception as e:
                    print(f"DEBUG: Error checking whitelist for inputs_destinations: {e}")
                    # Continue without whitelist check if there's an error accessing it
                
                modification_data = {
                    'table': 'inputs_destinations',
                    'column': 'Demand',
                    'new_value': extracted_value,
                    'description': 'Update demand in inputs_destinations table',
                    'percentage_info': percentage_info  # Add percentage info
                }
                return {
                    **state,
                    "modification_request": modification_data,
                    "identified_tables": [modification_data['table']],
                    "identified_columns": [modification_data['column']],
                    "current_values": {"Demand": "unknown"},
                    "new_values": {"Demand": extracted_value},
                    "messages": state["messages"] + [AIMessage(content=f"Identified modification: {modification_data}")]
                }
            
            # For other cases, use the enhanced LLM to analyze the request
            # Get current whitelist to include in prompt
            current_whitelist = set()
            try:
                import main
                current_whitelist = main.get_table_whitelist()
            except Exception as e:
                print(f"DEBUG: Could not get whitelist for prompt: {e}")
            
            # Build whitelist information and table descriptions
            whitelist_info = ""
            table_descriptions = {}
            
            if current_whitelist:
                whitelist_info = f"""
**WHITELISTED TABLES FOR MODIFICATIONS:**
The following tables are currently enabled for modifications:
{', '.join(sorted(current_whitelist))}

⚠️ **CRITICAL: You MUST choose a table from this whitelist. Tables not in this list cannot be modified.**
"""
                
                # Get schema info to provide better descriptions of whitelisted tables
                if state.get("database_schema") or self.cached_database_schema:
                    schema_data = state.get("database_schema") or self.cached_database_schema
                    if "tables" in schema_data:
                        for table_info in schema_data["tables"]:
                            table_name = table_info.get("name", "")
                            if table_name in current_whitelist:
                                columns = [col.get("name", "") for col in table_info.get("columns", [])]
                                table_descriptions[table_name] = f"- {table_name}: Columns include {', '.join(columns[:5])}{'...' if len(columns) > 5 else ''}"
                
                if table_descriptions:
                    whitelist_info += f"""

**WHITELISTED TABLE DETAILS:**
{chr(10).join(table_descriptions.values())}
"""
            
            system_prompt = f"""Analyze the database modification request and identify exactly what needs to be changed.

Database Schema:
{schema_context}

{whitelist_info}

You are analyzing an operations research model with hub location optimization. Common parameters that might be modified include:
- Hub capacity/demand limits
- Cost parameters  
- Distance/route parameters
- Supply/demand values

PERCENTAGE MODIFICATIONS SUPPORT:
The system now supports percentage-based modifications with the following patterns:
1. **Absolute Percentage Changes:**
   - "increase by 10%" → Increase current value by 10%
   - "decrease by 15%" → Decrease current value by 15%
   - "reduce by 5%" → Decrease current value by 5%
   - "decrease by half" → Decrease current value by 50%
   - "double the capacity" → Increase current value by 100%

2. **Relative Percentage Changes:**
   - "increase by 10% of capacity" → Add (10% of capacity_value) to current value
   - "set to 20% of maximum" → Set to (20% of maximum_value)
   - "reduce by 5% of demand" → Subtract (5% of demand_value) from current value
   - "set to 2000% of Minimum Hub Demand" → Set to (2000% of Minimum Hub Demand value)
   - "set demand to twice that of oxford" → Set to (200% of Oxford's demand value)

3. **Natural Language Fractions:**
   - "half" = 50%, "quarter" = 25%, "third" = 33.33%
   - "double" = 200%, "triple" = 300%, "quadruple" = 400%
   - "decrease by half" = decrease by 50%
   - "increase by a quarter" = increase by 25%
   - "twice that of X" = 200% of X's value

4. **Percentage Detection Patterns:**
   - Look for keywords: increase, decrease, reduce, set, change
   - Followed by: by, to
   - Then percentage: X%, X percent, or natural language (half, quarter, etc.)
   - For relative calculations: "of [reference_column]" where reference_column can be multi-word
   - For relative calculations: "that of [reference_location]" where reference_location is a location name

IMPORTANT: Pay attention to table-specific requests. Examples:
- "Change x in table_name" → Use the specified table_name (if whitelisted)
- "Update maximum hub demand in params table" → Look for whitelisted table containing "params"
- "Set cost to 500 in routes table" → Look for whitelisted table containing "routes"
- "Modify capacity in hubs_data" → Look for whitelisted table containing "hubs" or "capacity"
- "Increase demand for birmingham" → Look for whitelisted table containing demand/destination data

For general requests without table specification:
- Look through the WHITELISTED TABLES ONLY
- Match column names and data types to the user's request
- Consider table names that suggest the relevant data type (destinations, hubs, routes, params, etc.)
- Use the table descriptions provided above to find the best match

IMPORTANT: Extract the exact numeric value AND parameter name from the user's request. For example:
- "Change maximum hub demand to 20000" → NEW_VALUE: 20000, Parameter: 'Maximum Hub Demand'
- "Set hub capacity to 15000" → NEW_VALUE: 15000
- "Update Operating Cost (Fixed) to 1000" → NEW_VALUE: 1000, Parameter: 'Operating Cost (Fixed)'
- "Change Operating Cost per Unit to 25.5" → NEW_VALUE: 25.5, Parameter: 'Operating Cost per Unit'
- "Update Opening Cost to 500000" → NEW_VALUE: 500000, Parameter: 'Opening Cost'
- "Change Closing Cost to 150000" → NEW_VALUE: 150000, Parameter: 'Closing Cost'
- "Increase demand by 10%" → PERCENTAGE_TYPE: absolute, PERCENTAGE_VALUE: 10, OPERATION: increase
- "Decrease demand by half" → PERCENTAGE_TYPE: absolute, PERCENTAGE_VALUE: 50, OPERATION: decrease
- "Set capacity to 20% of maximum" → PERCENTAGE_TYPE: relative, PERCENTAGE_VALUE: 20, REFERENCE_COLUMN: maximum, OPERATION: set
- "Set to 2000% of Minimum Hub Demand" → PERCENTAGE_TYPE: relative, PERCENTAGE_VALUE: 2000, REFERENCE_COLUMN: Minimum Hub Demand, OPERATION: set
- "Set demand to twice that of oxford" → PERCENTAGE_TYPE: relative, PERCENTAGE_VALUE: 200, REFERENCE_COLUMN: Demand, OPERATION: set, WHERE_CONDITION: Location = 'Oxford'

For parameter tables (like inputs_params), you may need to identify:
- The WHERE condition to target the specific parameter row
- The exact parameter name that needs to be updated

TABLE DETECTION RULES:
1. If user specifies "in [table_name]" → Use that exact table name (if whitelisted)
2. If user mentions specific table → Use that table (if whitelisted)
3. **For any modification**: ONLY use tables from the whitelist above
4. Match the modification request to whitelisted tables by:
   - Table name keywords (destinations, hubs, routes, params, etc.)
   - Column names that match the requested parameter
   - Data types that fit the modification (demand, capacity, cost, etc.)
5. **NEVER** suggest tables not in the whitelist, regardless of naming patterns

CRITICAL PERCENTAGE HANDLING:
- For relative percentage operations (e.g., "twice that of oxford"), DO NOT generate SQL expressions
- Instead, set the percentage fields correctly and let the system handle the calculation
- For "twice that of oxford" → PERCENTAGE_TYPE: relative, PERCENTAGE_VALUE: 200, REFERENCE_COLUMN: Demand, WHERE_CONDITION: Location = 'Oxford'
- The system will automatically calculate the new value based on these fields

Analyze the request and identify:
1. Which WHITELISTED table contains the parameter to be modified
2. Which column(s) need to be updated  
3. What the exact new value should be (extract from user request)
4. Any WHERE conditions needed to target the right row (e.g., Location = 'Birmingham')
5. **NEW:** Percentage information if applicable

Respond in this exact format:
TABLE: [table_name_from_whitelist]
COLUMN: [column_name] 
NEW_VALUE: [exact_numeric_value_from_request OR "PERCENTAGE_CALCULATION"]
WHERE_CONDITION: [if needed, e.g., Location = 'Birmingham']
DESCRIPTION: [brief description of the change]
PERCENTAGE_TYPE: [absolute/relative/none]
PERCENTAGE_VALUE: [numeric percentage value if applicable]
PERCENTAGE_OPERATION: [increase/decrease/set if applicable]
REFERENCE_COLUMN: [column name for relative calculations if applicable]"""

            response = self.llm.invoke([HumanMessage(content=f"{system_prompt}\n\nModification Request: {last_message}")])
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
                elif line.startswith('PERCENTAGE_TYPE:'):
                    modification_data['percentage_type'] = line.replace('PERCENTAGE_TYPE:', '').strip().lower()
                elif line.startswith('PERCENTAGE_VALUE:'):
                    modification_data['percentage_value'] = line.replace('PERCENTAGE_VALUE:', '').strip()
                elif line.startswith('PERCENTAGE_OPERATION:'):
                    modification_data['percentage_operation'] = line.replace('PERCENTAGE_OPERATION:', '').strip().lower()
                elif line.startswith('REFERENCE_COLUMN:'):
                    modification_data['reference_column'] = line.replace('REFERENCE_COLUMN:', '').strip()
            
            # Merge extracted percentage info with LLM response
            if percentage_info:
                modification_data.update(percentage_info)
                # If we have a reference_location, add it to the prompt context
                if 'reference_location' in percentage_info:
                    print(f"DEBUG: Found reference location: {percentage_info['reference_location']}")
                    # Add reference location info to the prompt
                    system_prompt += f"\n\nREFERENCE LOCATION INFO:\nThe percentage operation references location: '{percentage_info['reference_location']}'\nThis means you need to set REFERENCE_COLUMN to the actual column name (e.g., 'Demand') and use the reference location in the WHERE condition for the reference query."
            
            # Debug: Log the raw response and parsed data
            print(f"DEBUG: LLM raw response for modification: {content}")
            print(f"DEBUG: Parsed modification data: {modification_data}")
            
            # If we have the correct table but the LLM didn't extract the numeric value, try again
            if modification_data.get('new_value') in ['<exact_numeric_value_from_request>', '[EXTRACT_FROM_REQUEST]', None]:
                modification_data['new_value'] = extracted_value
            
            # Check if target table is whitelisted for modifications
            target_table = modification_data.get('table', '')
            if target_table:
                try:
                    # Import the whitelist from main module
                    import main
                    current_whitelist = main.get_table_whitelist()
                    
                    if target_table not in current_whitelist:
                        error_message = f"❌ Table '{target_table}' is not whitelisted for modifications. Please enable it in the SQL Database tab."
                        print(f"DEBUG: Table '{target_table}' not in whitelist: {current_whitelist}")
                        return {
                            **state,
                            "whitelist_error": True,  # Flag to prevent execute node from running its error message
                            "messages": state["messages"] + [AIMessage(content=error_message)]
                        }
                    else:
                        print(f"DEBUG: Table '{target_table}' is whitelisted for modification")
                except Exception as e:
                    print(f"DEBUG: Error checking whitelist: {e}")
                    # Continue without whitelist check if there's an error accessing it
            
            return {
                **state,
                "modification_request": modification_data,
                "identified_tables": [modification_data.get('table', '')],
                "identified_columns": [modification_data.get('column', '')],
                "current_values": {modification_data.get('column', ''): "unknown"},
                "new_values": {modification_data.get('column', ''): modification_data.get('new_value', '')},
                "messages": state["messages"] + [AIMessage(content=f"Identified modification: {modification_data}")]
            }
            
        except Exception as e:
            return {
                **state,
                "db_modification_result": {
                    "success": False,
                    "error": f"Error preparing modification: {str(e)}"
                },
                "messages": state["messages"] + [AIMessage(content=f"❌ Error analyzing modification request: {str(e)}")]
            }

    def _extract_percentage_patterns(self, message: str) -> dict:
        """Extract percentage patterns from user message with natural language support"""
        import re
        
        percentage_info = {}
        message_lower = message.lower()
        
        # Natural language fraction mappings
        fraction_mappings = {
            'half': 50.0,
            'halves': 50.0,
            'quarter': 25.0,
            'quarters': 25.0,
            'third': 33.33,
            'thirds': 33.33,
            'fourth': 25.0,
            'fourths': 25.0,
            'fifth': 20.0,
            'fifths': 20.0,
            'sixth': 16.67,
            'sixths': 16.67,
            'seventh': 14.29,
            'sevenths': 14.29,
            'eighth': 12.5,
            'eighths': 12.5,
            'ninth': 11.11,
            'ninths': 11.11,
            'tenth': 10.0,
            'tenths': 10.0,
            'double': 200.0,
            'triple': 300.0,
            'quadruple': 400.0
        }
        
        # Helper function to convert natural language to percentage
        def convert_natural_to_percentage(text):
            for fraction, percentage in fraction_mappings.items():
                if fraction in text:
                    return percentage
            return None
        
        # Check for natural language fractions first (but skip if it's a relative pattern)
        # Skip natural language detection if it's a relative pattern like "twice that of X"
        if not any(pattern in message_lower for pattern in ['that of', 'of ']):
            natural_percentage = convert_natural_to_percentage(message_lower)
            if natural_percentage:
                # Determine operation from context
                if any(word in message_lower for word in ['decrease', 'reduce', 'lower', 'drop', 'cut']):
                    percentage_info['percentage_operation'] = 'decrease'
                elif any(word in message_lower for word in ['increase', 'raise', 'boost', 'double', 'triple', 'quadruple']):
                    percentage_info['percentage_operation'] = 'increase'
                else:
                    percentage_info['percentage_operation'] = 'set'
                
                percentage_info['percentage_type'] = 'absolute'
                percentage_info['percentage_value'] = natural_percentage
                return percentage_info
        
        # Pattern 1: Absolute percentage changes (increase/decrease by X%)
        absolute_patterns = [
            r'(increase|raise|boost).*?(?:by\s+)?(\d+(?:\.\d+)?)\s*%',
            r'(decrease|reduce|lower|drop).*?(?:by\s+)?(\d+(?:\.\d+)?)\s*%',
            r'(change|modify).*?(?:by\s+)?([+-]?\d+(?:\.\d+)?)\s*%'
        ]
        
        for pattern in absolute_patterns:
            match = re.search(pattern, message_lower)
            if match:
                operation = match.group(1)
                percentage_value = float(match.group(2))
                
                # Map operations to standard terms
                if operation in ['increase', 'raise', 'boost']:
                    percentage_info['percentage_operation'] = 'increase'
                elif operation in ['decrease', 'reduce', 'lower', 'drop']:
                    percentage_info['percentage_operation'] = 'decrease'
                else:
                    # For change/modify, check if there's a sign or context clues
                    if 'increase' in message_lower or 'raise' in message_lower or 'boost' in message_lower:
                        percentage_info['percentage_operation'] = 'increase'
                    elif 'decrease' in message_lower or 'reduce' in message_lower or 'lower' in message_lower or 'drop' in message_lower:
                        percentage_info['percentage_operation'] = 'decrease'
                    elif percentage_value < 0:
                        percentage_info['percentage_operation'] = 'decrease'
                        percentage_info['percentage_value'] = abs(percentage_value)
                    else:
                        percentage_info['percentage_operation'] = 'set'
                
                percentage_info['percentage_type'] = 'absolute'
                percentage_info['percentage_value'] = abs(percentage_value)
                break
        
        # Pattern 2: Relative percentage changes (X% of Y) - FIXED to capture multi-word references
        relative_patterns = [
            # Patterns with explicit "of" keyword
            r'(increase|raise|boost).*?(?:by\s+)?(\d+(?:\.\d+)?)\s*%\s+of\s+([^,\s]+(?:\s+[^,\s]+)*)',
            r'(decrease|reduce|lower|drop).*?(?:by\s+)?(\d+(?:\.\d+)?)\s*%\s+of\s+([^,\s]+(?:\s+[^,\s]+)*)',
            r'(set|change|modify).*?(?:to\s+)?(\d+(?:\.\d+)?)\s*%\s+of\s+([^,\s]+(?:\s+[^,\s]+)*)',
            r'(\d+(?:\.\d+)?)\s*%\s+of\s+([^,\s]+(?:\s+[^,\s]+)*)',  # Generic pattern
            # Patterns with quoted references (avoid capturing "the" before quotes)
            r'(increase|raise|boost).*?(?:by\s+)?(\d+(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?"([^"]+)"',
            r'(decrease|reduce|lower|drop).*?(?:by\s+)?(\d+(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?"([^"]+)"',
            r'(set|change|modify).*?(?:to\s+)?(\d+(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?"([^"]+)"',
            r'(\d+(?:\.\d+)?)\s*%\s+of\s+(?:the\s+)?"([^"]+)"',  # Generic pattern with quotes
            # Patterns for "twice that of X" format (location-based references)
            r'(set|change|modify).*?(?:to\s+)?(twice|double)\s+that\s+of\s+([^,\s]+(?:\s+[^,\s]+)*)',
            r'(twice|double)\s+that\s+of\s+([^,\s]+(?:\s+[^,\s]+)*)',  # Generic pattern for "twice that of X"
            r'(set|change|modify).*?(?:to\s+)?(twice|double)\s+that\s+of\s+(?:the\s+)?"([^"]+)"',
            r'(twice|double)\s+that\s+of\s+(?:the\s+)?"([^"]+)"'  # Generic pattern with quotes
        ]
        
        for pattern in relative_patterns:
            match = re.search(pattern, message_lower)
            if match:
                if len(match.groups()) == 3:
                    operation, percentage_value, reference = match.groups()
                    if operation in ['increase', 'raise', 'boost']:
                        percentage_info['percentage_operation'] = 'increase'
                    elif operation in ['decrease', 'reduce', 'lower', 'drop']:
                        percentage_info['percentage_operation'] = 'decrease'
                    else:
                        percentage_info['percentage_operation'] = 'set'
                    
                    # Handle "twice that of X" format
                    if percentage_value in ['twice', 'double']:
                        percentage_info['percentage_value'] = 200.0
                    else:
                        percentage_info['percentage_value'] = float(percentage_value)
                        
                elif len(match.groups()) == 2:
                    percentage_value, reference = match.groups()
                    percentage_info['percentage_operation'] = 'set'
                    
                    # Handle "twice that of X" format
                    if percentage_value in ['twice', 'double']:
                        percentage_info['percentage_value'] = 200.0
                    else:
                        percentage_info['percentage_value'] = float(percentage_value)
                
                percentage_info['percentage_type'] = 'relative'
                # Clean up reference name (remove quotes, extra spaces)
                reference_clean = reference.strip().strip('"').strip("'")
                
                # For "twice that of X" patterns, the reference is a location, not a column
                # We'll let the LLM determine the correct column name
                if percentage_value in ['twice', 'double']:
                    percentage_info['reference_location'] = reference_clean
                    # Don't set reference_column here - let the LLM set it
                else:
                    percentage_info['reference_column'] = reference_clean
                break
        
        # Pattern 3: Set to percentage (set to X%)
        set_patterns = [
            r'(set|change)\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*%',
        ]
        
        for pattern in set_patterns:
            match = re.search(pattern, message_lower)
            if match and 'percentage_type' not in percentage_info:  # Only if not already found
                percentage_info['percentage_type'] = 'absolute'
                percentage_info['percentage_operation'] = 'set'
                percentage_info['percentage_value'] = float(match.group(2))
                break
        
        return percentage_info
    
    def _execute_db_modification_node(self, state: AgentState) -> AgentState:
        """Execute the database modification with detailed change tracking and parameter validation"""
        # Check if whitelist error already occurred in prepare phase
        if state.get("whitelist_error"):
            print(f"DEBUG: Whitelist error already handled in prepare phase, skipping execute")
            return state
        
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
            error_msg = "❌ **No modification data available.** This could be because:\n"
            error_msg += "• The requested table is not whitelisted for modifications\n"
            error_msg += "• The preparation step failed to identify the table or column\n\n"
            
            # Check if we have database schema information and whitelist
            if state.get("database_schema") or self.cached_database_schema:
                available_tables = []
                if state.get("database_schema"):
                    schema_data = state["database_schema"].get("tables", [])
                    available_tables = [t["name"] for t in schema_data if isinstance(t, dict) and "name" in t]
                elif self.cached_database_schema:
                    schema_data = self.cached_database_schema.get("tables", [])
                    available_tables = [t["name"] for t in schema_data if isinstance(t, dict) and "name" in t]
                
                # Get whitelisted tables
                try:
                    import main
                    current_whitelist = main.get_table_whitelist()
                    whitelisted_tables = [table for table in available_tables if table in current_whitelist]
                    
                    if whitelisted_tables:
                        error_msg += f"**Tables whitelisted for modifications ({len(whitelisted_tables)} total):**\n"
                        for table in whitelisted_tables:
                            error_msg += f"• {table}\n"
                        error_msg += f"\n**Please try again with one of the whitelisted table names above.**\n"
                        error_msg += f"\n💡 **Tip:** You can manage table permissions in the SQL Database tab."
                    else:
                        error_msg += "**No tables are currently whitelisted for modifications.**\n"
                        error_msg += "Please enable table modifications in the SQL Database tab first."
                except Exception as e:
                    print(f"DEBUG: Error getting whitelist: {e}")
                    # Fallback to showing all tables if whitelist access fails
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
            
            # Handle percentage calculations if applicable
            percentage_calculation_performed = False
            original_new_value = new_value
            
            # Check if this is a percentage modification
            percentage_type = modification_data.get('percentage_type', '').lower()
            percentage_operation = modification_data.get('percentage_operation', '').lower()
            percentage_value = modification_data.get('percentage_value')
            reference_column = modification_data.get('reference_column', '')
            
            # Only process percentage calculations if we have valid percentage data
            # Exclude 'none' values which indicate non-percentage operations
            if (percentage_type and percentage_type not in ['none', '', 'n/a'] and 
                percentage_value is not None and str(percentage_value).lower() not in ['none', '', 'n/a']):
                try:
                    percentage_value = float(percentage_value)
                    calculated_value = None
                    calculation_description = ""
                    
                    # Validate percentage value
                    if percentage_value < 0:
                        print(f"DEBUG: Warning - negative percentage value: {percentage_value}%")
                    if percentage_value > 1000:
                        print(f"DEBUG: Warning - very large percentage value: {percentage_value}%")
                        # Still allow it as user requested no limits on percentage changes
                    
                    if percentage_type == 'absolute':
                        # Absolute percentage changes (increase/decrease by X%)
                        if old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                            try:
                                current_value = float(old_values[0])
                                percentage_change = (percentage_value / 100.0) * current_value
                                
                                if percentage_operation == 'increase':
                                    calculated_value = current_value + percentage_change
                                    calculation_description = f"Increased {current_value} by {percentage_value}% ({percentage_change:.2f})"
                                elif percentage_operation == 'decrease':
                                    calculated_value = current_value - percentage_change
                                    calculation_description = f"Decreased {current_value} by {percentage_value}% ({percentage_change:.2f})"
                                elif percentage_operation == 'set':
                                    calculated_value = (percentage_value / 100.0) * current_value
                                    calculation_description = f"Set to {percentage_value}% of current value ({current_value})"
                                
                                # Round to 2 decimal places
                                calculated_value = round(calculated_value, 2)
                                
                            except (ValueError, TypeError) as e:
                                print(f"DEBUG: Error in absolute percentage calculation: {e}")
                    
                    elif percentage_type == 'relative':
                        # Relative percentage changes (X% of Y)
                        # First, get the reference value
                        reference_value = None
                        try:
                            # Check if we have a reference location (for "twice that of X" patterns)
                            reference_location = modification_data.get('reference_location')
                            if reference_location:
                                # For location-based references, query the same column but for the reference location
                                quoted_ref_column = quote_identifier(column)  # Use the same column being modified
                                ref_sql = f"SELECT {quoted_ref_column} FROM {quoted_table} WHERE Location = '{reference_location}'"
                                print(f"DEBUG: Reference query (location-based): {ref_sql}")
                            else:
                                # For column-based references, use the reference column
                                quoted_ref_column = quote_identifier(reference_column)
                                
                                if where_condition and 'formatted_where' in locals():
                                    ref_sql = f"SELECT {quoted_ref_column} FROM {quoted_table} WHERE {formatted_where}"
                                elif where_condition:
                                    where_parts = where_condition.split('=', 1)
                                    if len(where_parts) == 2:
                                        left_part = where_parts[0].strip()
                                        right_part = where_parts[1].strip()
                                        quoted_left = quote_identifier(left_part)
                                        ref_sql = f"SELECT {quoted_ref_column} FROM {quoted_table} WHERE {quoted_left} = {right_part}"
                                    else:
                                        ref_sql = f"SELECT {quoted_ref_column} FROM {quoted_table} WHERE {where_condition}"
                                else:
                                    ref_sql = f"SELECT {quoted_ref_column} FROM {quoted_table}"
                                
                                print(f"DEBUG: Reference query (column-based): {ref_sql}")
                            
                            cursor.execute(ref_sql)
                            ref_results = cursor.fetchall()
                            
                            if ref_results:
                                reference_value = float(ref_results[0][0])
                            
                        except Exception as e:
                            print(f"DEBUG: Error getting reference value for {reference_column}: {e}")
                            # Try to find reference in same row if it's a different column
                            try:
                                if where_condition and 'formatted_where' in locals():
                                    ref_sql = f"SELECT {quoted_ref_column} FROM {quoted_table} WHERE {formatted_where}"
                                    cursor.execute(ref_sql)
                                    ref_results = cursor.fetchall()
                                    if ref_results:
                                        reference_value = float(ref_results[0][0])
                            except:
                                pass
                        
                        if reference_value is not None:
                            percentage_amount = (percentage_value / 100.0) * reference_value
                            
                            # Handle location-based vs column-based references in description
                            reference_location = modification_data.get('reference_location')
                            if reference_location:
                                reference_desc = f"{column} of {reference_location}"
                            else:
                                reference_desc = reference_column
                            
                            if percentage_operation == 'set':
                                calculated_value = percentage_amount
                                calculation_description = f"Set to {percentage_value}% of {reference_desc} ({reference_value}) = {percentage_amount:.2f}"
                            elif percentage_operation == 'increase':
                                if old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                                    current_value = float(old_values[0])
                                    calculated_value = current_value + percentage_amount
                                    calculation_description = f"Increased {current_value} by {percentage_value}% of {reference_desc} ({reference_value}) = +{percentage_amount:.2f}"
                            elif percentage_operation == 'decrease':
                                if old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                                    current_value = float(old_values[0])
                                    calculated_value = current_value - percentage_amount
                                    calculation_description = f"Decreased {current_value} by {percentage_value}% of {reference_desc} ({reference_value}) = -{percentage_amount:.2f}"
                            
                            # Round to 2 decimal places
                            if calculated_value is not None:
                                calculated_value = round(calculated_value, 2)
                    
                    # Update new_value if calculation was successful
                    if calculated_value is not None:
                        # Additional validation for the calculated result
                        if calculated_value < 0 and percentage_operation == 'decrease':
                            print(f"DEBUG: Warning - percentage decrease resulted in negative value: {calculated_value}")
                        
                        new_value = str(calculated_value)
                        percentage_calculation_performed = True
                        print(f"DEBUG: Percentage calculation: {calculation_description} → {calculated_value}")
                    else:
                        error_msg = f"❌ **Percentage calculation failed** - "
                        if percentage_type == 'absolute' and (not old_values or old_values[0] in ["Could not retrieve:", "unknown"]):
                            error_msg += "Could not retrieve current value for percentage calculation."
                        elif percentage_type == 'relative' and not reference_column:
                            error_msg += "Reference column not specified for relative percentage calculation."
                        else:
                            error_msg += "Could not determine required values for percentage calculation."
                        
                        print(f"DEBUG: Percentage calculation failed - could not determine values")
                        # Return early with error message for percentage calculation failures
                        return {
                            **state,
                            "db_modification_result": {
                                "success": False,
                                "error": "Percentage calculation failed"
                            },
                            "messages": state["messages"] + [AIMessage(content=error_msg)]
                        }
                        
                except Exception as e:
                    error_msg = f"❌ **Percentage calculation error:** {str(e)}\n\n"
                    error_msg += "Please check that:\n"
                    error_msg += "• The current value can be retrieved from the database\n"
                    error_msg += "• For relative percentages, the reference column exists\n"
                    error_msg += "• The percentage value is valid\n"
                    print(f"DEBUG: Error in percentage calculation: {e}")
                    return {
                        **state,
                        "db_modification_result": {
                            "success": False,
                            "error": f"Percentage calculation error: {str(e)}"
                        },
                        "messages": state["messages"] + [AIMessage(content=error_msg)]
                    }
            
            print(f"DEBUG: Final new_value after percentage calculation: {new_value} (was: {original_new_value})")
            
            # Generate SQL UPDATE statement with proper quoting
            try:
                # Clean and validate the new value
                clean_value = str(new_value).strip()
                if not clean_value:
                    raise ValueError("Empty value")
                float(clean_value)  # Test if it's a valid number
                sql = f"UPDATE {quoted_table} SET {quoted_column} = {clean_value}"
            except ValueError:
                # If not a valid number, treat as string but prevent SQL injection
                clean_value = clean_value.replace("'", "''")  # Escape single quotes
                sql = f"UPDATE {quoted_table} SET {quoted_column} = '{clean_value}'"
            
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
            
            # Add percentage calculation details if applicable
            if percentage_calculation_performed:
                change_summary += f"🧮 **Calculation Type:** Percentage-based modification\n"
                if percentage_type == 'absolute':
                    operation_desc = f"{percentage_operation.title()} by {percentage_value}%"
                elif percentage_type == 'relative':
                    operation_desc = f"{percentage_operation.title()} by {percentage_value}% of {reference_column}"
                change_summary += f"📈 **Operation:** {operation_desc}\n"
                change_summary += f"💡 **Calculation:** {calculation_description}\n"
            
            change_summary += f"🔄 **Change:**\n"
            
            if len(old_values) == 1 and len(new_values) == 1:
                change_summary += f"   - **Before:** {old_values[0]}\n"
                change_summary += f"   - **After:** {new_values[0]}\n"
                
                # Add percentage change summary if it was a percentage calculation
                if percentage_calculation_performed and len(old_values) == 1:
                    try:
                        old_val = float(old_values[0])
                        new_val = float(new_values[0])
                        actual_change = new_val - old_val
                        actual_percentage = (actual_change / old_val) * 100 if old_val != 0 else 0
                        change_summary += f"   - **Net Change:** {actual_change:+.2f} ({actual_percentage:+.2f}%)\n"
                    except (ValueError, TypeError):
                        pass
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
            if percentage_calculation_performed:
                print(f"Percentage calculation: {calculation_description}")
                print(f"Original requested value: {original_new_value}")
                print(f"Calculated value: {new_value}")
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
                    "parameter_validation": parameter_validation,
                    "percentage_calculation_performed": percentage_calculation_performed,
                    "percentage_type": percentage_type if percentage_calculation_performed else None,
                    "percentage_operation": percentage_operation if percentage_calculation_performed else None,
                    "percentage_value": percentage_value if percentage_calculation_performed else None,
                    "calculation_description": calculation_description if percentage_calculation_performed else None,
                    "original_requested_value": original_new_value if percentage_calculation_performed else None
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



    def _clean_visualization_code(self, code_content: str) -> str:
        """Enhanced cleaning for plotly visualization code to remove all markdown artifacts and fix indentation"""
        import re
        
        # First, extract only the actual Python code if there's markdown text
        code_blocks = re.findall(r'```(?:python|py)?\n(.*?)```', code_content, re.DOTALL)
        if code_blocks:
            # Use the last code block if multiple exist
            code_content = code_blocks[-1]
        
        # Remove any remaining markdown explanation lines
        lines = code_content.split('\n')
        cleaned_lines = []
        for line in lines:
            # Skip lines that look like markdown text
            if line.strip().endswith(':') and not line.strip().startswith('#'):
                continue
            if line.strip().startswith(('Here', 'Now', 'First', 'Then', 'Finally', 'Next', 'Let')):
                continue
            cleaned_lines.append(line)
        
        # Fix indentation
        fixed_lines = []
        current_block_indent = 0
        in_function = False
        in_loop = False
        in_if = False
        
        for i, line in enumerate(cleaned_lines):
            stripped = line.strip()
            if not stripped:  # Empty line
                fixed_lines.append('')
                continue
                
            # Determine the base indentation for this line
            if stripped.startswith(('def ', 'class ')):
                current_block_indent = 4
                in_function = True
            elif stripped.startswith(('if ', 'for ', 'while ', 'try:', 'else:', 'elif ')):
                if not in_function:
                    current_block_indent = 4
                else:
                    current_block_indent += 4
                if stripped.startswith(('for ', 'while ')):
                    in_loop = True
                if stripped.startswith(('if ', 'elif ', 'else:')):
                    in_if = True
            elif stripped.endswith(':'):  # Other block starts
                current_block_indent += 4
            elif in_loop and any(x in stripped for x in ['break', 'continue']):
                # These should be at the same level as the loop body
                pass
            elif in_if and stripped.startswith(('break', 'continue', 'return')):
                # These should be at the same level as the if body
                pass
            elif stripped.startswith(('return', 'break', 'continue', 'raise')):
                # These should be at the same level as the function body
                if in_function:
                    current_block_indent = 4
            elif i > 0 and cleaned_lines[i-1].strip().endswith(':'):
                # This line should be indented if it follows a block starter
                pass
            else:
                # Check if this line looks like it should end a block
                if current_block_indent > 0 and not any(stripped.startswith(x) for x in ['.', '+', '-', '*', '/', '=', 'and ', 'or ']):
                    current_block_indent = max(0, current_block_indent - 4)
                    in_loop = False
                    in_if = False
            
            # Apply the indentation
            fixed_lines.append(' ' * current_block_indent + stripped)
        
        code_content = '\n'.join(fixed_lines)
        
        # Ensure all required imports are at the start
        required_imports = '''import os
import time
import datetime
import random
import sqlite3
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import numpy as np'''
        
        # Remove any existing imports
        code_lines = code_content.split('\n')
        non_import_lines = [line for line in code_lines if not line.strip().startswith('import') and not line.strip().startswith('matplotlib.use') and not line.strip().startswith('pio.')]
        
        # Combine required imports with cleaned code
        code_content = required_imports + '\n\n' + '\n'.join(non_import_lines)
        
        # Add standard database connection and plotly configuration if not present
        db_connection = '''
# Set plotly configuration for interactive charts
pio.templates.default = "plotly_white"

# Connect to the database
conn = sqlite3.connect('project_data.db')
print("Connected to database: project_data.db")

# Check available tables
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]
print(f"Available tables: {tables}")

# IMPORTANT: After reading data with pd.read_sql, ensure numeric columns are properly converted
# This prevents the issue where bars show 0,1,2,3 instead of actual values
def ensure_numeric_columns(df, table_name=None):
    """Convert numeric columns to proper numeric types for visualization using database schema"""
    try:
        if df is None or not hasattr(df, 'columns'):
            return df
        
                 print(f"Starting column type conversion for table: {table_name}")
         print(f"Original DataFrame columns: {list(df.columns)}")
         print(f"Original DataFrame dtypes: {df.dtypes.to_dict()}")
         
         # Get column types from database schema - always try to get schema info
         column_types = {}
         tables_to_check = []
         
         # If table_name is provided, use it; otherwise try to infer from DataFrame columns
         if table_name:
             tables_to_check.append(table_name)
         else:
             # Try to infer table name from common patterns in the DataFrame
             # This is useful when the system automatically chooses a table
             try:
                 conn = sqlite3.connect('project_data.db')
                 cursor = conn.cursor()
                 cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                 all_tables = [row[0] for row in cursor.fetchall()]
                 conn.close()
                 
                 # Look for tables that might contain our columns
                 for table in all_tables:
                     try:
                         conn = sqlite3.connect('project_data.db')
                         cursor = conn.cursor()
                         cursor.execute(f"PRAGMA table_info({table})")
                         table_info = cursor.fetchall()
                         conn.close()
                         
                         table_columns = [col[1] for col in table_info]
                         # Check if this table contains our DataFrame columns
                         if all(col in table_columns for col in df.columns):
                             tables_to_check.append(table)
                             print(f"Found matching table '{table}' for columns: {list(df.columns)}")
                             break
                     except Exception:
                         continue
             except Exception as e:
                 print(f"Warning: Could not get table list: {e}")
         
         # Get schema info for the identified table(s)
         for table in tables_to_check:
             try:
                 conn = sqlite3.connect('project_data.db')
                 cursor = conn.cursor()
                 cursor.execute(f"PRAGMA table_info({table})")
                 table_info = cursor.fetchall()
                 conn.close()
                 
                 # Extract column names and types
                 for col_info in table_info:
                     col_name = col_info[1]  # Column name
                     col_type = col_info[2].upper()  # Column type
                     column_types[col_name] = col_type
                 print(f"Database schema for {table}: {column_types}")
                 break  # Use the first matching table
             except Exception as e:
                 print(f"Warning: Could not get schema info for table {table}: {e}")
         
         if not column_types:
             print("No database schema found - will use fallback logic for column types")
         
         # Only convert columns that are CLEARLY numeric based on database schema or name patterns
         for col in df.columns:
             should_convert = False
             
             # Check database schema first (most reliable)
             if col in column_types:
                 col_type = column_types[col]
                 # Only convert if explicitly marked as numeric in database
                 if col_type in ['INTEGER', 'REAL', 'NUMERIC', 'DECIMAL', 'DOUBLE', 'FLOAT']:
                     should_convert = True
                     print(f"Converting column '{col}' based on database schema: {col_type}")
                 else:
                     print(f"Preserving text column '{col}' (database type: {col_type})")
             else:
                 # Fallback: Only convert columns with clearly numeric names
                 numeric_indicators = ['DEMAND', 'COST', 'CAPACITY', 'SUPPLY', 'VALUE', 'AMOUNT', 'QUANTITY', 'NUMBER', 'COUNT', 'TOTAL', 'SUM', 'AVERAGE', 'AVG', 'MIN', 'MAX', 'PRICE', 'RATE', 'FACTOR', 'WEIGHT', 'DISTANCE', 'TIME', 'DURATION', 'SCORE', 'PERCENT', 'RATIO', 'SIZE', 'LENGTH', 'WIDTH', 'HEIGHT', 'AREA', 'VOLUME']
                 if any(indicator in col.upper() for indicator in numeric_indicators):
                     should_convert = True
                     print(f"Converting column '{col}' based on name pattern (likely numeric)")
                 else:
                     print(f"Preserving column '{col}' as text (no clear numeric indicators)")
             
             # Only convert if we determined it should be numeric
             if should_convert:
                 try:
                     # Try to convert to numeric, keep as string if it fails
                     original_dtype = df[col].dtype
                     df[col] = pd.to_numeric(df[col], errors='coerce')
                     
                     # Check if conversion was successful
                     if df[col].dtype != original_dtype:
                         # If successful and all values are integers, convert to int
                         if df[col].notna().all() and all(float(x).is_integer() for x in df[col].dropna()):
                             df[col] = df[col].astype('Int64')
                         print(f"Successfully converted column '{col}' to numeric type: {df[col].dtype}")
                     else:
                         print(f"Column '{col}' conversion failed or not needed, keeping as: {df[col].dtype}")
                 except Exception as e:
                     print(f'Could not convert column {col} to numeric: {e}')
                     # Keep original data type if conversion fails
                     pass
         
         print(f"Final DataFrame dtypes: {df.dtypes.to_dict()}")
         return df
          except Exception as e:
         print(f'Error in ensure_numeric_columns: {e}')
         return df
'''
        # Insert after imports
        lines = code_content.split('\n')
        import_end = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ', '#')):
                import_end = i + 1
            elif line.strip() and not line.strip().startswith(('import ', 'from ', '#')):
                break
        lines.insert(import_end, ensure_numeric_columns_def)
        code_content = '\n'.join(lines)

        # Remove duplicate manual conversion blocks if both exist
        if 'ensure_numeric_columns(df)' in code_content:
            # Remove any manual conversion loop after pd.read_sql or in the script
            import re
            # Remove the block: for col in columns_to_convert: ... (the manual loop)
            code_content = re.sub(
                r'columns_to_convert\s*=\s*list\(df\.columns\)\nfor col in columns_to_convert:[\s\S]+?except Exception as e:[\s\S]+?pass',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove redundant conversion blocks that convert all columns
            code_content = re.sub(
                r'# Convert numeric columns to proper numeric types\ncolumns_to_convert\s*=\s*list\(df\.columns\)\nfor col in columns_to_convert:[\s\S]+?pass\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove the initial conversion that converts ALL columns (this is the main culprit)
            code_content = re.sub(
                r'# Clean and convert data types for visualization\ndf\.columns\s*=\s*df\.columns\.str\.strip\(\)\n\n# Convert numeric columns to proper numeric types\ncolumns_to_convert\s*=\s*list\(df\.columns\)\nfor col in columns_to_convert:[\s\S]+?pass\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove the SAFETY block that does redundant conversion
            code_content = re.sub(
                r'# SAFETY: Ensure all variables are properly defined for data conversion\ntry:\s*# Convert numeric columns safely[\s\S]+?except Exception as e:\s*print\(f\'Error during data type conversion: \{e\}\'\)\s*# Continue with original data types\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove duplicate "Converting data types for visualization" blocks
            code_content = re.sub(
                r'# CRITICAL: Ensure numeric columns are properly converted for visualization\nprint\("Converting data types for visualization\.\.\."\)\ncolumns_to_convert\s*=\s*\[\'Demand\'\]\nfor col in columns_to_convert:[\s\S]+?print\(f"Column \'{col}\' converted to: \{df\[col\]\.dtype\}"\)\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove redundant data display blocks
            code_content = re.sub(
                r'# Display data info for debugging\nprint\(\'DataFrame info:\'\)\nprint\(df\.info\(\)\)\nprint\(\'\\nData types:\'\)\nprint\(df\.dtypes\)\nprint\(\'\\nFirst few rows:\'\)\nprint\(df\.head\(\)\)\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove the data file search block that's not needed
            code_content = re.sub(
                r'# Find data files recursively in all directories\n[\s\S]+?print\(f"Found data files: \{data_files\}"\)\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
            
            # Remove the simple ensure_numeric_columns function that doesn't use schema
            code_content = re.sub(
                r'def ensure_numeric_columns\(df, table_name\):\s*# Assuming the schema is known[\s\S]+?return df\n',
                '',
                code_content,
                flags=re.MULTILINE
            )
        
        # Remove orphaned print statements that reference undefined variables
        # Remove lines like: print(f'Could not convert column {col} to numeric: {e}')
        # when they appear outside of exception handlers
        lines = code_content.split('\n')
        cleaned_lines = []
        in_exception_handler = False
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('try:'):
                in_exception_handler = True
            elif stripped.startswith('except') and ':' in stripped:
                in_exception_handler = True
            elif stripped.startswith('finally:') or (stripped and not stripped.startswith((' ', '\t', '#')) and not in_exception_handler):
                in_exception_handler = False
            
            # Skip orphaned print statements that reference undefined variables
            if (not in_exception_handler and 
                stripped.startswith('print(') and 
                ('{col}' in stripped or '{e}' in stripped) and
                'Could not convert column' in stripped):
                continue
            
            cleaned_lines.append(line)
        
        code_content = '\n'.join(cleaned_lines)
        # --- END PATCH ---

        # Final strip
        return code_content.strip()

    def _get_data_sample(self, table: str, columns: List[str], filters: str = None, limit: int = 5) -> Dict:
        """Get a sample of data and statistics for specified table and columns"""
        try:
            conn = sqlite3.connect('project_data.db')
            cursor = conn.cursor()
            
            # Build the query
            columns_str = ", ".join(columns)
            query = f"SELECT {columns_str} FROM {table}"
            if filters:
                query += f" WHERE {filters}"
            query += f" LIMIT {limit}"
            
            # Get sample data
            cursor.execute(query)
            sample_rows = cursor.fetchall()
            
            # Get basic statistics for each column
            stats = {}
            for col in columns:
                stats_query = f"""
                SELECT 
                    COUNT(*) as count,
                    COUNT(DISTINCT {col}) as unique_count,
                    MIN({col}) as min_val,
                    MAX({col}) as max_val,
                    AVG({col}) as avg_val
                FROM {table}
                {f'WHERE {filters}' if filters else ''}
                """
                try:
                    cursor.execute(stats_query)
                    count, unique_count, min_val, max_val, avg_val = cursor.fetchone()
                    stats[col] = {
                        "count": count,
                        "unique_count": unique_count,
                        "min": min_val,
                        "max": max_val,
                        "avg": avg_val,
                        "data_type": type(min_val).__name__ if min_val is not None else "unknown"
                    }
                except sqlite3.OperationalError:
                    # If statistical analysis fails (e.g., for text columns)
                    cursor.execute(f"SELECT COUNT(*), COUNT(DISTINCT {col}) FROM {table}")
                    count, unique_count = cursor.fetchone()
                    stats[col] = {
                        "count": count,
                        "unique_count": unique_count,
                        "data_type": "text"
                    }
            
            conn.close()
            return {
                "sample_data": sample_rows,
                "columns": columns,
                "statistics": stats
            }
            
        except Exception as e:
            print(f"Error getting data sample: {e}")
            return {"error": str(e)}

    def _validate_sql_against_schema(self, sql_query: str, schema_context: str) -> Dict[str, any]:
        """Validate SQL query against database schema to catch column/table errors before execution"""
        try:
            # Extract table and column information from schema context
            schema_info = self._parse_schema_context(schema_context)
            
            # Parse the SQL query to extract table and column references
            sql_info = self._parse_sql_query(sql_query)
            
            # Validate tables
            for table in sql_info["tables"]:
                if table not in schema_info["tables"]:
                    return {
                        "valid": False,
                        "error": f"Table '{table}' does not exist in the database. Available tables: {list(schema_info['tables'].keys())}"
                    }
            
            # Validate columns
            for table, columns in sql_info["columns"].items():
                if table not in schema_info["tables"]:
                    continue  # Table validation will catch this
                
                available_columns = schema_info["tables"][table]
                for column in columns:
                    if column not in available_columns:
                        return {
                            "valid": False,
                            "error": f"Column '{column}' does not exist in table '{table}'. Available columns: {available_columns}"
                        }
            
            return {"valid": True, "error": None}
            
        except Exception as e:
            return {
                "valid": False,
                "error": f"Schema validation error: {str(e)}"
            }
    
    def _parse_schema_context(self, schema_context: str) -> Dict[str, any]:
        """Parse the schema context string to extract table and column information"""
        schema_info = {"tables": {}}
        current_table = None
        
        lines = schema_context.split('\n')
        for line in lines:
            line = line.strip()
            
            # Extract table name
            if line.startswith("TABLE: "):
                current_table = line.replace("TABLE: ", "").strip()
                schema_info["tables"][current_table] = []
            
            # Extract column information
            elif line.startswith("  * ") and current_table:
                # Format: "  * column_name (type)"
                column_info = line.replace("  * ", "").strip()
                if " (" in column_info:
                    column_name = column_info.split(" (")[0].strip()
                    schema_info["tables"][current_table].append(column_name)
        
        return schema_info
    
    def _parse_sql_query(self, sql_query: str) -> Dict[str, any]:
        """Parse SQL query to extract table and column references"""
        import re
        
        sql_info = {"tables": set(), "columns": {}}
        
        # Extract table names (simplified - looks for FROM and JOIN clauses)
        from_pattern = r'FROM\s+(\w+)'
        join_pattern = r'JOIN\s+(\w+)'
        
        from_matches = re.findall(from_pattern, sql_query, re.IGNORECASE)
        join_matches = re.findall(join_pattern, sql_query, re.IGNORECASE)
        
        for table in from_matches + join_matches:
            sql_info["tables"].add(table)
        
        # Extract column references (simplified - looks for SELECT clause)
        select_pattern = r'SELECT\s+(.*?)\s+FROM'
        select_match = re.search(select_pattern, sql_query, re.IGNORECASE | re.DOTALL)
        
        if select_match:
            select_clause = select_match.group(1)
            # Look for table.column patterns
            column_pattern = r'(\w+)\.(\w+)'
            column_matches = re.findall(column_pattern, select_clause)
            
            for table, column in column_matches:
                if table not in sql_info["columns"]:
                    sql_info["columns"][table] = set()
                sql_info["columns"][table].add(column)
        
        # Convert sets to lists for easier handling
        sql_info["tables"] = list(sql_info["tables"])
        for table in sql_info["columns"]:
            sql_info["columns"][table] = list(sql_info["columns"][table])
        
        return sql_info







def create_agent(ai_model: str, temp_dir: str, agent_type: str = None) -> CodeExecutorAgent:
    """Factory function to create an agent"""
    return CodeExecutorAgent(ai_model=ai_model, temp_dir=temp_dir, agent_type=agent_type) 
