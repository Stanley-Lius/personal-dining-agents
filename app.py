import os
import re
from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st
import json
import logging
import asyncio
import datetime
from pydantic import BaseModel, Field

# MCP and Google GenAI imports
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from google import genai
from google.genai import types

# Local tools
from src import map_search
from src import utils

# --- Configuration & Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger("AppOrchestrator")

DEFAULT_USER_ID = "test_user_01"
MODEL_NAME = "gemini-2.5-flash"

# Initialize Gemini Client
try:
    api_key = os.environ.get("GEMINI_API_KEY")
    gemini_client = genai.Client(api_key=api_key) if api_key else genai.Client()
except Exception as e:
    logger.error(f"Failed to initialize Gemini Client: {e}")
    gemini_client = None

# --- Pydantic Schemas ---

class Agent2Query(BaseModel):
    map_query: str = Field(description="The optimal natural language query to send to Google Maps Places API (New).")

class MenuRecommendation(BaseModel):
    dish_name: str
    exact_price: str = Field(description="Exact price of the dish. Do not use price ranges. Extract from menu photos or web search.")
    description: str

class RichRestaurantRecommendation(BaseModel):
    restaurant_name: str
    google_maps_url: str
    phone_number: str
    todays_hours: str
    useful_reviews: list[str]
    top_3_menus: list[MenuRecommendation]
    agent2_reasoning: str = Field(description="Recommendation reasoning. Strictly under 50 words.")
    menu_photo_url: str | None = Field(default=None, description="URL of the menu photo if exact prices were not found.")

# --- Core Logic ---

async def fetch_db_history() -> str:
    server_params = StdioServerParameters(
        command="python",
        args=["src/db_mcp_server.py"],
        env=os.environ.copy()
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool("get_recent_history", arguments={"user_id": DEFAULT_USER_ID, "limit": 3})
                if result.content and len(result.content) > 0:
                    return result.content[0].text
                return "No DB history found."
    except Exception as e:
        logger.error(f"MCP DB Fetch failed: {e}")
        return "Database unavailable."

async def write_db_feedback(feedback_text: str, rating: int):
    server_params = StdioServerParameters(
        command="python",
        args=["src/db_mcp_server.py"],
        env=os.environ.copy()
    )
    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                await session.call_tool("record_dining_feedback", arguments={
                    "user_id": DEFAULT_USER_ID,
                    "restaurant_name": "Feedback Context",
                    "feedback": f"Rating: {rating}/5 - {feedback_text}",
                    "accepted": True
                })
    except Exception as e:
        logger.error(f"MCP DB Write failed: {e}")

def update_user_preferences_markdown(context_update: str):
    old_md = utils.load_user_markdown(DEFAULT_USER_ID)
    prompt = f"""
    You are an expert AI profiling agent. Update the user's Markdown preference file based on the new interaction.
    Current Markdown:
    {old_md}
    
    New Interaction/Feedback:
    {context_update}
    
    Rewrite the Markdown to incorporate this new knowledge. Keep it concise, organized by categories (e.g., Favorite Foods, Dislikes, Price Sensitivity, Usual Locations). Output ONLY the Markdown text.
    """
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
        )
        utils.save_user_markdown(DEFAULT_USER_ID, response.text)
        st.session_state.trajectory.append("System: Updated user preferences Markdown.")
    except Exception as e:
        logger.error(f"Failed to update Markdown: {e}")

def run_agent1_planning(original_request: str, db_history: str, is_rejection: bool = False, rejection_reason: str = None) -> dict:
    if not gemini_client:
        return {"status": "error", "message": "Gemini Client not initialized."}
        
    markdown_prefs = utils.load_user_markdown(DEFAULT_USER_ID)
    context_type = "REJECTION RE-PLANNING" if is_rejection else "NEW PROPOSAL"
    
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
    
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.3
            )
        )
        briefing = response.text
        
        if "SECURITY_ALERT" in briefing:
            st.session_state.trajectory.append("Agent 1: SECURITY ALERT. Prompt Injection detected.")
            return {"status": "error", "message": "Malicious input detected."}
            
        if "[ASK_USER:" in briefing:
            match = re.search(r'\[ASK_USER:\s*(.*?)\]', briefing, re.DOTALL)
            question = match.group(1).strip() if match else "Do you have any more specific requirements?"
            st.session_state.trajectory.append(f"Agent 1 asks User: {question}")
            return {"status": "ask_user", "message": question}
            
        st.session_state.trajectory.append(f"Agent 1 Briefing: {briefing}")
        
        if not is_rejection:
            update_user_preferences_markdown(f"User explicitly requested: {user_input}")
            
        return {"status": "success", "briefing": briefing}
    except Exception as e:
        return {"status": "error", "message": f"Agent 1 Planning failed (API Error): {e}"}

