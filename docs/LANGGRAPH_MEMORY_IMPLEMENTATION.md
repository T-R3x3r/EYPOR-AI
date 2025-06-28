# LangGraph-Only Implementation with Human-in-the-Loop

## Overview

This document explains the **LangGraph-only implementation** with built-in memory and **human-in-the-loop (HITL)** functionality in the EY Project system. The manual memory system has been removed in favor of LangGraph's native capabilities.

## Core Architecture

### LangGraph Memory System

**Automatic State Persistence**: LangGraph handles all conversation state through checkpointers
- **SQLite Checkpointer**: Persistent disk-based storage (preferred)
- **Memory Checkpointer**: In-memory storage (fallback)
- **Thread-based Conversations**: Multiple conversation threads with unique IDs
- **Automatic Checkpointing**: State saved after each node execution

### Human-in-the-Loop Framework

**Interrupt-based Approval**: Workflow pauses for human approval on high-risk operations
- **Approval Nodes**: Dedicated nodes for requesting human approval
- **Workflow Interrupts**: Graph execution pauses at approval points
- **Continuation**: Workflow resumes after human response
- **Multi-level Approval**: Support for cascading approval requests

## Implementation Details

### Backend: LangGraph Agent

#### Memory Infrastructure

```python
class CodeExecutorAgent:
    def __init__(self, ai_model: str = "openai", temp_dir: str = "", agent_type: str = None):
        # Initialize LangGraph memory checkpointer
        self.checkpointer = self._initialize_memory()
        
        # Build graph with memory and interrupts
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
        """Build workflow with memory and human-in-the-loop"""
        workflow = StateGraph(AgentState)
        
        # Add human-in-the-loop nodes
        workflow.add_node("request_approval", self._request_approval_node)
        workflow.add_node("process_approval", self._process_approval_node)
        workflow.add_node("human_feedback", self._human_feedback_node)
        
        # Approval workflow
        workflow.add_edge("request_approval", END)  # Interrupt for human approval
        workflow.add_edge("process_approval", "execute_file")  # Continue after approval
        workflow.add_edge("human_feedback", "vanna_generator")  # Retry with feedback
        
        return workflow.compile(checkpointer=self.checkpointer)
```

#### Human-in-the-Loop Nodes

```python
def _request_approval_node(self, state: AgentState) -> AgentState:
    """Request human approval for high-risk operations"""
    approval_id = str(uuid.uuid4())
    
    # Determine what needs approval
    if state.get("action_type") == "DATABASE_MODIFICATION":
        approval_message = f"🚨 **Database Modification Request**\n\n"
        approval_message += f"The system wants to modify the database:\n"
        # ... detailed approval message
    
    return {
        **state,
        "approval_required": True,
        "approval_message": approval_message,
        "pending_approval": {
            "id": approval_id,
            "type": state.get("action_type", "UNKNOWN"),
            "message": approval_message,
            "data": approval_data,
            "timestamp": time.time()
        },
        "interrupt_reason": "APPROVAL_REQUIRED",
        "messages": state["messages"] + [AIMessage(content=approval_message)]
    }

def _process_approval_node(self, state: AgentState) -> AgentState:
    """Process human approval response"""
    user_feedback = state.get("user_feedback", "").lower().strip()
    
    if "approve" in user_feedback or "yes" in user_feedback:
        return {
            **state,
            "approval_required": False,
            "pending_approval": {},
            "messages": state["messages"] + [AIMessage(content="✅ **Approved by user** - Proceeding...")]
        }
    # ... handle reject/feedback cases
```

#### Workflow Execution with Interrupts

```python
def run(self, user_message: str, thread_id: str = "default", user_feedback: str = ""):
    """Run workflow with memory and human-in-the-loop"""
    config = {"configurable": {"thread_id": thread_id}}
    
    # Use stream to handle interrupts
    for chunk in self.graph.stream(initial_state, config=config):
        # Check for interrupts (approval requests)
        if isinstance(chunk, dict):
            for node_name, node_state in chunk.items():
                if node_state.get("approval_required"):
                    # Return approval request to frontend
                    return self._format_approval_response(node_state), []
    
    # Workflow completed without interrupts
    return full_response, created_files

def continue_after_approval(self, thread_id: str, approval_response: str):
    """Continue workflow after receiving human approval"""
    config = {"configurable": {"thread_id": thread_id}}
    
    # Get current state from checkpointer
    checkpoint = self.checkpointer.get(config)
    current_state = checkpoint.values
    current_state["user_feedback"] = approval_response
    
    # Continue workflow from checkpoint
    for chunk in self.graph.stream(current_state, config=config):
        # Handle additional interrupts or completion
        pass
```

### API Endpoints

#### Core Chat with Memory

```python
@app.post("/action-chat")
async def action_chat(request: ActionRequest):
    """Chat with LangGraph memory and HITL support"""
    agent = get_or_create_agent()
    
    response, created_files = agent.run(
        user_message=request.message,
        thread_id=request.thread_id,
        user_feedback=""
    )
    
    # Check if response requires approval
    if "APPROVAL_REQUIRED" in response:
        return {
            "response": response,
            "requires_approval": True,
            "thread_id": request.thread_id
        }
    else:
        return {
            "response": response,
            "requires_approval": False,
            "thread_id": request.thread_id
        }
```

#### Human-in-the-Loop Endpoints

