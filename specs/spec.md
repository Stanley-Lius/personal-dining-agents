# System Specification: Concierge Dining Advisor

## 1. Overview
The Concierge Dining Advisor is a multi-agent system designed for the Kaggle "AI Agents: Intensive Vibe Coding Capstone Project". 
It acts as a personalized dining assistant that tracks user eating habits, synthesizes real-time constraints (location, budget, time, distance), and uses Google Maps API to recommend the best restaurant and menu options. The system features a self-improvement loop where user feedback (accept/reject) updates their historical preferences.

**Target Track:** Concierge Agents
**Primary Language:** Python

---

## 2. System Architecture

The architecture consists of four main components:
1. **Frontend UI:** An interactive web interface (Streamlit or Gradio) allowing users to input constraints and chat with the agent.
2. **Agent 1 (Dietary Preference Manager):** The orchestrator agent. Interacts with the user, manages memory, and handles the self-improvement loop.
3. **Agent 2 (Restaurant Matcher):** The execution agent. Specialized in querying the Google Maps API efficiently based on precise criteria.
4. **Database MCP Server:** A local Model Context Protocol (MCP) server managing an SQLite database to store user profiles, dining history, and preference vectors.

---

## 3. Dual-Memory System: MCP Server & Markdown Profiles

To solve the challenge of context window bloat when feeding an entire dining history to the LLM, we implemented a dual-memory architecture:

1. **Short-Term Context (SQLite via MCP)**: 
   The local Model Context Protocol (MCP) Server provides tools for Agent 1 to read/write recent interactions. We fetch only the `limit=3` most recent records to maintain conversational continuity.
2. **Long-Term Memory (Markdown Profiles)**: 
   Whenever the user accepts or rejects a restaurant, the system updates a concise Markdown profile (`user_preferences_*.md`). This organically synthesizes overriding dietary habits into a lean text file, ensuring the agent gets smarter over time without exploding the prompt size.

**SQLite Schema Draft:**
- `users`: `user_id`, `name`, `general_preferences`
- `dining_history`: `record_id`, `user_id`, `restaurant_name`, `food_type`, `price`, `timestamp`, `user_rating` (accept/reject), `feedback_reason`

**MCP Tools Provided:**
- `get_user_profile(user_id)`
- `get_recent_history(user_id, limit)`
- `record_feedback(user_id, restaurant_data, feedback_reason)`
- `clear_user_data(user_id)`

---

## 4. API Integration & Cost Control

**Language Models:**
- **Gemini API (`google-genai`):** Used as the brain for both Agent 1 and Agent 2. 
- *Cost Control:* We will use `gemini-2.5-flash` for Agent 2 (faster, cheaper for parsing JSON and API results) and `gemini-2.5-pro` (or flash depending on complexity) for Agent 1 (requires better reasoning for user intent and history synthesis).

**Google Maps API:**
- **Places API (New or Legacy):** Used for `Text Search` or `Nearby Search` to find restaurants.
- **Distance Matrix API:** Used to verify the "within X minutes driving" constraint.
- *Cost Control & Agent 2 Execution:* 
  - Agent 2 performs a broad Places API search first and retrieves the top 5 highest-scored restaurants based on ratings and user review counts.
  - It sequentially iterates through these candidates. If a candidate fails the strict LLM verification (e.g., closed today, doesn't match requirements), Agent 2 automatically evaluates the next best option.
  - Only if all 5 candidates fail will Agent 2 return an error to Agent 1, triggering a re-plan or user prompt.

---

## 5. UI & Deployment

**Web Framework:** Streamlit (`streamlit` package)
- Provides a clean, chat-based interface (`st.chat_message`).
- Allows sidebar configuration for API keys, user simulation selection, and current location mock.

**Directory Structure:**
- `app.py`: Main Streamlit interface
- `src/`: Core agent logic, Google Maps integration, and MCP server
- `data/`: Local SQLite database and Markdown preference profiles
- `specs/` & `docs/`: System specs and documentation files

**Deployment & Sync:**
- The project will be initialized as a Git repository and pushed to GitHub.
- The Streamlit app is intended to be deployed on Streamlit Community Cloud.
- A GitHub Page will be used to present project documentation and results for Kaggle Hackathon judges.
