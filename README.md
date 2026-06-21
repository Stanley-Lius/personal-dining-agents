# 🍽️ Concierge Dining Advisor

An autonomous multi-agent dining concierge designed for the **Kaggle AI Agents: Intensive Vibe Coding Capstone Project**. This project embodies the core philosophies of **Agentic Engineering** and **Vibe Coding** to deliver an intelligent, self-correcting assistant that understands your dining preferences.

**Kaggle Username:** w550954

---

## 🚀 The Pitch: Why Agents?

### The Problem
Finding a restaurant is easy; finding one that fits your real-time constraints (open now, 10 mins away) *and* your unstated personal vibes (doesn't like loud places, hates cilantro) is incredibly hard. Standard filtering algorithms fail at fuzzy constraints and cannot dynamically reason about the trade-offs of real-world dining.

### The Solution
We built a multi-agent system that acts like a human concierge. It doesn't just filter; it *evaluates*. It can visually read a menu photo to check exact prices, synthesize past dining rejections into future preferences, and self-correct when it realizes a proposed restaurant will close before you arrive.

## 🧠 Key Agentic Concepts Demonstrated

This project directly addresses the Hackathon rubric by applying the following concepts:

1. **Agent / Multi-agent system**: 
   - **Agent 1 (The Planner)**: Handles user interaction, synthesizes memory, and creates high-level goals. It distinguishes between *hard* constraints (explicit user requests) and *soft* constraints (inferred from past data).
   - **Agent 2 (The Executor)**: Specialized in querying external APIs (Google Maps) and visually analyzing menus to verify if real-world constraints are strictly met.
2. **MCP Server**: 
   - Built a local **Model Context Protocol (FastMCP) Server** connecting an SQLite database to give Agent 1 long-term memory of dining history and feedback.
3. **Agent Skills / Tools Use**: 
   - Agents are equipped with tools to query Google Maps, visually analyze photos, and search the web for menu prices.
4. **Deployability**: 
   - Seamlessly deployable via Streamlit Community Cloud with a Dev Container setup for easy local reproduction.

## 🧗 The Build Journey: Challenges & Solutions

Building autonomous agents for real-world tasks presents unique challenges. Here is how we solved them using an agentic approach:

### Challenge 1: The "Closed Upon Arrival" Problem
APIs often return places that match a query but close in 10 minutes. Early iterations of the agent recommended closed restaurants.
* **Solution (Fallback Loop)**: We implemented a strict verification step in Agent 2. It fetches the top 5 places and strictly compares "Today's Hours" against "Current Local Time" + "Travel Time". If a restaurant fails, Agent 2 autonomously rejects it and evaluates the next option without bothering the user. If all 5 fail, it triggers Agent 1 to re-plan.

### Challenge 2: Context Window Bloat
Feeding the user's entire dining history into the prompt for every query was inefficient and expensive.
* **Solution (Dual-Memory System)**: We built a local **MCP Server** with SQLite to retrieve only the 3 most recent interactions for short-term context. For long-term context, Agent 1 organically rewrites a concise Markdown preference profile whenever the user accepts or rejects a recommendation. 

### Challenge 3: Finding Exact Prices
Standard APIs rarely return accurate menu prices, usually just returning a generic `$$` indicator.
* **Solution (Visual Tooling)**: We gave Agent 2 the ability to fetch restaurant menu photos from Google Maps and analyze them using Gemini Vision to extract exact dish prices. If the photos are unreadable, it falls back to a `google_search` tool.

## 🛠️ System Architecture

- **Frontend**: Streamlit (Chat-based UI designed for real-time vibe interactions)
- **AI Brain**: Google Gemini 2.5 via `google-genai` SDK
- **Data & Tools Integration**: FastMCP serving an SQLite database.
- **External APIs**: Google Maps Places API (New) for real-time location, hours, reviews, and images.

### Noteworthy UI Features
- **Transparent Trajectory Tracing**: A real-time sidebar logs the internal thoughts, actions, and rejections of both agents, providing deep visibility into the system's dynamic decision-making.
- **State Management & Reset**: Direct controls to edit the Markdown memory profile or reset the database entirely, demonstrating robust user data lifecycle control.

## 💻 Quick Start

### Prerequisites
1. Python >= 3.10
2. Google Gemini API Key (`GEMINI_API_KEY`)
3. Google Maps API Key (`GOOGLE_MAPS_API_KEY`)

### Local Setup
```bash
git clone https://github.com/Stanley-Lius/personal-dining-agents.git
cd agent
pip install -r requirements.txt
streamlit run app.py
```
