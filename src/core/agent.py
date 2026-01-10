import json
import logging
import inspect

from src.config import SYSTEM_PROMPT
from src.core.llm import GroqClient
from src.core.registry import registry

logger = logging.getLogger("Agent")


class Agent:
    def __init__(self, memory):
        self.llm = GroqClient()
        self.memory = memory

    async def process_message(
        self, user_input: str, user_name: str, context: dict = None
    ) -> str:
        """
        Main Agentic Loop:
        1. Parse mentions in user_input
        2. Retrieve context
        3. Loop: LLM -> Tool? -> Execute -> LLM
        4. Post-process mentions in response
        """
        context = context or {}

        # 1. Retrieve Context (Passive RAG)
        context_data = await self.memory.get_context(user_input=user_input)

        # 2. Build Message History
        system_message = {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nUser Name: {user_name}\n\n{context_data}\n\n"
            f"CURRENT CONTEXT: {json.dumps(context.get('server_info', {}))}",
        }

        messages = [system_message] + self.memory.get_short_term_memory()
        messages.append({"role": "user", "content": user_input})

        final_response = ""

        # 3. Execution Loop
        for _ in range(5):
            response = await self.llm.chat_completion(
                messages=messages, tools=registry.get_schemas()
            )

            msg = response.choices[0].message

            # Log the "Thought" or content logic if present (Chain of Thought)
            if msg.content:
                logger.info(f"🤔 Thought: {msg.content}")

            if not msg.tool_calls:
                final_response = msg.content
                break

            messages.append(msg)

            for tool_call in msg.tool_calls:
                func_name = tool_call.function.name
                arguments_json = tool_call.function.arguments
                call_id = tool_call.id

                logger.info(f"🤖 Tool Call: {func_name}")

                try:
                    args = json.loads(arguments_json)
                    func = registry.get_tool(func_name)

                    if func:
                        # Inject user_id and session_id if needed
                        sig = inspect.signature(func)
                        if "user_id" in sig.parameters:
                            args["user_id"] = self.memory.user_id
                        if "session_id" in sig.parameters:
                            args["session_id"] = self.memory.session_id

                        # CRITICAL: Async-aware execution
                        if inspect.iscoroutinefunction(func):
                            tool_result = await func(**args)
                        else:
                            tool_result = func(**args)
                    else:
                        tool_result = f"Error: Tool {func_name} not found."

                except Exception as e:
                    logger.error(f"Tool Error: {e}")
                    tool_result = f"Error executing tool: {str(e)}"

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": func_name,
                        "content": str(tool_result),
                    }
                )

        # 4. Save and Return
        await self.memory.add_interaction(user_input, final_response)
        return final_response
