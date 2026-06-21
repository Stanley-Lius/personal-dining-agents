import os
from dotenv import load_dotenv
load_dotenv(override=True)

import streamlit as st
import json
import logging
import asyncio
from pydantic import BaseModel, Field

# MCP and Google GenAI imports
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.session import ClientSession
from google import genai
from google.genai import types

# Local tools
import map_search
import utils

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
    opening_hours: list[str]
    useful_reviews: list[str]
    top_3_menus: list[MenuRecommendation]
    agent2_reasoning: str

# --- Core Logic ---

async def fetch_db_history() -> str:
    server_params = StdioServerParameters(
        command="python",
        args=["db_mcp_server.py"],
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
        args=["db_mcp_server.py"],
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

def run_agent1_planning(user_input: str, db_history: str, is_rejection: bool = False) -> dict:
    if not gemini_client:
        return {"status": "error", "message": "Gemini Client not initialized."}
        
    markdown_prefs = utils.load_user_markdown(DEFAULT_USER_ID)
    
    context_type = "REJECTION RE-PLANNING" if is_rejection else "NEW PROPOSAL"
    
    prompt = f"""
    You are Agent 1, the Master Dining Planner.
    Context Type: {context_type}
    
    User Input / Rejection Reason: "{user_input}"
    
    User Markdown Preferences:
    {markdown_prefs}
    
    Recent DB History:
    {db_history}
    
    Task: 
    1. Understand the user's intent, current constraints, and historical preferences.
    2. If this is a REJECTION, you MUST propose a relaxed or alternative constraint that aligns with their past habits.
    3. You have the `google_search` tool enabled. Use it to find features (e.g., "cooling foods near Taichung Park").
    4. Output a natural language briefing directed to Agent 2. The brief MUST clearly specify what Agent 2 needs to search for on Google Maps. Do NOT output JSON. Write a clear, conversational instruction.
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
            
        st.session_state.trajectory.append(f"Agent 1 Briefing: {briefing}")
        
        # Update Markdown with the user's latest query
        if not is_rejection:
            update_user_preferences_markdown(f"User explicitly requested: {user_input}")
            
        return {"status": "success", "briefing": briefing}
    except Exception as e:
        return {"status": "error", "message": f"Agent 1 Planning failed (API Error): {e}"}

def run_agent2_execution(agent1_briefing: str) -> dict:
    if not gemini_client:
        return {"status": "error", "message": "Gemini Client not initialized."}
        
    # Step 1: Generate Map Query
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
        
    # Step 2: Execute Map Search
    map_results = map_search.search_google_maps(map_query)
    if "error" in map_results:
        return {"status": "error", "message": f"Map Search Failed: {map_results['error']}"}
        
    st.session_state.trajectory.append(f"Agent 2: Found restaurant {map_results.get('name')}")
    
    # Step 3: Fetch Photos
    photo_parts = []
    for p_name in map_results.get("photo_names", [])[:2]: # Max 2 photos to save latency
        bytes_data = map_search.fetch_photo_bytes(p_name)
        if bytes_data:
            photo_parts.append(types.Part.from_bytes(data=bytes_data, mime_type="image/jpeg"))
            
    # Step 4: Final Rich Output with Multimodal + Web Search
    final_prompt = f"""
    You are Agent 2. You have retrieved the following restaurant data from Google Maps API (New):
    Name: {map_results.get('name')}
    Address: {map_results.get('address')}
    Phone: {map_results.get('phone_number')}
    Hours: {map_results.get('opening_hours')}
    Maps URL: {map_results.get('google_maps_uri')}
    Top Reviews: {map_results.get('reviews')}
    
    Agent 1's Briefing:
    {agent1_briefing}
    
    Task:
    1. I have provided {len(photo_parts)} menu/food photos from the restaurant (if any). Analyze them to find exact dish prices.
    2. If the photos are insufficient, use your `google_search` tool to search for "{map_results.get('name')} menu prices".
    3. Output the final recommendation strictly matching the JSON schema. YOU MUST include exact prices for the 3 menus.
    """
    
    contents = [final_prompt] + photo_parts
    
    try:
        response = gemini_client.models.generate_content(
            model=MODEL_NAME,
            contents=contents,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RichRestaurantRecommendation,
                tools=[{"google_search": {}}],
                temperature=0.2
            )
        )
        rec = json.loads(response.text)
        st.session_state.trajectory.append(f"Agent 2: Final Selection: {rec['restaurant_name']}")
        return {"status": "success", "recommendation": rec}
    except Exception as e:
        return {"status": "error", "message": f"Agent 2 Execution failed: {e}"}

# --- Streamlit UI ---
st.set_page_config(page_title="Concierge Dining Advisor - Advanced", layout="wide")

if "trajectory" not in st.session_state:
    st.session_state.trajectory = []
if "current_recommendation" not in st.session_state:
    st.session_state.current_recommendation = None
if "agent1_briefing" not in st.session_state:
    st.session_state.agent1_briefing = None

st.title("🍽️ Concierge Dining Advisor (Advanced Multi-Agent)")
st.markdown("Powered by Gemini 2.5 Flash, Places API (New), and Markdown Memory.")

user_input = st.chat_input("請輸入您的用餐需求 (例如：在台中一中街附近的公園，想吃解暑料理、不能吃花生)")

if user_input:
    st.session_state.trajectory.append(f"User: {user_input}")
    
    with st.spinner("Fetching DB History..."):
        db_history = asyncio.run(fetch_db_history())
        st.session_state.trajectory.append("System: Fetched DB History.")
        
    with st.spinner("Agent 1 is planning and updating preferences..."):
        a1_result = run_agent1_planning(user_input, db_history, is_rejection=False)
        
    if a1_result["status"] == "error":
        st.error(a1_result["message"])
    else:
        st.session_state.agent1_briefing = a1_result["briefing"]
        
        with st.spinner("Agent 2 is executing Maps API and analyzing menus..."):
            a2_result = run_agent2_execution(st.session_state.agent1_briefing)
            
        if a2_result["status"] == "error":
            st.error(a2_result["message"])
        else:
            st.session_state.current_recommendation = a2_result["recommendation"]

# Display Recommendation & Feedback Loop
if st.session_state.current_recommendation:
    rec = st.session_state.current_recommendation
    st.success(f"### 🎉 推薦餐廳：{rec['restaurant_name']}")
    st.markdown(f"**📍 導航:** [Google Maps]({rec['google_maps_url']}) | **📞 電話:** {rec['phone_number']}")
    
    st.markdown("#### 🕒 營業時間")
    for h in rec['opening_hours']:
        st.write(f"- {h}")
        
    st.markdown("#### 🗣️ 精選評論")
    for r in rec['useful_reviews']:
        st.info(f'"{r}"')
        
    st.markdown("#### 🍽️ 推薦菜色與精確價位")
    cols = st.columns(3)
    for idx, menu in enumerate(rec['top_3_menus']):
        with cols[idx]:
            st.warning(f"**{menu['dish_name']}**\n\n💰 {menu['exact_price']}\n\n_{menu['description']}_")
            
    st.markdown(f"**💡 Agent 2 推薦理由:** {rec['agent2_reasoning']}")
    
    # HITL Action Buttons
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("##### 為這次的推薦評分 (0-5星)")
        rating = st.feedback("stars")
        if rating is not None:
            actual_rating = rating + 1 # st.feedback is 0-indexed (0-4), we want 1-5
            st.write(f"您給了 {actual_rating} 顆星！正在更新您的喜好紀錄...")
            asyncio.run(write_db_feedback(f"Accepted {rec['restaurant_name']}", actual_rating))
            update_user_preferences_markdown(f"User rated the recommendation '{rec['restaurant_name']}' {actual_rating} out of 5 stars.")
            st.session_state.current_recommendation = None # Reset
            st.rerun()
            
    with col2:
        st.markdown("##### 或者重新規劃")
        rejection_reason = st.text_input("告訴我們哪裡不滿意？(選填)")
        if st.button("❌ 拒絕並重新規劃 (放寬條件)"):
            feedback_str = f"Rejected: {rec['restaurant_name']}. Reason: {rejection_reason}"
            st.session_state.trajectory.append(f"User {feedback_str}")
            update_user_preferences_markdown(feedback_str)
            
            with st.spinner("Agent 1 is re-planning with relaxed constraints..."):
                db_history = asyncio.run(fetch_db_history())
                a1_result = run_agent1_planning(f"I rejected the previous suggestion because: {rejection_reason}. Please offer a relaxed or alternative proposal.", db_history, is_rejection=True)
                
                if a1_result["status"] == "success":
                    st.session_state.agent1_briefing = a1_result["briefing"]
                    with st.spinner("Agent 2 is finding a new restaurant..."):
                        a2_result = run_agent2_execution(st.session_state.agent1_briefing)
                        if a2_result["status"] == "success":
                            st.session_state.current_recommendation = a2_result["recommendation"]
                            st.rerun()

# Sidebar Trajectory
with st.sidebar:
    st.header("🧠 Multi-Agent Trajectory")
    for msg in st.session_state.trajectory:
        st.write(f"- {msg}")
