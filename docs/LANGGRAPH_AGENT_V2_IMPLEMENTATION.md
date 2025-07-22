# LangGraph Agent v2 Implementation Guide

## Overview

LangGraph Agent v2 is the core intelligent agent for EYProject, designed to handle natural language requests, scenario-aware database operations, code generation, visualization, file editing, and multi-scenario comparison. It is built on a modular, node-based workflow using the LangGraph library, with deep integration into the scenario management and database context system.

---

## Function and Method Reference

Below is a comprehensive list of all functions and methods in `langgraph_agent_v2.py`, grouped by class or section, with signatures and short descriptions:

### Module-Level Functions
- `set_langgraph_model(model_name: str) -> bool`: Set the current LLM model for the agent.
- `get_langgraph_model() -> str`: Get the current LLM model name.
- `get_available_models() -> Dict[str, str]`: Get all available LLM models.

### DatabaseContext (dataclass)
- `is_valid(self) -> bool`: Check if the database context is valid (single or multi-scenario).
- `get_primary_context(self) -> Optional['DatabaseContext']`: Get the primary context in comparison mode.
- `get_all_database_paths(self) -> List[str]`: Get all database paths (for comparison).
- `get_scenario_names(self) -> List[str]`: Get all scenario names (for comparison).

### AgentState (TypedDict)
- `is_valid(self) -> bool`: Check if the agent state is valid (all required fields present).

