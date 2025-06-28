# Action-Based System Implementation

## Overview

This document describes the implementation of a new **Action-Based System** that provides intelligent request classification and specialized routing for optimal processing of user queries. This system addresses the issue where parameter change requests like "change the maximum hub demand to 20000" were being incorrectly processed as SQL queries instead of database modifications.

## Problem Solved

**Original Issue:** 
```
Query: in the input params change the maxium hub demand to 20000
Generated SQL: SELECT name as Table_Name FROM sqlite_master WHERE type='table' ORDER BY name
```

The system was treating parameter change requests as regular SQL queries, which made no sense.

## Solution: Action-Based Routing

The new system implements intelligent request classification that routes different types of requests to specialized handlers:

### 1. **Action Types**

#### 🎯 SQL_QUERY
- **Purpose**: Execute database queries and data analysis
- **Examples**: 
  - "Show me the top 10 hubs with highest demand"
  - "What is the total demand by region?"
  - "List all operating hubs"

#### 📈 VISUALIZATION  
- **Purpose**: Create charts, maps, and visual representations
- **Examples**:
  - "Create a map of hub allocations"
  - "Visualize demand distribution" 
  - "Show hub performance chart"

#### ⚙️ DATABASE_MODIFICATION
- **Purpose**: Modify database parameters and re-run models
- **Examples**:
  - "Change maximum hub demand to 20000"
  - "Set opening cost to 5000"
  - "Update route supply limit"

## Architecture

### Backend Implementation

#### 1. **Request Classification** (`_classify_user_request()`)
```python
def _classify_user_request(self, message: str) -> str:
    """Classify the user's request to determine the appropriate action type"""
    message_lower = message.lower()
    
    # Database modification patterns
    db_modification_patterns = ['change', 'update', 'set', 'modify', 'alter', 'adjust']
    parameter_patterns = ['parameter', 'param', 'maximum', 'minimum', 'limit', 'cost']
    
    # Visualization patterns  
    visualization_patterns = ['visualiz', 'visual', 'chart', 'graph', 'plot', 'map']
    
    # SQL query patterns
    sql_patterns = ['select', 'query', 'find', 'search', 'get', 'retrieve']
```

#### 2. **Action Router Node** (`_action_router_node()`)
- Classifies incoming requests
- Routes to appropriate specialized handlers
- Provides clear feedback about detected action type

#### 3. **Specialized Handlers**

**Database Modification Agent** (`_database_modification_agent()`):
- Detects parameter change patterns
- Updates database parameters
- Generates and executes model re-run scripts
- Provides feedback on parameter changes

**Enhanced Visualization Agent** (`_visualization_agent_node()`):
- Handles visualization requests directly
- Creates custom Python scripts for different visualization types
- Supports maps, bar charts, line charts, scatter plots, pie charts
- Generates interactive Plotly visualizations

**SQL Query Handler** (existing Vanna integration):
- Processes traditional database queries
- Generates and executes SQL
- Returns tabular results

### Frontend Implementation

#### 1. **Action Type Selector**
- Optional dropdown to manually specify action type
- Auto-detection when no type is specified
- Real-time examples and descriptions

#### 2. **System Toggle**
- Switch between Action-Based and Traditional systems
- Visual indicators of current mode
- Different welcome screens for each mode

#### 3. **Specialized Response Handling**
- Different UI handling for each action type
- Visualization files automatically displayed
- Parameter change feedback with execution results

## API Endpoints

### `/action-chat` (POST)
```typescript
interface ActionRequest {
  message: string;
  action_type?: string; // Optional manual specification
}

interface ActionResponse {
  response?: string;
  action_type: string;
  success: boolean;
  error?: string;
  // Type-specific fields
  sql_query?: string;
  result_data?: any[];
  created_files?: string[];
  output_files?: OutputFile[];
  parameter_updated?: string;
  new_value?: any;
  execution_output?: string;
  execution_error?: string;
}
```

### `/action-types` (GET)
Returns available action types with descriptions and examples.

## Benefits

### 1. **Intelligent Routing**
- No more parameter changes treated as SQL queries
- Each request type gets optimal processing
- Specialized handlers for maximum efficiency

### 2. **Enhanced User Experience**
- Clear feedback about detected action type
- Optional manual action type selection
- Type-specific examples and guidance

### 3. **Better Results**
- Database modifications actually update parameters AND re-run models
- Visualizations get dedicated processing pipeline
- SQL queries optimized for data retrieval

### 4. **Extensible Architecture**
- Easy to add new action types
- Modular handler system
- Clear separation of concerns

## Usage Examples

### Example 1: Database Modification
```
User: "Change the maximum hub demand to 20000"
System: 🎯 Action Type: Database Modification
Response: ⚙️ Successfully updated Maximum_Hub_Demand to 20000
         🔄 Model Re-run Results: [execution output]
```

### Example 2: Visualization
```
User: "Create a map showing hub allocations"
System: 🎯 Action Type: Visualization  
Response: 🎨 Created custom visualization script. Executing...
Files: hub_allocation_map.html, visualization_script.py
```

### Example 3: SQL Query
```
User: "Show me the top 10 hubs with highest demand"
System: 🎯 Action Type: SQL Query
Response: [SQL results table with top 10 hubs]
```

## Future Enhancements

### Planned Features
1. **Action History**: Track and replay previous actions
2. **Batch Actions**: Process multiple actions in sequence
3. **Action Templates**: Pre-defined action patterns
4. **Advanced Visualization Types**: 3D plots, animations, dashboards
5. **Model Comparison**: Compare results before/after parameter changes

### Extensibility
- New action types can be added by:
  1. Adding classification patterns
  2. Implementing specialized handler
  3. Adding routing logic
  4. Updating frontend UI

## Technical Notes

### Classification Accuracy
- Uses pattern matching with multiple keyword sets
- Considers context and combinations of patterns
- Falls back to SQL_QUERY for ambiguous cases
- Manual override always available

### Error Handling
- Each action type has specific error handling
- Graceful fallbacks to alternative methods
- Clear error messages with action type context
- Automatic retry mechanisms where appropriate

### Performance
- Parallel processing where possible
- Specialized pipelines avoid unnecessary overhead
- Cached action type definitions
- Efficient routing decisions

## Migration Guide

### For Existing Users
1. **Automatic**: System automatically classifies existing query patterns
2. **Optional**: Can still use traditional system via toggle
3. **Enhanced**: Better results for parameter changes and visualizations
4. **Compatible**: All existing queries continue to work

### For Developers
1. **Backend**: New endpoints complement existing ones
2. **Frontend**: Action system can be enabled/disabled
3. **API**: Backward compatible with existing endpoints
4. **Extensions**: Easy to add new action types

---

**Implementation Status**: ✅ Complete - Ready for testing and deployment 