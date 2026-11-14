"""
agent/brain.py
AI reasoning engine powered by the official google-genai SDK.
Generates human-like, niche-specific Threads posts and smart contextual replies.
Features automatic model failover between next-gen Gemini Flash models.
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
    if text.startswith("> "):
        text = text[2:].strip()
    return text


def _get_genai_client() -> genai.Client:
    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(api_version="v1beta", timeout=60000),
    )


def generate_post(config: dict) -> str:
    """
    Randomly selects one of config['post_styles'], injects persona & instructions,
    and generates a human-like Threads post strictly under 350 characters with retry backoff.
    """
    client = _get_genai_client()
    primary_model = config.get("gemini_model", "gemini-3.8-flash")
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

    models_to_try = [primary_model]
    for fallback in ["gemini-3-flash-preview", "gemini-3.1-flash-lite"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_text = ""
    for model_name in models_to_try:
        try:
            logger.info("Generating post with model %s (style: %s)...", model_name, selected_style)
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
            logger.warning("Post length (%d chars) exceeded 350 chars with model %s.", len(cleaned), model_name)
        except Exception as e:
            logger.warning("Model %s encountered error: %s. Trying fallback model...", model_name, e)

    if last_text:
        truncated = last_text[:347].rsplit(" ", 1)[0] + "..."
        logger.info("Fallback: truncated post to strictly stay under 350 chars.")
        return truncated

    raise RuntimeError("Failed to generate valid Threads post across all available Gemini models.")


def generate_reply(post_text: str, author: str, comment_text: str, config: dict) -> str | None:
    """
    Evaluates incoming comments using persona and custom_instructions.
    Returns None if the comment is spam/crypto/self-promo (SKIP),
    otherwise drafts a casual 1-sentence peer-to-peer reply (max 15 words).
    """
    client = _get_genai_client()
    primary_model = config.get("gemini_model", "gemini-3.8-flash")
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

    models_to_try = [primary_model, "gemini-3-flash-preview", "gemini-3.1-flash-lite"]

    for model_name in models_to_try:
        try:
            logger.info("Evaluating comment by @%s (model: %s)...", author, model_name)
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

            if cleaned.upper() == "SKIP" or cleaned.upper().startswith("SKIP"):
                logger.info("Comment by @%s flagged as SKIP (spam/irrelevant/promo).", author)
                return None

            words = cleaned.split()
            if len(words) > 15:
                cleaned = " ".join(words[:15])

            logger.info("Generated reply to @%s: %s", author, cleaned)
            return cleaned

        except Exception as e:
            logger.warning("Error evaluating reply with model %s: %s", model_name, e)

    logger.error("Failed to evaluate reply after retries. Skipping.")
    return None
