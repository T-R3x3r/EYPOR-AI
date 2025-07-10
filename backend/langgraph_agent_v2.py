"""
Simplified LangGraph Agent v2 for EYProject

This is a redesigned agent that addresses the following issues:
1. Proper scenario database routing (always uses current scenario's DB)
2. Simplified workflow with more agent freedom
3. Built-in chat capability for Q&A without code execution
4. Architecture supports future multi-scenario comparisons
5. Always generates Plotly visualizations
6. Preserves working DB modification logic
"""

import os
import sys
import sqlite3
import time
import random
import json
import glob
import re
from typing import Dict, List, Any, Optional, Tuple, Literal
from datetime import datetime
from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from typing_extensions import Annotated, TypedDict

# Import scenario management
from scenario_manager import ScenarioManager


@dataclass
class DatabaseContext:
    """Contains all database-related context for the current scenario"""
    scenario_id: Optional[int]
    database_path: Optional[str]
    schema_info: Optional[Dict[str, Any]]
    temp_dir: Optional[str]
    
    def is_valid(self) -> bool:
        """Check if database context is valid and usable"""
        return (
            self.database_path is not None and 
            os.path.exists(self.database_path) and
            self.temp_dir is not None
        )


class AgentState(TypedDict):
    """Simplified state for the agent workflow"""
    messages: Annotated[List[BaseMessage], add_messages]
    user_request: str
    request_type: str  # 'chat', 'sql_query', 'visualization', 'db_modification'
    db_context: DatabaseContext
    
    # Execution results
    generated_files: List[str]
    execution_output: str
    execution_error: str
    
    # DB modification specific (preserved from v1)
    modification_request: Optional[Dict[str, Any]]
    db_modification_result: Optional[Dict[str, Any]]


