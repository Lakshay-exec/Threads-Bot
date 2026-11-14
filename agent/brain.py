"""
agent/brain.py
AI reasoning engine powered by the official google-genai SDK.
Generates authentic, short, punchy, high-engagement Threads posts (1-2 lines)
with genuine humor, relatable gaming/anime moments, natural emojis, and smart peer replies.
"""
import logging
import os
import random
import re
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

STYLE_DESCRIPTIONS = {
    "VIRAL_QUESTION": (
        "Ask a super short, interactive question or challenge that practically forces people in the comments "
        "to reply (e.g. 'drop your rank and main agent...', 'tell me your favorite anime villain without saying their name...')."
    ),
    "HOT_TAKE": (
        "Drop a spicy, punchy 1-line controversial opinion about ranked teammates, agent meta, or anime storylines."
    ),
    "RELATABLE_MOMENT": (
        "A hilarious, painful, or relatable 1-2 line observation about competitive gaming or anime grind that everyone relates to."
    ),
    "UNPOPULAR_OPINION": (
        "A sharp 'unpopular opinion:' take that challenges the community consensus in 1 or 2 quick sentences."
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
    """Validates that a post is complete, punchy (not an essay), and doesn't trail off."""
    # Enforce concise length: between 35 and 150 characters
    if len(text) < 35 or len(text) > 150:
        return False

    words = text.split()
    if len(words) < 5:
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
    Generates a genuine, short, punchy Threads post (1-2 lines) with emojis.
    Uses thinking_budget=0 for instant, uninhibited concise generation.
    """
    client = _get_genai_client()
    primary_model = config.get("gemini_model", "gemini-3-flash-preview")
    niche = config.get("niche", "Competitive Gaming, Valorant, and Dark Psychological Anime")
    persona = config.get("persona", "A witty 20-something competitive gamer and anime enthusiast.")
    custom_instructions = config.get("custom_instructions", "Keep it short (1-2 lines), witty, and highly engaging with 1-2 emojis.")
    post_styles = config.get("post_styles", ["VIRAL_QUESTION", "HOT_TAKE", "RELATABLE_MOMENT", "UNPOPULAR_OPINION"])

    selected_style = random.choice(post_styles) if post_styles else "HOT_TAKE"
    style_desc = STYLE_DESCRIPTIONS.get(
        selected_style,
        "Share a short, punchy thought that sparks instant engagement."
    )

    prompt = f"""You are posting a quick, authentic thought on Meta Threads from your phone.

Account Persona:
{persona}

Niche:
{niche}

Post Style:
[{selected_style}] {style_desc}

User Guidelines:
{custom_instructions}

Style Reference Examples (Match this brevity, completeness, and vibe):
- "drop your rank and your main agent. i'll tell you your biggest red flag 💀"
- "the urge to queue one more ranked game after losing 3 in a row is an actual mental illness 😭"
- "unpopular opinion: phantom spray feels 10x more satisfying than a vandal one-tap 🔥"
- "tell me your favorite anime villain without saying their name, let's see if anyone guesses 🖤"
- "nothing humbles you faster than getting one-tapped by a player named 'i miss her' 💀"
- "name one anime death that permanently altered your brain chemistry 😭"
- "playing competitive games until 3am just to end up on the exact same RR as yesterday 💀"
- "Thorfinn realizing he has no enemies is still peak fiction 🖤"

Strict Generation Rules:
1. STRICT LENGTH: 1 to 2 lines maximum (between 40 and 130 characters total).
2. NO LONG PARAGRAPHS OR ESSAYS. Keep it punchy, conversational, and direct.
3. Include 1 or 2 natural, expressive emojis (e.g. 💀, 😭, 🖤, 🔥).
4. NO hashtag stuffing. Max 1 subtle hashtag at the end or none at all.
5. MUST BE A 100% COMPLETE, FINISHED THOUGHT. Never cut off or trail off mid-sentence.
6. Output ONLY the raw post text. No preamble, no quotes around the text.
"""

    models_to_try = [primary_model]
    for fallback in ["gemini-3.1-flash-lite", "gemini-3-flash-preview"]:
        if fallback not in models_to_try:
            models_to_try.append(fallback)

    last_text = ""
    for model_name in models_to_try:
        for attempt in range(2):
            try:
                logger.info("Generating post with model %s (attempt %d, style: %s)...", model_name, attempt + 1, selected_style)
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.9,
                        max_output_tokens=150,
                        thinking_config=types.ThinkingConfig(thinking_budget=0),
                    ),
                )

                raw_text = response.text or ""
                cleaned = _clean_generated_text(raw_text)

                if _is_valid_complete_post(cleaned):
                    logger.info("Generated high-quality post (%d chars): %s", len(cleaned), cleaned)
                    return cleaned

                last_text = cleaned
                logger.warning("Post candidate did not meet length/completeness checks (%d chars): '%s'.", len(cleaned), cleaned)
            except Exception as e:
                logger.warning("Model %s attempt %d encountered error: %s", model_name, attempt + 1, e)

    if last_text and 35 <= len(last_text) <= 160:
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
    primary_model = config.get("gemini_model", "gemini-3-flash-preview")
    persona = config.get("persona", "A witty 20-something competitive gamer and anime enthusiast.")
    custom_instructions = config.get("custom_instructions", "Keep it short, witty, and engaging with 1-2 emojis.")

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
   - STRICT CONSTRAINT: Maximum 15 words total.
   - Do NOT include @mentions or greetings like "Hey @{author}".
   - Do NOT wrap in quotes.
   - Output ONLY the reply sentence.
"""

    models_to_try = [primary_model, "gemini-3.1-flash-lite"]

    for model_name in models_to_try:
        try:
            logger.info("Evaluating comment by @%s (model: %s)...", author, model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.8,
                    max_output_tokens=60,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
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
