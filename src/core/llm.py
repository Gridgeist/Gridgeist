from groq import AsyncGroq

from src.config import GROQ_API_KEY, LLM_MODEL


class GroqClient:
    def __init__(self):
        self.client = AsyncGroq(api_key=GROQ_API_KEY)

    async def chat_completion(self, messages, tools=None):
        """
        Wrapper for Groq API call.
        """
        # Prepare arguments
        kwargs = {
            "model": LLM_MODEL,
            "messages": messages,
            "temperature": 0.6,
        }
        
        # Only add tools if provided
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        response = await self.client.chat.completions.create(**kwargs)
        return response