### SimplifiedAgent (main class)
- `__init__(self, ai_model: str = "openai", scenario_manager: ScenarioManager = None)`: Initialize the agent with model and scenario manager.
- `_get_llm(self)`: Get or create the LLM instance (lazy initialization).
- `_build_graph(self) -> StateGraph`: Build the workflow graph (nodes and edges).
- `_get_database_context(self, scenario_id: Optional[int] = None) -> DatabaseContext`: Get the database context for a scenario.
- `_resolve_scenario_names(self, scenario_names: List[str]) -> Dict[str, str]`: Fuzzy-match scenario names to database paths.
- `_create_comparison_database_context(self, scenario_names: List[str], primary_scenario: Optional[str] = None) -> DatabaseContext`: Build a multi-scenario comparison context.
- `_extract_comparison_scenarios(self, user_request: str) -> List[str]`: Extract scenario names from a comparison request.
- `_determine_comparison_type(self, user_request: str) -> str`: Determine comparison type (table, chart, analysis).
- `_classify_request(self, state: AgentState) -> AgentState`: Classify the user request and set request type.
- `_llm_classify_request(self, user_request: str) -> str`: Use LLM to classify ambiguous requests.
- `_route_request(self, state: AgentState) -> str`: Route request to the correct node based on type.
- `_handle_chat(self, state: AgentState) -> AgentState`: Handle general chat/Q&A requests.
- `_handle_sql_query(self, state: AgentState) -> AgentState`: Generate code for SQL queries and prepare for execution.
- `_handle_visualization(self, state: AgentState) -> AgentState`: Generate code for visualizations (single or multi-scenario).
- `_handle_single_visualization(self, state: AgentState) -> AgentState`: Generate code for single-scenario visualization.
- `_handle_comparison_visualization(self, state: AgentState) -> AgentState`: Generate code for multi-scenario comparison visualization.
- `_determine_comparison_chart_type(self, user_request: str) -> str`: Determine the best chart type for comparison.
- `_handle_scenario_comparison(self, state: AgentState) -> AgentState`: Handle multi-scenario comparison analysis/visualization.
- `_prepare_db_modification(self, state: AgentState) -> AgentState`: Analyze and validate DB modification requests.
- `_execute_db_modification(self, state: AgentState) -> AgentState`: Execute validated DB modifications.
- `_extract_percentage_patterns(self, message: str) -> dict`: Extract percentage-based modification patterns from text.
- `_execute_code(self, state: AgentState) -> AgentState`: Execute generated Python scripts and capture outputs/errors.
- `_respond(self, state: AgentState) -> AgentState`: Format and return the final response.
- `_get_database_info(self, db_path: str) -> Dict[str, Any]`: Get schema and table info for a database.
- `_build_schema_context(self, schema_info: Optional[Dict[str, Any]]) -> str`: Build a schema context string for prompts.
- `run(self, user_message: str, scenario_id: Optional[int] = None, edit_mode: bool = False, editing_file_path: Optional[str] = None) -> Tuple[str, List[str], str, str]`: Main entry point for running the agent.
- `_extract_code_and_explanation(self, llm_response: str) -> tuple[str, str]`: Split LLM response into code and explanation.
- `_clean_generated_code(self, code_content: str) -> str`: Clean up generated code for execution.
- `_validate_sql_against_schema(self, sql_query: str, schema_context: str) -> Dict[str, any]`: Validate SQL against schema.
- `_parse_schema_context(self, schema_context: str) -> Dict[str, any]`: Parse schema context string.
- `_parse_sql_query(self, sql_query: str) -> Dict[str, any]`: Parse SQL query string.
- `_execute_multi_database_query(self, sql_query_template: str, db_contexts: Dict[str, DatabaseContext], params: Optional[Dict[str, Any]] = None) -> 'pd.DataFrame'`: Execute a query across multiple databases.
- `_aggregate_scenario_data(self, db_contexts: Dict[str, DatabaseContext], table_name: str, required_columns: Optional[List[str]] = None, optional_columns: Optional[List[str]] = None) -> 'pd.DataFrame'`: Aggregate data for comparison.
- `_generate_comparison_table(self, db_contexts: Dict[str, DatabaseContext], table_name: str, key_column: str, value_columns: List[str], highlight_thresholds: Optional[Dict[str, float]] = None) -> str`: Generate a comparison table for scenarios.
- `_generate_comparison_file_path(self, scenario_names: List[str], file_type: str, extension: str = "html", base_directory: Optional[str] = None) -> str`: Generate a file path for comparison outputs.
- `_ensure_directory_exists(self, directory_path: str) -> str`: Ensure a directory exists.
- `_track_comparison_output(self, scenario_names: List[str], comparison_type: str, output_file_path: str, description: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> bool`: Track generated comparison outputs.
- `_extract_scenarios(self, state: AgentState) -> AgentState`: Node for extracting scenarios from a request.
- `_fallback_scenario_extraction(self, llm_response: str, available_scenarios: List[str]) -> List[str]`: Fallback for scenario extraction.
- `_find_best_scenario_match(self, extracted_name: str, available_scenarios: List[str]) -> Optional[str]`: Fuzzy-match scenario names.
- `_load_file_for_editing(self, file_path: str, db_context: Optional[DatabaseContext] = None) -> str`: Load file content for editing.
- `_save_file_modification(self, file_path: str, new_content: str, modification_query: str, query_id: str, db_context: Optional[DatabaseContext] = None) -> bool`: Save a file modification.
- `_get_file_modification_context(self, file_path: str, db_context: Optional[DatabaseContext] = None) -> Dict[str, Any]`: Build context for file modification.
- `_validate_file_modification(self, original_content: str, new_content: str, file_path: str) -> Dict[str, Any]`: Validate a file modification.
- `_track_file_modification(self, file_path: str, query_id: str, modification_query: str, new_content_hash: str, db_context: Optional[DatabaseContext] = None)`: Track file modification history.
- `_get_file_modification_history(self, file_path: str) -> List[Dict[str, Any]]`: Get file modification history.
- `_hash_content(self, content: str) -> str`: Hash file content for tracking.
- `_store_query_file_mapping(self, query_id: str, file_path: str, original_query: str, scenario_id: Optional[int] = None)`: Map queries to files.
- `_get_files_for_query(self, query_id: str) -> List[str]`: Get files for a query.
- `_get_query_for_file(self, file_path: str) -> Optional[str]`: Get query for a file.
- `_handle_file_edit(self, state: AgentState) -> AgentState`: Node for file editing requests.
- `_extract_file_path_from_request(self, user_request: str) -> Optional[str]`: Extract file path from a request.
- `_build_modification_prompt(self, user_request: str, original_content: str, modification_context: Dict[str, Any]) -> str`: Build prompt for file modification.
- `_extract_modified_content(self, llm_response: str, original_content: str) -> str`: Extract modified content from LLM response.
- `_format_modification_history(self, history: List[Dict[str, Any]]) -> str`: Format file modification history.
- `_generate_query_id(self, query: str) -> str`: Generate a unique query ID.
- `_resolve_file_path(self, file_path: str, db_context: Optional[DatabaseContext] = None) -> str`: Resolve file path for editing.

