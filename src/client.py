import logging

import discord

from src.core.agent import Agent
from src.memory.manager import MemoryManager

from src.core.registry import registry
from src.core.logger import setup_rich_logging

# Load skills dynamically
# This allows 'plugins' to be added simply by dropping files into src/skills
registry.load_skills("src.skills")


# Setup basic logging
# Setup aesthetic logging
setup_rich_logging()
logger = logging.getLogger("DiscordBot")


class BotClient(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.agents = {}  # Map user_id -> Agent

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")

    async def on_message(self, message):
        # 1. Ignore self and other bots
        if message.author == self.user or message.author.bot:
            return

        # 2. Filter: Only respond in DMs or when mentioned
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_mentioned = self.user.mentioned_in(message)

        if not (is_dm or is_mentioned):
            return

        # 3. Determine Session and User
        # For DMs, session = user_id. For Channels, session = channel_id
        session_id = str(message.channel.id) if not is_dm else f"dm_{message.author.id}"
        user_id = str(message.author.id)
        user_name = message.author.display_name

        # 4. Pre-process: Resolve Mentions to plaintext
        from src.core.utils import resolve_mentions, format_mentions, get_server_context

        clean_content = resolve_mentions(message.content, message.guild)

        # Remove bot name if it was a mention to clean up the prompt
        bot_mention = f"@{self.user.display_name}"
        clean_content = clean_content.replace(bot_mention, "").strip()

        logger.info(f"[{session_id}] {user_name}: {clean_content}")

        # 5. Initialize or Get Agent
        if session_id not in self.agents:
            memory = MemoryManager(session_id, user_id)
            self.agents[session_id] = Agent(memory)

        # 6. Process response
        async with message.channel.typing():
            try:
                # Provide server context to the agent
                context = {"server_info": get_server_context(message)}

                response = await self.agents[session_id].process_message(
                    user_input=clean_content, user_name=user_name, context=context
                )

                # 7. Post-process: Resolve plaintext mentions back to Discord tags
                # We suppress mentions for the author to avoid "double pings" or annoying reply pings
                final_response = format_mentions(
                    response, message.guild, suppress_user_ids=[message.author.id]
                )

                # 8. Send message (handling length limits)
                # Use reply() to maintain conversation thread, but disable mention_author to avoid pinging
                send_method = message.reply
                kwargs = {"mention_author": False}

                if len(final_response) > 2000:
                    for i in range(0, len(final_response), 2000):
                        chunk = final_response[i : i + 2000]
                        try:
                            await send_method(chunk, **kwargs)
                        except discord.HTTPException:
                            # Fallback if reply fails (e.g. original message deleted)
                            await message.channel.send(chunk)
                        # Only reply to the first chunk, subsequent chunks are just sent to channel
                        send_method = message.channel.send
                        kwargs = {}
                else:
                    try:
                        await send_method(final_response, **kwargs)
                    except discord.HTTPException:
                        await message.channel.send(final_response)

            except Exception as e:
                logger.error(f"Error processing message: {e}", exc_info=True)
                await message.channel.send("❌ My neural links are fuzzy. Try again?")
