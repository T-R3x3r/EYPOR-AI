# LangGraph-Only Implementation with Memory

## Overview

This document explains the **LangGraph-only implementation** with built-in memory in the EY Project system. The manual memory system has been removed in favor of LangGraph's native capabilities.

## Core Architecture

### LangGraph Memory System

**Automatic State Persistence**: LangGraph handles all conversation state through checkpointers
- **SQLite Checkpointer**: Persistent disk-based storage (preferred)
- **Memory Checkpointer**: In-memory storage (fallback)
- **Thread-based Conversations**: Multiple conversation threads with unique IDs
- **Automatic Checkpointing**: State saved after each node execution

## Implementation Details

### Backend: LangGraph Agent

#### Memory Infrastructure

```python
class CodeExecutorAgent:
    def __init__(self, ai_model: str = "openai", temp_dir: str = "", agent_type: str = None):
        # Initialize LangGraph memory checkpointer
        self.checkpointer = self._initialize_memory()
        
        # Build graph with memory
        self.graph = self._build_graph()

    def _initialize_memory(self):
        """Initialize LangGraph memory checkpointer"""
        try:
            # SQLite checkpointer for persistent memory
            memory_db_path = os.path.join(self.temp_dir, "langgraph_memory.db")
            from langgraph.checkpoint.sqlite import SqliteSaver
            return SqliteSaver.from_conn_string(f"sqlite:///{memory_db_path}")
        except ImportError:
            # Fallback to in-memory checkpointer
            from langgraph.checkpoint.memory import MemorySaver
            return MemorySaver()

    def _build_graph(self):
        """Build workflow with memory"""
        workflow = StateGraph(AgentState)
        
        # Add model selection node (only human-in-the-loop that actually works)
        workflow.add_node("request_model_selection", self._request_model_selection_node)
        
        # Model selection workflow
        workflow.add_edge("request_model_selection", END)  # Interrupt for model selection
        
        return workflow.compile(checkpointer=self.checkpointer)
```

#### Model Selection Node (Only Working HITL)

```python
def _request_model_selection_node(self, state: AgentState) -> AgentState:
    """Request user to select which models to run"""
    available_models = state.get("available_models", [])
    
    selection_message = "🔧 **Model Selection Required**\n\n"
    selection_message += "The following Python model files were found:\n\n"
    
    for i, model in enumerate(available_models, 1):
        selection_message += f"{i}. {model}\n"
    
    selection_message += "\nWhich models would you like to execute? (provide numbers separated by commas, or 'all' for all models)"
    
    return {
        **state,
        "approval_required": True,
        "approval_message": selection_message,
        "pending_approval": {
            "type": "MODEL_SELECTION",
            "models": available_models,
            "message": selection_message
        },
        "interrupt_reason": "MODEL_SELECTION_REQUIRED",
        "messages": state["messages"] + [AIMessage(content=selection_message)]
    }
```

#### Workflow Execution

```python
def run(self, user_message: str, thread_id: str = "default", user_feedback: str = ""):
    """Run workflow with memory"""
    config = {"configurable": {"thread_id": thread_id}}
    
    # Use stream to handle interrupts
    for chunk in self.graph.stream(initial_state, config=config):
        # Check for interrupts (model selection requests)
        if isinstance(chunk, dict):
            for node_name, node_state in chunk.items():
                if node_state.get("approval_required"):
                    # Return model selection request to frontend
                    return self._format_model_selection_response(node_state), []
    
    # Workflow completed without interrupts
    return full_response, created_files
```

### API Endpoints

#### Core Chat with Memory

```python
@app.post("/action-chat")
async def action_chat(request: ActionRequest):
    """Chat with LangGraph memory"""
    agent = get_or_create_agent()
    
    response, created_files = agent.run(
        user_message=request.message,
        thread_id=request.thread_id,
        user_feedback=""
    )
    
    # Check if response requires model selection
    if "MODEL_SELECTION_REQUIRED" in response:
        return {
            "response": response,
            "requires_model_selection": True,
            "thread_id": request.thread_id
        }
    else:
        return {
            "response": response,
            "requires_model_selection": False,
            "thread_id": request.thread_id
        }
```

#### Model Selection Endpoints

```python
@app.post("/approval/respond")
async def respond_to_model_selection(request: ApprovalRequest):
    """Respond to model selection request"""
    agent = get_or_create_agent()
    
    response, created_files = agent.continue_after_model_selection(
        thread_id=request.thread_id,
        selection_response=request.approval_response
    )
    
    return {
        "response": response,
        "requires_model_selection": "MODEL_SELECTION_REQUIRED" in response,
        "created_files": created_files
    }

@app.get("/approval/status/{thread_id}")
async def get_model_selection_status(thread_id: str):
    """Get pending model selection status"""
    agent = get_or_create_agent()
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint = agent.checkpointer.get(config)
    
    if checkpoint and checkpoint.values.get("pending_approval"):
        return {
            "has_pending_selection": True,
            "selection_data": checkpoint.values["pending_approval"]
        }
    return {"has_pending_selection": False}
```

### Frontend: Simplified Chat Service

#### LangGraph-Only Memory

