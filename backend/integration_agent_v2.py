"""
Integration guide for using the new SimplifiedAgent v2 in main.py

This shows how to integrate the new agent that properly handles scenario database routing.
"""

# Add this import at the top of main.py
from langgraph_agent_v2 import SimplifiedAgent, create_agent_v2
from main import get_current_ai, scenario_manager, app, log_execution_to_scenario, ChatMessage, ActionRequest
from fastapi import Request

# Global agent instance (add this with other globals)
agent_v2 = None

def get_or_create_agent_v2():
    """Get or create the simplified agent v2 instance"""
    global agent_v2
    
    if agent_v2 is None:
        # Get the current AI model setting
        current_ai = get_current_ai()  # This function already exists in main.py
        ai_model = current_ai.get("model", "openai")
        
        # Create agent with scenario manager
        agent_v2 = create_agent_v2(ai_model=ai_model, scenario_manager=scenario_manager)
    
    return agent_v2

# Replace the existing langgraph_chat endpoint with this version:
@app.post("/langgraph-chat-v2")
async def langgraph_chat_v2(message: ChatMessage, request: Request = None):
    """Enhanced chat endpoint using the new simplified agent v2"""
    try:
        # Get the agent
        agent = get_or_create_agent_v2()
        
        # Get current scenario ID for context
        current_scenario = scenario_manager.get_current_scenario()
        scenario_id = current_scenario.id if current_scenario else None
        
        # Run the agent
        response, generated_files = agent.run(
            user_message=message.content,
            scenario_id=scenario_id
        )
        
        # Log execution to scenario history if files were generated
        if generated_files:
            log_execution_to_scenario(
                command=f"Agent v2: {message.content}",
                output=response,
                output_files=generated_files
            )
        
        return {
            "response": response,
            "generated_files": generated_files,
            "scenario_id": scenario_id,
            "agent_version": "v2"
        }
        
    except Exception as e:
        print(f"ERROR in langgraph_chat_v2: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "response": f"❌ Error: {str(e)}",
            "generated_files": [],
            "scenario_id": None,
            "agent_version": "v2"
        }

# Modified action chat endpoint to use agent v2:
@app.post("/action-chat-v2")
async def action_chat_v2(request: ActionRequest):
    """Enhanced action chat using simplified agent v2"""
    try:
        # Get the agent
        agent = get_or_create_agent_v2()
        
        # Get current scenario
        current_scenario = scenario_manager.get_current_scenario()
        scenario_id = current_scenario.id if current_scenario else None
        
        # Run the agent (it will automatically classify and route the request)
        response, generated_files = agent.run(
            user_message=request.message,
            scenario_id=scenario_id
        )
        
        # Log to scenario history
        if generated_files or "modification completed" in response.lower():
            log_execution_to_scenario(
                command=f"Action v2: {request.message}",
                output=response,
                output_files=generated_files
            )
        
        return {
            "response": response,
            "generated_files": generated_files,
            "scenario_id": scenario_id,
            "classification": "auto-detected",
            "agent_version": "v2"
        }
        
    except Exception as e:
        print(f"ERROR in action_chat_v2: {e}")
        return {
            "response": f"❌ Error: {str(e)}",
            "generated_files": [],
            "scenario_id": None,
            "agent_version": "v2"
        }

# Add endpoint to switch between agent versions:
@app.post("/switch-agent-version")
async def switch_agent_version(request: dict):
    """Switch between agent v1 and v2"""
    global agent_v2
    
    version = request.get("version", "v2")
    
    if version == "v2":
        # Initialize v2 agent
        agent_v2 = None  # Force recreation
        get_or_create_agent_v2()
        return {"message": "Switched to Agent v2 (Simplified with proper scenario routing)", "version": "v2"}
    else:
        return {"message": "Agent v1 is still available through existing endpoints", "version": "v1"}

@app.get("/agent-version")
async def get_agent_version():
    """Get current agent version info"""
    return {
        "v1_available": True,
        "v2_available": agent_v2 is not None,
        "v2_features": [
            "Proper scenario database routing",
            "Simplified workflow", 
            "Chat without code execution",
            "Always uses current scenario DB",
            "Plotly-only visualizations",
            "Preserved DB modification logic"
        ]
    }

# Instructions for frontend integration:
"""
Frontend Integration Notes:

1. Update the chat service to use the new endpoints:
   - /langgraph-chat-v2 for general chat
   - /action-chat-v2 for action-based requests
   
2. The new agent automatically:
   - Routes requests to appropriate handlers
   - Uses the current scenario's database
   - Generates Plotly visualizations
   - Handles chat without unnecessary code execution
   
3. Response format includes:
   - response: The agent's response text
   - generated_files: List of created files
   - scenario_id: Current scenario ID
   - agent_version: "v2"
   
4. All generated files will be created in the scenario's database directory,
   ensuring proper scenario isolation.
""" 