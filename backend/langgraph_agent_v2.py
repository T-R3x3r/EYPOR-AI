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
from typing import Dict, List, Any, Optional, Tuple, Literal, TYPE_CHECKING
from datetime import datetime
from dataclasses import dataclass

from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from typing_extensions import Annotated, TypedDict

# Import scenario management
from scenario_manager import ScenarioManager

# Type hints for pandas (avoid circular imports)
if TYPE_CHECKING:
    import pandas as pd


@dataclass
class DatabaseContext:
    """Contains all database-related context for the current scenario"""
    scenario_id: Optional[int]
    database_path: Optional[str]
    schema_info: Optional[Dict[str, Any]]
    temp_dir: Optional[str]
    
    # Multi-scenario comparison fields
    multi_database_contexts: Optional[Dict[str, 'DatabaseContext']] = None
    comparison_mode: bool = False
    primary_scenario: Optional[str] = None
    
    def is_valid(self) -> bool:
        """Check if database context is valid and usable"""
        if self.comparison_mode:
            # In comparison mode, check all databases in multi_database_contexts
            if not self.multi_database_contexts:
                return False
            
            # Check that all database contexts are valid
            for scenario_name, db_context in self.multi_database_contexts.items():
                if not db_context.is_valid():
                    print(f"Warning: Database context for scenario '{scenario_name}' is not valid")
                    return False
            
            # Check that primary scenario is specified and exists
            if not self.primary_scenario or self.primary_scenario not in self.multi_database_contexts:
                print(f"Warning: Primary scenario '{self.primary_scenario}' not found in comparison contexts")
                return False
            
            return True
        else:
            # Single scenario mode - use original validation logic
            return (
                self.database_path is not None and 
                os.path.exists(self.database_path) and
                self.temp_dir is not None
            )
    
    def get_primary_context(self) -> Optional['DatabaseContext']:
        """Get the primary database context for comparison operations"""
        if self.comparison_mode and self.primary_scenario and self.multi_database_contexts:
            return self.multi_database_contexts.get(self.primary_scenario)
        return None
    
    def get_all_database_paths(self) -> List[str]:
        """Get all database paths in comparison mode"""
        if self.comparison_mode and self.multi_database_contexts:
            return [ctx.database_path for ctx in self.multi_database_contexts.values() if ctx.database_path]
        elif self.database_path:
            return [self.database_path]
        return []
    
    def get_scenario_names(self) -> List[str]:
        """Get all scenario names in comparison mode"""
        if self.comparison_mode and self.multi_database_contexts:
            return list(self.multi_database_contexts.keys())
        return []