def run_agent2_execution(agent1_briefing: str) -> dict:
    if not gemini_client:
        return {"status": "error", "message": "Gemini Client not initialized."}
        
    try:
        query_res = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=f"Extract the best Google Maps search query from Agent 1's briefing:\n\n{agent1_briefing}",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Agent2Query,
                temperature=0.1
            )
        )
        map_query = json.loads(query_res.text).get("map_query", "restaurant")
        st.session_state.trajectory.append(f"Agent 2: Extracted Map Query: {map_query}")
    except Exception as e:
        return {"status": "error", "message": f"Agent 2 Query Gen failed: {e}"}
        
    map_results = map_search.search_google_maps(map_query)
    if "error" in map_results:
        return {"status": "needs_more_info", "reason": f"Map Search Failed: {map_results['error']}"}
        
    st.session_state.trajectory.append(f"Agent 2: Found restaurant {map_results.get('name')}")
    
    today_index = datetime.datetime.today().weekday()
    hours_list = map_results.get('opening_hours', [])
    todays_hours = hours_list[today_index] if today_index < len(hours_list) else "Unknown opening hours today"
    
    photo_parts = []
    photo_urls_mapping = ""
    maps_api_key = os.environ.get("GOOGLE_MAPS_API_KEY")
    
    for i, p_name in enumerate(map_results.get("photo_names", [])[:2]): 
        bytes_data = map_search.fetch_photo_bytes(p_name)
        if bytes_data:
            photo_parts.append(types.Part.from_bytes(data=bytes_data, mime_type="image/jpeg"))
            public_url = f"https://places.googleapis.com/v1/{p_name}/media?maxWidthPx=800&key={maps_api_key}"
            photo_urls_mapping += f"\nImage {i+1} Public URL: {public_url}"
            
    current_time_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    analysis_prompt = f"""
    You are Agent 2. You have retrieved the following restaurant data from Google Maps API (New):
    Name: {map_results.get('name')}
    Address: {map_results.get('address')}
    Phone: {map_results.get('phone_number')}
    Today's Hours: {todays_hours}
    Current Local Time: {current_time_str}
    Maps URL: {map_results.get('google_maps_uri')}
    Top Reviews: {map_results.get('reviews')}
    
    Agent 1's Briefing:
    {agent1_briefing}
    
    Task:
    1. STRICT VERIFICATION: Verify if the restaurant TRULY matches Agent 1's core requirements. Critically, you MUST check the "Today's Hours" against the "Current Local Time" and consider the travel time mentioned in Agent 1's briefing. Ensure the restaurant will still be open and serving food by the time the user arrives. If it is closed, will close too soon, or drastically fails other requirements (e.g., all-you-can-eat, specific food type), output ONLY this tag: [REJECT_AND_ASK_AGENT1: <Reason why it failed>]. Do not output anything else.
    2. Analyze the {len(photo_parts)} menu/food photos provided. Here are their public URLs: {photo_urls_mapping}
    3. If the photos are insufficient to find exact prices for the 3 menus, use your `google_search` tool to search for "{map_results.get('name')} menu prices".
    4. Output a detailed text summary of the Top 3 menus and their exact prices.
    5. Provide your reasoning based on Agent 1's briefing (strictly limit reasoning to under 50 words).
    6. If you cannot find exact prices from web or photos, and one of the images provided is a Menu, specify its Public URL so we can show it to the user.
    """
    
    contents = [analysis_prompt] + photo_parts
    
    try:
        analysis_response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                tools=[{"google_search": {}}],
                temperature=0.2
            )
        )
        raw_analysis = analysis_response.text
        
        if "[REJECT_AND_ASK_AGENT1:" in raw_analysis:
            match = re.search(r'\[REJECT_AND_ASK_AGENT1:\s*(.*?)\]', raw_analysis, re.DOTALL)
            reason = match.group(1).strip() if match else "Restaurant does not meet core requirements"
            st.session_state.trajectory.append(f"Agent 2 Rejected result. Reason: {reason}")
            return {"status": "needs_more_info", "reason": reason}
        
        format_prompt = f"""
        Format the following restaurant analysis into the required JSON schema.
        Restaurant Name: {map_results.get('name')}
        Google Maps URL: {map_results.get('google_maps_uri')}
        Phone: {map_results.get('phone_number')}
        Today's Hours: {todays_hours}
        Reviews: {map_results.get('reviews')}
        
        Detailed Analysis (contains menus, prices, reasoning, and optional menu_photo_url):
        {raw_analysis}
        """
        
        format_response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=format_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RichRestaurantRecommendation,
                temperature=0.1
            )
        )
        
        rec = json.loads(format_response.text)
        st.session_state.trajectory.append(f"Agent 2: Final Selection: {rec['restaurant_name']}")
        return {"status": "success", "recommendation": rec}
    except Exception as e:
        return {"status": "error", "message": f"Agent 2 Execution failed: {e}"}