### Module Utility Functions
- `contains_template_markers(value)`: Check if a value contains template markers (for validation).
- `quote_identifier(name)`: Properly quote SQL identifiers.
- `convert_natural_to_percentage(text)`: Convert natural language fractions to percentages.
- `sanitize_filename(name: str) -> str`: Sanitize a filename for output.
- `create_agent_v2(ai_model: str = "openai", scenario_manager: ScenarioManager = None) -> SimplifiedAgent`: Factory function to create a new agent instance.

---

## High-Level Architecture

- **Workflow Engine:** Uses a directed graph (StateGraph) where each node is a handler for a specific type of request or operation.
- **Scenario Awareness:** All operations are routed through a scenario-aware `DatabaseContext`, ensuring correct data isolation and reproducibility.
- **Request Classification:** User requests are classified into types (chat, sql_query, visualization, db_modification, scenario_comparison, file_edit) and routed accordingly.
- **Extensible Nodes:** Each node in the workflow graph is a Python method that can be extended or replaced for new capabilities.
- **LLM Integration:** Uses OpenAI (or other LLMs) for request classification, code generation, and natural language understanding.

---

## Workflow Graph Nodes

### 1. `classify_request`
- **Purpose:** Classifies the user request into one of the main types using keyword rules and LLM fallback.
- **Routes to:** `handle_chat`, `handle_sql_query`, `handle_visualization`, `extract_scenarios`, `handle_file_edit`, or `prepare_db_modification`.

### 2. `extract_scenarios`
- **Purpose:** Extracts scenario names from comparison requests using regex and fuzzy matching.
- **Routes to:** `handle_scenario_comparison`.

### 3. `handle_chat`
- **Purpose:** Handles general Q&A and non-code requests using the LLM.
- **Routes to:** `respond`.

### 4. `handle_sql_query`
- **Purpose:** Generates Python code for SQL queries, writes scripts, and prepares for execution.
- **Routes to:** `execute_code`.

### 5. `handle_visualization`
- **Purpose:** Generates Python code for data visualizations (single or multi-scenario), writes scripts, and prepares for execution.
- **Routes to:** `execute_code`.

### 6. `handle_scenario_comparison`
- **Purpose:** Handles multi-scenario comparison analysis and visualization, including code generation and aggregation.
- **Routes to:** `execute_code`.

### 7. `handle_file_edit`
- **Purpose:** Handles file editing requests, including context extraction, validation, and code generation for modifications.
- **Routes to:** `execute_code`.

### 8. `prepare_db_modification`
- **Purpose:** Analyzes and validates database modification requests, extracts target table/column/value, and prepares for execution.
- **Routes to:** `execute_db_modification`.

### 9. `execute_db_modification`
- **Purpose:** Executes validated database modifications (UPDATEs, percentage changes, etc.) and logs changes.
- **Routes to:** `respond`.

### 10. `execute_code`
- **Purpose:** Executes generated Python scripts (SQL, visualization, file edit) and captures outputs/errors.
- **Routes to:** `respond`.

### 11. `respond`
- **Purpose:** Formats and returns the final response, including outputs, errors, and generated files.
- **Routes to:** END.

---

