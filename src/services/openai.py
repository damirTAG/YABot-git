import logging

import aiohttp

from config.constants import CHATGPT_ROLE
from config.settings import GEMINI_TOKEN

# Google Gemini (Generative Language API). Kept in openai.py so existing imports
# (`from services.openai import generate_response`) keep working.
GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_API_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
MAX_OUTPUT_TOKENS = 800

logger = logging.getLogger()


async def generate_response(prompt: str) -> str | None:
    """Generate a response from Google's Gemini API.

    Returns the text, or ``None`` on any failure (quota, blocked content,
    network) so callers fall back to their "response failed" branch.
    """
    if not GEMINI_TOKEN:
        logger.error("[gemini] GEMINI_TOKEN is not set")
        return None

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": GEMINI_TOKEN,
    }
    data = {
        "system_instruction": {"parts": [{"text": CHATGPT_ROLE}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": MAX_OUTPUT_TOKENS, "temperature": 0.9},
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GEMINI_API_URL, headers=headers, json=data) as response:
                result = await response.json()

                if response.status != 200:
                    logger.error(f"[gemini] API error {response.status}: {result}")
                    return None

                candidates = result.get("candidates")
                if not candidates:
                    # No candidates usually means the prompt/response was blocked.
                    logger.warning(f"[gemini] No candidates returned: {result}")
                    return None

                parts = candidates[0].get("content", {}).get("parts", [])
                text = "".join(part.get("text", "") for part in parts).strip()
                return text or None
    except Exception as e:
        logger.error(f"[gemini] Error generating response: {e}")
        return None
