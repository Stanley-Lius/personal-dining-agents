import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import datetime

load_dotenv(override=True)
client = genai.Client()

MODEL_NAME = "gemini-2.5-flash"

def test_agent1_planning(original_request: str, is_rejection: bool = False, mocked_time: str = None):
    markdown_prefs = """
    # User Profile
    Favorite foods: 燒烤、炸雞、麵食
    Allergies: None
    """
    
    db_history = """
    Recent History:
    1. Restaurant: NCHU 燒肉, Price: 200 NTD, Time: 20 mins, Status: accepted
    2. Restaurant: NCHU 麵館, Price: 150 NTD, Time: 15 mins, Status: accepted
    3. Restaurant: 麥當勞, Price: 180 NTD, Time: 10 mins, Status: accepted
    """
    
    context_type = "REJECTION RE-PLANNING" if is_rejection else "NEW PROPOSAL"
    current_time = mocked_time if mocked_time else datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rejection_reason = "Agent 2 rejected the finding because: The restaurant does not primarily serve this food." if is_rejection else "None"
    
    prompt = f"""
    You are Agent 1, the Master Dining Planner.
    Context Type: {context_type}
    Current Local Time: {current_time}
    
    Original User Input (Contains HARD CONSTRAINTS): "{original_request}"
    Rejection Reason (If any): "{rejection_reason}"
    
    User Markdown Preferences:
    {markdown_prefs}
    
    Recent DB History:
    {db_history}
    
    Task: 
    1. CATEGORIZE CONSTRAINTS:
       - HARD CONSTRAINTS: Any explicit condition provided by the user in the CURRENT input (e.g., specific location, food type, time, budget). These are ABSOLUTE and UNBREAKABLE.
       - SOFT CONSTRAINTS: Any missing dimension inferred from the user's past DB history or Markdown preferences.
    2. INFERRING MISSING INFO: For any missing dimension (location, budget, time, food), intelligently infer a SOFT CONSTRAINT from past records (e.g., average budget, most frequented area, usual food types).
    3. STRICT HARD CONSTRAINT PRESERVATION: You are STRICTLY FORBIDDEN from modifying, replacing, or expanding any HARD CONSTRAINT using past memory. If a hard constraint is a location, it stays locked to that location. If it's a food, only search for that food. Do NOT blend past memory into explicit current requests.
    4. RELAXATION PROTOCOL (REJECTION ONLY): If this is a REJECTION and you must propose relaxed constraints to broaden the search:
       - You may ONLY relax or drop SOFT CONSTRAINTS.
       - If keeping all HARD CONSTRAINTS makes the search impossible or returns no results, you MUST NOT guess or swap them. Instead, you MUST immediately output the [ASK_USER: <question>] tag to ask the user which hard constraint they are willing to compromise on.
    5. Output a natural language briefing directed to Agent 2. The brief MUST clearly specify what Agent 2 needs to search for on Google Maps, and MUST include the estimated travel time and the Current Local Time so Agent 2 can check opening hours. Do NOT output JSON. Write a clear, conversational instruction.
    """
    
    print(f"\n--- Testing: '{original_request}' (Rejection: {is_rejection}) ---")
    response = client.models.generate_content(
        model=MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.3
        )
    )
    print(">> AGENT 1 RESPONSE:")
    print(response.text)
    print("-" * 50)

if __name__ == "__main__":
    print("=== STARTING AGENT 1 LOGIC TESTS ===")
    
    # Test 1: Explicit Hard Constraint + Rejection
    test_agent1_planning(
        original_request="我要吃滷味", 
        is_rejection=True,
        mocked_time="2026-06-21 19:00:00"
    )
    
    # Test 2: Missing Info Inference
    test_agent1_planning(
        original_request="肚子餓", 
        is_rejection=False,
        mocked_time="2026-06-21 12:00:00"
    )
    
    # Test 3: Realistic Extreme - Late Night Sushi
    test_agent1_planning(
        original_request="現在半夜一點，我想吃壽司", 
        is_rejection=False,
        mocked_time="2026-06-21 01:00:00"
    )
    
    # Test 4: Location Hard Constraint + Rejection (Bug Repro)
    test_agent1_planning(
        original_request="NCHU, 滷味, available after 6 pm", 
        is_rejection=True,
        mocked_time="2026-06-21 16:00:00"
    )
    
    print("=== TESTS COMPLETE ===")
