import sys
import uuid
import asyncio
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Enforce UTF-8 coding schemas for clean terminal outputs on Windows machines
if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

# Core engine imports
from app.graph import compiled_graph
from app.database import save_debate_session

app = FastAPI(
    title="Cyber Court API Gateway",
    description="Asynchronous input-driven server linking frontend states to dynamic LangGraph nodes.",
    version="1.1.0"
)

# CORS middleware configured broadly to allow local development connections from v0/Bolt.new
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 📋 1. Structured Schema for JSON API Inputs
class DynamicDebateConfig(BaseModel):
    topic: str = "AI should replace human judges"
    max_rounds: int = 2
    prosecutor_persona: str = "Tech Optimist"
    defender_persona: str = "Civil Liberties Advocate"
    session_id: Optional[str] = None

@app.get("/")
async def root():
    return {"status": "online", "engine": "AI Courtroom Input Core"}

# ⚡ 2. Real-Time Interactive WebSocket Endpoint
@app.websocket("/ws/debate")
async def websocket_debate(websocket: WebSocket):
    """
    WebSocket channel that accepts dynamic user inputs from the React frontend,
    injects them directly into the LangGraph state loop, and streams progress live.
    """
    await websocket.accept()
    session_id = None
    
    try:
        # A. Capture the dynamic configurations right from the frontend's user input fields
        user_input_payload = await websocket.receive_json()
        
        topic = user_input_payload.get("topic", "AI should replace human judges").strip()
        max_rounds = int(user_input_payload.get("max_rounds", 2))
        prosecutor_persona = user_input_payload.get("prosecutor_persona", "Tech Optimist").strip()
        defender_persona = user_input_payload.get("defender_persona", "Civil Liberties Advocate").strip()
        session_id = user_input_payload.get("session_id") or f"cyber_{uuid.uuid4().hex[:8]}"
        
        # B. Establish the baseline dynamic state mapping dictionary
        initial_state = {
            "topic": topic,
            "prosecutor_persona": prosecutor_persona,
            "defender_persona": defender_persona,
            "history": [],
            "round": 1,
            "max_rounds": max_rounds, 
            "prosecutor_score": 0.0,
            "defender_score": 0.0,
            "session_id": session_id,
            "current_turn_text": "",
            "latest_evaluation": {},
            "final_verdict": "" 
        }
        
        # C. Broadcast the initial setup parameters back to the UI to update titles & status blocks
        await websocket.send_json({
            "event": "court_initialized",
            "session_id": session_id,
            "topic": topic,
            "max_rounds": max_rounds,
            "personas": {
                "prosecutor": prosecutor_persona,
                "defender": defender_persona
            }
        })
        
        # D. Log the dynamic session to Supabase database
        save_debate_session(session_id=session_id, topic=topic)
        
        # E. Attach the active websocket channel directly into the execution configuration thread
        run_config = {"configurable": {"websocket": websocket, "session_id": session_id}}
        current_state = initial_state.copy()
        
        # F. Stream the graph actions live as they execute through the nodes
        async for event in compiled_graph.astream(initial_state, run_config):
            for node_name, output in event.items():
                if output:
                    current_state.update(output)
                    
                    # 🎭 Stream explicit data to control the frontend courtroom animations
                    await websocket.send_json({
                        "event": "node_transition",
                        "active_node": node_name,  # 'prosecutor_node', 'defender_node', 'judge_node', 'marshall_node'
                        "data": {
                            "text": output.get("current_turn_text", ""),
                            "evaluation": output.get("latest_evaluation", {})
                        },
                        "scoreboard": {
                            "current_round": current_state.get("round", 1),
                            "p_score": current_state.get("prosecutor_score", 0.0),
                            "d_score": current_state.get("defender_score", 0.0),
                            "verdict": current_state.get("final_verdict", "")
                        }
                    })
                    
        # G. Adjourn Court: final completion dispatch
        await websocket.send_json({
            "event": "court_adjourned",
            "session_id": session_id,
            "final_verdict": current_state.get("final_verdict", "")
        })
        
    except WebSocketDisconnect:
        print(f"🔌 Marshall Alert: Frontend user closed connection manually for session {session_id}")
    except Exception as e:
        print(f"❌ Marshall Alert: Execution pipeline halted due to error: {str(e)}")
        try:
            await websocket.send_json({"event": "court_error", "details": str(e)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

# 🧪 3. Fallback Synchronous API Endpoint for Simple Testing
@app.post("/api/debate/run-sync")
async def run_sync_debate(config: DynamicDebateConfig):
    session_id = config.session_id or f"sync_{uuid.uuid4().hex[:8]}"
    initial_state = {
        "topic": config.topic,
        "prosecutor_persona": config.prosecutor_persona,
        "defender_persona": config.defender_persona,
        "history": [],
        "round": 1,
        "max_rounds": config.max_rounds,
        "session_id": session_id
    }
    try:
        save_debate_session(session_id=session_id, topic=config.topic)
        current_state = initial_state.copy()
        async for event in compiled_graph.astream(initial_state, {"configurable": {"websocket": None}}):
            for _, output in event.items():
                if output:
                    current_state.update(output)
        return {"success": True, "session_id": session_id, "results": current_state}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    print("🚀 AI Courtroom Multi-Agent Gateway starting up up on port 8000...")
    uvicorn.run(app, host="0.0.0.0", port=8000)