# Agent Design: Concierge Dining Advisor

This document details the multi-agent orchestration, agent roles, prompts, and communication protocols for the Concierge Dining Advisor project.

## 1. Multi-Agent Choreography

The system utilizes a dual-agent architecture to split the cognitive load between understanding user preferences (Agent 1) and executing external API searches (Agent 2).

**Workflow:**
1. **User Input:** User provides criteria (e.g., "烤肉, 預算1000台幣, 距離開車20分鐘內, 晚間5:00, 內用") and current location.
2. **Agent 1 (Dietary Manager):** 
   - Retrieves user's past eating habits and preferences via the DB MCP Server.
   - Synthesizes the user's constraints with historical preferences to generate a concrete **Menu Suggestion** (e.g., "User likes Japanese BBQ, budget fits 'Yakiniku Smile', suggest dining in").
   - Sends the structured suggestion and search criteria to Agent 2.
3. **Agent 2 (Restaurant Matcher):**
   - Receives criteria from Agent 1.
   - Formulates and executes a query using the **Google Maps API**.
   - Evaluates the results. 
     - **If successful:** Formats the best option (Name, Menu recommendation, Price, Reason) and returns it to Agent 1.
     - **If unsuccessful:** Returns a failure notice with reasons (e.g., "No BBQ open at 5 PM within 20 mins").
4. **Agent 1 (Feedback Loop):**
   - **On Success:** Presents the option to the user. 
     - If User **Accepts**: Agent 1 logs the choice to the DB MCP to improve future recommendations.
     - If User **Rejects**: Agent 1 asks for the reason, logs the negative feedback to the DB MCP, redesigns the menu suggestion, and re-triggers Agent 2.
   - **On Failure:** Asks the user to relax constraints or suggests alternative food types based on history.

---

## 2. Agent 1 Specification (Habit & Menu Planner)

**Role:** The core brain interacting with the user, managing memory, and planning.

**System Prompt (Draft):**
> You are a Concierge Dining Planner. Your primary goal is to provide highly personalized restaurant and menu suggestions.
> You have access to the user's eating history and preferences via the Database MCP.
> When a user gives you dining constraints (food type, budget, distance, time, dine-in/take-out) and location:
> 1. Query the DB MCP to understand their past preferences and aversions.
> 2. Formulate a specific "Menu Suggestion" that aligns their request with their history.
> 3. Delegate the actual restaurant search to the Restaurant Matcher Agent (Agent 2) by providing it with your Menu Suggestion and the user's constraints.
> 4. When Agent 2 replies, present the finding to the user.
> 5. If the user rejects the suggestion, ask why, record this feedback via the DB MCP, and plan a new suggestion for Agent 2. If the user accepts, record the success via the DB MCP.

**Tools (Skills):**
- `get_user_preferences(user_id)`: Retrieve dietary history.
- `log_user_feedback(user_id, restaurant, status, reason)`: Store accept/reject data.
- `delegate_to_matcher(criteria, menu_suggestion)`: Send message to Agent 2.

---

## 3. Agent 2 Specification (Restaurant Matcher)

**Role:** The execution agent specialized in geospatial search and API interaction.

**System Prompt (Draft):**
> You are a Restaurant Matcher Agent. Your job is to take a specific menu suggestion and constraints (location, time, budget, distance, food type) and find the single best restaurant matching these criteria using the Google Maps API.
> Focus on minimizing API calls: formulate precise search queries based on the constraints.
> Return the result strictly in this format: 
> - Restaurant Name
> - Recommended Menu Items
> - Price Range
> - Recommendation Reason (matching the constraints)
> If no restaurant perfectly matches, return a structured failure message indicating which constraint failed (e.g., distance or open hours).

**Tools (Skills):**
- `search_nearby_restaurants(location, keyword, radius_meters, open_now)`: Google Maps Places API wrapper.
- `get_route_duration(origin, destination, mode)`: Google Maps Distance Matrix/Directions API wrapper to check driving time.

---

## 4. Message Protocols (JSON Format)

**Agent 1 -> Agent 2 (Search Request):**
```json
{
  "location": "Current Lat,Lng or Address",
  "constraints": {
    "food_type": "烤肉",
    "budget_max": 1000,
    "max_duration_mins": 20,
    "time": "17:00",
    "mode": "dine-in"
  },
  "menu_suggestion": "User prefers Japanese style BBQ. Look for places with high ratings for Wagyu or set meals."
}
```

**Agent 2 -> Agent 1 (Search Response - Success):**
```json
{
  "status": "success",
  "data": {
    "restaurant_name": "Yakiniku Smile",
    "recommended_menu": "Premium Beef Set",
    "price_range": "800-1000 NTD",
    "reason": "Matches Japanese BBQ preference, within 15 mins drive, open at 17:00."
  }
}
```

**Agent 2 -> Agent 1 (Search Response - Failure):**
```json
{
  "status": "failure",
  "reason": "No BBQ places found within a 20-minute drive that open at 17:00."
}
```
