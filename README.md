# 🍽️ Concierge Dining Advisor

An autonomous multi-agent dining concierge designed for the **Kaggle AI Agents: Intensive Vibe Coding Capstone Project**. This project embodies the core philosophies of **Agentic Engineering** and **Vibe Coding** to deliver an intelligent, self-correcting assistant that understands your dining preferences.

**Kaggle Username:** w550954

## 🚀 The Vision: Vibe Coding meets Agentic Engineering

This project is built from the ground up focusing on rapid prototyping, seamless flow, and agentic orchestration (Vibe Coding). Rather than writing every piece of logic imperatively, the system relies on specialized AI agents orchestrating dynamic context handling, tool use, and self-improvement loops.

### Key Agentic Patterns Implemented
1. **Multi-Agent Orchestration**: 
   - **Agent 1 (The Planner)**: Handles user interaction, memory synthesis, and high-level goal planning. It distinguishes between *hard* constraints (explicit user requests) and *soft* constraints (inferred from past data).
   - **Agent 2 (The Executor)**: Specialized in querying external APIs (Google Maps) and visually analyzing menus to verify if real-world constraints (like current time and travel distance) are met.
2. **Context Memory & Self-Improvement Loop**: 
   The system utilizes an **MCP (Model Context Protocol) SQLite Database Server** to persist user interactions. When a user accepts or rejects a recommendation, Agent 1 actively rewrites a Markdown preference profile ensuring the agent gets smarter over time.
3. **Auto-Correction & Reflection (Fallback Loop)**: 
   If Agent 2 discovers a restaurant is closed upon arrival or doesn't match the criteria, it explicitly rejects the finding. Agent 2 then **iterates through a fallback list of the top 5 best-matching restaurants** before ultimately asking Agent 1 to re-plan with relaxed constraints if all candidates fail.
4. **State Management & Reset**: 
   The UI provides a direct control to reset the database and Markdown memory profiles while maintaining the underlying schema formats, demonstrating robust user data lifecycle control.

## 🛠️ System Architecture

- **Frontend**: Streamlit (Chat-based UI designed for real-time vibe interactions)
- **AI Brain**: Google Gemini 2.5 (Flash/Pro) via `google-genai` SDK
- **Data & Tools Integration**: Model Context Protocol (FastMCP) serving an SQLite database.
- **External APIs**: Google Maps Places API (New) for real-time location, opening hours, reviews, and visual menu analysis.

### Directory Structure
```text
.
├── app.py                      # Main Streamlit Orchestration
├── requirements.txt            # System dependencies
├── README.md                   
├── /src                        # Core agent logic and tools
│   ├── map_search.py           # Google Maps API Integration
│   ├── utils.py                # Preference synthesis tools
│   └── db_mcp_server.py        # FastMCP Database Server
├── /data                       # Local persistent context
│   ├── dev_dining_history.db   # SQLite Memory
│   └── user_preferences_*.md   # Markdown profiles
├── /specs                      # Technical documentation
└── /docs                       # Reference documents
```

## 💻 Quick Start & Deployment

This project is designed for seamless deployment on **Streamlit Community Cloud** and **GitHub Pages**.

### Prerequisites
1. Python >= 3.10
2. Google Gemini API Key (`GEMINI_API_KEY`)
3. Google Maps API Key (`GOOGLE_MAPS_API_KEY`)

### Local Setup
```bash
# Clone the repository
git clone [https://github.com/Stanley-Lius/Agents.git](https://github.com/Stanley-Lius/personal-dining-agents.git)
cd agent

# Install dependencies
pip install -r requirements.txt

# Run the application
streamlit run app.py
```

## 🏆 Hackathon Focus
This project directly addresses the capstone requirements by integrating a custom MCP server, leveraging advanced prompt engineering (reflection and explicit reasoning constraints), and adopting an agile, vibe-coding approach to build a highly personal, location-aware agent.
