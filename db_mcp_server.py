import os
from dotenv import load_dotenv
load_dotenv(override=True)
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from mcp.server.fastmcp import FastMCP

# --- Security & Audit Logging (MCP_roles.txt Compliance) ---
# We set up logging to ensure all tool usage is audited.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DB_MCP_Server")

# --- Environment Variable & DB Configuration ---
# Complying with: "Don't hardcode credentials" & "Development Data Only"
# We default to a clearly named dev database if the environment variable is not set.
DB_PATH = os.environ.get("DINING_DB_PATH", "dev_dining_history.db")

# Initialize the FastMCP Server
# This is the most stable and official way to build MCP servers in Python.
mcp = FastMCP("DiningHistoryDB")

def init_db():
    """Initialize the SQLite development database and create tables if they do not exist."""
    logger.info(f"Initializing database at {DB_PATH}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Table 1: User Profiles
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            dietary_restrictions TEXT,
            preferred_cuisines TEXT
        )
    ''')
    
    # Table 2: Dining History 
    # (Includes new columns: price_range, dining_time as requested)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS dining_history (
            record_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            restaurant_name TEXT,
            price_range TEXT,
            dining_time TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT,  -- e.g., 'accepted', 'rejected'
            feedback_reason TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialization complete.")

# --- MCP Tools (Skills) Exposed to the Agent ---

@mcp.tool()
def get_user_profile(user_id: str) -> Dict[str, Any]:
    """
    Retrieve the general preferences and dietary restrictions for a user.
    """
    logger.info(f"[AUDIT] Tool Called: get_user_profile for user_id={user_id}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return dict(row)
    else:
        return {"error": "User not found", "user_id": user_id}

@mcp.tool()
def update_user_preferences(user_id: str, name: str, dietary_restrictions: str, preferred_cuisines: str) -> str:
    """
    Create or update a user's general dining preferences.
    """
    logger.info(f"[AUDIT] Tool Called: update_user_preferences for user_id={user_id}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO users (user_id, name, dietary_restrictions, preferred_cuisines)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            name=excluded.name,
            dietary_restrictions=excluded.dietary_restrictions,
            preferred_cuisines=excluded.preferred_cuisines
    ''', (user_id, name, dietary_restrictions, preferred_cuisines))
    
    conn.commit()
    conn.close()
    return f"Successfully updated preferences for user {user_id}."

@mcp.tool()
def get_recent_history(user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """
    Retrieve the user's recent dining history and feedback to understand what they recently liked/rejected.
    """
    logger.info(f"[AUDIT] Tool Called: get_recent_history for user_id={user_id}, limit={limit}")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT restaurant_name, price_range, dining_time, timestamp, status, feedback_reason 
        FROM dining_history 
        WHERE user_id = ? 
        ORDER BY timestamp DESC LIMIT ?
    ''', (user_id, limit))
    
    rows = cursor.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

@mcp.tool()
def record_dining_feedback(
    user_id: str, 
    restaurant_name: str, 
    price_range: str, 
    dining_time: str, 
    status: str, 
    feedback_reason: str
) -> str:
    """
    Record an accepted or rejected dining recommendation.
    Status should be 'accepted' or 'rejected'.
    """
    logger.info(f"[AUDIT] Tool Called: record_dining_feedback for user_id={user_id}, restaurant={restaurant_name}, status={status}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO dining_history (user_id, restaurant_name, price_range, dining_time, status, feedback_reason)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, restaurant_name, price_range, dining_time, status, feedback_reason))
    
    conn.commit()
    conn.close()
    return f"Successfully recorded {status} feedback for restaurant '{restaurant_name}'."

if __name__ == "__main__":
    # Initialize DB before starting server
    init_db()
    logger.info("Starting Database MCP Server via stdio transport...")
    
    # Run the server using Standard IO (stdio) which is the default for MCP integration
    mcp.run(transport="stdio")
