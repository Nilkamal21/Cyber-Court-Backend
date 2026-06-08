import os
from typing import Dict, Any, List
from dotenv import load_dotenv
from neo4j import GraphDatabase, basic_auth

# Load the environment variables cleanly
load_dotenv()

# Grab the variables from your .env file
URI = os.getenv("NEO4J_URI")  
USERNAME = os.getenv("NEO4J_USERNAME" )
PASSWORD = os.getenv("NEO4J_PASSWORD")
DATABASE = os.getenv("NEO4J_DATABASE" )  # Default to 'neo4j' if not specified
# Initialize the cloud driver securely using explicit basic_auth tokens
if URI and PASSWORD:
    print(f"[*] Initiating strict token-based handshake with Aura at: {URI}")
    try:
        driver = GraphDatabase.driver(
            URI, 
            auth=basic_auth(USERNAME, PASSWORD),
            max_connection_lifetime=120,  # Keeps the connection fresh
            keep_alive=True
        )
    except Exception as init_error:
        driver = None
        print(f"[ERROR] Driver failed initialization: {str(init_error)}")
else:
    driver = None
    print("[WARNING] Neo4j credentials completely missing from .env file!")

def close_driver():
    if driver:
        driver.close()

def get_db_driver():
    """Dynamically creates a fresh connection driver every time it is called to prevent caching bugs."""
    # Force load environment variables freshly from disk
    load_dotenv(override=True)
    
    # Raw credentials fallback chain
    URI = os.getenv("NEO4J_URI", "neo4j+s://800c6edc.databases.neo4j.io")
    USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    PASSWORD = os.getenv("NEO4J_PASSWORD", "KWdwIj6YvZvGcwogOItS7hEqOgBTYYk9AjGD1hMslUU")

    try:
        # Use native basic_auth wrapping to bypass driver string encoding bugs
        return GraphDatabase.driver(URI, auth=basic_auth(USERNAME, PASSWORD))
    except Exception as e:
        print(f"[ERROR] Failed to instantiate Neo4j Driver: {str(e)}")
        return None

def log_turn_to_graph(session_id: str, topic: str, round_number: int, speaker: str, content: str, evaluation_data: Dict[str, Any]):
    """Creates interconnected entities, arguments, and fallacy vectors safely in separate transaction chunks."""
    driver = get_db_driver()
    if not driver:
        print("[WARNING] Neo4j driver could not connect. Skipping graph push.")
        return

    fallacies: List[Dict[str, str]] = evaluation_data.get("fallacies", [])
    if not isinstance(fallacies, list):
        fallacies = []
        
    score = int(evaluation_data.get("score", 80))
    argument_id = f"{session_id}_{round_number}_{speaker}"

    # 1. Base Setup: Sessions, Speakers, and core Argument node
    base_query = """
    MERGE (s:Session { id: $session_id })
    ON CREATE SET s.topic = $topic, s.created_at = timestamp()
    
    WITH s
    MERGE (p:Speaker { name: $speaker })
    MERGE (s)-[:HAS_SPEAKER]->(p)
    
    WITH s, p
    CREATE (a:Argument {
        id: $argument_id,
        round: $round_number,
        content: $content,
        judge_score: $score,
        timestamp: timestamp()
    })
    CREATE (p)-[:SPOKE]->(a)
    """

    # 2. Counter-linkages: Connect this argument to the previous argument in the session
    counter_query = """
    MATCH (s:Session { id: $session_id })-[:HAS_SPEAKER]->()-[:SPOKE]->(prev:Argument)
    WHERE prev.id <> $argument_id
    WITH prev
    ORDER BY prev.timestamp DESC
    LIMIT 1
    MATCH (a:Argument { id: $argument_id })
    MERGE (a)-[:COUNTERS]->(prev)
    """

    # 3. Fallacy linking: Map any logical fallacies captured by the judge
    fallacy_query = """
    MATCH (a:Argument { id: $argument_id })
    MERGE (f:Fallacy { name: $f_type })
    CREATE (a)-[:CONTAINED { context: $f_context }]->(f)
    """

    try:
        # Explicitly declare the target database for Aura instances
        with driver.session(database=DATABASE) as session:
            # Execute base topology structure
            session.run(base_query, session_id=str(session_id), topic=str(topic), round_number=int(round_number), speaker=str(speaker), content=str(content), score=int(score), argument_id=argument_id)
            
            # Execute contextual pointer thread
            session.run(counter_query, session_id=str(session_id), argument_id=argument_id)
            
            # Execute safe loop mapping for individual fallacies
            for f_data in fallacies:
                f_type = f_data.get("type", "").strip()
                f_context = f_data.get("sentence", "").strip()
                if f_type:
                    session.run(fallacy_query, argument_id=argument_id, f_type=f_type, f_context=f_context)
                    
        print(f"[SUCCESS] [GRAPH SUCCESS] Successfully synced Round {round_number} ({speaker}) to Aura Cloud!")
    except Exception as e:
        print(f"[ERROR] NEO4J TRANSACTION REJECTED: {str(e)}")
    finally:
        driver.close()

def get_opponent_intel(opponent_name: str) -> str:
    """Queries Neo4j to find the behavioral habits and repeating fallacies of the opponent."""
    driver = get_db_driver()
    if not driver:
        return "No historical intelligence profile available (Driver Offline)."

    cypher_query = """
    MATCH (p:Speaker { name: $opponent })-[:SPOKE]->(a:Argument)-[r:CONTAINED]->(f:Fallacy)
    RETURN f.name AS fallacy_type, count(f) AS frequency, collect(r.context)[0] AS example_quote
    ORDER BY frequency DESC
    LIMIT 3
    """

    try:
        with driver.session(database=DATABASE) as session:
            result = session.run(cypher_query, opponent=str(opponent_name))
            records = list(result)
            
            if not records:
                return "Strategic Brief: Opponent has a clean record with no major fallacy habits recorded yet."

            brief = "[INTEL] [STRATEGIC INTEL REPORT ON YOUR OPPONENT]:\n"
            for rec in records:
                brief += f"- They habitually rely on the '{rec['fallacy_type']}' fallacy (Flagged {rec['frequency']} times across trials).\n"
                if rec['example_quote']:
                    brief += f"  * Past offensive line captured: \"{rec['example_quote']}\"\n"
            
            brief += "\nWEAPONIZE this data! If they commit these habits on this turn, call them out explicitly to damage their credibility with the judge."
            return brief
    except Exception as e:
        return f"Intelligence pipeline offline: {str(e)}"
    finally:
        driver.close()