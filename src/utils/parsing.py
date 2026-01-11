import re
import discord
from typing import Dict


def resolve_mentions(content: str, guild: discord.Guild) -> str:
    """
    Translates Discord mentions (<@ID>, <#ID>) into plaintext ([User: Name], [Channel: Name]).
    """
    if not guild:
        return content

    # Resolve User Mentions
    user_mentions = re.findall(r"<@!?(\d+)>", content)
    for user_id in user_mentions:
        member = guild.get_member(int(user_id))
        name = member.display_name if member else f"UnknownUser_{user_id}"
        content = content.replace(f"<@{user_id}>", f"@{name}")
        content = content.replace(f"<@!{user_id}>", f"@{name}")

    # Resolve Channel Mentions
    channel_mentions = re.findall(r"<#(\d+)>", content)
    for channel_id in channel_mentions:
        channel = guild.get_channel(int(channel_id))
        name = channel.name if channel else f"UnknownChannel_{channel_id}"
        content = content.replace(f"<#{channel_id}>", f"#{name}")

    return content


def format_mentions(
    content: str, guild: discord.Guild, suppress_user_ids: list[int] = None
) -> str:
    """
    Translates plaintext mentions (@Name, #Name) back into Discord tags (<@ID>, <#ID>).
    """
    if not guild or not content:
        return content

    # 1. Channels - Search for #ChannelName
    # Sort by length descending to catch "#general-chat" before "#general"
    channels = sorted(guild.channels, key=lambda c: len(c.name), reverse=True)
    for channel in channels:
        if isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
            pattern = f"#{channel.name}"
            if pattern in content:
                content = content.replace(pattern, f"<#{channel.id}>")

    # 2. Users - Search for @DisplayName
    # Only iterate through members currently in the guild context to avoid overhead
    members = sorted(guild.members, key=lambda m: len(m.display_name), reverse=True)
    suppress_user_ids = suppress_user_ids or []

    # Track restored values to swapping them back at the end
    restorations = {}

    for member in members:
        pattern = f"@{member.display_name}"
        if pattern in content:
            # If this user is in the suppression list, use a placeholder to protect it
            # from being matched by shorter substrings (e.g. @AnthonyBot vs @Anthony)
            if member.id in suppress_user_ids:
                placeholder = f"__SUPPRESSED_MENTION_{member.id}__"
                content = content.replace(pattern, placeholder)
                restorations[placeholder] = pattern
                continue

            # Simple replacement
            content = content.replace(pattern, f"<@{member.id}>")

    # Restore suppressed mentions
    for placeholder, original in restorations.items():
        content = content.replace(placeholder, original)

    return content


def get_server_context(message: discord.Message) -> Dict:
    """
    Extracts relevant server info (channels, members) for the LLM.
    """
    if not message.guild:
        return {"type": "DM"}

    return {
        "type": "Server",
        "server_name": message.guild.name,
        "current_channel": message.channel.name,
        "available_channels": [c.name for c in message.guild.text_channels[:10]],
        "recent_members": [m.display_name for m in message.guild.members[:10]],
    }