## Request Classification and Routing
- **Keyword and Pattern Matching:** Uses keyword lists and regex to classify requests (e.g., "compare", "chart", "change").
- **LLM Fallback:** For ambiguous cases, uses the LLM to classify the request into one of the main types.
- **Routing:** The result determines which node the workflow graph transitions to next.

---

## Scenario and Database Context Management
- **DatabaseContext:** A dataclass that holds scenario ID, database path, schema info, temp directory, and (for comparisons) a mapping of multiple scenario contexts.
- **ScenarioManager:** Provides access to all scenarios, their databases, and metadata.
- **Context Validation:** Each operation checks that the database context is valid and points to an existing, correct database.
- **Multi-Scenario Support:** For comparisons, a `DatabaseContext` holds multiple scenario contexts and can aggregate data across them.

---

## Node and Function Details

### `handle_chat`
- Uses the LLM to answer general questions, explain concepts, or provide guidance.
- Includes scenario/database context in the system prompt for relevance.

### `handle_sql_query`
- Generates Python code to execute SQL queries and create Plotly tables.
- Writes scripts to the scenario's temp directory.
- Ensures all data is converted to lists and indexes are reset for Plotly compatibility.

### `handle_visualization` and `handle_comparison_visualization`
- Generates Python code for single or multi-scenario visualizations (bar, line, scatter, heatmap, etc.).
- Handles color coding, legends, and interactive features for comparisons.
- Writes scripts to the appropriate temp directory.

### `handle_scenario_comparison`
- Extracts scenario names, builds comparison database context, and generates code for analysis or visualization.
- Aggregates data using helper methods (`_aggregate_scenario_data`, `_generate_comparison_table`).

### `handle_file_edit`
- Loads file content, builds modification context, and uses the LLM to generate code for file edits.
- Validates modifications, tracks history, and ensures changes are scenario-aware.

### `prepare_db_modification` and `execute_db_modification`
- Analyzes modification requests, extracts target table/column/value, and validates against the whitelist.
- Supports absolute/relative/percentage changes and natural language fractions.
- Executes safe SQL UPDATEs and logs changes.

### `execute_code`
- Runs generated Python scripts in the correct temp directory.
- Captures stdout, errors, and output files.
- Handles encoding, file paths, and output formatting.

### `respond`
- Formats the final response, including outputs, errors, and links to generated files.
- Handles error reporting and user feedback.

---

## Tool Calls and Integration
- **LLM Calls:** Used for request classification, code generation, and natural language understanding.
- **SQL Execution:** Scripts are generated and executed in the scenario's temp directory, always using the correct database path.
- **File Operations:** All file reads/writes are scenario-aware and use absolute paths.
- **Plotly Integration:** All visualizations are generated as interactive HTML files, with best practices for data conversion and layout.

---

## Multi-Scenario Comparison and Aggregation
- **Comparison Context:** Uses a multi-database `DatabaseContext` to aggregate data across scenarios.
- **Aggregation Helpers:** Methods like `_aggregate_scenario_data` and `_generate_comparison_table` combine data for comparison charts/tables.
- **Chart Types:** Supports grouped bars, faceted plots, line charts, scatter plots, heatmaps, and more.
- **Scenario Mapping:** Maintains mapping of scenario names to database paths and IDs for accurate aggregation.

---

## Error Handling, Validation, and Response Generation
- **Validation:** Every node checks for valid context, correct table/column names, and safe operations.
- **Error Reporting:** All errors are caught and returned as user-friendly messages.
- **Response Formatting:** The `respond` node assembles outputs, errors, and file links for the frontend.

---

## Extensibility and Advanced Features
- **Add New Nodes:** New request types or operations can be added as new nodes in the workflow graph.
- **Custom Tool Calls:** Integrate additional LLMs, APIs, or data sources by extending node handlers.
- **Scenario Comparison:** Easily extendable for more complex multi-scenario analytics.
- **File Editing:** Built-in support for scenario-aware file editing and modification tracking.
- **Percentage and Natural Language Modifications:** Advanced parsing for natural language parameter changes.

---