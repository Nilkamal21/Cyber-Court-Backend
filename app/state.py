from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, TypedDict

# ==========================================
# 1. PYDANTIC SCHEMAS (For Judge JSON Output)
# ==========================================

class Fallacy(BaseModel):
    type: str = Field(
        description="The type of fallacy detected (e.g., 'strawman', 'ad hominem', 'slippery slope')."
    )
    sentence: str = Field(
        description="The exact sentence from the argument where this fallacy occurred."
    )

class SentenceScore(BaseModel):
    sentence: str = Field(description="The exact sentence being evaluated.")
    score: int = Field(description="A logical validity score from 0 to 100.")
    note: str = Field(description="A brief 1-sentence analytical reason for this score.")

class JudgeEvaluation(BaseModel):
    score: int = Field(description="Overall argument score from 0 to 100 based on logical strength.")
    novelty: float = Field(description="Novelty score from 0.0 to 1.0 (how many fresh points are raised vs repetitions).")
    fallacies: List[Fallacy] = Field(description="List of logical fallacies detected in the text.")
    per_sentence_scores: List[SentenceScore] = Field(description="Sentence-by-sentence evaluation array.")

# ==========================================
# 2. LANGGRAPH STATE DEFINITION
# ==========================================

class DebateState(TypedDict):
    topic: str
    history: List[Dict[str, str]]
    round: int
    max_rounds: int
    prosecutor_score: float
    defender_score: float
    session_id: str
    graph_nodes: List[Dict[str, Any]]
    graph_edges: List[Dict[str, Any]]
    current_turn_text: str
    latest_evaluation: Dict[str, Any]
    # NEW FEATURE: Holds the deep final legal analysis of the entire match
    final_verdict: str