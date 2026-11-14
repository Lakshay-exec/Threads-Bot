"""
main.py
Main entrypoint for the Meta Threads AI Agent.
Orchestrates configuration, token refresh, post generation/publishing,
smart reply engagement, and persistent state management.
"""
import logging
import os
import sys

# Attempt to load local .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from agent.brain import generate_post, generate_reply
from agent.storage import load_config, load_state, save_state
from agent.threads_api import (
    auto_refresh_token,
    get_recent_threads,
    get_replies,
    publish_post,
    publish_reply,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("threads-agent")


def validate_environment(state: dict) -> bool:
    """Validates that necessary credentials exist in environment or state."""
    missing = []
    if not os.environ.get("GEMINI_API_KEY"):
        missing.append("GEMINI_API_KEY")
    if not os.environ.get("THREADS_USER_ID"):
        missing.append("THREADS_USER_ID")

    has_token = bool(state.get("active_threads_token") or os.environ.get("THREADS_ACCESS_TOKEN"))
    if not has_token:
        missing.append("THREADS_ACCESS_TOKEN (or active_threads_token in state.json)")

    if missing:
        logger.error("Missing required credentials: %s", ", ".join(missing))
        return False
    return True


def main():
    logger.info("=== Starting Meta Threads AI Agent ===")

    # 1. Load config and state
    config = load_config()
    state = load_state()

    # 2. Check credentials
    if not validate_environment(state):
        logger.error("Environment verification failed. Please configure repository secrets or .env.")
        sys.exit(1)

    # 3. Token Auto-Refresh
    logger.info("--- Step 1: Checking and Auto-Refreshing Access Token ---")
    try:
        refreshed = auto_refresh_token(state)
        if refreshed:
            logger.info("Threads access token renewed.")
    except Exception as e:
        logger.error("Token refresh check failed: %s", e)

    # 4. Generate and Publish Post
    logger.info("--- Step 2: Content Creation & Publishing ---")
    try:
        post_text = generate_post(config)
        logger.info("Generated post draft:\n%s", post_text)
        result = publish_post(post_text, state)
        post_id = result.get("id")
        if post_id:
            state["last_post_id"] = post_id
            logger.info("Successfully published post to Threads! ID: %s", post_id)
    except Exception as e:
        logger.error("Post generation/publishing failed: %s", e)

    # 5. Audience Engagement / Auto-Reply
    logger.info("--- Step 3: Audience Engagement & Auto-Reply ---")
    if config.get("auto_reply_enabled", True):
        try:
            max_threads = config.get("max_threads_to_scan", 3)
            recent_threads = get_recent_threads(state, limit=max_threads)
            replied_ids = set(state.get("replied_comment_ids", []))
            processed_count = 0

            for thread in recent_threads:
                thread_id = thread.get("id")
                thread_text = thread.get("text", "")
                if not thread_id:
                    continue

                replies = get_replies(thread_id, state)
                for reply in replies:
                    comment_id = reply.get("id")
                    author = reply.get("username", "user")
                    comment_text = reply.get("text", "")

                    if not comment_id or comment_id in replied_ids:
                        continue

                    logger.info("Evaluating reply from @%s on thread %s...", author, thread_id)
                    try:
                        reply_draft = generate_reply(
                            post_text=thread_text,
                            author=author,
                            comment_text=comment_text,
                            config=config,
                        )

                        if reply_draft:
                            logger.info("Posting reply to @%s: '%s'", author, reply_draft)
                            publish_reply(reply_to_id=comment_id, text=reply_draft, state=state)
                        else:
                            logger.info("Skipped spam/irrelevant comment %s from @%s.", comment_id, author)

                        # Record processed comment ID in state
                        state.setdefault("replied_comment_ids", []).append(comment_id)
                        replied_ids.add(comment_id)
                        processed_count += 1

                    except Exception as reply_err:
                        logger.error("Failed to handle reply for comment %s: %s", comment_id, reply_err)

            logger.info("Engagement step complete. Processed %d new comments.", processed_count)
        except Exception as e:
            logger.error("Engagement pipeline encountered an error: %s", e)
    else:
        logger.info("Auto-reply is disabled in config.json.")

    # 6. Save State
    logger.info("--- Step 4: Persisting Agent State ---")
    try:
        save_state(state)
        logger.info("State successfully updated and saved to state.json.")
    except Exception as e:
        logger.error("Failed to save state.json: %s", e)

    logger.info("=== Meta Threads AI Agent Run Completed ===")


if __name__ == "__main__":
    main()
