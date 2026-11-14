"""
agent/brain.py
AI reasoning engine powered by the official google-genai SDK.
Generates human-like, niche-specific Threads posts and smart contextual replies.
"""
import logging
import os
import random
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

STYLE_DESCRIPTIONS = {
    "MINI_REVIEW": (
        "Share an unfiltered, authentic mini-review of a specific game mechanic, anime arc, "
        "episode, agent/champion, or design choice. Be honest and punchy."
    ),
    "QUESTION_DEBATE": (
        "Ask a polarizing, intriguing, or thought-provoking question about the niche "
        "that begs people in the replies to defend their opinions."
    ),
    "HOT_TAKE": (
        "Drop a bold, slightly controversial take that challenges conventional wisdom "
        "in the community while staying relatable."
    ),
}


def _clean_generated_text(text: str) -> str:
    """Strips surrounding quotes and unwanted whitespace from generated text."""
    text = text.strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    # Strip markdown block quotes if present
    if text.startswith("> "):
        text = text[2:].strip()
    return text


def generate_post(config: dict) -> str:
    """
    Randomly selects one of config['post_styles'], injects persona & instructions,
    and generates a human-like Threads post strictly under 350 characters with retry backoff.
    """
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_name = config.get("gemini_model", "gemini-3.8-flash")
    niche = config.get("niche", "Competitive Gaming, Valorant, and Dark Psychological Anime")
    persona = config.get("persona", "A 20-year-old gamer posting casual thoughts.")
    custom_instructions = config.get("custom_instructions", "Keep it casual and authentic.")
    post_styles = config.get("post_styles", ["MINI_REVIEW", "QUESTION_DEBATE", "HOT_TAKE"])

    selected_style = random.choice(post_styles) if post_styles else "HOT_TAKE"
    style_desc = STYLE_DESCRIPTIONS.get(
        selected_style,
        "Share a bold, authentic thought that sparks engagement in the community."
    )

    prompt = f"""You are posting on Meta Threads from your phone.

Persona:
{persona}

Niche:
{niche}

Custom Instructions:
{custom_instructions}

Target Post Style:
[{selected_style}] {style_desc}

Hard Constraints:
1. Write ONE raw, organic post.
2. STRICT LENGTH: Absolutely must be under 350 characters total.
3. Sound completely natural, casual, and human. No corporate buzzwords, no AI clichés.
4. Output ONLY the raw post content. No introductory text, no explanations, no wrapping quotes.
"""

    max_retries = 3
    delay = 2.0
    last_text = ""

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Generating post (style: %s, attempt %d/%d)...", selected_style, attempt, max_retries)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.88,
                    max_output_tokens=200,
                ),
            )

            raw_text = response.text or ""
            cleaned = _clean_generated_text(raw_text)

            if cleaned and len(cleaned) <= 350:
                logger.info("Generated post (%d chars): %s", len(cleaned), cleaned)
                return cleaned

            last_text = cleaned
            logger.warning(
                "Post length (%d chars) exceeded 350 chars on attempt %d. Retrying...",
                len(cleaned),
                attempt,
            )
        except Exception as e:
            logger.warning("Error generating post on attempt %d: %s", attempt, e)

        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2

    # If all attempts exceeded 350, truncate cleanly at sentence or word boundary
    if last_text:
        truncated = last_text[:347].rsplit(" ", 1)[0] + "..."
        logger.info("Fallback: truncated post to strictly stay under 350 chars.")
        return truncated

    raise RuntimeError("Failed to generate valid Threads post after all retries.")


def generate_reply(post_text: str, author: str, comment_text: str, config: dict) -> str | None:
    """
    Evaluates incoming comments using persona and custom_instructions.
    Returns None if the comment is spam/crypto/self-promo (SKIP),
    otherwise drafts a casual 1-sentence peer-to-peer reply (max 15 words).
    """
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    model_name = config.get("gemini_model", "gemini-3.8-flash")
    persona = config.get("persona", "A 20-year-old gamer posting casual thoughts.")
    custom_instructions = config.get("custom_instructions", "Keep it casual and authentic.")

    prompt = f"""You are managing replies on your Meta Threads account.

Persona:
{persona}

Custom Instructions:
{custom_instructions}

Context:
- Your Post: "{post_text}"
- User @{author} commented: "{comment_text}"

Decision Task:
1. SPAM / SCAM / SELF-PROMO FILTER:
   If the comment is spam, crypto/trading solicitation, bot follow-bait, adult promo,
   or completely irrelevant self-advertisement, output ONLY: SKIP

2. CASUAL PEER REPLY:
   If it is a real human comment:
   - Draft a natural, witty 1-sentence peer-to-peer reply.
   - STRICT CONSTRAINT: Maximum 15 words total.
   - Do NOT include @mentions or greetings like "Hey @{author}".
   - Do NOT wrap in quotes.
   - Output ONLY the reply sentence.
"""

    max_retries = 3
    delay = 2.0

    for attempt in range(1, max_retries + 1):
        try:
            logger.info("Evaluating comment by @%s (attempt %d/%d)...", author, attempt, max_retries)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=60,
                ),
            )

            raw_text = (response.text or "").strip()
            cleaned = _clean_generated_text(raw_text)

            # Check if flagged as SKIP
            if cleaned.upper() == "SKIP" or cleaned.upper().startswith("SKIP"):
                logger.info("Comment by @%s flagged as SKIP (spam/irrelevant/promo).", author)
                return None

            # Enforce max 15 words constraint
            words = cleaned.split()
            if len(words) > 15:
                cleaned = " ".join(words[:15])

            logger.info("Generated reply to @%s: %s", author, cleaned)
            return cleaned

        except Exception as e:
            logger.warning("Error generating reply on attempt %d: %s", attempt, e)

        if attempt < max_retries:
            time.sleep(delay)
            delay *= 2

    logger.error("Failed to evaluate reply after retries. Skipping.")
    return None