# --- Streamlit UI ---
st.set_page_config(page_title="Concierge Dining Advisor", layout="wide")

if "trajectory" not in st.session_state:
    st.session_state.trajectory = []
if "current_recommendation" not in st.session_state:
    st.session_state.current_recommendation = None
if "agent1_briefing" not in st.session_state:
    st.session_state.agent1_briefing = None
if "system_message" not in st.session_state:
    st.session_state.system_message = None
if "current_request" not in st.session_state:
    st.session_state.current_request = None

st.title("🍽️ Concierge Dining Advisor")
st.markdown("Powered by Multi-Agent Auto-Correction & Feedback Loops")

if st.session_state.system_message:
    st.warning(st.session_state.system_message)

user_input = st.chat_input("Please enter your dining preferences...")

if user_input:
    st.session_state.current_request = user_input
    st.session_state.trajectory.append(f"User: {user_input}")
    st.session_state.current_recommendation = None # clear old
    st.session_state.system_message = None # clear old message
    
    with st.spinner("Fetching DB History..."):
        db_history = asyncio.run(fetch_db_history())
        st.session_state.trajectory.append("System: Fetched DB History.")
        
    with st.spinner("Agent 1 is planning and updating preferences..."):
        a1_result = run_agent1_planning(st.session_state.current_request, db_history, is_rejection=False)
        
    if a1_result["status"] == "error":
        st.session_state.system_message = a1_result["message"]
        st.rerun()
    elif a1_result["status"] == "ask_user":
        st.session_state.system_message = f"🤔 **Assistant needs more information:**\n\n{a1_result['message']}"
        st.rerun()
    else:
        st.session_state.agent1_briefing = a1_result["briefing"]
        
        with st.spinner("Agent 2 is executing Maps API and verifying requirements..."):
            a2_result = run_agent2_execution(st.session_state.agent1_briefing)
            
        if a2_result["status"] == "needs_more_info":
            with st.spinner(f"🔄 **Restaurant found does not meet requirements ({a2_result['reason']}), asking Agent 1 to re-plan...**"):
                a1_result_retry = run_agent1_planning(st.session_state.current_request, db_history, is_rejection=True, rejection_reason=f"Agent 2 rejected the finding because: {a2_result['reason']}. Please propose a broader or different search constraint. If impossible, ask the user.")
                
                if a1_result_retry["status"] == "ask_user":
                    st.session_state.system_message = f"🤔 **Assistant needs your help:**\n\n{a1_result_retry['message']}"
                    st.rerun()
                elif a1_result_retry["status"] == "success":
                    with st.spinner("Agent 2 is searching again with new constraints..."):
                        a2_result_retry = run_agent2_execution(a1_result_retry["briefing"])
                        if a2_result_retry["status"] == "success":
                            st.session_state.current_recommendation = a2_result_retry["recommendation"]
                            st.rerun()
                        elif a2_result_retry["status"] == "needs_more_info":
                             st.session_state.system_message = "❌ Sorry, even after relaxing constraints, no suitable restaurant was found. Please try a different location or constraint."
                             st.rerun()
                        else:
                             st.session_state.system_message = a2_result_retry.get("message", "Error executing agent 2 retry")
                             st.rerun()
                else:
                     st.session_state.system_message = a1_result_retry.get("message", "Error executing agent 1 retry")
                     st.rerun()
        elif a2_result["status"] == "error":
            st.session_state.system_message = a2_result["message"]
            st.rerun()
        else:
            st.session_state.current_recommendation = a2_result["recommendation"]
            st.rerun()