class AgentState(TypedDict):
    """Simplified state for the agent workflow"""
    messages: Annotated[List[BaseMessage], add_messages]
    user_request: str
    request_type: str  # 'chat', 'sql_query', 'visualization', 'db_modification', 'scenario_comparison'
    db_context: DatabaseContext
    
    # Execution results
    generated_files: List[str]
    execution_output: str
    execution_error: str
    
    # DB modification specific (preserved from v1)
    modification_request: Optional[Dict[str, Any]]
    db_modification_result: Optional[Dict[str, Any]]
    
    # Multi-scenario comparison specific
    comparison_scenarios: List[str]  # list of scenario names to compare
    comparison_data: Dict[str, Any]  # aggregated data from multiple scenarios
    comparison_type: str  # type of comparison ('table', 'chart', 'analysis')
    scenario_name_mapping: Dict[str, int]  # map scenario names to IDs


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
            # Load environment variables from EY.env file
            import os
            from dotenv import load_dotenv
            
            # Try to load from EY.env file
            ey_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "EY.env")
            if os.path.exists(ey_env_path):
                load_dotenv(ey_env_path)
                print(f"DEBUG: Loaded environment from {ey_env_path}")
            else:
                print(f"DEBUG: EY.env file not found at {ey_env_path}")
            
            if self.ai_model == "openai":
                from langchain_openai import ChatOpenAI
                # Check if API key is available
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY not found in environment variables. Please check your EY.env file.")
                
                print(f"DEBUG: Using OpenAI API key: {api_key[:10]}...")
                self.llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
            else:
                raise ValueError(f"Unsupported AI model: {self.ai_model}")
        return self.llm
    
    def _build_graph(self) -> StateGraph:
        """Build simplified workflow graph"""
        workflow = StateGraph(AgentState)
        
        # Core nodes
        workflow.add_node("classify_request", self._classify_request)
        workflow.add_node("extract_scenarios", self._extract_scenarios)  # New node for scenario extraction
        workflow.add_node("handle_chat", self._handle_chat)
        workflow.add_node("handle_sql_query", self._handle_sql_query)
        workflow.add_node("handle_visualization", self._handle_visualization)
        workflow.add_node("handle_scenario_comparison", self._handle_scenario_comparison)
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
                "scenario_comparison": "extract_scenarios",  # Route to scenario extraction first
                "db_modification": "prepare_db_modification"
            }
        )
        
        # Chat goes directly to response
        workflow.add_edge("handle_chat", "respond")
        
        # SQL and visualization go to code execution
        workflow.add_edge("handle_sql_query", "execute_code")
        workflow.add_edge("handle_visualization", "execute_code")
        workflow.add_edge("execute_code", "respond")
        
        # Scenario comparison workflow: extract scenarios -> handle comparison -> execute code
        workflow.add_edge("extract_scenarios", "handle_scenario_comparison")
        workflow.add_edge("handle_scenario_comparison", "execute_code")
        
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
    
    def _resolve_scenario_names(self, scenario_names: List[str]) -> Dict[str, str]:
        """
        Resolve scenario names to their database paths with fuzzy matching.
        
        Args:
            scenario_names: List of scenario names (strings) from user input
            
        Returns:
            Dict mapping scenario names to their database paths
            
        Raises:
            ValueError: If scenarios cannot be found or resolved
        """
        if not self.scenario_manager:
            raise ValueError("No scenario manager available")
        
        # Get all available scenarios
        all_scenarios = self.scenario_manager.list_scenarios()
        if not all_scenarios:
            raise ValueError("No scenarios available in the system")
        
        # Create a mapping of normalized names to scenario objects
        name_to_scenario = {}
        for scenario in all_scenarios:
            # Store both exact and normalized versions
            name_to_scenario[scenario.name] = scenario
            name_to_scenario[scenario.name.lower()] = scenario
            name_to_scenario[scenario.name.strip()] = scenario
            
            # Also store partial matches (for fuzzy matching)
            words = scenario.name.lower().split()
            for word in words:
                if len(word) > 2:  # Only consider words longer than 2 characters
                    name_to_scenario[word] = scenario
        
        # Resolve each requested scenario name
        resolved_scenarios = {}
        missing_scenarios = []
        
        for requested_name in scenario_names:
            requested_name = requested_name.strip()
            resolved = False
            
            # Try exact match first
            if requested_name in name_to_scenario:
                scenario = name_to_scenario[requested_name]
                resolved_scenarios[requested_name] = scenario.database_path
                resolved = True
                continue
            
            # Try case-insensitive match
            if requested_name.lower() in name_to_scenario:
                scenario = name_to_scenario[requested_name.lower()]
                resolved_scenarios[requested_name] = scenario.database_path
                resolved = True
                continue
            
            # Try partial matching (substring search)
            for scenario in all_scenarios:
                if requested_name.lower() in scenario.name.lower():
                    resolved_scenarios[requested_name] = scenario.database_path
                    resolved = True
                    break
            
            # Try word-based matching
            if not resolved:
                requested_words = requested_name.lower().split()
                for scenario in all_scenarios:
                    scenario_words = scenario.name.lower().split()
                    # Check if any requested word matches any scenario word
                    if any(req_word in scenario_words for req_word in requested_words):
                        resolved_scenarios[requested_name] = scenario.database_path
                        resolved = True
                        break
            
            if not resolved:
                missing_scenarios.append(requested_name)
        
        # If any scenarios couldn't be resolved, provide detailed error message
        if missing_scenarios:
            available_names = [s.name for s in all_scenarios]
            error_msg = f"Could not find the following scenarios: {', '.join(missing_scenarios)}\n"
            error_msg += f"Available scenarios: {', '.join(available_names)}"
            raise ValueError(error_msg)
        
        return resolved_scenarios
    
    def _create_comparison_database_context(self, scenario_names: List[str], primary_scenario: Optional[str] = None) -> DatabaseContext:
        """
        Create a multi-database context for comparison operations.
        
        Args:
            scenario_names: List of scenario names to compare
            primary_scenario: Name of the primary scenario (defaults to first scenario)
            
        Returns:
            DatabaseContext configured for comparison mode
        """
        print(f"🔍 DEBUG: _create_comparison_database_context called with scenarios: {scenario_names}")
        
        if not self.scenario_manager:
            print(f"🔍 DEBUG: No scenario manager available, returning empty context")
            return DatabaseContext(None, None, None, None, comparison_mode=True)
        
        # Resolve scenario names to database paths
        try:
            print(f"🔍 DEBUG: Resolving scenario names to database paths...")
            scenario_paths = self._resolve_scenario_names(scenario_names)
            print(f"🔍 DEBUG: Resolved scenario paths: {scenario_paths}")
        except ValueError as e:
            print(f"🔍 DEBUG: Error resolving scenario names: {e}")
            return DatabaseContext(None, None, None, None, comparison_mode=True)
        
        # Create individual database contexts for each scenario
        multi_contexts = {}
        print(f"🔍 DEBUG: Creating individual database contexts...")
        for scenario_name, database_path in scenario_paths.items():
            print(f"🔍 DEBUG: Processing scenario '{scenario_name}' with path '{database_path}'")
            
            # Get scenario ID
            scenario = None
            all_scenarios = self.scenario_manager.list_scenarios()
            for s in all_scenarios:
                if s.database_path == database_path:
                    scenario = s
                    break
            
            if not scenario:
                print(f"🔍 DEBUG: Could not find scenario object for '{scenario_name}'")
                continue
            
            print(f"🔍 DEBUG: Found scenario object with ID: {scenario.id}")
            
            # Get schema info
            schema_info = None
            if database_path and os.path.exists(database_path):
                try:
                    schema_info = self._get_database_info(database_path)
                    print(f"🔍 DEBUG: Got schema info for '{scenario_name}': {len(schema_info.get('tables', {}))} tables")
                except Exception as e:
                    print(f"🔍 DEBUG: Error getting schema info for {scenario_name}: {e}")
            else:
                print(f"🔍 DEBUG: Database path does not exist: {database_path}")
            
            # Create temp directory
            temp_dir = os.path.dirname(database_path)
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)
                print(f"🔍 DEBUG: Created temp directory: {temp_dir}")
            
            # Create individual context
            individual_context = DatabaseContext(
                scenario_id=scenario.id,
                database_path=database_path,
                schema_info=schema_info,
                temp_dir=temp_dir,
                comparison_mode=False  # Individual contexts are not in comparison mode
            )
            
            print(f"🔍 DEBUG: Created individual context for '{scenario_name}' - valid: {individual_context.is_valid()}")
            multi_contexts[scenario_name] = individual_context
        
        print(f"🔍 DEBUG: Created {len(multi_contexts)} individual contexts")
        
        # Set primary scenario (default to first if not specified)
        if not primary_scenario and multi_contexts:
            primary_scenario = list(multi_contexts.keys())[0]
            print(f"🔍 DEBUG: Set primary scenario to: {primary_scenario}")
        
        # Create comparison context
        comparison_context = DatabaseContext(
            scenario_id=None,  # No single scenario ID in comparison mode
            database_path=None,  # No single database path in comparison mode
            schema_info=None,  # Schema info varies by scenario
            temp_dir=None,  # Temp dir will be set to primary scenario's dir
            multi_database_contexts=multi_contexts,
            comparison_mode=True,
            primary_scenario=primary_scenario
        )
        
        # Set temp directory to primary scenario's directory
        if primary_scenario and primary_scenario in multi_contexts:
            comparison_context.temp_dir = multi_contexts[primary_scenario].temp_dir
            print(f"🔍 DEBUG: Set temp directory to primary scenario: {comparison_context.temp_dir}")
        
        print(f"🔍 DEBUG: Created comparison context - valid: {comparison_context.is_valid()}, comparison_mode: {comparison_context.comparison_mode}")
        return comparison_context
    
    def _extract_comparison_scenarios(self, user_request: str) -> List[str]:
        """
        Extract scenario names from comparison requests using regex patterns.
        
        Args:
            user_request: The user's request text
            
        Returns:
            List of scenario names found in the request, or empty list if no comparison detected
        """
        import re
        
        print(f"🔍 DEBUG: _extract_comparison_scenarios called with: '{user_request}'")
        
        # Comparison keywords that indicate a comparison request
        comparison_keywords = [
            "compare", "comparison", "versus", "vs", "between", "across", 
            "difference", "differences", "compare", "comparing"
        ]
        
        # Check if request contains comparison keywords
        request_lower = user_request.lower()
        has_comparison_keyword = any(keyword in request_lower for keyword in comparison_keywords)
        print(f"🔍 DEBUG: Has comparison keyword: {has_comparison_keyword}")
        print(f"🔍 DEBUG: Found keywords: {[kw for kw in comparison_keywords if kw in request_lower]}")
        
        if not has_comparison_keyword:
            print(f"🔍 DEBUG: No comparison keywords found, returning empty list")
            return []
        
        # Get all available scenario names for matching
        if not self.scenario_manager:
            print(f"🔍 DEBUG: No scenario manager available")
            return []
        
        all_scenarios = self.scenario_manager.list_scenarios()
        scenario_names = [s.name for s in all_scenarios]
        print(f"🔍 DEBUG: Available scenarios: {scenario_names}")
        
        # Try different regex patterns to extract scenario names
        
        # Pattern 1: "scenario A vs scenario B" or "compare A and B"
        patterns = [
            # "compare Base and Test" - simple pattern
            r'compare\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:and|&)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',
            # "compare Base Scenario and Test Scenario" - with "Scenario" keyword
            r'compare\s+([A-Za-z]+\s+Scenario)\s+(?:and|&)\s+([A-Za-z]+\s+Scenario)',
            # "Base vs Test" - simple vs pattern
            r'([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+(?:vs|versus)\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',
            # "compare Base, Test" - comma separated
            r'compare\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*,\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)',
            # "between Base and Test"
            r'between\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s+and\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)',
            # "across Base, Test"
            r'across\s+([A-Za-z]+(?:\s+[A-Za-z]+)*)\s*,\s*([A-Za-z]+(?:\s+[A-Za-z]+)*)',
        ]
        
        print(f"🔍 DEBUG: Testing regex patterns...")
        for i, pattern in enumerate(patterns):
            matches = re.findall(pattern, user_request, re.IGNORECASE)
            print(f"🔍 DEBUG: Pattern {i+1}: '{pattern}' -> matches: {matches}")
            if matches:
                # Flatten the matches and clean up
                found_scenarios = []
                for match in matches:
                    if isinstance(match, tuple):
                        found_scenarios.extend(match)
                    else:
                        found_scenarios.append(match)
                
                print(f"🔍 DEBUG: Found scenarios from pattern: {found_scenarios}")
                
                # Clean up scenario names and validate against available scenarios
                valid_scenarios = []
                for scenario_name in found_scenarios:
                    scenario_name_clean = scenario_name.strip().lower()
                    best_match = None
                    best_score = 0
                    for available_name in scenario_names:
                        available_name_lower = available_name.lower()
                        # Exact match
                        if scenario_name_clean == available_name_lower:
                            best_match = available_name
                            best_score = 100
                            break
                        # Substring match
                        if scenario_name_clean in available_name_lower or available_name_lower in scenario_name_clean:
                            if best_score < 80:
                                best_match = available_name
                                best_score = 80
                        # Fuzzy match (sequence matcher)
                        import difflib
                        ratio = difflib.SequenceMatcher(None, scenario_name_clean, available_name_lower).ratio()
                        if ratio > best_score/100 and ratio >= 0.5:
                            best_match = available_name
                            best_score = int(ratio*100)
                    if best_match and best_match not in valid_scenarios:
                        print(f"🔍 DEBUG: Fuzzy matched '{scenario_name}' to '{best_match}' (score={best_score})")
                        valid_scenarios.append(best_match)
                print(f"🔍 DEBUG: Valid scenarios found: {valid_scenarios}")
                if len(valid_scenarios) >= 2:
                    print(f"🔍 DEBUG: Returning valid scenarios: {valid_scenarios}")
                    return valid_scenarios
        
        # If no patterns matched, try to find scenario names in the text
        # Look for scenario names that appear in the request
        print(f"🔍 DEBUG: No regex patterns matched, looking for scenario names in text...")
        found_scenarios = []
        for scenario_name in scenario_names:
            if scenario_name.lower() in request_lower:
                print(f"🔍 DEBUG: Found scenario name '{scenario_name}' in request")
                found_scenarios.append(scenario_name)
        
        # If we found multiple scenarios and there are comparison keywords, it's likely a comparison
        if len(found_scenarios) >= 2 and has_comparison_keyword:
            print(f"🔍 DEBUG: Found multiple scenarios with comparison keywords: {found_scenarios}")
            return found_scenarios
        
        print(f"🔍 DEBUG: No valid scenarios found, returning empty list")
        return []
    
    def _determine_comparison_type(self, user_request: str) -> str:
        """
        Determine the type of comparison based on the user request.
        
        Args:
            user_request: The user's request text
            
        Returns:
            Comparison type: 'table', 'chart', or 'analysis'
        """
        request_lower = user_request.lower()
        
        # Check for visualization keywords
        viz_keywords = ["chart", "graph", "plot", "visualiz", "draw", "map", "diagram", "bar", "line", "pie"]
        if any(keyword in request_lower for keyword in viz_keywords):
            return "chart"
        
        # Check for table keywords
        table_keywords = ["table", "list", "show", "display", "data", "results"]
        if any(keyword in request_lower for keyword in table_keywords):
            return "table"
        
        # Default to analysis
        return "analysis"
    
    def _classify_request(self, state: AgentState) -> AgentState:
        """Classify the user request to determine how to handle it"""
        print(f"🔍 DEBUG: _classify_request called with state keys: {list(state.keys())}")
        
        user_request = state.get("user_request", "")
        if not user_request:
            # Get from messages
            for msg in reversed(state["messages"]):
                if isinstance(msg, HumanMessage):
                    user_request = msg.content
                    break
        
        print(f"🔍 DEBUG: User request: '{user_request}'")
        
        # Check for comparison keywords to identify comparison requests
        comparison_keywords = [
            "compare", "comparison", "versus", "vs", "between", "across", 
            "difference", "differences", "compare", "comparing"
        ]
        
        request_lower = user_request.lower()
        has_comparison_keyword = any(keyword in request_lower for keyword in comparison_keywords)
        
        if has_comparison_keyword:
            print(f"🔍 DEBUG: Comparison keywords detected, classifying as scenario_comparison")
            request_type = "scenario_comparison"
            
            # Get database context for current scenario (will be updated by extract_scenarios node)
            db_context = self._get_database_context()
            
            return {
                **state,
                "user_request": user_request,
                "request_type": request_type,
                "db_context": db_context,
                "messages": state["messages"] + [AIMessage(content=f"🎯 Request classified as: {request_type}")],
                # Initialize comparison fields with default values (will be populated by extract_scenarios)
                "comparison_scenarios": [],
                "comparison_data": {},
                "comparison_type": "",
                "scenario_name_mapping": {}
            }
        
        print(f"🔍 DEBUG: Not a comparison request, checking other patterns...")
        
        # Simple keyword-based classification with LLM fallback
        # Check for clear DB modification patterns
        db_mod_patterns = ["change", "update", "set", "modify", "alter", "edit"]
        param_patterns = ["parameter", "param", "cost", "demand", "capacity", "limit"]
        
        if any(pattern in request_lower for pattern in db_mod_patterns) and \
           any(pattern in request_lower for pattern in param_patterns):
            request_type = "db_modification"
            print(f"🔍 DEBUG: Classified as db_modification")
        
        # Check for visualization patterns
        elif any(pattern in request_lower for pattern in [
            "chart", "graph", "plot", "visualiz", "draw", "map", "diagram"
        ]):
            request_type = "visualization"
            print(f"🔍 DEBUG: Classified as visualization")
        
        # Check for SQL patterns
        elif any(pattern in request_lower for pattern in [
            "select", "query", "find", "search", "get", "retrieve", "list", "show", "count", "sum"
        ]):
            request_type = "sql_query"
            print(f"🔍 DEBUG: Classified as sql_query")
        
        # For ambiguous cases, use LLM classification
        else:
            print(f"🔍 DEBUG: Using LLM classification for ambiguous request")
            request_type = self._llm_classify_request(user_request)
            print(f"🔍 DEBUG: LLM classified as: {request_type}")
        
        # Get database context for current scenario
        print(f"🔍 DEBUG: Getting database context for current scenario...")
        db_context = self._get_database_context()
        print(f"🔍 DEBUG: Database context - valid: {db_context.is_valid()}, path: {db_context.database_path}")
        
        return {
            **state,
            "user_request": user_request,
            "request_type": request_type,
            "db_context": db_context,
            "messages": state["messages"] + [AIMessage(content=f"🎯 Request classified as: {request_type}")],
            # Initialize comparison fields with default values
            "comparison_scenarios": [],
            "comparison_data": {},
            "comparison_type": "",
            "scenario_name_mapping": {}
        }
    
    def _llm_classify_request(self, user_request: str) -> str:
        """Use LLM to classify ambiguous requests"""
        system_prompt = """Classify this user request into one of five categories:

1. **chat** - General questions, explanations, or conversations that don't require data analysis or code execution
   Examples: "What is this model about?", "How does optimization work?", "Explain the parameters"

2. **sql_query** - Requests for data retrieval, analysis, or querying 
   Examples: "Show me the top 10 hubs", "What is the total demand?", "List all routes"

3. **visualization** - Requests for charts, graphs, plots, or visual representations
   Examples: "Create a chart", "Visualize the data", "Show me a bar chart", "Plot the results"

4. **db_modification** - Requests to change database values or parameters
   Examples: "Change the maximum demand to 5000", "Update the cost parameter", "Set capacity to 1000"

5. **scenario_comparison** - Requests to compare multiple scenarios
   Examples: "Compare Base Scenario and Test Scenario", "Show differences between scenarios", "Base Scenario vs Test Scenario"

Respond with exactly one word: chat, sql_query, visualization, db_modification, or scenario_comparison"""
        
        try:
            response = self._get_llm().invoke([HumanMessage(content=f"{system_prompt}\n\nUser request: {user_request}")])
            classification = response.content.strip().lower()
            if classification in ["chat", "sql_query", "visualization", "db_modification", "scenario_comparison"]:
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
        
        # Check if this is a comparison visualization
        is_comparison = db_context.comparison_mode and db_context.multi_database_contexts
        
        if is_comparison:
            # Handle comparison visualization
            return self._handle_comparison_visualization(state)
        else:
            # Handle single scenario visualization
            return self._handle_single_visualization(state)
    
    def _handle_single_visualization(self, state: AgentState) -> AgentState:
        """Generate Python code for single scenario visualization"""
        user_request = state["user_request"]
        db_context = state["db_context"]
        
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
    
    def _handle_comparison_visualization(self, state: AgentState) -> AgentState:
        """Generate Python code for multi-scenario comparison visualization"""
        user_request = state["user_request"]
        db_context = state["db_context"]
        
        # Get scenario information
        scenario_names = db_context.get_scenario_names()
        all_database_paths = db_context.get_all_database_paths()
        
        # Get primary context for schema info and temp directory
        primary_context = db_context.get_primary_context()
        if not primary_context:
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No primary scenario context available")]
            }
        
        # Build schema context from primary scenario
        schema_context = self._build_schema_context(primary_context.schema_info)
        
        # Create database path mapping for the code - use absolute paths
        db_path_mapping = {}
        for i, scenario_name in enumerate(scenario_names):
            if i < len(all_database_paths):
                # Use absolute paths to ensure correct database access regardless of execution directory
                abs_db_path = all_database_paths[i]
                db_path_mapping[scenario_name] = abs_db_path.replace('\\', '/')
        
        print(f"🔍 DEBUG: Database path mapping (absolute paths): {db_path_mapping}")
        
        # Determine chart type based on user request
        chart_type = self._determine_comparison_chart_type(user_request)
        
        system_prompt = f"""Generate Python code to create an advanced comparison visualization across multiple scenarios.

Scenarios to compare: {', '.join(scenario_names)}
Database files: {', '.join([f"{name}: {path}" for name, path in db_path_mapping.items()])}

Schema from primary scenario:
{schema_context}

Chart Type: {chart_type}

COMPARISON CHART REQUIREMENTS:

1. **Data Aggregation:**
   - Connect to all scenario databases using the provided absolute paths
   - Query the same data from each scenario for comparison
   - Use the _aggregate_scenario_data method to combine data with consistent structure
   - Handle different table structures gracefully

2. **Chart Types for Comparison:**
   - **Side-by-side bars**: Use go.Bar with barmode='group' for categorical comparisons
   - **Grouped bars**: Use go.Bar with barmode='group' for multiple metrics
   - **Faceted plots**: Use subplots for complex multi-metric comparisons
   - **Line charts**: Use go.Scatter with different colors per scenario
   - **Scatter plots**: Use go.Scatter with scenario color coding
   - **Heatmaps**: Use go.Heatmap for matrix-style comparisons

3. **Scenario Color Coding:**
   - Use distinct colors for each scenario (e.g., ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728'])
   - Add scenario names to legend
   - Include scenario information in hover text

4. **Enhanced Features:**
   - Add scenario legends with proper labels
   - Include scenario annotations for key differences
   - Show percentage differences or absolute values
   - Add trend lines or reference lines where appropriate
   - Include statistical summaries in annotations

5. **Interactive Elements:**
   - Hover information should show scenario name, values, and differences
   - Add buttons to toggle between scenarios
   - Include zoom and pan capabilities
   - Add download buttons for data

CRITICAL REQUIREMENTS:
- Use the provided absolute database paths (not just filenames, not relative paths)
- Save HTML file in the current directory
- Use plotly.graph_objects for interactive visualizations
- DO NOT use fig.show() - only save as HTML file
- DO NOT use encoding parameter in write_html() - Plotly handles encoding automatically
- Use dynamic file naming with timestamp
- Use fig.write_html(html_file_path) without any encoding parameter
- IMPORTANT: Convert all pandas Series/DataFrame data to Python lists using .tolist() before plotting
- Reset DataFrame indexes using df.reset_index(drop=True) before extracting data for plotting
- Ensure data arrays contain actual values, not DataFrame indexes
- Use the _aggregate_scenario_data method for data combination

User request: {user_request}

Generate complete Python code that creates an advanced comparison visualization:"""
        
        try:
            response = self._get_llm().invoke([HumanMessage(content=system_prompt)])
            llm_response = response.content.strip()
            
            # Extract code and explanation
            code_content, explanation = self._extract_code_and_explanation(llm_response)
            
            # Clean up code
            code_content = self._clean_generated_code(code_content)
            
            # Generate filename using scenario manager
            filename = self.scenario_manager.generate_comparison_filename(
                scenario_names=scenario_names,
                comparison_type="visualization",
                extension="py"
            )
            file_path = os.path.join(primary_context.temp_dir, filename)
            
            # Write the file with UTF-8 encoding
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            # Create response message with explanation
            response_message = f"📊 Generated comparison visualization script: {filename}"
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
                "messages": state["messages"] + [AIMessage(content=f"❌ Error generating comparison visualization: {str(e)}")]
            }
    
    def _determine_comparison_chart_type(self, user_request: str) -> str:
        """Determine the most appropriate chart type for comparison visualization"""
        request_lower = user_request.lower()
        
        # Check for specific chart type requests
        if any(word in request_lower for word in ["side by side", "side-by-side", "grouped bars", "grouped bar"]):
            return "side_by_side_bars"
        elif any(word in request_lower for word in ["faceted", "subplot", "multiple charts"]):
            return "faceted_plots"
        elif any(word in request_lower for word in ["scatter", "correlation", "relationship"]):
            return "scatter_plot"
        elif any(word in request_lower for word in ["heatmap", "matrix", "grid"]):
            return "heatmap"
        elif any(word in request_lower for word in ["line", "trend", "time series"]):
            return "line_chart"
        elif any(word in request_lower for word in ["pie", "donut", "proportion"]):
            return "pie_chart"
        else:
            # Default to grouped bars for most comparisons
            return "grouped_bars"
    
    def _handle_scenario_comparison(self, state: AgentState) -> AgentState:
        """Generate Python code for multi-scenario comparison operations"""
        print(f"🔍 DEBUG: _handle_scenario_comparison called")
        print(f"🔍 DEBUG: State keys: {list(state.keys())}")
        
        user_request = state["user_request"]
        db_context = state["db_context"]
        comparison_scenarios = state.get("comparison_scenarios", [])
        comparison_type = state.get("comparison_type", "analysis")
        
        print(f"🔍 DEBUG: User request: '{user_request}'")
        print(f"🔍 DEBUG: DB context valid: {db_context.is_valid()}")
        print(f"🔍 DEBUG: DB context comparison mode: {db_context.comparison_mode}")
        print(f"🔍 DEBUG: Comparison scenarios: {comparison_scenarios}")
        print(f"🔍 DEBUG: Comparison type: {comparison_type}")
        
        if not db_context.is_valid() or not db_context.comparison_mode:
            print(f"🔍 DEBUG: Invalid database context or not in comparison mode")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No valid comparison database context available")]
            }
        
        if len(comparison_scenarios) < 2:
            print(f"🔍 DEBUG: Not enough scenarios for comparison: {len(comparison_scenarios)}")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ Need at least 2 scenarios for comparison")]
            }
        
        # If this is a chart or table comparison, delegate to the visualization handler
        if comparison_type in ("chart", "table"):
            print(f"🔍 DEBUG: Delegating to comparison visualization handler")
            return self._handle_comparison_visualization(state)
        
        print(f"🔍 DEBUG: Using analysis code generation logic")
        
        # Otherwise, use the original code-generation logic for 'analysis' or other types
        # Get primary context for schema info and temp directory
        primary_context = db_context.get_primary_context()
        if not primary_context:
            print(f"🔍 DEBUG: No primary context available")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content="❌ No primary scenario context available")]
            }
        
        print(f"🔍 DEBUG: Primary context found - valid: {primary_context.is_valid()}")
        
        # Build schema context from primary scenario
        schema_context = self._build_schema_context(primary_context.schema_info)
        
        # Get all database paths for comparison
        all_database_paths = db_context.get_all_database_paths()
        scenario_names = db_context.get_scenario_names()
        
        print(f"🔍 DEBUG: All database paths: {all_database_paths}")
        print(f"🔍 DEBUG: Scenario names: {scenario_names}")
        
        # Create database path mapping for the code - use absolute paths
        db_path_mapping = {}
        for i, scenario_name in enumerate(scenario_names):
            if i < len(all_database_paths):
                # Use absolute paths to ensure correct database access regardless of execution directory
                abs_db_path = all_database_paths[i]
                db_path_mapping[scenario_name] = abs_db_path.replace('\\', '/')
        
        print(f"🔍 DEBUG: Database path mapping (absolute paths): {db_path_mapping}")
        
        # Build system prompt for analysis
        system_prompt = f"""Generate Python code to perform analysis across multiple scenarios.

Scenarios to compare: {', '.join(scenario_names)}
Database files: {', '.join([f"{name}: {path}" for name, path in db_path_mapping.items()])}

IMPORTANT: Each scenario has its own subdirectory containing a database.db file. 
The database paths shown above are the absolute paths to each scenario's database file. 
You MUST use these absolute paths to connect to each scenario's database. Do NOT use just 'database.db'.

Schema from primary scenario:
{schema_context}

Requirements:
1. Connect to all scenario databases using the provided absolute paths
2. Query and analyze data from each scenario
3. Create a comprehensive analysis that compares scenarios
4. Generate both visualizations and summary statistics
5. Include scenario names to distinguish data sources
6. Save results as interactive HTML file in the current directory

Key requirements:
- Use plotly.graph_objects for creating visualizations
- Use pandas for data manipulation and analysis
- Create interactive charts and tables with hover effects
- Include proper error handling with try/except blocks
- Make outputs responsive and well-formatted
- Add scenario names to distinguish data sources

CRITICAL REQUIREMENTS:
- Use the exact absolute database paths provided (not just filenames, not relative paths)
- Save HTML file in the current directory
- Use plotly.graph_objects for interactive outputs
- DO NOT use fig.show() - only save as HTML file
- DO NOT use encoding parameter in write_html() - Plotly handles encoding automatically
- Use dynamic file naming with timestamp
- Use fig.write_html(html_file_path) without any encoding parameter
- IMPORTANT: Convert all pandas Series/DataFrame data to Python lists using .tolist() before plotting
- Reset DataFrame indexes using df.reset_index(drop=True) before extracting data for plotting
- Ensure data arrays contain actual values, not DataFrame indexes

User request: {user_request}

Generate complete Python code that performs scenario comparison analysis:"""
        
        try:
            print(f"🔍 DEBUG: Calling LLM for code generation...")
            response = self._get_llm().invoke([HumanMessage(content=system_prompt)])
            llm_response = response.content.strip()
            
            print(f"🔍 DEBUG: LLM response received, extracting code...")
            
            # Extract code and explanation
            code_content, explanation = self._extract_code_and_explanation(llm_response)
            
            # Clean up code
            code_content = self._clean_generated_code(code_content)
            
            print(f"🔍 DEBUG: Code extracted and cleaned, generating filename...")
            
            # Generate filename using scenario manager
            filename = self.scenario_manager.generate_comparison_filename(
                scenario_names=comparison_scenarios,
                comparison_type=comparison_type,
                extension="py"
            )
            file_path = os.path.join(primary_context.temp_dir, filename)
            
            print(f"🔍 DEBUG: Writing file to: {file_path}")
            
            # Write the file with UTF-8 encoding
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(code_content)
            
            print(f"🔍 DEBUG: File written successfully")
            
            # Create response message with explanation
            response_message = f"📊 Generated {comparison_type} comparison script: {filename}"
            if explanation:
                response_message += f"\n\n{explanation}"
            
            print(f"🔍 DEBUG: Returning success response")
            return {
                **state,
                "generated_files": [filename],
                "messages": state["messages"] + [AIMessage(content=response_message)]
            }
            
        except Exception as e:
            print(f"🔍 DEBUG: Error in comparison code generation: {e}")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"❌ Error generating comparison: {str(e)}")]
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
        print(f"🔍 DEBUG: _execute_code called")
        print(f"🔍 DEBUG: State keys: {list(state.keys())}")
        
        generated_files = state.get("generated_files", [])
        db_context = state["db_context"]
        
        print(f"🔍 DEBUG: Generated files: {generated_files}")
        print(f"🔍 DEBUG: DB context valid: {db_context.is_valid()}")
        print(f"🔍 DEBUG: DB context temp_dir: {db_context.temp_dir}")
        
        if not generated_files or not db_context.is_valid():
            print(f"🔍 DEBUG: No files to execute or invalid database context")
            return {
                **state,
                "execution_error": "No files to execute or invalid database context"
            }
        
        # Execute the most recent file
        filename = generated_files[-1]
        file_path = os.path.join(db_context.temp_dir, filename)
        
        print(f"🔍 DEBUG: Executing file: {filename}")
        print(f"🔍 DEBUG: Full file path: {file_path}")
        
        if not os.path.exists(file_path):
            print(f"🔍 DEBUG: Generated file not found: {file_path}")
            return {
                **state,
                "execution_error": f"Generated file not found: {filename}"
            }
        
        print(f"🔍 DEBUG: File exists, proceeding with execution")
        
        # Execute Python file
        try:
            import subprocess
            
            # Execute in the database directory so output files are created there
            if db_context.comparison_mode and db_context.multi_database_contexts:
                # In comparison mode, use the primary scenario's directory
                primary_context = db_context.get_primary_context()
                if primary_context and primary_context.database_path:
                    db_dir = os.path.dirname(primary_context.database_path)
                else:
                    # Fallback to temp_dir if available
                    db_dir = db_context.temp_dir or os.getcwd()
            else:
                # Single scenario mode
                db_dir = os.path.dirname(db_context.database_path)
            
            # For comparison files, ensure we're executing in the correct directory
            # Check if the file being executed is a comparison file
            if filename and ('comparison' in filename.lower() or 'vs_' in filename.lower()):
                # For comparison files, use the directory where the file is located
                file_dir = os.path.dirname(file_path)
                if file_dir and os.path.exists(file_dir):
                    db_dir = file_dir
                    print(f"🔍 DEBUG: Using comparison file's directory for execution: {db_dir}")
            
            print(f"🔍 DEBUG: Execution directory: {db_dir}")
            
            # Use the same Python executable as the current process
            python_executable = sys.executable
            print(f"🔍 DEBUG: Python executable: {python_executable}")
            
            # Record existing files BEFORE execution to avoid picking up old files
            existing_files = set()
            if os.path.exists(db_dir):
                for file in os.listdir(db_dir):
                    if file.endswith('.html'):
                        existing_files.add(file)
            print(f"🔍 DEBUG: Existing HTML files before execution: {existing_files}")
            
            print(f"🔍 DEBUG: Starting subprocess execution...")
            result = subprocess.run(
                [python_executable, file_path],
                cwd=db_dir,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='replace',  # Replace problematic characters
                timeout=120  # Increased timeout for slower imports
            )
            
            print(f"🔍 DEBUG: Subprocess completed with return code: {result.returncode}")
            print(f"🔍 DEBUG: Subprocess stdout: {result.stdout[:200]}...")
            print(f"🔍 DEBUG: Subprocess stderr: {result.stderr[:200]}...")
            
            if result.returncode == 0:
                # Find ONLY newly generated output files (HTML files) in database directory
                output_files = []
                if os.path.exists(db_dir):
                    for file in os.listdir(db_dir):
                        if file.endswith('.html'):
                            # Only include files that didn't exist before execution
                            if file not in existing_files:
                                output_files.append(file)
                
                print(f"🔍 DEBUG: Newly generated HTML files: {output_files}")
                
                execution_output = result.stdout
                if output_files:
                    execution_output += f"\n\n📁 Generated files: {', '.join(output_files)}"
                
                # Only return files generated in this specific request
                # The state.get("generated_files", []) contains the Python file from this request
                # The output_files contains the HTML files generated by this request
                current_request_files = state.get("generated_files", []) + output_files
                
                print(f"🔍 DEBUG: Returning success with files: {current_request_files}")
                return {
                    **state,
                    "execution_output": execution_output,
                    "execution_error": "",
                    "generated_files": current_request_files  # Only files from this request
                }
            else:
                print(f"🔍 DEBUG: Subprocess failed, returning error")
                return {
                    **state,
                    "execution_output": result.stdout,
                    "execution_error": result.stderr
                }
                
        except subprocess.TimeoutExpired:
            print(f"🔍 DEBUG: Subprocess timed out")
            return {
                **state,
                "execution_error": "Execution timed out (120 seconds). The script may be importing heavy libraries or taking too long to run."
            }
        except Exception as e:
            print(f"🔍 DEBUG: Subprocess exception: {e}")
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
                "db_modification_result": None,
                # Initialize comparison fields
                "comparison_scenarios": [],
                "comparison_data": {},
                "comparison_type": "",
                "scenario_name_mapping": {}
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

    def _execute_multi_database_query(
        self,
        sql_query_template: str,
        db_contexts: Dict[str, DatabaseContext],
        params: Optional[Dict[str, Any]] = None
    ) -> 'pd.DataFrame':
        """
        Execute the same SQL query against each scenario's database, aggregate results, and add scenario name as a column.
        Handles schema differences gracefully (missing columns, etc.).

        Args:
            sql_query_template: SQL query string (may use named placeholders for params)
            db_contexts: Dict mapping scenario names to DatabaseContext objects
            params: Optional dict of parameters to use in the query
        Returns:
            Aggregated pandas DataFrame with scenario name as a column
        """
        import pandas as pd
        results = []
        for scenario_name, db_ctx in db_contexts.items():
            db_path = db_ctx.database_path
            if not db_path or not os.path.exists(db_path):
                print(f"[WARN] Database for scenario '{scenario_name}' not found: {db_path}")
                continue
            try:
                conn = sqlite3.connect(db_path)
                # Try to execute the query, handle missing columns gracefully
                try:
                    if params:
                        df = pd.read_sql_query(sql_query_template, conn, params=params)
                    else:
                        df = pd.read_sql_query(sql_query_template, conn)
                    df["scenario"] = scenario_name
                    results.append(df)
                except Exception as e:
                    print(f"[WARN] Query failed for scenario '{scenario_name}': {e}")
                    # Try to get columns from the schema and adjust query if possible
                    try:
                        cursor = conn.execute("PRAGMA table_info(main)")
                        schema_cols = [row[1] for row in cursor.fetchall()]
                        print(f"[DEBUG] Columns in scenario '{scenario_name}': {schema_cols}")
                    except Exception as e2:
                        print(f"[ERROR] Could not fetch schema for scenario '{scenario_name}': {e2}")
                finally:
                    conn.close()
            except Exception as e:
                print(f"[ERROR] Could not connect to database for scenario '{scenario_name}': {e}")
        if results:
            # Union all results, aligning columns
            df_all = pd.concat(results, axis=0, ignore_index=True, sort=True)
            return df_all
        else:
            # Return empty DataFrame with scenario column
            return pd.DataFrame(columns=["scenario"])
    
    def _aggregate_scenario_data(
        self,
        db_contexts: Dict[str, DatabaseContext],
        table_name: str,
        required_columns: Optional[List[str]] = None,
        optional_columns: Optional[List[str]] = None
    ) -> 'pd.DataFrame':
        """
        Combine data from multiple scenarios into a unified format with consistent column naming.
        
        Args:
            db_contexts: Dict mapping scenario names to DatabaseContext objects
            table_name: Name of the table to aggregate from each scenario
            required_columns: List of columns that must exist in all scenarios
            optional_columns: List of columns to include if available (will be filled with None if missing)
            
        Returns:
            Aggregated pandas DataFrame with scenario_name column and consistent structure
            
        Raises:
            ValueError: If required columns are missing from any scenario
        """
        import pandas as pd
        
        results = []
        all_columns = set()
        scenario_schemas = {}
        
        # First pass: collect schema information and validate required columns
        for scenario_name, db_ctx in db_contexts.items():
            db_path = db_ctx.database_path
            if not db_path or not os.path.exists(db_path):
                print(f"[WARN] Database for scenario '{scenario_name}' not found: {db_path}")
                continue
            
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                
                # Check if table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
                if not cursor.fetchone():
                    print(f"[WARN] Table '{table_name}' not found in scenario '{scenario_name}'")
                    conn.close()
                    continue
                
                # Get table schema
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = [row[1] for row in cursor.fetchall()]
                scenario_schemas[scenario_name] = columns
                all_columns.update(columns)
                
                # Validate required columns
                if required_columns:
                    missing_columns = [col for col in required_columns if col not in columns]
                    if missing_columns:
                        raise ValueError(f"Scenario '{scenario_name}' is missing required columns: {missing_columns}")
                
                conn.close()
                
            except Exception as e:
                print(f"[ERROR] Error analyzing schema for scenario '{scenario_name}': {e}")
                continue
        
        if not scenario_schemas:
            return pd.DataFrame(columns=["scenario_name"])
        
        # Determine final column structure
        final_columns = ["scenario_name"]
        if required_columns:
            final_columns.extend(required_columns)
        if optional_columns:
            final_columns.extend(optional_columns)
        
        # Add any additional columns found in any scenario
        additional_columns = all_columns - set(required_columns or []) - set(optional_columns or [])
        final_columns.extend(sorted(additional_columns))
        
        # Second pass: extract data from each scenario
        for scenario_name, db_ctx in db_contexts.items():
            if scenario_name not in scenario_schemas:
                continue
            
            db_path = db_ctx.database_path
            try:
                conn = sqlite3.connect(db_path)
                
                # Build SELECT clause with all possible columns
                select_columns = []
                for col in final_columns[1:]:  # Skip scenario_name
                    if col in scenario_schemas[scenario_name]:
                        select_columns.append(col)
                    else:
                        # Column doesn't exist in this scenario, use NULL
                        select_columns.append(f"NULL as {col}")
                
                if not select_columns:
                    print(f"[WARN] No valid columns found for scenario '{scenario_name}'")
                    conn.close()
                    continue
                
                # Execute query
                select_clause = ", ".join(select_columns)
                query = f"SELECT {select_clause} FROM {table_name}"
                
                df = pd.read_sql_query(query, conn)
                df["scenario_name"] = scenario_name
                
                # Reorder columns to match final structure
                df = df[final_columns]
                results.append(df)
                
                conn.close()
                
            except Exception as e:
                print(f"[ERROR] Error extracting data from scenario '{scenario_name}': {e}")
                continue
        
        if not results:
            return pd.DataFrame(columns=final_columns)
        
        # Combine all results
        combined_df = pd.concat(results, axis=0, ignore_index=True)
        
        # Validate final structure
        if required_columns:
            missing_in_final = [col for col in required_columns if col not in combined_df.columns]
            if missing_in_final:
                raise ValueError(f"Required columns missing from final aggregated data: {missing_in_final}")
        
        return combined_df
    
    def _generate_comparison_table(
        self,
        db_contexts: Dict[str, DatabaseContext],
        table_name: str,
        key_column: str,
        value_columns: List[str],
        highlight_thresholds: Optional[Dict[str, float]] = None
    ) -> str:
        """
        Generate HTML comparison table showing metrics across scenarios with highlighting and metadata.
        
        Args:
            db_contexts: Dict mapping scenario names to DatabaseContext objects
            table_name: Name of the table to compare
            key_column: Column to use as row identifier (e.g., 'Location', 'Hub')
            value_columns: List of columns to compare across scenarios
            highlight_thresholds: Dict mapping column names to percentage thresholds for highlighting
            
        Returns:
            HTML string with formatted comparison table
        """
        import pandas as pd
        
        # Default highlighting thresholds
        if highlight_thresholds is None:
            highlight_thresholds = {
                'default': 10.0,  # 10% change threshold
                'high': 20.0,     # 20% change threshold
                'critical': 50.0   # 50% change threshold
            }
        
        # Aggregate data from all scenarios
        try:
            combined_df = self._aggregate_scenario_data(
                db_contexts=db_contexts,
                table_name=table_name,
                required_columns=[key_column] + value_columns
            )
        except ValueError as e:
            return f"<div class='error'>Error aggregating data: {str(e)}</div>"
        
        if combined_df.empty:
            return "<div class='error'>No data available for comparison</div>"
        
        # Get scenario metadata
        scenario_metadata = {}
        for scenario_name, db_ctx in db_contexts.items():
            if db_ctx.scenario_id and self.scenario_manager:
                scenario = self.scenario_manager.get_scenario(db_ctx.scenario_id)
                if scenario:
                    scenario_metadata[scenario_name] = {
                        'created': scenario.created_at.strftime('%Y-%m-%d %H:%M') if scenario.created_at else 'Unknown',
                        'description': scenario.description or 'No description',
                        'id': scenario.id
                    }
        
        # Create comparison table HTML
        html_parts = []
        
        # CSS Styles
        html_parts.append("""
        <style>
        .comparison-table {
            font-family: Arial, sans-serif;
            border-collapse: collapse;
            width: 100%;
            margin: 20px 0;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .comparison-table th, .comparison-table td {
            border: 1px solid #ddd;
            padding: 12px;
            text-align: center;
        }
        .comparison-table th {
            background-color: #f2f2f2;
            font-weight: bold;
            color: #333;
        }
        .comparison-table tr:nth-child(even) {
            background-color: #f9f9f9;
        }
        .comparison-table tr:hover {
            background-color: #f0f0f0;
        }
        .scenario-header {
            background-color: #4CAF50 !important;
            color: white !important;
            font-weight: bold;
        }
        .key-column {
            background-color: #e8f5e8;
            font-weight: bold;
            text-align: left;
        }
        .highlight-low {
            background-color: #fff3cd;
            color: #856404;
        }
        .highlight-medium {
            background-color: #f8d7da;
            color: #721c24;
        }
        .highlight-high {
            background-color: #d4edda;
            color: #155724;
        }
        .highlight-critical {
            background-color: #f8d7da;
            color: #721c24;
            font-weight: bold;
        }
        .difference {
            font-size: 0.9em;
            font-style: italic;
        }
        .percentage {
            font-size: 0.8em;
            color: #666;
        }
        .metadata {
            background-color: #f8f9fa;
            padding: 10px;
            margin: 10px 0;
            border-radius: 5px;
            border-left: 4px solid #007bff;
        }
        .metadata h3 {
            margin: 0 0 10px 0;
            color: #007bff;
        }
        .metadata p {
            margin: 5px 0;
            font-size: 0.9em;
        }
        .summary-stats {
            background-color: #e9ecef;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }
        .summary-stats h4 {
            margin: 0 0 10px 0;
            color: #495057;
        }
        .summary-stats ul {
            margin: 0;
            padding-left: 20px;
        }
        </style>
        """)
        
        # Scenario Metadata Section
        if scenario_metadata:
            html_parts.append("<div class='metadata'>")
            html_parts.append("<h3>📊 Scenario Comparison Metadata</h3>")
            for scenario_name, metadata in scenario_metadata.items():
                html_parts.append(f"""
                <p><strong>{scenario_name}:</strong> Created {metadata['created']} | {metadata['description']}</p>
                """)
            html_parts.append("</div>")
        
        # Summary Statistics
        html_parts.append("<div class='summary-stats'>")
        html_parts.append("<h4>📈 Comparison Summary</h4>")
        html_parts.append(f"<ul>")
        html_parts.append(f"<li>Comparing {len(db_contexts)} scenarios</li>")
        html_parts.append(f"<li>Analyzing {len(value_columns)} metrics: {', '.join(value_columns)}</li>")
        html_parts.append(f"<li>Total rows: {len(combined_df)}</li>")
        html_parts.append("</ul>")
        html_parts.append("</div>")
        
        # Start table
        html_parts.append("<table class='comparison-table'>")
        
        # Table header
        header_cells = [f"<th class='key-column'>{key_column}</th>"]
        for scenario_name in db_contexts.keys():
            header_cells.append(f"<th class='scenario-header'>{scenario_name}</th>")
        html_parts.append(f"<tr>{''.join(header_cells)}</tr>")
        
        # Get unique keys (locations, hubs, etc.)
        unique_keys = combined_df[key_column].unique()
        
        # Process each row
        for key_value in sorted(unique_keys):
            row_data = combined_df[combined_df[key_column] == key_value]
            
            # Start row
            html_parts.append(f"<tr>")
            html_parts.append(f"<td class='key-column'>{key_value}</td>")
            
            # Get values for each scenario
            scenario_values = {}
            for scenario_name in db_contexts.keys():
                scenario_row = row_data[row_data['scenario_name'] == scenario_name]
                if not scenario_row.empty:
                    scenario_values[scenario_name] = {}
                    for col in value_columns:
                        if col in scenario_row.columns:
                            scenario_values[scenario_name][col] = scenario_row[col].iloc[0]
                        else:
                            scenario_values[scenario_name][col] = None
                else:
                    scenario_values[scenario_name] = {col: None for col in value_columns}
            
            # Calculate differences and generate cells
            baseline_scenario = list(db_contexts.keys())[0]
            baseline_values = scenario_values.get(baseline_scenario, {})
            
            for scenario_name in db_contexts.keys():
                cell_content = []
                
                for col in value_columns:
                    current_value = scenario_values[scenario_name].get(col)
                    baseline_value = baseline_values.get(col)
                    
                    if current_value is not None:
                        # Format the value
                        if isinstance(current_value, (int, float)):
                            formatted_value = f"{current_value:,.2f}" if current_value % 1 != 0 else f"{current_value:,.0f}"
                        else:
                            formatted_value = str(current_value)
                        
                        cell_content.append(f"<strong>{formatted_value}</strong>")
                        
                        # Calculate difference if we have baseline
                        if baseline_value is not None and baseline_value != current_value:
                            try:
                                if baseline_value != 0:
                                    percentage_diff = ((current_value - baseline_value) / baseline_value) * 100
                                    abs_diff = current_value - baseline_value
                                    
                                    # Determine highlighting class
                                    threshold = highlight_thresholds.get(col, highlight_thresholds['default'])
                                    if abs(percentage_diff) >= highlight_thresholds.get('critical', 50.0):
                                        highlight_class = "highlight-critical"
                                    elif abs(percentage_diff) >= highlight_thresholds.get('high', 20.0):
                                        highlight_class = "highlight-high"
                                    elif abs(percentage_diff) >= threshold:
                                        highlight_class = "highlight-medium"
                                    else:
                                        highlight_class = "highlight-low"
                                    
                                    diff_sign = "+" if abs_diff > 0 else ""
                                    cell_content.append(f"<div class='difference {highlight_class}'>{diff_sign}{abs_diff:,.2f}</div>")
                                    cell_content.append(f"<div class='percentage {highlight_class}'>{diff_sign}{percentage_diff:+.1f}%</div>")
                                else:
                                    cell_content.append(f"<div class='difference'>N/A</div>")
                            except (TypeError, ValueError):
                                cell_content.append(f"<div class='difference'>N/A</div>")
                    else:
                        cell_content.append("<em>N/A</em>")
                
                # Join cell content
                cell_html = "<br>".join(cell_content)
                html_parts.append(f"<td>{cell_html}</td>")
            
            html_parts.append("</tr>")
        
        # Close table
        html_parts.append("</table>")
        
        # Legend
        html_parts.append("""
        <div style='margin-top: 20px; padding: 10px; background-color: #f8f9fa; border-radius: 5px;'>
        <h4>🎨 Highlighting Legend</h4>
        <ul style='margin: 0; padding-left: 20px;'>
        <li><span style='background-color: #fff3cd; padding: 2px 5px;'>Low</span>: Changes &lt; 10%</li>
        <li><span style='background-color: #f8d7da; padding: 2px 5px;'>Medium</span>: Changes 10-20%</li>
        <li><span style='background-color: #d4edda; padding: 2px 5px;'>High</span>: Changes 20-50%</li>
        <li><span style='background-color: #f8d7da; color: #721c24; font-weight: bold; padding: 2px 5px;'>Critical</span>: Changes &gt; 50%</li>
        </ul>
        </div>
        """)
        
        return "".join(html_parts)
    
    def _generate_comparison_file_path(
        self,
        scenario_names: List[str],
        file_type: str,
        extension: str = "html",
        base_directory: Optional[str] = None
    ) -> str:
        """
        Generate absolute file paths for comparison outputs using scenario manager.
        
        Args:
            scenario_names: List of scenario names to include in filename
            file_type: Type of comparison file (e.g., 'table', 'chart', 'analysis')
            extension: File extension (default: 'html')
            base_directory: Optional base directory (defaults to project root)
            
        Returns:
            Absolute file path for the comparison output file
        """
        if self.scenario_manager:
            # Use scenario manager's filename generation
            filename = self.scenario_manager.generate_comparison_filename(
                scenario_names=scenario_names,
                comparison_type=file_type,
                extension=extension
            )
            return self.scenario_manager.get_comparison_file_path(filename)
        else:
            # Fallback to manual generation if no scenario manager
            import os
            from datetime import datetime
            
            # Sanitize scenario names for file system compatibility
            def sanitize_filename(name: str) -> str:
                """Convert scenario name to filesystem-safe filename"""
                # Replace problematic characters with underscores
                import re
                # Remove or replace characters that are problematic in filenames
                sanitized = re.sub(r'[<>:"/\\|?*]', '_', name)
                # Replace spaces with underscores
                sanitized = sanitized.replace(' ', '_')
                # Remove multiple consecutive underscores
                sanitized = re.sub(r'_+', '_', sanitized)
                # Remove leading/trailing underscores
                sanitized = sanitized.strip('_')
                # Limit length to avoid filesystem issues
                if len(sanitized) > 50:
                    sanitized = sanitized[:50]
                return sanitized or 'scenario'
            
            # Determine base directory
            if base_directory is None:
                # Fallback to current working directory
                base_directory = os.getcwd()
            
            # Create comparison directory
            comparison_dir = os.path.join(base_directory, "comparisons")
            os.makedirs(comparison_dir, exist_ok=True)
            
            # Generate timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Create filename components
            sanitized_names = [sanitize_filename(name) for name in scenario_names]
            
            # Limit number of scenario names in filename to avoid extremely long names
            if len(sanitized_names) > 3:
                # Use first 2 and last 1 scenario names
                scenario_part = f"{sanitized_names[0]}_{sanitized_names[1]}_and_{len(sanitized_names)-2}_more"
            else:
                scenario_part = "_vs_".join(sanitized_names)
            
            # Generate filename
            filename = f"comparison_{file_type}_{scenario_part}_{timestamp}.{extension}"
            
            # Ensure filename is not too long (some filesystems have limits)
            max_filename_length = 200  # Conservative limit
            if len(filename) > max_filename_length:
                # Truncate scenario part if needed
                available_length = max_filename_length - len(f"comparison_{file_type}_TIMESTAMP.{extension}")
                if available_length > 20:  # Ensure we have some space for scenario names
                    scenario_part = scenario_part[:available_length]
                    filename = f"comparison_{file_type}_{scenario_part}_{timestamp}.{extension}"
                else:
                    # Fallback to generic name
                    filename = f"comparison_{file_type}_{timestamp}.{extension}"
            
            # Create full path
            file_path = os.path.join(comparison_dir, filename)
            
            # Ensure path is absolute and normalized
            file_path = os.path.abspath(file_path)
            
            # Verify the path is valid for the current operating system
            try:
                # Test if we can create a file with this path
                test_path = file_path + ".test"
                with open(test_path, 'w') as f:
                    f.write("test")
                os.remove(test_path)
            except (OSError, IOError) as e:
                # If there's an issue, fall back to a simpler path
                print(f"Warning: Could not create file at {file_path}: {e}")
                fallback_filename = f"comparison_{file_type}_{timestamp}.{extension}"
                file_path = os.path.join(comparison_dir, fallback_filename)
                file_path = os.path.abspath(file_path)
            
            return file_path
    
    def _ensure_directory_exists(self, directory_path: str) -> str:
        """
        Ensure a directory exists and return the absolute path.
        
        Args:
            directory_path: Path to the directory
            
        Returns:
            Absolute path to the directory (created if it didn't exist)
        """
        import os
        
        # Convert to absolute path
        abs_path = os.path.abspath(directory_path)
        
        # Create directory if it doesn't exist
        os.makedirs(abs_path, exist_ok=True)
        
        return abs_path
    
    def _track_comparison_output(self, scenario_names: List[str], comparison_type: str, 
                                output_file_path: str, description: Optional[str] = None,
                                metadata: Optional[Dict[str, Any]] = None) -> bool:
        """
        Track a comparison output in the scenario manager's comparison history.
        
        Args:
            scenario_names: List of scenario names used in the comparison
            comparison_type: Type of comparison ('table', 'chart', 'analysis')
            output_file_path: Path to the generated comparison file
            description: Optional description of the comparison
            metadata: Optional additional metadata
            
        Returns:
            True if tracking was successful, False otherwise
        """
        if not self.scenario_manager:
            return False
        
        try:
            # Get scenario IDs from names
            scenario_ids = []
            all_scenarios = self.scenario_manager.list_scenarios()
            scenario_name_to_id = {s.name: s.id for s in all_scenarios}
            
            for scenario_name in scenario_names:
                if scenario_name in scenario_name_to_id:
                    scenario_ids.append(scenario_name_to_id[scenario_name])
            
            if not scenario_ids:
                print(f"Warning: Could not find scenario IDs for names: {scenario_names}")
                return False
            
            # Get current scenario ID for created_by_scenario_id
            current_scenario = self.scenario_manager.get_current_scenario()
            created_by_scenario_id = current_scenario.id if current_scenario else None
            
            # Generate comparison name
            comparison_name = f"Comparison of {', '.join(scenario_names)}"
            
            # Add to comparison history
            self.scenario_manager.add_comparison_history(
                comparison_name=comparison_name,
                scenario_ids=scenario_ids,
                scenario_names=scenario_names,
                comparison_type=comparison_type,
                output_file_path=output_file_path,
                created_by_scenario_id=created_by_scenario_id,
                description=description,
                metadata=metadata
            )
            
            print(f"✅ Tracked comparison output: {output_file_path}")
            return True
            
        except Exception as e:
            print(f"Error tracking comparison output: {e}")
            return False

    def _extract_scenarios(self, state: AgentState) -> AgentState:
        """Extract scenario names from user request using LLM for complex pattern matching"""
        print(f"🔍 DEBUG: _extract_scenarios called")
        print(f"🔍 DEBUG: User request: '{state.get('user_request', '')}'")
        
        user_request = state.get("user_request", "")
        if not user_request:
            return state
        
        # Get all available scenarios
        if not self.scenario_manager:
            print(f"🔍 DEBUG: No scenario manager available")
            return state
        
        all_scenarios = self.scenario_manager.list_scenarios()
        scenario_names = [s.name for s in all_scenarios]
        print(f"🔍 DEBUG: Available scenarios: {scenario_names}")
        
        # Use LLM to extract scenario names from complex requests
        system_prompt = f"""You are an expert at identifying scenario names from user requests for a multi-scenario comparison system.

Available scenarios: {scenario_names}

Your task is to extract the scenario names that the user wants to compare from their request.

EXAMPLES:
- "compare base and test1" → ["Base Scenario", "test1"]
- "compare the demand for birmingham in base and test1" → ["Base Scenario", "test1"]
- "show differences between base scenario and test scenario" → ["Base Scenario", "test1"]
- "compare base vs test1" → ["Base Scenario", "test1"]
- "compare demand across base and test1" → ["Base Scenario", "test1"]
- "compare the top 10 hubs by demand across base and test1" → ["Base Scenario", "test1"]
- "base scenario versus test1" → ["Base Scenario", "test1"]
- "compare base, test1, and scenario1" → ["Base Scenario", "test1", "Scenario1"]

RULES:
1. Look for scenario names that appear in the available scenarios list
2. Use fuzzy matching - "base" should match "Base Scenario"
3. Use substring matching - "test" should match "test1"
4. Ignore extra words like "demand", "birmingham", "hubs", etc.
5. Return ONLY the scenario names, not the extra context
6. Return at least 2 scenarios for a valid comparison
7. If you can't find at least 2 scenarios, return an empty list

Respond with ONLY a JSON array of scenario names, like: ["Base Scenario", "test1"]"""

        try:
            response = self._get_llm().invoke([
                HumanMessage(content=f"{system_prompt}\n\nUser request: {user_request}")
            ])
            
            # Parse the response
            content = response.content.strip()
            print(f"🔍 DEBUG: LLM response: {content}")
            
            # Try to extract JSON array from response
            import re
            import json
            
            # Look for JSON array pattern
            json_match = re.search(r'\[.*?\]', content)
            if json_match:
                try:
                    extracted_scenarios = json.loads(json_match.group())
                    print(f"🔍 DEBUG: Extracted scenarios from JSON: {extracted_scenarios}")
                except json.JSONDecodeError:
                    print(f"🔍 DEBUG: Failed to parse JSON, trying alternative extraction")
                    extracted_scenarios = self._fallback_scenario_extraction(content, scenario_names)
            else:
                # Fallback: try to extract scenario names from text
                extracted_scenarios = self._fallback_scenario_extraction(content, scenario_names)
            
            # Validate extracted scenarios against available scenarios
            valid_scenarios = []
            for extracted in extracted_scenarios:
                best_match = self._find_best_scenario_match(extracted, scenario_names)
                if best_match:
                    valid_scenarios.append(best_match)
                    print(f"🔍 DEBUG: Matched '{extracted}' to '{best_match}'")
            
            print(f"🔍 DEBUG: Final valid scenarios: {valid_scenarios}")
            
            if len(valid_scenarios) >= 2:
                # Create comparison database context
                db_context = self._create_comparison_database_context(valid_scenarios)
                comparison_type = self._determine_comparison_type(user_request)
                
                return {
                    **state,
                    "comparison_scenarios": valid_scenarios,
                    "comparison_data": {},
                    "comparison_type": comparison_type,
                    "scenario_name_mapping": {name: i for i, name in enumerate(valid_scenarios)},
                    "db_context": db_context,
                    "messages": state["messages"] + [AIMessage(content=f"🎯 Extracted scenarios: {', '.join(valid_scenarios)}")]
                }
            else:
                print(f"🔍 DEBUG: Not enough valid scenarios found: {valid_scenarios}")
                return {
                    **state,
                    "messages": state["messages"] + [AIMessage(content=f"❌ Could not identify at least 2 scenarios to compare. Available scenarios: {', '.join(scenario_names)}")]
                }
                
        except Exception as e:
            print(f"🔍 DEBUG: Error in scenario extraction: {e}")
            return {
                **state,
                "messages": state["messages"] + [AIMessage(content=f"❌ Error extracting scenarios: {str(e)}")]
            }
    
    def _fallback_scenario_extraction(self, llm_response: str, available_scenarios: List[str]) -> List[str]:
        """Fallback method to extract scenario names from LLM response text"""
        extracted = []
        
        # Look for scenario names in the response
        for scenario in available_scenarios:
            if scenario.lower() in llm_response.lower():
                extracted.append(scenario)
        
        # Also look for partial matches
        for scenario in available_scenarios:
            scenario_words = scenario.lower().split()
            for word in scenario_words:
                if len(word) > 2 and word in llm_response.lower():
                    if scenario not in extracted:
                        extracted.append(scenario)
                    break
        
        return extracted
    
    def _find_best_scenario_match(self, extracted_name: str, available_scenarios: List[str]) -> Optional[str]:
        """Find the best matching scenario name using fuzzy matching"""
        import difflib
        
        extracted_lower = extracted_name.lower()
        
        # Try exact match first
        for scenario in available_scenarios:
            if extracted_lower == scenario.lower():
                return scenario
        
        # Try substring match
        for scenario in available_scenarios:
            if extracted_lower in scenario.lower() or scenario.lower() in extracted_lower:
                return scenario
        
        # Try word-based matching
        extracted_words = extracted_lower.split()
        for scenario in available_scenarios:
            scenario_words = scenario.lower().split()
            if any(word in scenario_words for word in extracted_words):
                return scenario
        
        # Try fuzzy matching
        best_match = None
        best_score = 0
        for scenario in available_scenarios:
            score = difflib.SequenceMatcher(None, extracted_lower, scenario.lower()).ratio()
            if score > best_score and score >= 0.6:
                best_score = score
                best_match = scenario
        
        return best_match


def create_agent_v2(ai_model: str = "openai", scenario_manager: ScenarioManager = None) -> SimplifiedAgent:
    """Create a new simplified agent instance"""
    return SimplifiedAgent(ai_model=ai_model, scenario_manager=scenario_manager) 