class SimplifiedAgent:
    """Simplified agent with proper scenario database routing"""
    
    def __init__(self, ai_model: str = "openai", scenario_manager: ScenarioManager = None):
        self.ai_model = ai_model
        self.scenario_manager = scenario_manager
        self.llm = None  # Initialize lazily
        
        # Build the workflow graph
        self.workflow = self._build_graph()
        self.graph = self.workflow.compile()
    
    def _get_llm(self):
        """Get or create the LLM instance (lazy initialization)"""
        if self.llm is None:
            if self.ai_model == "openai":
                from langchain_openai import ChatOpenAI
                self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
            else:
                raise ValueError(f"Unsupported AI model: {self.ai_model}")
        return self.llm
    
    def _build_graph(self) -> StateGraph:
        """Build simplified workflow graph"""
        workflow = StateGraph(AgentState)
        
        # Core nodes
        workflow.add_node("classify_request", self._classify_request)
        workflow.add_node("handle_chat", self._handle_chat)
        workflow.add_node("handle_sql_query", self._handle_sql_query)
        workflow.add_node("handle_visualization", self._handle_visualization)
        workflow.add_node("prepare_db_modification", self._prepare_db_modification)
        workflow.add_node("execute_db_modification", self._execute_db_modification)
        workflow.add_node("execute_code", self._execute_code)
        workflow.add_node("respond", self._respond)
        
        # Entry point
        workflow.add_edge(START, "classify_request")
        
        # Route based on request type
        workflow.add_conditional_edges(
            "classify_request",
            self._route_request,
            {
                "chat": "handle_chat",
                "sql_query": "handle_sql_query", 
                "visualization": "handle_visualization",
                "db_modification": "prepare_db_modification"
            }
        )
        
        # Chat goes directly to response
        workflow.add_edge("handle_chat", "respond")
        
        # SQL and visualization go to code execution
        workflow.add_edge("handle_sql_query", "execute_code")
        workflow.add_edge("handle_visualization", "execute_code")
        workflow.add_edge("execute_code", "respond")
        
        # DB modification workflow (preserved from v1)
        workflow.add_edge("prepare_db_modification", "execute_db_modification")
        workflow.add_edge("execute_db_modification", "respond")
        
        # End
        workflow.add_edge("respond", END)
        
        return workflow
    
    def _get_database_context(self, scenario_id: Optional[int] = None) -> DatabaseContext:
        """Get database context for current or specified scenario"""
        if not self.scenario_manager:
            return DatabaseContext(None, None, None, None)
        
        # Get current scenario if none specified
        if scenario_id is None:
            current_scenario = self.scenario_manager.get_current_scenario()
            if not current_scenario:
                return DatabaseContext(None, None, None, None)
            scenario_id = current_scenario.id
            database_path = current_scenario.database_path
        else:
            scenario = self.scenario_manager.get_scenario(scenario_id)
            if not scenario:
                return DatabaseContext(None, None, None, None)
            database_path = scenario.database_path
        
        # Get schema info
        schema_info = None
        if database_path and os.path.exists(database_path):
            try:
                schema_info = self._get_database_info(database_path)
            except Exception as e:
                print(f"Error getting schema info: {e}")
        
        # Get temp directory for the scenario - use the database directory for consistency
        # This ensures both Python files and HTML files are in the same location
        temp_dir = os.path.dirname(database_path)
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir, exist_ok=True)
        
        return DatabaseContext(
            scenario_id=scenario_id,
            database_path=database_path,
            schema_info=schema_info,
            temp_dir=temp_dir
        )
    
    def _classify_request(self, state: AgentState) -> AgentState:
        """Classify the user request to determine how to handle it"""
        user_request = state.get("user_request", "")
        if not user_request:
            # Get from messages
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_request = msg.content
                    break
        
        # Simple keyword-based classification with LLM fallback
        request_lower = user_request.lower()
        
        # Check for clear DB modification patterns
        db_mod_patterns = ["change", "update", "set", "modify", "alter", "edit"]
        param_patterns = ["parameter", "param", "cost", "demand", "capacity", "limit"]
        
        if any(pattern in request_lower for pattern in db_mod_patterns) and \
           any(pattern in request_lower for pattern in param_patterns):
            request_type = "db_modification"
        
        # Check for visualization patterns
        elif any(pattern in request_lower for pattern in [
            "chart", "graph", "plot", "visualiz", "draw", "map", "diagram"
        ]):
            request_type = "visualization"
        
        # Check for SQL patterns
        elif any(pattern in request_lower for pattern in [
            "select", "query", "find", "search", "get", "retrieve", "list", "show", "count", "sum"
        ]):
            request_type = "sql_query"
        
        # For ambiguous cases, use LLM classification
        else:
            request_type = self._llm_classify_request(user_request)
        
        # Get database context for current scenario
        db_context = self._get_database_context()
        
        return {
            **state,
            "user_request": user_request,
            "request_type": request_type,
            "db_context": db_context,
            "messages": state["messages"] + [AIMessage(content=f"🎯 Request classified as: {request_type}")]
        }
    
    def _llm_classify_request(self, user_request: str) -> str:
        """Use LLM to classify ambiguous requests"""
        system_prompt = """Classify this user request into one of four categories:

1. **chat** - General questions, explanations, or conversations that don't require data analysis or code execution
   Examples: "What is this model about?", "How does optimization work?", "Explain the parameters"

2. **sql_query** - Requests for data retrieval, analysis, or querying 
   Examples: "Show me the top 10 hubs", "What is the total demand?", "List all routes"

3. **visualization** - Requests for charts, graphs, plots, or visual representations
   Examples: "Create a chart", "Visualize the data", "Show me a bar chart", "Plot the results"

4. **db_modification** - Requests to change database values or parameters
   Examples: "Change the maximum demand to 5000", "Update the cost parameter", "Set capacity to 1000"

Respond with exactly one word: chat, sql_query, visualization, or db_modification"""
        
        try:
            response = self._get_llm().invoke([HumanMessage(content=f"{system_prompt}\n\nUser request: {user_request}")])
            classification = response.content.strip().lower()
            if classification in ["chat", "sql_query", "visualization", "db_modification"]:
                return classification
        except Exception as e:
            print(f"LLM classification error: {e}")
        
        # Default fallback
        return "chat"
    
    def _route_request(self, state: AgentState) -> str:
        """Route request based on classification"""
        request_type = state.get("request_type", "chat")
        return request_type
    
    def _handle_chat(self, state: AgentState) -> AgentState:
        """Handle general chat/Q&A requests without code execution"""
        user_request = state["user_request"]
        db_context = state["db_context"]
        
        # Build context about the current scenario and database
        context_info = ""
        if db_context.is_valid():
            context_info = f"\nCurrent scenario database: {os.path.basename(db_context.database_path)}"
            if db_context.schema_info:
                table_names = list(db_context.schema_info.get("tables", {}).keys())
                context_info += f"\nAvailable tables: {', '.join(table_names[:5])}"
                if len(table_names) > 5:
                    context_info += f" and {len(table_names) - 5} more"
        
        system_prompt = f"""You are a helpful assistant for an Operations Research optimization project that is used to help visualize and analyze data. 
        
The user is working with optimization models that typically involve:
- constraints and parameters
- python code that defines the optimization model

{context_info}

Provide helpful, informative responses about the model, data, or optimization concepts. 
If the user needs data analysis or visualizations, suggest they rephrase their request to be more specific about what data they want to see or analyze."""

        try:
            response = self._get_llm().invoke([
                AIMessage(content=system_prompt),
                HumanMessage(content=user_request)
            ])
            
            chat_response = response.content
            
        except Exception as e:
            chat_response = f"I apologize, but I encountered an error processing your question: {str(e)}"
        
        return {
            **state,
            "messages": state["messages"] + [AIMessage(content=chat_response)]
        }
    
    def _handle_sql_query(self, state: AgentState) -> AgentState:
        """Generate Python code for SQL query execution with Plotly table output"""
        user_request = state["user_request"]
        db_context = state["db_context"]
        
        if not db_context.is_valid():
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No database available for the current scenario")]
            }
        
        # Build schema context
        schema_context = self._build_schema_context(db_context.schema_info)
        
        # Get database filename for relative path usage
        db_filename = os.path.basename(db_context.database_path)
        
        system_prompt = f"""Generate Python code to answer the user's SQL query request with an interactive Plotly table.

Database Schema:
{schema_context}

Requirements:
1. Connect to the database file: {db_filename} (the database file is in the current directory)
2. Generate appropriate SQL query based on user request
3. Create an interactive Plotly table to display results
4. Handle errors gracefully
5. Print query results summary

The code should:
- Import pandas and plotly.graph_objects
- Connect to the database file: {db_filename} (use just the filename, not full path)
- Execute the SQL query
- Create an interactive Plotly table with results
- Save as interactive HTML file in the current directory
- Include proper error handling with try/except blocks

CRITICAL REQUIREMENTS:
- Use the database filename: {db_filename} (not the full path)
- Save HTML file in the current directory
- Use plotly.graph_objects for interactive tables
- DO NOT use fig.show() - only save as HTML file
- DO NOT use encoding parameter in write_html() - Plotly handles encoding automatically
- Use dynamic file naming with timestamp
- Use fig.write_html(html_file_path) without any encoding parameter
- IMPORTANT: Convert all pandas Series/DataFrame data to Python lists using .tolist() before plotting
- Reset DataFrame indexes using df.reset_index(drop=True) before extracting data for plotting
- Ensure data arrays contain actual values, not DataFrame indexes

User request: {user_request}

Generate complete Python code:"""
        
        try:
            response = self._get_llm().invoke([HumanMessage(content=system_prompt)])
            llm_response = response.content.strip()
            
            # Extract code and explanation
            code_content, explanation = self._extract_code_and_explanation(llm_response)
            
            # Clean up code
            code_content = self._clean_generated_code(code_content)
            
            # Generate filename
            timestamp = int(time.time())
            random_id = random.randint(1000, 9999)
            filename = f"sql_query_{timestamp}_{random_id}.py"
            file_path = os.path.join(db_context.temp_dir, filename)
            
            # Write the file with UTF-8 encoding
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            # Create response message with explanation
            response_message = f"📊 Generated SQL query script: {filename}"
            if explanation:
                response_message += f"\n\n{explanation}"
            
            return {
                **state,
                "generated_files": [filename],
                "messages": state["messages"] + [AIMessage(content=response_message)]
            }
            
        except Exception as e:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"❌ Error generating SQL query: {str(e)}")]
            }
    
    def _handle_visualization(self, state: AgentState) -> AgentState:
        """Generate Python code for data visualization with Plotly"""
        user_request = state["user_request"]
        db_context = state["db_context"]
        
        if not db_context.is_valid():
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No database available for the current scenario")]
            }
        
        # Build schema context
        schema_context = self._build_schema_context(db_context.schema_info)
        
        # Get database filename for relative path usage
        db_filename = os.path.basename(db_context.database_path)
        
        system_prompt = f"""Generate Python code to create an interactive Plotly visualization based on the user's request.

Database Schema:
{schema_context}

Requirements:
1. Connect to database: {db_filename} (the database file is in the current directory)
2. Query appropriate data for the visualization
3. Create an interactive Plotly chart (bar, line, scatter, pie, etc.)
4. Choose the most appropriate chart type for the data
5. Include proper titles, labels, and formatting
6. Save as interactive HTML file in the current directory
7. Handle data type conversion properly

Key requirements:
- Use plotly.graph_objects for creating charts
- Use pandas for data manipulation (it's available)
- Create interactive charts with hover effects
- Include proper error handling with try/except blocks
- Make charts responsive and well-formatted

CRITICAL REQUIREMENTS:
- Use the database filename: {db_filename} (not the full path)
- Save HTML file in the current directory
- Use plotly.graph_objects for interactive visualizations
- DO NOT use fig.show() - only save as HTML file
- DO NOT use encoding parameter in write_html() - Plotly handles encoding automatically
- Use dynamic file naming with timestamp
- Use fig.write_html(html_file_path) without any encoding parameter
- IMPORTANT: Convert all pandas Series/DataFrame data to Python lists using .tolist() before plotting
- Reset DataFrame indexes using df.reset_index(drop=True) before extracting data for plotting
- Ensure data arrays contain actual values, not DataFrame indexes

User request: {user_request}

Generate complete Python code that creates an interactive Plotly visualization:"""
        
        try:
            response = self._get_llm().invoke([HumanMessage(content=system_prompt)])
            llm_response = response.content.strip()
            
            # Extract code and explanation
            code_content, explanation = self._extract_code_and_explanation(llm_response)
            
            # Clean up code
            code_content = self._clean_generated_code(code_content)
            
            # Generate filename
            timestamp = int(time.time())
            random_id = random.randint(1000, 9999)
            filename = f"visualization_{timestamp}_{random_id}.py"
            file_path = os.path.join(db_context.temp_dir, filename)
            
            # Write the file with UTF-8 encoding
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            # Create response message with explanation
            response_message = f"📈 Generated visualization script: {filename}"
            if explanation:
                response_message += f"\n\n{explanation}"
            
            return {
                **state,
                "generated_files": [filename],
                "messages": state["messages"] + [AIMessage(content=response_message)]
            }
            
        except Exception as e:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"❌ Error generating visualization: {str(e)}")]
            }
    
    # === PRESERVED DB MODIFICATION LOGIC FROM V1 ===
    # (Copy the working DB modification methods exactly as they are)
    
    def _prepare_db_modification(self, state: AgentState) -> AgentState:
        """Prepare database modification (enhanced with v1 validation logic)"""
        user_request = state["user_request"]
        db_context = state["db_context"]
        
        if not db_context.is_valid():
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No database available for modification")]
            }
        
        # Get schema context
        schema_context = self._build_schema_context(db_context.schema_info)
        
        try:
            # Enhanced extraction for both absolute values and percentage patterns
            import re
            
            # First, check for percentage patterns
            percentage_info = self._extract_percentage_patterns(user_request)
            
            # Extract numeric value from the request (for non-percentage cases)
            value_patterns = [
                r'to\s+(\d+(?:\.\d+)?)',  # matches "to 2000" or "to 2000.5"
                r'=\s*(\d+(?:\.\d+)?)',    # matches "= 2000" or "=2000.5"
                r'(\d+(?:\.\d+)?)\s*$'     # matches number at end of string
            ]
            
            extracted_value = None
            for pattern in value_patterns:
                matches = re.findall(pattern, user_request)
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
                matches = re.findall(pattern, user_request.lower())
                if matches:
                    extracted_table = matches[0]
                    break
            
            print(f"DEBUG: Extracted value: {extracted_value}")
            print(f"DEBUG: Extracted table: {extracted_table}")
            print(f"DEBUG: Percentage info: {percentage_info}")
            
            # Check if table exists in schema (v1 validation logic)
            table_exists = False
            if extracted_table:
                if db_context.schema_info and "tables" in db_context.schema_info:
                    schema_tables = db_context.schema_info.get("tables", {})
                    table_exists = extracted_table.lower() in [t.lower() for t in schema_tables.keys()]
                
                if not table_exists:
                    # Try fuzzy matching for similar table names (v1 logic)
                    available_tables = []
                    if db_context.schema_info and "tables" in db_context.schema_info:
                        available_tables = list(db_context.schema_info["tables"].keys())
                    
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
            
            # Use the enhanced LLM to analyze the request
            # Get current whitelist to include in prompt
            current_whitelist = set()
            try:
                from main import get_table_whitelist
                current_whitelist = get_table_whitelist()
            except Exception as e:
                print(f"DEBUG: Could not get whitelist for prompt: {e}")
            
            # Build whitelist information and table descriptions (v1 enhanced logic)
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
                if db_context.schema_info and "tables" in db_context.schema_info:
                    for table_name, table_info in db_context.schema_info["tables"].items():
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

            response = self._get_llm().invoke([HumanMessage(content=f"{system_prompt}\n\nModification Request: {user_request}")])
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
            
            # Check if the LLM response couldn't be parsed (empty modification_data)
            if not modification_data or len(modification_data) == 0:
                # Check if the LLM response contains helpful information about whitelisted tables
                if "whitelisted" in content.lower() and "table" in content.lower():
                    # Show the actual LLM response which contains helpful information
                    error_message = f"❌ **Invalid Request**: {content}"
                else:
                    error_message = "❌ **Invalid Request**: Could not determine what to modify from your request.\n\n"
                    error_message += "**Examples of valid requests:**\n"
                    error_message += "• 'Change the distance to Birmingham to 150'\n"
                    error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                    error_message += "• 'Increase demand for Birmingham by 20%'\n"
                    error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                    error_message += "**Your request was:** " + user_request
                
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=error_message)]
                }
            
            # Check if the LLM explicitly said it couldn't determine the values
            if any(phrase in content.lower() for phrase in [
                "does not specify", "not clear", "more details", "more specific", 
                "template for how", "assuming", "if more details", "please provide",
                "need more information", "not clear about", "assuming the intent",
                "cannot determine", "no action can be taken", "lack of specificity"
            ]):
                error_message = "❌ **Invalid Request**: The request is not specific enough to determine what to modify.\n\n"
                error_message += "**Examples of valid requests:**\n"
                error_message += "• 'Change the distance to Birmingham to 150'\n"
                error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                error_message += "• 'Increase demand for Birmingham by 20%'\n"
                error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                error_message += "**Your request was:** " + user_request
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=error_message)]
                }
            
            # Validate that we have proper values (not placeholders)
            target_table = modification_data.get('table', '')
            target_column = modification_data.get('column', '')
            new_value = modification_data.get('new_value', '')
            
            # Check for placeholder values that indicate the LLM couldn't determine the actual values
            placeholder_patterns = [
                '[column_name]', '[COLUMN_NAME]', 'column_name', 'COLUMN_NAME',
                '[exact_numeric_value_from_request OR "PERCENTAGE_CALCULATION"]',
                '[exact_numeric_value_from_request]', '[EXTRACT_FROM_REQUEST]',
                '<exact_numeric_value_from_request>', '[EXTRACT_FROM_REQUEST]',
                '[brief description of the change]', '[BRIEF_DESCRIPTION]',
                '[absolute/relative/none]', '[increase/decrease/set if applicable]',
                '[column name for relative calculations if applicable]',
                'N/A', 'n/a', 'None', 'none'
            ]
            
            # Check for invalid responses that indicate the request cannot be processed
            invalid_responses = [
                'None (requested table is not whitelisted)', 'None', 'none',
                'not available for modifications', 'not in the whitelist',
                'cannot be made', 'no changes can be made'
            ]
            
            # Also check for any value that contains square brackets (template responses)
            def contains_template_markers(value):
                if not value:
                    return True
                return '[' in value and ']' in value
            
            # Check if table is invalid (not whitelisted or not available)
            if target_table in invalid_responses or any(invalid in target_table for invalid in invalid_responses):
                error_message = "❌ **Invalid Request**: The requested table is not available for modifications.\n\n"
                error_message += "**Available tables for modification:**\n"
                if current_whitelist:
                    for table in current_whitelist:
                        error_message += f"• {table}\n"
                error_message += "\n**Examples of valid requests:**\n"
                error_message += "• 'Change the distance to Birmingham to 150'\n"
                error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                error_message += "• 'Increase demand for Birmingham by 20%'\n"
                error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                error_message += "**Your request was:** " + user_request
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=error_message)]
                }
            
            # Check if column is a placeholder or invalid
            if (target_column in placeholder_patterns or 
                target_column in invalid_responses or 
                contains_template_markers(target_column) or 
                not target_column):
                error_message = "❌ **Invalid Request**: Could not identify which column to modify. Please be more specific about what you want to change.\n\n"
                error_message += "**Examples of valid requests:**\n"
                error_message += "• 'Change the distance to Birmingham to 150'\n"
                error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                error_message += "• 'Increase demand for Birmingham by 20%'\n"
                error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                error_message += "**Your request was:** " + user_request
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=error_message)]
                }
            
            # Check if new value is a placeholder or invalid
            if (new_value in placeholder_patterns or 
                new_value in invalid_responses or 
                contains_template_markers(new_value) or 
                not new_value):
                error_message = "❌ **Invalid Request**: Could not identify what value to set. Please specify the exact numeric value.\n\n"
                error_message += "**Examples of valid requests:**\n"
                error_message += "• 'Change the distance to Birmingham to 150'\n"
                error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                error_message += "• 'Increase demand for Birmingham by 20%'\n"
                error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                error_message += "**Your request was:** " + user_request
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=error_message)]
                }
            
            # If we have the correct table but the LLM didn't extract the numeric value, try again
            if new_value in ['<exact_numeric_value_from_request>', '[EXTRACT_FROM_REQUEST]', None]:
                modification_data['new_value'] = extracted_value
            
            # Validate that we have a proper numeric value (if not a percentage calculation)
            final_new_value = modification_data.get('new_value', '')
            percentage_type = modification_data.get('percentage_type', '')
            
            # Check for invalid percentage calculation cases
            if (final_new_value == 'PERCENTAGE_CALCULATION' and 
                percentage_type in ['none', '']):
                error_message = "❌ **Invalid Request**: Could not identify what value to set. Please specify the exact numeric value.\n\n"
                error_message += "**Examples of valid requests:**\n"
                error_message += "• 'Change the distance to Birmingham to 150'\n"
                error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                error_message += "• 'Increase demand for Birmingham by 20%'\n"
                error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                error_message += "**Your request was:** " + user_request
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=error_message)]
                }
            
            # Check for valid numeric values (if not a percentage calculation)
            if (final_new_value and 
                final_new_value not in ['PERCENTAGE_CALCULATION', 'percentage_calculation'] and
                not modification_data.get('percentage_type') in ['absolute', 'relative']):
                try:
                    float(final_new_value)
                except (ValueError, TypeError):
                    error_message = "❌ **Invalid Request**: Could not identify a valid numeric value to set.\n\n"
                    error_message += "**Examples of valid requests:**\n"
                    error_message += "• 'Change the distance to Birmingham to 150'\n"
                    error_message += "• 'Set the cost for Birmingham routes to 500'\n"
                    error_message += "• 'Increase demand for Birmingham by 20%'\n"
                    error_message += "• 'Update capacity in Birmingham to 1000'\n\n"
                    error_message += f"**Your request was:** {user_request}\n"
                    error_message += f"**Extracted value:** {final_new_value}"
                    return {
                        **state,
                        "messages": state["messages"] + [AIMessage(content=error_message)]
                    }
            
            # Check if target table is whitelisted for modifications (v1 enhanced validation)
            if target_table:
                try:
                    # Import the whitelist from main module
                    from main import get_table_whitelist
                    current_whitelist = get_table_whitelist()
                    
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
                "messages": state["messages"] + [AIMessage(content=f"🔧 Identified modification: {modification_data.get('description', 'Update database parameter')}")]
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
    
    def _execute_db_modification(self, state: AgentState) -> AgentState:
        """Execute database modification (preserved from v1)"""
        modification_data = state.get("modification_request", {})
        db_context = state["db_context"]
        
        if not modification_data:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No modification data available")]
            }
        
        if not db_context.is_valid():
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No database available for modification")]
            }
        
        try:
            import sqlite3
            
            # Extract modification details
            table = modification_data.get('table', '').strip('`').strip()
            column = modification_data.get('column', '').strip('`').strip()
            new_value = modification_data.get('new_value', '').strip('`').strip()
            where_condition = modification_data.get('where_condition', '').strip('`').strip()
            
            # Connect to database
            conn = sqlite3.connect(db_context.database_path)
            cursor = conn.cursor()
            
            # Helper function to properly quote column/table names
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
                
                cursor.execute(check_sql)
                results = cursor.fetchall()
                old_values = [str(row[0]) for row in results]
            except Exception as e:
                old_values = [f"Could not retrieve: {e}"]
            
            # Handle percentage calculations if applicable
            percentage_type = modification_data.get('percentage_type', '').lower()
            percentage_value = modification_data.get('percentage_value')
            percentage_operation = modification_data.get('percentage_operation', '').lower()
            reference_column = modification_data.get('reference_column', '')
            reference_location = modification_data.get('reference_location', '')
            
            calculated_value = new_value
            if (percentage_type and percentage_type not in ['none', '', 'n/a'] and 
                percentage_value is not None):
                try:
                    percentage_value = float(percentage_value)
                    
                    if percentage_type == 'absolute' and old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                        current_value = float(old_values[0])
                        percentage_change = (percentage_value / 100.0) * current_value
                        
                        if percentage_operation == 'increase':
                            calculated_value = current_value + percentage_change
                        elif percentage_operation == 'decrease':
                            calculated_value = current_value - percentage_change
                        elif percentage_operation == 'set':
                            calculated_value = (percentage_value / 100.0) * current_value
                        
                        calculated_value = round(calculated_value, 2)
                    
                    elif percentage_type == 'relative' and reference_column:
                        # Handle relative percentage calculations
                        reference_value = None
                        
                        # Try to get reference value from the same table
                        try:
                            if reference_location:
                                # Location-based reference (e.g., "twice that of oxford")
                                ref_sql = f"SELECT {quoted_column} FROM {quoted_table} WHERE Location = ?"
                                cursor.execute(ref_sql, (reference_location,))
                                ref_result = cursor.fetchone()
                                if ref_result:
                                    reference_value = float(ref_result[0])
                            else:
                                # Column-based reference (e.g., "20% of maximum")
                                ref_sql = f"SELECT {quoted_column} FROM {quoted_table} WHERE {quoted_column} = (SELECT MAX({quoted_column}) FROM {quoted_table})"
                                cursor.execute(ref_sql)
                                ref_result = cursor.fetchone()
                                if ref_result:
                                    reference_value = float(ref_result[0])
                        except Exception as e:
                            print(f"DEBUG: Could not get reference value: {e}")
                        
                        if reference_value is not None:
                            percentage_amount = (percentage_value / 100.0) * reference_value
                            
                            if percentage_operation == 'set':
                                calculated_value = percentage_amount
                            elif percentage_operation == 'increase':
                                if old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                                    current_value = float(old_values[0])
                                    calculated_value = current_value + percentage_amount
                            elif percentage_operation == 'decrease':
                                if old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                                    current_value = float(old_values[0])
                                    calculated_value = current_value - percentage_amount
                            
                            calculated_value = round(calculated_value, 2)
                
                except (ValueError, TypeError) as e:
                    print(f"DEBUG: Error in percentage calculation: {e}")
            
            # Execute the modification
            if where_condition:
                if 'formatted_where' in locals():
                    update_sql = f"UPDATE {quoted_table} SET {quoted_column} = ? WHERE {formatted_where}"
                else:
                    where_parts = where_condition.split('=', 1)
                    if len(where_parts) == 2:
                        left_part = where_parts[0].strip()
                        right_part = where_parts[1].strip()
                        quoted_left = quote_identifier(left_part)
                        update_sql = f"UPDATE {quoted_table} SET {quoted_column} = ? WHERE {quoted_left} = {right_part}"
                    else:
                        update_sql = f"UPDATE {quoted_table} SET {quoted_column} = ? WHERE {where_condition}"
            else:
                update_sql = f"UPDATE {quoted_table} SET {quoted_column} = ?"
            
            cursor.execute(update_sql, (calculated_value,))
            conn.commit()
            conn.close()
            
            # Create detailed success message with comprehensive information
            change_summary = "🔧 **DATABASE MODIFICATION COMPLETED**\n\n"
            change_summary += f"📊 **Table:** `{table}`\n"
            change_summary += f"📝 **Column:** `{column}`\n"
            
            # Add percentage calculation details if applicable
            percentage_calculation_performed = False
            calculation_description = ""
            percentage_type = modification_data.get('percentage_type', '').lower()
            percentage_operation = modification_data.get('percentage_operation', '').lower()
            percentage_value = modification_data.get('percentage_value')
            reference_column = modification_data.get('reference_column', '')
            
            if (percentage_type and percentage_type not in ['none', '', 'n/a'] and 
                percentage_value is not None and str(percentage_value).lower() not in ['none', '', 'n/a']):
                percentage_calculation_performed = True
                change_summary += f"🧮 **Calculation Type:** Percentage-based modification\n"
                if percentage_type == 'absolute':
                    operation_desc = f"{percentage_operation.title()} by {percentage_value}%"
                elif percentage_type == 'relative':
                    operation_desc = f"{percentage_operation.title()} by {percentage_value}% of {reference_column}"
                change_summary += f"📈 **Operation:** {operation_desc}\n"
                
                # Create calculation description
                if percentage_type == 'absolute' and old_values and old_values[0] not in ["Could not retrieve:", "unknown"]:
                    try:
                        current_value = float(old_values[0])
                        percentage_change = (float(percentage_value) / 100.0) * current_value
                        if percentage_operation == 'increase':
                            calculation_description = f"Increased {current_value} by {percentage_value}% ({percentage_change:.2f})"
                        elif percentage_operation == 'decrease':
                            calculation_description = f"Decreased {current_value} by {percentage_value}% ({percentage_change:.2f})"
                        elif percentage_operation == 'set':
                            calculation_description = f"Set to {percentage_value}% of current value ({current_value})"
                    except (ValueError, TypeError):
                        calculation_description = f"Percentage calculation: {percentage_operation} by {percentage_value}%"
                else:
                    calculation_description = f"Percentage calculation: {percentage_operation} by {percentage_value}%"
                
                change_summary += f"💡 **Calculation:** {calculation_description}\n"
            
            change_summary += f"🔄 **Change:**\n"
            
            if len(old_values) == 1:
                change_summary += f"   - **Before:** {old_values[0]}\n"
                change_summary += f"   - **After:** {calculated_value}\n"
                
                # Add percentage change summary if it was a percentage calculation
                if percentage_calculation_performed and len(old_values) == 1:
                    try:
                        old_val = float(old_values[0])
                        new_val = float(calculated_value)
                        actual_change = new_val - old_val
                        actual_percentage = (actual_change / old_val) * 100 if old_val != 0 else 0
                        change_summary += f"   - **Net Change:** {actual_change:+.2f} ({actual_percentage:+.2f}%)\n"
                    except (ValueError, TypeError):
                        pass
            else:
                change_summary += f"   - **Rows affected:** {len(old_values)}\n"
                change_summary += f"   - **Old values:** {', '.join(old_values[:5])}{'...' if len(old_values) > 5 else ''}\n"
                change_summary += f"   - **New value:** {calculated_value}\n"
            
            change_summary += f"\n📈 **Rows affected:** {len(old_values)}\n"
            
            # Add WHERE condition if present
            if where_condition:
                change_summary += f"🔍 **Condition:** `{where_condition}`\n"
            
            # Add the actual SQL query that was executed
            if where_condition:
                if 'formatted_where' in locals():
                    executed_sql = f"UPDATE {quoted_table} SET {quoted_column} = {calculated_value} WHERE {formatted_where}"
                else:
                    where_parts = where_condition.split('=', 1)
                    if len(where_parts) == 2:
                        left_part = where_parts[0].strip()
                        right_part = where_parts[1].strip()
                        quoted_left = quote_identifier(left_part)
                        executed_sql = f"UPDATE {quoted_table} SET {quoted_column} = {calculated_value} WHERE {quoted_left} = {right_part}"
                    else:
                        executed_sql = f"UPDATE {quoted_table} SET {quoted_column} = {calculated_value} WHERE {where_condition}"
            else:
                executed_sql = f"UPDATE {quoted_table} SET {quoted_column} = {calculated_value}"
            
            change_summary += f"💾 **SQL executed:** `{executed_sql}`\n"
            
            # Add parameter validation results if available (placeholder for future enhancement)
            # if parameter_validation:
            #     if parameter_validation["success"]:
            #         change_summary += "✅ **Parameter validation:** Changes successfully applied and verified\n"
            #     else:
            #         change_summary += "⚠️ **Parameter validation:** Some issues detected with parameter changes\n"
            
            change_summary += "\n✅ **Database successfully updated.** Models will use the latest parameters when executed."
            
            # Print to console for debugging
            print(f"\n=== DATABASE CHANGE DETAILS ===")
            print(f"Table: {table}")
            print(f"Column: {column}")
            print(f"Old value(s): {old_values}")
            print(f"New value: {calculated_value}")
            if percentage_calculation_performed:
                print(f"Percentage calculation: {calculation_description}")
            print(f"Rows affected: {len(old_values)}")
            if where_condition:
                print(f"Condition: {where_condition}")
            print("================================\n")
            
            return {
                **state,
                "db_modification_result": {
                    "success": True,
                    "rows_affected": len(old_values),
                    "table": table,
                    "column": column,
                    "old_values": old_values,
                    "new_value": calculated_value,
                    "percentage_calculation_performed": percentage_calculation_performed,
                    "percentage_type": percentage_type if percentage_calculation_performed else None,
                    "percentage_operation": percentage_operation if percentage_calculation_performed else None,
                    "percentage_value": percentage_value if percentage_calculation_performed else None,
                    "calculation_description": calculation_description if percentage_calculation_performed else None
                },
                "messages": state["messages"] + [AIMessage(content=change_summary)]
            }
            
        except Exception as e:
            error_message = f"❌ **Database modification failed:** {str(e)}\n\n"
            error_message += "Please check that:\n"
            error_message += "• The table and column names are correct\n"
            error_message += "• The WHERE condition (if any) is valid\n"
            error_message += "• The new value is in the correct format\n"
            error_message += "• The database is accessible and not locked\n\n"
            error_message += f"**Technical details:** {str(e)}"
            
            print(f"DEBUG: Database modification error: {e}")
            return {
                **state,
                "db_modification_result": {
                    "success": False,
                    "error": str(e)
                },
                "messages": state["messages"] + [AIMessage(content=error_message)]
            }
    
    def _extract_percentage_patterns(self, message: str) -> dict:
        """Extract percentage patterns from user message with natural language support (v1 enhanced logic)"""
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
                percentage_info['reference_column'] = reference.strip()
                
                # Check if this is a location-based reference (e.g., "twice that of oxford")
                if 'that of' in message_lower:
                    percentage_info['reference_location'] = reference.strip()
                
                break
        
        return percentage_info
    
    def _execute_code(self, state: AgentState) -> AgentState:
        """Execute generated Python code"""
        generated_files = state.get("generated_files", [])
        db_context = state["db_context"]
        

        
        if not generated_files or not db_context.is_valid():
            return {
                **state,
                "execution_error": "No files to execute or invalid database context"
            }
        
        # Execute the most recent file
        filename = generated_files[-1]
        file_path = os.path.join(db_context.temp_dir, filename)
        
        if not os.path.exists(file_path):
            return {
                **state,
                "execution_error": f"Generated file not found: {filename}"
            }
        
        # Execute Python file
        try:
            import subprocess
            
            # Execute in the database directory so output files are created there
            db_dir = os.path.dirname(db_context.database_path)
            
            # Use the same Python executable as the current process
            python_executable = sys.executable
            
            # Record existing files BEFORE execution to avoid picking up old files
            existing_files = set()
            if os.path.exists(db_dir):
                for file in os.listdir(db_dir):
                    if file.endswith('.html'):
                        existing_files.add(file)
            
            result = subprocess.run(
                [python_executable, file_path],
                cwd=db_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace problematic characters
                timeout=120  # Increased timeout for slower imports
            )
            
            if result.returncode == 0:
                # Find ONLY newly generated output files (HTML files) in database directory
                output_files = []
                if os.path.exists(db_dir):
                    for file in os.listdir(db_dir):
                        if file.endswith('.html'):
                            # Only include files that didn't exist before execution
                            if file not in existing_files:
                                output_files.append(file)
                
                execution_output = result.stdout
                if output_files:
                    execution_output += f"\n\n📁 Generated files: {', '.join(output_files)}"
                
                # Only return files generated in this specific request
                # The state.get("generated_files", []) contains the Python file from this request
                # The output_files contains the HTML files generated by this request
                current_request_files = state.get("generated_files", []) + output_files
                
                return {
                    **state,
                    "execution_output": execution_output,
                    "execution_error": "",
                    "generated_files": current_request_files  # Only files from this request
                }
            else:
                return {
                    **state,
                    "execution_output": result.stdout,
                    "execution_error": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            return {
                **state,
                "execution_error": "Execution timed out (120 seconds). The script may be importing heavy libraries or taking too long to run."
            }
        except Exception as e:
            error_msg = f"Execution failed: {str(e)}"
            if "KeyboardInterrupt" in str(e):
                error_msg = "Execution was interrupted. This may be due to heavy imports or long-running operations."
            elif "ModuleNotFoundError" in str(e):
                error_msg = f"Missing module: {str(e)}. Please ensure all required packages are installed."
            return {
                **state,
                "execution_error": error_msg
            }
    
    def _respond(self, state: AgentState) -> AgentState:
        """Generate final response"""
        request_type = state.get("request_type", "")
        execution_output = state.get("execution_output", "")
        execution_error = state.get("execution_error", "")
        
        # Check if there's already a detailed response from database modification
        response_messages = [msg for msg in state["messages"] if isinstance(msg, AIMessage)]
        if response_messages:
            last_message = response_messages[-1].content
            # If the last message contains detailed database modification info, don't override it
            if ("DATABASE MODIFICATION COMPLETED" in last_message or 
                "Database modification completed" in last_message or
                "Table:" in last_message or
                "Column:" in last_message or
                "Before:" in last_message or
                "After:" in last_message):
                return state
        
        if request_type == "chat":
            # Chat responses are already handled
            return state
        
        elif execution_error:
            error_msg = f"❌ **Execution Error**\n\n{execution_error}"
            if "ModuleNotFoundError" in execution_error:
                error_msg += "\n\n💡 Try installing missing Python packages using the requirements.txt file."
            
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=error_msg)]
            }
        
        elif execution_output:
            success_msg = f"✅ **Execution Completed Successfully**\n\n{execution_output}"
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=success_msg)]
            }
        
        # If we reach here, it means no specific response was generated
        # This could happen if the request was invalid but no error was caught
        # In this case, don't add any message - let the existing error messages stand
        return state
    
    def _get_database_info(self, db_path: str) -> Dict[str, Any]:
        """Get database information (moved from main.py to avoid circular imports)"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get all tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = cursor.fetchall()
            
            db_info = {
                "tables": {},
                "total_tables": len(tables),
                "database_path": db_path
            }
            
            for (table_name,) in tables:
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                
                # Get row count
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cursor.fetchone()[0]
                
                # Get sample data
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                sample_data = cursor.fetchall()
                
                db_info["tables"][table_name] = {
                    "columns": [{"name": col[1], "type": col[2]} for col in columns],
                    "row_count": row_count,
                    "sample_data": sample_data
                }
            
            conn.close()
            return db_info
            
        except Exception as e:
            return {"error": str(e), "tables": {}, "total_tables": 0}

    def _build_schema_context(self, schema_info: Optional[Dict[str, Any]]) -> str:
        """Build schema context string for LLM"""
        if not schema_info or "tables" not in schema_info:
            return "No schema information available"
        
        context = "Available Tables:\n"
        for table_name, table_info in schema_info["tables"].items():
            context += f"\n{table_name}:\n"
            if "columns" in table_info:
                for col_info in table_info["columns"]:
                    col_name = col_info.get("name", "UNKNOWN")
                    col_type = col_info.get("type", "UNKNOWN")
                    context += f"  - {col_name} ({col_type})\n"
        
        return context
    
    def run(self, user_message: str, scenario_id: Optional[int] = None) -> Tuple[str, List[str], str, str]:
        """Run the agent with a user message"""
        try:
            # Initialize state
            initial_state = {
                "messages": [HumanMessage(content=user_message)],
                "user_request": user_message,
                "request_type": "",
                "db_context": self._get_database_context(scenario_id),
                "generated_files": [],
                "execution_output": "",
                "execution_error": "",
                "modification_request": None,
                "db_modification_result": None
            }
            
            # Run the workflow
            final_state = self.graph.invoke(initial_state)
            
            # Extract response
            response_messages = [msg for msg in final_state["messages"] if isinstance(msg, AIMessage)]
            if response_messages:
                response = response_messages[-1].content
            else:
                response = "No response generated"
            
            # Extract generated files and execution results
            generated_files = final_state.get("generated_files", [])
            execution_output = final_state.get("execution_output", "")
            execution_error = final_state.get("execution_error", "")
            

            
            return response, generated_files, execution_output, execution_error
            
        except Exception as e:
            error_response = f"❌ Agent error: {str(e)}"
            return error_response, [], "", str(e)

    def _extract_code_and_explanation(self, llm_response: str) -> tuple[str, str]:
        """Extract Python code and explanatory text from LLM response"""
        import re
        
        # Look for code blocks
        code_pattern = r'```(?:python)?\s*\n(.*?)\n```'
        code_matches = re.findall(code_pattern, llm_response, re.DOTALL)
        
        if code_matches:
            # Extract the code
            code_content = code_matches[0].strip()
            
            # Remove the code block from the response to get explanation
            explanation = re.sub(code_pattern, '', llm_response, flags=re.DOTALL).strip()
            
            # Clean up explanation (remove extra whitespace and empty lines)
            explanation = re.sub(r'\n\s*\n', '\n', explanation).strip()
            
            return code_content, explanation
        else:
            # No code blocks found, treat everything as explanation
            return "", llm_response.strip()

    def _clean_generated_code(self, code_content: str) -> str:
        """Clean up generated code to fix common issues"""
        import re
        
        # Fix markdown-style numbered lists to Python comments
        # Pattern: "1. Some text" -> "# 1. Some text"
        code_content = re.sub(r'^(\d+\.\s+)', r'# \1', code_content, flags=re.MULTILINE)
        
        # Fix markdown-style bullet points to Python comments
        # Pattern: "- Some text" -> "# - Some text"
        code_content = re.sub(r'^(-\s+)', r'# \1', code_content, flags=re.MULTILINE)
        
        # Fix markdown-style headers to Python comments
        # Pattern: "**Text**" -> "# Text"
        code_content = re.sub(r'\*\*(.*?)\*\*', r'# \1', code_content)
        
        # Fix any remaining markdown-style text that's not in strings
        # Pattern: "Text:" (at start of line) -> "# Text:"
        code_content = re.sub(r'^([A-Z][a-zA-Z\s]+:)\s*$', r'# \1', code_content, flags=re.MULTILINE)
        
        # Remove any remaining markdown artifacts
        code_content = re.sub(r'^\s*`.*?`\s*$', '', code_content, flags=re.MULTILINE)
        
        # Add UTF-8 encoding declaration at the top if not present
        if not code_content.startswith('# -*- coding: utf-8 -*-') and not code_content.startswith('# coding: utf-8'):
            code_content = '# -*- coding: utf-8 -*-\n' + code_content
        
        # Ensure proper file writing without encoding parameter
        # Replace any hardcoded file paths with dynamic ones
        code_content = re.sub(
            r'html_file_path\s*=\s*["\'][^"\']*["\']',
            'html_file_path = os.path.join(os.path.dirname(database_path), f"query_results_{timestamp}.html")',
            code_content
        )
        
        # Remove encoding parameter from write_html calls
        code_content = re.sub(
            r'fig\.write_html\([^)]*,\s*encoding\s*=\s*["\'][^"\']*["\'][^)]*\)',
            'fig.write_html(html_file_path)',
            code_content
        )
        
        # Ensure write_html calls don't have encoding parameter
        code_content = re.sub(
            r'fig\.write_html\(html_file_path,\s*encoding\s*=\s*["\'][^"\']*["\']\)',
            'fig.write_html(html_file_path)',
            code_content
        )
        
        # Add proper imports if missing
        if 'import os' not in code_content and 'from datetime import datetime' not in code_content:
            code_content = 'import os\nfrom datetime import datetime\n' + code_content
        
        return code_content

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


def create_agent_v2(ai_model: str = "openai", scenario_manager: ScenarioManager = None) -> SimplifiedAgent:
    """Create a new simplified agent instance"""
    return SimplifiedAgent(ai_model=ai_model, scenario_manager=scenario_manager) 