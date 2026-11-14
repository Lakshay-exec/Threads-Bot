"""
agent/brain.py
AI reasoning engine powered by the official google-genai SDK.
Generates authentic, complete, highly engaging Threads posts with genuine emotion,
tasteful emojis, and smart contextual replies.
"""
import logging
import os
import random
import re
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

STYLE_DESCRIPTIONS = {
    "MINI_REVIEW": (
        "Drop a sharp, unfiltered mini-review of a specific game mechanic, anime arc, "
        "character philosophy, or agent balance. Give an honest rating or verdict with a punchy conclusion."
    ),
    "QUESTION_DEBATE": (
        "Ask a provocative, polarizing, debate-sparking question about Valorant or anime lore "
        "that forces people in the comments to take a side. Include full context so it is a complete, intriguing post."
    ),
    "HOT_TAKE": (
        "Deliver a spicy, controversial hot take about ranked teammates, agent meta, or anime storylines "
        "that challenges the consensus. Back it up with a funny or relatable observation."
    ),
    "DEEP_PERSPECTIVE": (
        "Share a dark, poetic, or philosophical perspective connecting human struggle to anime "
        "(Vinland Saga, Attack on Titan, Berserk, Monster) or high-stakes competitive gaming."
    ),
}

INCOMPLETE_TRAILERS = {
    "and", "or", "but", "with", "the", "a", "an", "zero", "my", "to", "in", "of", "for", "on", "at", "if", "then"
}


def _clean_generated_text(text: str) -> str:
    """Strips surrounding quotes, AI preambles, and unwanted whitespace from generated text."""
    text = text.strip()
    text = re.sub(
        r"^(?:(?:Draft|Post|Threads Post|Here is(?: a| the)? post|Status update)[\s:*_*-]*)+",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        text = text[1:-1].strip()
    if text.startswith("> "):
        text = text[2:].strip()
    return text.strip()


def _is_valid_complete_post(text: str) -> bool:
    """Validates that a post is complete, of reasonable length, and doesn't trail off."""
    if len(text) < 60 or len(text) > 450:
        return False

    words = text.split()
    if len(words) < 8:
        return False

    # Check if the last word is an incomplete grammatical trailer
    last_word = words[-1].lower().strip(".,!?:;\"'()#")
    if last_word in INCOMPLETE_TRAILERS:
        return False

    return True


def _get_genai_client() -> genai.Client:
    return genai.Client(
        api_key=os.environ["GEMINI_API_KEY"],
        http_options=types.HttpOptions(api_version="v1beta", timeout=60000),
    )


def generate_post(config: dict) -> str:
    """
    Generates a genuine, complete, human-like Threads post with emojis and hashtags.
    Includes failover between next-gen Gemini models.
    """
    client = _get_genai_client()
    primary_model = config.get("gemini_model", "gemini-3.8-flash")
    niche = config.get("niche", "Competitive Gaming, Valorant, and Dark Psychological Anime")
    persona = config.get("persona", "A 20-year-old competitive gamer and anime enthusiast.")
    custom_instructions = config.get("custom_instructions", "Keep it authentic, complete, and engaging with emojis.")
    post_styles = config.get("post_styles", ["MINI_REVIEW", "QUESTION_DEBATE", "HOT_TAKE", "DEEP_PERSPECTIVE"])

    selected_style = random.choice(post_styles) if post_styles else "HOT_TAKE"
    style_desc = STYLE_DESCRIPTIONS.get(
        selected_style,
        "Share an authentic thought that sparks instant engagement in the community."
    )

    prompt = f"""You are posting authentic thoughts on Meta Threads from your phone.

Account Persona:
{persona}

Niche:
{niche}

Style for this post:
[{selected_style}] {style_desc}

User Guidelines:
{custom_instructions}

Style Reference Examples (Match this quality, completeness, and vibe):
- "Riot could completely delete Reyna's kit and my instalock teammate would STILL lock her in 0.001s, dry peek mid, die instantly, and blame team comms. You can nerf her stats all you want, but you can't patch out the ego. 💀 #valorant #ranked"
- "A curse is rarely born from pure malice; it's usually love twisted by grief. We build our own inner hells out of things we refused to forgive ourselves for. 🖤 #jjk #anime"
- "Be honest: is Jett dash actually balanced now, or have we all just developed collective Stockholm syndrome after 4 years of dealing with it? 😭 Drop your rank before answering. #valorant"
- "Johan Liebert remains the most terrifying antagonist in anime because he never needed superpowers. All he did was whisper the truth people were already too scared to admit. ⚔️ #monster #anime"

Strict Generation Rules:
1. MUST BE A 100% COMPLETE, FINISHED THOUGHT. Never cut off or trail off mid-sentence.
2. Length: Between 100 and 380 characters total.
3. Include 1 to 3 natural, expressive emojis (e.g., 💀, 🖤, 😭, 🔥, ⚔️, 🎮).
4. Include 2-3 relevant hashtags at the very end (e.g. #valorant #anime #gaming).
5. Output ONLY the raw post text. No preamble, no quotes around the text.
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
                    max_output_tokens=350,
                ),
            )

            raw_text = response.text or ""
            cleaned = _clean_generated_text(raw_text)

            if _is_valid_complete_post(cleaned):
                logger.info("Generated high-quality post (%d chars): %s", len(cleaned), cleaned)
                return cleaned

            last_text = cleaned
            logger.warning("Post candidate did not meet completeness checks: '%s'. Retrying...", cleaned)
        except Exception as e:
            logger.warning("Model %s encountered error: %s. Trying fallback model...", model_name, e)

    if last_text and len(last_text) >= 50:
        logger.info("Fallback: using last generated candidate.")
        return last_text

    raise RuntimeError("Failed to generate valid Threads post across all available Gemini models.")


def generate_reply(post_text: str, author: str, comment_text: str, config: dict) -> str | None:
    """
    Evaluates incoming comments using persona and custom_instructions.
    Returns None if the comment is spam/crypto/self-promo (SKIP),
    otherwise drafts a casual 1-sentence peer-to-peer reply with emojis.
    """
    client = _get_genai_client()
    primary_model = config.get("gemini_model", "gemini-3.8-flash")
    persona = config.get("persona", "A 20-year-old competitive gamer and anime enthusiast.")
    custom_instructions = config.get("custom_instructions", "Keep it authentic, complete, and engaging with emojis.")

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
   - Draft a natural, witty 1-sentence peer-to-peer reply with 1 tasteful emoji (e.g. 💀, 🖤, 😭).
   - STRICT CONSTRAINT: Maximum 18 words total.
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
                    max_output_tokens=70,
                ),
            )

            raw_text = (response.text or "").strip()
            cleaned = _clean_generated_text(raw_text)

            if cleaned.upper() == "SKIP" or cleaned.upper().startswith("SKIP"):
                logger.info("Comment by @%s flagged as SKIP (spam/irrelevant/promo).", author)
                return None

            words = cleaned.split()
            if len(words) > 18:
                cleaned = " ".join(words[:18])

            logger.info("Generated reply to @%s: %s", author, cleaned)
            return cleaned

        except Exception as e:
            logger.warning("Error evaluating reply with model %s: %s", model_name, e)

    logger.error("Failed to evaluate reply after retries. Skipping.")
    return None
