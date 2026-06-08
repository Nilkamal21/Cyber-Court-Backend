import sys
import json
import re
from typing import Dict, Any
from langgraph.graph import StateGraph, END
from langchain_core.runnables import RunnableConfig
from app.state import DebateState
from app.agents import llm, PROSECUTOR_SYSTEM_PROMPT, DEFENDER_SYSTEM_PROMPT, JUDGE_SYSTEM_PROMPT
from langchain_core.messages import SystemMessage, HumanMessage
from app.neo4j_db import get_opponent_intel

# Force configuration checks for Windows CLI stream environments
if sys.platform.startswith("win"):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

# Helper to extract and dispatch real-time stream event updates to the web client
async def send_token_to_frontend(config: RunnableConfig, speaker: str, content: str, event_type: str = "token_stream"):
    """Extracts the WebSocket channel from the graph config context and dispatches data payload frames."""
    configurable = config.get("configurable", {})
    websocket = configurable.get("websocket")
    if websocket:
        try:
            await websocket.send_json({
                "event": event_type,
                "speaker": speaker,
                "text": content
            })
        except Exception:
            pass  # Fail-safe protection if client disconnects mid-sentence

# ==========================================
# 1. DEBATER NODES (Dual Stream: Terminal + Socket)
# ==========================================

async def prosecutor_node(state: DebateState, config: RunnableConfig) -> Dict[str, Any]:
    print(f"\n📢 [ROUND {state['round']}] PROSECUTOR TURN >>> ", end="")
    sys.stdout.flush()
    
    # Graph-RAG Interception: Fetch Neo4j behavioural tracking metrics
    opponent_intel = get_opponent_intel("defender")
    
    # 🌟 INPUT DRIVEN: Read persona dynamically from frontend user selections
    persona = state.get("prosecutor_persona", "Tech Optimist")
    system_prompt = PROSECUTOR_SYSTEM_PROMPT.format(
        persona=persona, 
        topic=state["topic"]
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=opponent_intel) 
    ]
    
    for msg in state["history"]:
        if msg["role"] == "prosecutor":
            messages.append(HumanMessage(content=f"My previous point: {msg['content']}"))
        else:
            messages.append(HumanMessage(content=f"Opponent's counter: {msg['content']}"))
            
    if state.get("latest_evaluation"):
        eval_data = state["latest_evaluation"]
        if state["history"][-1]["role"] == "prosecutor":
            messages.append(SystemMessage(content=f"""
            [JUDICIAL FEEDBACK WARNING]: On your last turn, the Judge scored you a {eval_data.get('score', 80)}/100.
            The Judge flagged these fallacies in your speech: {json.dumps(eval_data.get('fallacies', []))}.
            You MUST briefly address or correct these flaws in your opening paragraph before pivoting to your main argument!
            """))
            
    full_text_buffer = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_text_buffer += token
            print(token, end="", flush=True)
            # 🌟 REAL-TIME FRONTEND SYNC: Lights up Prosecutor's podium card on UI live!
            await send_token_to_frontend(config, "prosecutor", full_text_buffer)
            
    print("\n[Prosecutor Finished Speaking]")
    updated_history = list(state["history"]) + [{"role": "prosecutor", "content": full_text_buffer}]
    
    return {
        "history": updated_history,
        "current_turn_text": full_text_buffer
    }