```typescript
export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  threadId: string;
  pendingModelSelection?: ChatMessage;  // Model selection support
}

@Injectable({providedIn: 'root'})
export class ChatService {
  private chatStateSubject = new BehaviorSubject<ChatState>({
    messages: [],
    isLoading: false,
    threadId: 'default'
  });

  // No localStorage - LangGraph handles all persistence
  // Thread management
  switchThread(threadId: string): void {
    this.updateState({
      ...this.getCurrentState(),
      threadId,
      messages: [] // LangGraph will load messages
    });
  }

  // Model selection support
  setPendingModelSelection(message: ChatMessage): void {
    this.updateState({
      ...this.getCurrentState(),
      pendingModelSelection: message
    });
  }
}
```

#### Chat Component with Model Selection

```typescript
export class ChatComponent {
  async sendMessage(): Promise<void> {
    const threadId = this.chatService.getCurrentThreadId();
    
    // Check if this is a model selection response
    if (this.chatState.pendingModelSelection) {
      await this.handleModelSelectionResponse(messageToSend, threadId);
      return;
    }
    
    // Send regular message
    const response = await this.apiService.actionChat(
      messageToSend, 
      actionType, 
      [], // No manual history - LangGraph handles this
      threadId
    ).toPromise();

    // Handle model selection requests
    if (response.requires_model_selection) {
      this.handleModelSelectionRequest(response, threadId);
    } else {
      this.addAssistantMessage(response.response);
    }
  }

  async handleModelSelectionResponse(selectionResponse: string, threadId: string): Promise<void> {
    const response = await this.apiService.respondToModelSelection(
      threadId,
      selectionResponse
    ).toPromise();

    this.chatService.clearPendingModelSelection();
    
    if (response.requires_model_selection) {
      this.handleModelSelectionRequest(response, threadId);
    } else {
      this.addAssistantMessage(response.response);
    }
  }
}
```

## Model Selection Features

### Selection Triggers

1. **Database Modifications**: After parameter changes, system discovers available models
2. **Model Discovery**: Automatically finds relevant model files
3. **Runall Priority**: Highlights and recommends runall files

### Selection Types

1. **✅ Select Models**: Choose specific models to run
2. **❌ Skip Models**: Continue without running models
3. **💬 Provide Feedback**: Give specific instructions for model execution

### Workflow Interrupts

```python
# Workflow pauses at model selection nodes
workflow.add_edge("request_model_selection", END)  # Interrupt

# User provides model selection response
selection_response = "1,2,3"  # or "all" or "skip"

# Workflow continues from checkpoint
agent.continue_after_model_selection(thread_id, selection_response)
```

## Key Benefits

### LangGraph-Only Advantages

1. **Native Memory**: No manual context passing required
2. **Persistent State**: Conversations survive server restarts
3. **Thread Management**: Multiple parallel conversations
4. **Complex State**: Full agent state, not just messages
5. **Automatic Checkpointing**: State saved after each step

### Model Selection Benefits

1. **User Control**: Always asks before running models
2. **Smart Discovery**: Automatically finds relevant model files
3. **Runall Priority**: Highlights and recommends runall files
4. **Database Preservation**: Maintains database state with change highlighting

## Implementation Status

### ✅ Completed Features

1. **LangGraph Memory**: SQLite/Memory checkpointers
2. **Thread-based Conversations**: Multi-threaded support
3. **Model Selection Node**: Working model selection workflow
4. **Workflow Interrupts**: Pause/resume functionality for model selection
5. **API Endpoints**: Model selection and memory management
6. **Frontend Integration**: Basic model selection support

### 🔄 In Progress

1. **Frontend UI**: Model selection interface components
2. **Error Handling**: Graceful fallback mechanisms
3. **Testing**: Comprehensive model selection testing

### 📋 Future Enhancements

1. **Selection UI**: Rich model selection interface with operation details
2. **Selection Policies**: Configurable model selection requirements
3. **Audit Dashboard**: View model execution history and patterns
4. **Batch Selection**: Select multiple models at once
5. **Selection Delegation**: Assign model selection to specific users

## Usage Examples

### Basic Conversation with Memory

```typescript
// Start conversation
this.apiService.actionChat("Show me the database schema", undefined, [], "thread_1");

// Continue in same thread - LangGraph remembers context
this.apiService.actionChat("Now show me the top 10 records", undefined, [], "thread_1");
```

### Model Selection

```typescript
// User requests database modification
this.apiService.actionChat("Change the maximum capacity to 5000", "DATABASE_MODIFICATION", [], "thread_1");

// System responds with model selection request
// Response: "🔧 Model Selection Required - Which models would you like to run?"

// User selects models
this.apiService.respondToModelSelection("thread_1", "1,2,3");

// System continues and executes the selected models
```

### Thread Management

```typescript
// Create new conversation thread
const newThreadId = this.chatService.createNewThread();

// Switch between threads
this.chatService.switchThread("thread_analytics");
this.chatService.switchThread("thread_modifications");

// Each thread maintains independent conversation history
```

## Conclusion

The LangGraph-only implementation with model selection provides a robust, scalable solution for AI-assisted operations with user control over model execution. By leveraging LangGraph's native memory and interrupt capabilities, the system offers true conversation continuity and controlled execution of models through user selection workflows. 