# Display Recommendation & Feedback Loop
if st.session_state.current_recommendation:
    rec = st.session_state.current_recommendation
    
    st.success(f"### 🎉 Recommended Restaurant: {rec['restaurant_name']}")
    st.markdown(f"**📍 Navigation:** [Google Maps]({rec['google_maps_url']}) | **📞 Phone:** {rec['phone_number']}")
    st.markdown(f"**🕒 Today's Hours:** {rec['todays_hours']}")
    st.markdown(f"**💡 Reason for Recommendation:** {rec['agent2_reasoning']}")
        
    st.markdown("#### 🗣️ Selected Reviews")
    for r in rec['useful_reviews']:
        st.info(f'"{r}"')
        
    st.markdown("#### 🍽️ Recommended Dishes & Exact Prices")
    cols = st.columns(3)
    for idx, menu in enumerate(rec['top_3_menus']):
        with cols[idx]:
            st.warning(f"**{menu['dish_name']}**\n\n💰 {menu['exact_price']}\n\n_{menu['description']}_")
            
    if rec.get('menu_photo_url'):
        st.markdown("#### 📸 Latest Menu Reference")
        st.image(rec['menu_photo_url'], caption="Restaurant Menu", use_container_width=True)
    
    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### Rate this recommendation (0-5 stars)")
        rating = st.feedback("stars")
        if rating is not None:
            actual_rating = rating + 1 
            st.write(f"You gave {actual_rating} stars! Updating your preferences...")
            asyncio.run(write_db_feedback(f"Accepted {rec['restaurant_name']}", actual_rating))
            update_user_preferences_markdown(f"User rated the recommendation '{rec['restaurant_name']}' {actual_rating} out of 5 stars.")
            st.session_state.current_recommendation = None 
            st.rerun()
            
    with col2:
        st.markdown("##### Or Re-plan")
        rejection_reason = st.text_input("Tell us what you didn't like (Optional)")
        if st.button("❌ Reject and Re-plan (Relax Constraints)"):
            feedback_str = f"Rejected: {rec['restaurant_name']}. Reason: {rejection_reason}"
            st.session_state.trajectory.append(f"User {feedback_str}")
            update_user_preferences_markdown(feedback_str)
            
            with st.spinner("Agent 1 is re-planning with relaxed constraints..."):
                db_history = asyncio.run(fetch_db_history())
                a1_result = run_agent1_planning(st.session_state.current_request, db_history, is_rejection=True, rejection_reason=f"I rejected the previous suggestion because: {rejection_reason}. Please offer a relaxed or alternative proposal.")
                
                if a1_result["status"] == "success":
                    st.session_state.agent1_briefing = a1_result["briefing"]
                    with st.spinner("Agent 2 is finding a new restaurant..."):
                        a2_result = run_agent2_execution(st.session_state.agent1_briefing)
                        if a2_result["status"] == "success":
                            st.session_state.current_recommendation = a2_result["recommendation"]
                            st.session_state.system_message = None
                            st.rerun()
                        elif a2_result["status"] == "needs_more_info":
                            st.session_state.current_recommendation = None
                            st.session_state.system_message = "❌ Sorry, even after relaxing constraints, no suitable restaurant was found. Please try a different location or constraint."
                            st.rerun()
                        else:
                            st.session_state.current_recommendation = None
                            st.session_state.system_message = a2_result.get("message", "Error finding new restaurant")
                            st.rerun()
                elif a1_result["status"] == "ask_user":
                    st.session_state.current_recommendation = None
                    st.session_state.system_message = f"🤔 **Assistant needs your help:**\n\n{a1_result['message']}"
                    st.rerun()
                else:
                    st.session_state.current_recommendation = None
                    st.session_state.system_message = a1_result.get("message", "Agent 1 Error")
                    st.rerun()

# Sidebar Trajectory
with st.sidebar:
    st.header("🧠 Multi-Agent Trajectory")
    for msg in st.session_state.trajectory:
        st.write(f"- {msg}")
