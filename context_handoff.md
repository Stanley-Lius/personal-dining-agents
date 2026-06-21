# Concierge Dining Advisor - Project Context Handoff

This document summarizes the current state, architecture, and recent optimizations of the Concierge Dining Advisor project. Please provide this to the AI Assistant in your new chat session to quickly bring them up to speed.

## 🏗️ System Architecture

The project is built on **Python**, **Streamlit**, and the **Google GenAI SDK (Gemini 2.5 Flash)**. It uses a Multi-Agent architecture:

1. **`app.py` (The Orchestrator)**: Handles the Streamlit UI and coordinates the AI Agents.
2. **Agent 1 (The Planner)**: Reads User Input, Long-Term Memory (Markdown), and Short-Term History (SQLite via MCP). Formulates a natural language search brief for Agent 2. 
3. **Agent 2 (The Executor)**: Generates an optimal Google Maps query, executes the REST API call, and uses **Gemini Vision (Multimodal)** to analyze menu photos and extract exact dish prices. Outputs a strict `RichRestaurantRecommendation` JSON schema.
4. **`map_search.py`**: Interacts with the **Google Maps Places API (New)** REST endpoints (`v1/places:searchText`) and the Media API to download photo bytes.
5. **`utils.py`**: Manages the reading and writing of `user_preferences_{user_id}.md` (Long-Term Memory).
6. **`db_mcp_server.py`**: An MCP (Model Context Protocol) server that logs short-term chat histories and ratings to a local SQLite database.

## 🔄 Core Workflows & Feedback Loops

We have implemented several self-correcting feedback loops to ensure high-quality recommendations:

1. **Agent 1 `[ASK_USER]` Logic**: If the user's input is too vague or missing critical constraints (e.g., budget, location), Agent 1 will output `[ASK_USER: <question>]`. The UI intercepts this and halts, prompting the user for clarification.
2. **Agent 2 `[REJECT_AND_ASK_AGENT1]` Logic (Reverse Loop)**: If Agent 2 finds a restaurant on Google Maps but determines it *fails* Agent 1's core requirements (e.g., asked for buffet, found a la carte), Agent 2 outputs `[REJECT_AND_ASK_AGENT1: <reason>]`. The UI automatically routes this failure back to Agent 1 to broaden the search constraints.
3. **User Rejection Loop**: If the user clicks "❌ 拒絕並重新規劃" in the UI, they can provide a reason. Agent 1 incorporates this rejection into its memory and re-plans instantly.
4. **5-Star Rating Loop**: Users can rate a suggestion. High ratings permanently update the user's Markdown preference file.

## 🚀 Recent Optimizations (v1.0 Ready)

- **Token Optimization**: 
  - Agent 2's reasoning is strictly limited to 50 Chinese characters.
  - Displaying only "Today's" opening hours instead of a massive weekly array.
  - If precise prices cannot be extracted from photos, Agent 2 outputs a `menu_photo_url` which the UI dynamically renders, rather than wasting tokens analyzing every food image.
- **API Bug Fixes**:
  - Bypassed the Gemini API limitation (cannot use `tools` and `response_schema` simultaneously) by splitting Agent 2's execution into a Two-Step process: Step 4a (Analysis + Tools) -> Step 4b (JSON Formatting + Schema).
  - Fixed Agent 1's "Hallucination" bug where it would blindly apply past budgets to new requests. It now treats memory strictly as background reference.

## 📝 Next Steps for New Session

The system is fully functional, stable, and committed to the Git `main` branch. 
To start the app: `streamlit run app.py`

In the new chat, you can ask the AI to:
- Add new features (e.g., multi-user login).
- Integrate new APIs.
- Further refine the UI.
