import os
import logging

logger = logging.getLogger(__name__)

def get_markdown_filename(user_id: str) -> str:
    return f"data/user_preferences_{user_id}.md"

def load_user_markdown(user_id: str) -> str:
    """Loads the user's preference markdown file. Returns an empty string if it doesn't exist."""
    filename = get_markdown_filename(user_id)
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            logger.error(f"Failed to read {filename}: {e}")
    return "尚無此使用者的歷史偏好紀錄。"

def save_user_markdown(user_id: str, content: str) -> bool:
    """Saves the user's preference markdown file."""
    filename = get_markdown_filename(user_id)
    try:
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to write {filename}: {e}")
        return False
