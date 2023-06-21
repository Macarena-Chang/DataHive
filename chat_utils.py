from langchain.llms import OpenAI
from langchain.callbacks import get_openai_callback
import json
from config import load_config
import logging

#=== CONFIG ===#
config = load_config("config.yaml")

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

llm = OpenAI(temperature=0, openai_api_key=config["OPENAI_API_KEY"])

async def limit_chat_history(chat_history, new_response, token_limit=2500):
    # Calculate total tokens in chat history + response
    with get_openai_callback() as cb:
        llm("\n".join(f'{msg["user"]}: {msg["message"]}' for msg in chat_history) + f'\nbot: {new_response}')
    total_tokens = cb.total_tokens

    logger.info(f"TOTAL TOKENS REDIS HISTORY: {total_tokens}")

    # If total exceed limit remove messages until under limit
    while total_tokens > token_limit:
        removed_message = chat_history.pop(0)
        with get_openai_callback() as cb:
            llm("\n".join(f'{msg["user"]}: {msg["message"]}' for msg in chat_history) + f'\nbot: {new_response}')
        total_tokens = cb.total_tokens

    return chat_history