async def defender_node(state: DebateState, config: RunnableConfig) -> Dict[str, Any]:
    print(f"\n🛡️ [ROUND {state['round']}] DEFENDER TURN >>> ", end="")
    sys.stdout.flush()
    
    opponent_intel = get_opponent_intel("prosecutor")
    
    # 🌟 INPUT DRIVEN: Read persona dynamically from frontend user selections
    persona = state.get("defender_persona", "Civil Liberties Advocate")
    system_prompt = DEFENDER_SYSTEM_PROMPT.format(
        persona=persona, 
        topic=state["topic"]
    )
    
    messages = [
        SystemMessage(content=system_prompt),
        SystemMessage(content=opponent_intel)
    ]
    
    for msg in state["history"]:
        if msg["role"] == "defender":
            messages.append(HumanMessage(content=f"My previous point: {msg['content']}"))
        else:
            messages.append(HumanMessage(content=f"Opponent's argument: {msg['content']}"))
            
    if state.get("latest_evaluation"):
        eval_data = state["latest_evaluation"]
        if state["history"][-1]["role"] == "defender":
            messages.append(SystemMessage(content=f"""
            [JUDICIAL FEEDBACK WARNING]: On your last turn, the Judge scored you a {eval_data.get('score', 80)}/100.
            The Judge flagged these fallacies in your speech: {json.dumps(eval_data.get('fallacies', []))}.
            You MUST briefly address or correct these flaws in your opening paragraph before pivoting to your main counter-argument!
            """))
            
    full_text_buffer = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_text_buffer += token
            print(token, end="", flush=True)
            # 🌟 REAL-TIME FRONTEND SYNC: Lights up Defender's podium card on UI live!
            await send_token_to_frontend(config, "defender", full_text_buffer)
            
    print("\n[Defender Finished Speaking]")
    updated_history = list(state["history"]) + [{"role": "defender", "content": full_text_buffer}]
    
    # 🌟 BUG FIX: Move the "round" increments safely out of here to keep the judge session aligned!
    return {
        "history": updated_history,
        "current_turn_text": full_text_buffer
    }

# ==========================================
# 2. EVALUATION NODE (Robust Fallback Parsing)
# ==========================================

async def judge_node(state: DebateState, config: RunnableConfig) -> Dict[str, Any]:
    print(f"\n👩‍⚖️ [JUDGE EVALUATION] Analyzing latest argument string...")
    
    last_message = state["history"][-1]
    speaker = last_message["role"]      
    argument_text = last_message["content"]
    
    formatting_instructions = """
    Analyze the text systematically. You MUST return your response as a raw JSON object matching the following structure exactly. Do not provide any conversational text before or after the JSON code block.
    
    {
      "score": 85,
      "novelty": 0.70,
      "fallacies": [
        {"type": "False Dichotomy", "sentence": "Cleaned line extract here"}
      ],
      "per_sentence_scores": [
        {"sentence": "Cleaned evaluation line", "score": 90, "note": "Analysis comment"}
      ]
    }
    """
    
    messages = [
        SystemMessage(content=JUDGE_SYSTEM_PROMPT + "\n" + formatting_instructions),
        HumanMessage(content=f"The topic is: '{state['topic']}'.\n\nEvaluate this argument from the {speaker}:\n{argument_text}")
    ]
    
    response = await llm.ainvoke(messages)
    raw_content = response.content.strip()
    
    if raw_content.startswith("```"):
        raw_content = re.sub(r"^```(?:json)?\n", "", raw_content)
        raw_content = re.sub(r"\n```$", "", raw_content)
    raw_content = raw_content.strip()
    raw_content = raw_content.replace("\\'", "'").replace("\\\\'", "'")
    
    try:
        evaluation_data = json.loads(raw_content)
    except Exception:
        print(f"⚠️ Data fallback triggered defensively...")
        evaluation_data = {
            "score": 82,
            "novelty": 0.75,
            "fallacies": [],
            "per_sentence_scores": [{"sentence": "Fallback analysis triggered", "score": 82, "note": "String fallback parsing executed."}]
        }
    
    print(f"\n📊 --- EVALUATION VERDICT FOR {speaker.upper()} ---")
    print(f"   - Score: {evaluation_data.get('score', 80)}/100")
    print("------------------------------------------------\n")
        
    # Cloud database syncing routine 
    from app.database import save_turn_transcript
    save_turn_transcript(
        session_id=state.get("session_id", "default_session"),
        round_number=state["round"],
        speaker=speaker,
        content=argument_text,
        score=evaluation_data.get('score', 80),
        evaluation_json=evaluation_data  
    )
    
    from app.neo4j_db import log_turn_to_graph
    log_turn_to_graph(
        session_id=state.get("session_id", "default_session"),
        topic=state["topic"],
        round_number=state["round"],
        speaker=speaker,
        content=argument_text,
        evaluation_data=evaluation_data
    )
    
    # 🌟 FRONTEND SYNC: Broadcasts the final judge analytical scorecard card directly to the UI
    await send_token_to_frontend(config, "judge", json.dumps(evaluation_data), event_type="judge_evaluation")
        
    # 🌟 SAFE ROUND INCREMENTATION: We cleanly step the global round up only after the Defender finishes a complete turn cycle
    next_round_value = state["round"] + 1 if speaker == "defender" else state["round"]
        
    return {
        "latest_evaluation": evaluation_data,
        "round": next_round_value,
        "prosecutor_score": evaluation_data.get('score', 80) if speaker == "prosecutor" else state["prosecutor_score"],
        "defender_score": evaluation_data.get('score', 80) if speaker == "defender" else state["defender_score"]
    }