```python
@app.post("/approval/respond")
async def respond_to_approval(request: ApprovalRequest):
    """Respond to approval request"""
    agent = get_or_create_agent()
    
    response, created_files = agent.continue_after_approval(
        thread_id=request.thread_id,
        approval_response=request.approval_response
    )
    
    return {
        "response": response,
        "requires_approval": "APPROVAL_REQUIRED" in response,
        "created_files": created_files
    }

@app.get("/approval/status/{thread_id}")
async def get_approval_status(thread_id: str):
    """Get pending approval status"""
    agent = get_or_create_agent()
    config = {"configurable": {"thread_id": thread_id}}
    checkpoint = agent.checkpointer.get(config)
    
    if checkpoint and checkpoint.values.get("pending_approval"):
        return {
            "has_pending_approval": True,
            "approval_data": checkpoint.values["pending_approval"]
        }
    return {"has_pending_approval": False}
```

### Frontend: Simplified Chat Service

#### LangGraph-Only Memory

```typescript
export interface ChatState {
  messages: ChatMessage[];
  isLoading: boolean;
  threadId: string;
  pendingApproval?: ChatMessage;  // HITL support
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

  // Human-in-the-loop support
  setPendingApproval(message: ChatMessage): void {
    this.updateState({
      ...this.getCurrentState(),
      pendingApproval: message
    });
  }
}
```

#### Chat Component with HITL

```typescript
export class ChatComponent {
  async sendMessage(): Promise<void> {
    const threadId = this.chatService.getCurrentThreadId();
    
    // Check if this is an approval response
    if (this.chatState.pendingApproval) {
      await this.handleApprovalResponse(messageToSend, threadId);
      return;
    }
    
    // Send regular message
    const response = await this.apiService.actionChat(
      messageToSend, 
      actionType, 
      [], // No manual history - LangGraph handles this
      threadId
    ).toPromise();

    // Handle approval requests
    if (response.requires_approval) {
      this.handleApprovalRequest(response, threadId);
    } else {
      this.addAssistantMessage(response.response);
    }
  }

  async handleApprovalResponse(approvalResponse: string, threadId: string): Promise<void> {
    const response = await this.apiService.respondToApproval(
      threadId,
      approvalResponse
    ).toPromise();

    this.chatService.clearPendingApproval();
    
    if (response.requires_approval) {
      this.handleApprovalRequest(response, threadId);
    } else {
      this.addAssistantMessage(response.response);
    }
  }

  // Quick approval actions
  approveOperation(): void {
    this.currentMessage = 'approve';
    this.sendMessage();
  }

  rejectOperation(): void {
    this.currentMessage = 'reject';
    this.sendMessage();
  }
}
```

## Human-in-the-Loop Features

### Approval Triggers

1. **Database Modifications**: Parameter changes, data updates
2. **File Execution**: Running Python scripts that modify system state
3. **High-Risk Operations**: Delete operations, system modifications
4. **Custom Triggers**: Configurable approval requirements

### Approval Types

1. **✅ Approve**: Allow operation to proceed
2. **❌ Reject**: Cancel operation completely
3. **💬 Provide Feedback**: Give specific instructions for modification

### Workflow Interrupts

```python
# Workflow pauses at approval nodes
workflow.add_edge("request_approval", END)  # Interrupt

# User provides approval response
approval_response = "approve"  # or "reject" or feedback

# Workflow continues from checkpoint
agent.continue_after_approval(thread_id, approval_response)
```

## Key Benefits

### LangGraph-Only Advantages

1. **Native Memory**: No manual context passing required
2. **Persistent State**: Conversations survive server restarts
3. **Thread Management**: Multiple parallel conversations
4. **Complex State**: Full agent state, not just messages
5. **Automatic Checkpointing**: State saved after each step

### Human-in-the-Loop Benefits

1. **Risk Mitigation**: Human oversight for dangerous operations
2. **Quality Control**: Review before execution
3. **Flexible Approval**: Approve, reject, or provide feedback
4. **Workflow Continuity**: Seamless resume after approval
5. **Audit Trail**: Full record of approvals and decisions

## Implementation Status

### ✅ Completed Features

1. **LangGraph Memory**: SQLite/Memory checkpointers
2. **Thread-based Conversations**: Multi-threaded support
3. **Human-in-the-Loop Nodes**: Approval workflow nodes
4. **Workflow Interrupts**: Pause/resume functionality
5. **API Endpoints**: Approval and memory management
6. **Frontend Integration**: Basic HITL support

### 🔄 In Progress

1. **Frontend UI**: Approval interface components
2. **Error Handling**: Graceful fallback mechanisms
3. **Testing**: Comprehensive HITL testing

### 📋 Future Enhancements

1. **Approval UI**: Rich approval interface with operation details
2. **Approval Policies**: Configurable approval requirements
3. **Audit Dashboard**: View approval history and patterns
4. **Batch Approvals**: Approve multiple operations at once
5. **Approval Delegation**: Assign approvals to specific users

## Usage Examples

### Basic Conversation with Memory

```typescript
// Start conversation
this.apiService.actionChat("Show me the database schema", undefined, [], "thread_1");

// Continue in same thread - LangGraph remembers context
this.apiService.actionChat("Now show me the top 10 records", undefined, [], "thread_1");
```

### Human-in-the-Loop Approval

```typescript
// User requests database modification
this.apiService.actionChat("Change the maximum capacity to 5000", "DATABASE_MODIFICATION", [], "thread_1");

// System responds with approval request
// Response: "🚨 Database Modification Request - Do you want to proceed?"

// User approves
this.apiService.respondToApproval("thread_1", "approve");

// System continues and executes the modification
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

The LangGraph-only implementation with human-in-the-loop provides a robust, scalable solution for AI-assisted operations with human oversight. By leveraging LangGraph's native memory and interrupt capabilities, the system offers true conversation continuity and safe execution of potentially risky operations through human approval workflows. 