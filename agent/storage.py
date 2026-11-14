"""
agent/storage.py
Handles loading and persisting configuration and operational state.
Uses utf-8-sig encoding for safe reading (stripping any accidental BOM)
and standard utf-8 without BOM for writing.
"""
import json
import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_CONFIG = {
    "niche": "Competitive Gaming, Valorant, and Dark Psychological Anime",
    "persona": (
        "A 20-year-old gamer and anime fan posting raw, casual thoughts from their phone. "
        "Witty, blunt, relatable, never sounds like a brand or AI."
    ),
    "custom_instructions": (
        "Use natural phrasing and occasional lowercase. Never use corporate buzzwords, "
        "emojis, or motivational quotes. Maximum 1 hashtag or none at all. "
        "Focus on sparking debates and giving honest mini-reviews."
    ),
    "post_styles": [
        "MINI_REVIEW",
        "QUESTION_DEBATE",
        "HOT_TAKE",
    ],
    "auto_reply_enabled": True,
    "max_threads_to_scan": 3,
    "gemini_model": "gemini-3.8-flash",
}

DEFAULT_STATE = {
    "replied_comment_ids": [],
    "last_post_id": None,
    "active_threads_token": None,
}


def load_config(filepath: str = "config.json") -> dict:
    """
    Loads user configuration from JSON, stripping any BOM via utf-8-sig.
    Merges existing data over defaults to guarantee all required keys exist.
    """
    config = dict(DEFAULT_CONFIG)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                user_data = json.load(f)
            if isinstance(user_data, dict):
                config.update(user_data)
                logger.info("Successfully loaded config from %s", filepath)
            else:
                logger.warning("%s did not contain a JSON object. Using defaults.", filepath)
        except Exception as e:
            logger.error("Error reading %s: %s. Falling back to defaults.", filepath, e)
    else:
        logger.info("%s not found. Using default configuration.", filepath)
    return config


def load_state(filepath: str = "state.json") -> dict:
    """
    Loads agent runtime state from JSON, stripping any BOM via utf-8-sig.
    Merges existing data over defaults.
    """
    state = dict(DEFAULT_STATE)
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8-sig") as f:
                user_data = json.load(f)
            if isinstance(user_data, dict):
                state.update(user_data)
                logger.info("Successfully loaded state from %s", filepath)
            else:
                logger.warning("%s did not contain a JSON object. Using default state.", filepath)
        except Exception as e:
            logger.error("Error reading %s: %s. Falling back to default state.", filepath, e)
    else:
        logger.info("%s not found. Initializing fresh state.", filepath)

    if not isinstance(state.get("replied_comment_ids"), list):
        state["replied_comment_ids"] = []

    return state


def save_state(state: dict, filepath: str = "state.json") -> None:
    """
    Saves state to JSON, capping replied_comment_ids to the last 1,500 entries.
    Writes in standard UTF-8 without BOM with 2-space indentation.
    """
    replied = state.get("replied_comment_ids", [])
    if isinstance(replied, list) and len(replied) > 1500:
        state["replied_comment_ids"] = replied[-1500:]
        logger.info("Capped replied_comment_ids to latest 1,500 entries.")

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
            f.write("\n")
        logger.info("Saved state to %s", filepath)
    except Exception as e:
        logger.error("Failed to write state to %s: %s", filepath, e)
        raise
