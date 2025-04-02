import aiohttp, logging

from config.constants import CHATGPT_ROLE
from config.settings  import OPEN_AI_TOKEN

OPENAI_API_URL = "https://api.openai.com/v1/chat/completions"
logger = logging.getLogger()

async def generate_response(prompt: str) -> str:
    """
        Generate response from openai API
    """
    headers = {
        "Authorization": f"Bearer {OPEN_AI_TOKEN}",
        "Content-Type": "application/json"
    }
        
    data = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": CHATGPT_ROLE
            },
            {
                "role": "user", 
                "content": prompt
            }
        ],
        "max_tokens": 300
    }
        
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(OPENAI_API_URL, headers=headers, json=data) as response:
                if response.status == 200:
                    result = await response.json()
                    return result['choices'][0]['message']['content'].strip()
                else:
                    return None
    except Exception as e:
        logger.error(f"[chatgpt] Error generating response: {e}")
        return "An error occurred while processing your request."