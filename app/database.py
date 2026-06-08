import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Force load variables into system environment memory
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Missing Supabase credentials in your local .env file!")

# 🌟 GLOBAL INSTANTIATION: Accessible by all functions in this file
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
print("[SUCCESS] Supabase client successfully initialized.")


def save_debate_session(session_id: str, topic: str, prosecutor_score: int = 0, defender_score: int = 0, final_verdict: str = ""):
    """Inserts or updates the macro record of a debate trial session."""
    try:
        payload = {
            "session_id": session_id,
            "topic": topic,
            "prosecutor_final_score": int(prosecutor_score),
            "defender_final_score": int(defender_score),
            "final_verdict": final_verdict
        }
        response = supabase.table("debate_sessions").upsert(payload).execute()
        return response
    except Exception as e:
        print(f"⚠️ Error logging session metadata to Supabase: {str(e)}")


def save_turn_transcript(session_id: str, round_number: int, speaker: str, content: str, score: int, evaluation_json: dict):
    """Appends an individual turn's text and its judge structured JSON data metrics."""
    payload = {
        "session_id": session_id,
        "round_number": int(round_number),
        "speaker": speaker,
        "argument_content": content,
        "judge_score": int(score),
        "judge_evaluation_json": evaluation_json
    }
    try:
        response = supabase.table("debate_transcripts").insert(payload).execute()
        return response
    except Exception as e:
        err_msg = str(e)
        if '23503' in err_msg or 'foreign key' in err_msg.lower():
            print(f"⚠️ Parent session {session_id} missing in Supabase due to previous network failures. Attempting dynamic self-healing recovery...")
            try:
                save_debate_session(session_id=session_id, topic="Restored Debate Session")
                response = supabase.table("debate_transcripts").insert(payload).execute()
                print(f"[SUCCESS] Recovered successfully. Turn transcript saved.")
                return response
            except Exception as retry_err:
                print(f"❌ Dynamic self-healing database insert failed: {str(retry_err)}")
        else:
            print(f"⚠️ Error logging turn transcript to Supabase: {str(e)}")