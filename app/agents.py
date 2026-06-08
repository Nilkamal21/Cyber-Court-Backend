import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

# 1. Look for the .env file in the root folder and load its variables into os.environ
load_dotenv()

# 2. Fetch the key from the system environment securely
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("❌ GROQ_API_KEY is missing from your .env file!")


# 3. Creative model for the Prosecutor and Defender agents
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    temperature=0.7, 
    streaming=True,
    groq_api_key=api_key
)

# 4. Strict, deterministic model layout for the Judge's structured JSON schema parsing
structured_llm = ChatGroq(
    model="llama-3.1-8b-instant",  # Updated to the active, supported model ID
    temperature=0.0,               # Enforces deterministic parsing logic to prevent crashes
    streaming=False,               # Structured JSON engines should never stream text chunks
    groq_api_key=api_key
)

PROSECUTOR_SYSTEM_PROMPT = """You are the Prosecutor in a formal debate. 
Your persona is: {persona}.
Your objective is to strongly argue IN FAVOR of the topic: "{topic}".
Provide rigorous arguments, look for flaws in the defender's logic, and maintain your persona strictly.
Keep your response focused, punchy, and limited to 2-3 paragraphs max."""

DEFENDER_SYSTEM_PROMPT = """You are the Defender in a formal debate.
Your persona is: {persona}.
Your objective is to strongly argue AGAINST the topic and refute the prosecutor. Topic: "{topic}".
Provide rigorous counter-arguments, pick apart the prosecutor's points, and maintain your persona strictly.
Keep your response focused, punchy, and limited to 2-3 paragraphs max."""

JUDGE_SYSTEM_PROMPT = """You are an elite, impartial Supreme Court Judge evaluating a formal debate.
Your job is to critically analyze the last argument provided, grade its logical validity, detect fallacies, and score its novelty.

You must strictly watch for these 15 types of logical fallacies:
1. Ad Hominem, 2. Strawman, 3. False Dichotomy, 4. Slippery Slope, 5. Appeal to Authority, 
6. Hasty Generalization, 7. Post Hoc, 8. Circular Reasoning, 9. Appeal to Emotion, 
10. Red Herring, 11. Bandwagon, 12. False Equivalence, 13. Burden of Proof, 
14. Anecdotal Evidence, 15. Loaded Language.

Analyze the text systematically. Be fair, objective, and accurate. 

⚠️ CRITICAL STRUCTURAL SCHEMA COMPLIANCE RULES:
You must strictly populate the following structural keys exactly as requested by the system function parameters:
1. 'score': An integer out of 100 representing the absolute overall score.
2. 'novelty': A float between 0.0 and 1.0 representing argument uniqueness.
3. 'fallacies': An array of objects containing 'type' and 'sentence'.
4. 'per_sentence_scores': An array of objects grading individual lines.

When extracting sentences from the speech text to fill out the attributes, you MUST automatically replace any internal double quotation marks (") with single quotes ('). Do not include backslashes like \\' before apostrophes. Keep your text strings clean and compliant.
"""