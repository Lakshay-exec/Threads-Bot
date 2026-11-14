"""
agent/threads_api.py
Direct client interface for the official Meta Threads Graph API (v1.0).
Handles automatic 60-day token refresh, two-step container publishing,
and reading/replying to user interactions.
"""
import logging
import os
import time
import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://graph.threads.net/v1.0"
REFRESH_URL = "https://graph.threads.net/refresh_access_token"


def get_token(state: dict) -> str:
    """
    Returns the active refreshed token from state.json if available,
    falling back to the THREADS_ACCESS_TOKEN environment variable.
    Guarantees every API call uses the newest active token.
    """
    token = state.get("active_threads_token") or os.environ.get("THREADS_ACCESS_TOKEN", "").strip()
    if not token:
        raise ValueError(
            "Missing Threads access token. Set THREADS_ACCESS_TOKEN in secrets or environment, "
            "or populate active_threads_token in state.json."
        )
    return token


def get_user_id() -> str:
    """Fetches the numeric Threads User ID from environment variables."""
    user_id = os.environ.get("THREADS_USER_ID", "").strip()
    if not user_id:
        raise ValueError("Missing THREADS_USER_ID environment variable.")
    return user_id


def auto_refresh_token(state: dict) -> bool:
    """
    Calls GET https://graph.threads.net/refresh_access_token with grant_type='th_refresh_token'.
    If a renewed 60-day token is returned, updates state['active_threads_token'].
    Meta requires tokens to be at least 24 hours old before refresh;
    returns False safely if not yet eligible.
    """
    try:
        current_token = get_token(state)
    except ValueError as e:
        logger.error("Cannot refresh token: %s", e)
        return False

    params = {
        "grant_type": "th_refresh_token",
        "access_token": current_token,
    }

    try:
        logger.info("Checking Threads access token status with refresh endpoint...")
        response = requests.get(REFRESH_URL, params=params, timeout=30)
        data = response.json()

        if response.status_code == 200 and "access_token" in data:
            new_token = data["access_token"]
            expires_in = data.get("expires_in", "unknown")
            state["active_threads_token"] = new_token
            logger.info("Token refreshed successfully! Valid for approx %s seconds.", expires_in)
            return True
        else:
            logger.info(
                "Token refresh not required or token not yet eligible (>24h needed). Status: %s - %s",
                response.status_code,
                data.get("error", {}).get("message", response.text),
            )
            return False
    except Exception as e:
        logger.warning("Token refresh request encountered an error: %s. Continuing with current token.", e)
        return False


def publish_post(text: str, state: dict) -> dict:
    """
    Publishes a new top-level text post to Threads via Meta's 2-step container workflow:
    1. POST /{user_id}/threads (media_type="TEXT")
    2. Wait 30 seconds for Meta processing
    3. POST /{user_id}/threads_publish
    """
    user_id = get_user_id()
    token = get_token(state)

    # Step 1: Create media container
    create_url = f"{BASE_URL}/{user_id}/threads"
    create_payload = {
        "media_type": "TEXT",
        "text": text,
        "access_token": token,
    }

    logger.info("Creating Threads post container...")
    create_res = requests.post(create_url, data=create_payload, timeout=30)
    create_res.raise_for_status()
    create_data = create_res.json()
    creation_id = create_data.get("id")

    if not creation_id:
        raise RuntimeError(f"Threads API did not return container ID: {create_res.text}")

    logger.info("Container %s created. Waiting 30s for Meta processing...", creation_id)
    time.sleep(30)

    # Step 2: Publish container
    pub_url = f"{BASE_URL}/{user_id}/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": token,
    }

    logger.info("Publishing container %s...", creation_id)
    pub_res = requests.post(pub_url, data=pub_payload, timeout=30)
    pub_res.raise_for_status()
    pub_data = pub_res.json()

    logger.info("Successfully published thread post! Post ID: %s", pub_data.get("id"))
    return pub_data


def get_recent_threads(state: dict, limit: int = 3) -> list[dict]:
    """
    Fetches the user's most recent Threads posts.
    """
    user_id = get_user_id()
    token = get_token(state)

    url = f"{BASE_URL}/{user_id}/threads"
    params = {
        "fields": "id,text,timestamp",
        "limit": limit,
        "access_token": token,
    }

    try:
        res = requests.get(url, params=params, timeout=30)
        res.raise_for_status()
        data = res.json().get("data", [])
        logger.info("Retrieved %d recent threads.", len(data))
        return data
    except Exception as e:
        logger.error("Failed to fetch recent threads: %s", e)
        return []


def get_replies(thread_id: str, state: dict) -> list[dict]:
    """
    Retrieves incoming replies for a specific thread ID.
    """
    token = get_token(state)
    url = f"{BASE_URL}/{thread_id}/replies"
    params = {
        "fields": "id,text,username,timestamp",
        "access_token": token,
    }

    try:
        res = requests.get(url, params=params, timeout=30)
        res.raise_for_status()
        replies = res.json().get("data", [])
        logger.info("Retrieved %d replies for thread %s.", len(replies), thread_id)
        return replies
    except Exception as e:
        logger.warning("Could not fetch replies for thread %s: %s", thread_id, e)
        return []


def publish_reply(reply_to_id: str, text: str, state: dict) -> dict:
    """
    Publishes a reply to an existing comment/thread using Meta's 2-step container workflow:
    1. POST /{user_id}/threads with reply_to_id
    2. Wait 30 seconds
    3. POST /{user_id}/threads_publish
    """
    user_id = get_user_id()
    token = get_token(state)

    # Step 1: Create reply container
    create_url = f"{BASE_URL}/{user_id}/threads"
    create_payload = {
        "media_type": "TEXT",
        "text": text,
        "reply_to_id": reply_to_id,
        "access_token": token,
    }

    logger.info("Creating reply container targeting comment %s...", reply_to_id)
    create_res = requests.post(create_url, data=create_payload, timeout=30)
    create_res.raise_for_status()
    creation_id = create_res.json().get("id")

    if not creation_id:
        raise RuntimeError(f"Threads API did not return reply container ID: {create_res.text}")

    logger.info("Reply container %s created. Waiting 30s for Meta processing...", creation_id)
    time.sleep(30)

    # Step 2: Publish reply
    pub_url = f"{BASE_URL}/{user_id}/threads_publish"
    pub_payload = {
        "creation_id": creation_id,
        "access_token": token,
    }

    logger.info("Publishing reply container %s...", creation_id)
    pub_res = requests.post(pub_url, data=pub_payload, timeout=30)
    pub_res.raise_for_status()
    pub_data = pub_res.json()

    logger.info("Successfully published reply! Reply ID: %s", pub_data.get("id"))
    return pub_data