async def verdict_node(state: DebateState, config: RunnableConfig) -> Dict[str, Any]:
    print(f"\n👩‍⚖️ [COURTROOM BENCH] The Judge is drafting the final judicial verdict...")
    
    summary_context = f"""
    Debate Topic: {state['topic']}
    Final Prosecutor Score Tracked: {state['prosecutor_score']}/100
    Final Defender Score Tracked: {state['defender_score']}/100
    """
    
    messages = [
        SystemMessage(content="""You are the presiding Supreme Court Judge delivering your final absolute verdict paragraph.
        Review the entire transcript context, declare an absolute winner, and write an authoritative, legally sophisticated concluding verdict block. Be definitive."""),
        HumanMessage(content=f"Here is the history of the trial:\n{json.dumps(state['history'])}\n\nMetrics:\n{summary_context}")
    ]
    
    full_verdict_buffer = ""
    async for chunk in llm.astream(messages):
        token = chunk.content
        if token:
            full_verdict_buffer += token
            print(token, end="", flush=True)
            # 🌟 REAL-TIME FRONTEND SYNC: Renders the final verdict scroll box text live on screen!
            await send_token_to_frontend(config, "verdict", full_verdict_buffer)
            
    from app.database import save_debate_session
    save_debate_session(
        session_id=state.get("session_id", "default_session"),
        topic=state["topic"],
        prosecutor_score=state["prosecutor_score"],
        defender_score=state["defender_score"],
        final_verdict=full_verdict_buffer
    )
    
    return {"final_verdict": full_verdict_buffer}


def judge_router_condition(state: DebateState) -> str:
    last_message = state["history"][-1]
    last_speaker = last_message["role"]
    
    if last_speaker == "prosecutor":
        return "to_defender"
    
    # Uses clean comparative boundary routing 
    if state["round"] > state["max_rounds"]:
        return "to_verdict"
    
    return "to_prosecutor"


# ==========================================
# 3. GRAPH ARCHITECTURE COMPILATION
# ==========================================
workflow = StateGraph(DebateState)

workflow.add_node("prosecutor", prosecutor_node)
workflow.add_node("defender", defender_node)
workflow.add_node("judge", judge_node)
workflow.add_node("verdict", verdict_node) 

workflow.set_entry_point("prosecutor")
workflow.add_edge("prosecutor", "judge")
workflow.add_edge("defender", "judge")

workflow.add_conditional_edges(
    "judge",
    judge_router_condition,
    {
        "to_defender": "defender",
        "to_prosecutor": "prosecutor",
        "to_verdict": "verdict" 
    }
)

workflow.add_edge("verdict", END)
compiled_graph = workflow.compile()