"""
agent/storage.py
Persistent storage for agent configuration and execution state.
Guarantees clean UTF-8 without BOM and strictly strips private tokens before saving to disk.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "niche": "Competitive Gaming, Valorant, and Dark Psychological Anime",
    "persona": "A 20-something competitive gamer and anime enthusiast.",
    "custom_instructions": "Keep it authentic, punchy, and engaging.",
    "post_styles": ["VIRAL_QUESTION", "HOT_TAKE", "RELATABLE_MOMENT", "UNPOPULAR_OPINION"],
    "auto_reply_enabled": True,
    "max_threads_to_scan": 3,
    "gemini_model": "gemini-3-flash-preview",
}

DEFAULT_STATE = {
    "replied_comment_ids": [],
    "last_post_id": None,
}


def load_config(path: str = "config.json") -> dict:
    """Loads configuration with fallback to defaults."""
    if not os.path.exists(path):
        logger.warning("Config file %s not found. Using defaults.", path)
        return DEFAULT_CONFIG.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error("Error reading %s: %s", path, e)
        return DEFAULT_CONFIG.copy()


def load_state(path: str = "state.json") -> dict:
    """Loads persistent state with fallback to defaults."""
    if not os.path.exists(path):
        logger.info("State file %s not found. Initializing empty state.", path)
        return DEFAULT_STATE.copy()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            for key, default_val in DEFAULT_STATE.items():
                if key not in data:
                    data[key] = default_val
            return data
    except Exception as e:
        logger.error("Error reading %s: %s", path, e)
        return DEFAULT_STATE.copy()


def save_state(state: dict, path: str = "state.json") -> None:
    """Saves state atomically and strips all private tokens."""
    sanitized = state.copy()
    sanitized.pop("active_threads_token", None)
    sanitized.pop("active_ig_token", None)

    temp_path = f"{path}.tmp"
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(sanitized, f, indent=2, ensure_ascii=False)
            f.write("\n")
        if os.path.exists(path):
            os.replace(temp_path, path)
        else:
            os.rename(temp_path, path)
        logger.info("Saved sanitized state to %s (zero private tokens exposed).", path)
    except Exception as e:
        logger.error("Failed to save state to %s: %s", path, e)
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
