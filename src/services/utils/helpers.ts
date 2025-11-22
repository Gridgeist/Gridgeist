import { Client } from "discord.js";

/**
 * Parses Discord mentions in a message and converts them to plaintext.
 * Supports: user mentions <@ID>, channel mentions <#ID>, role mentions <@&ID>
 */
export const parseMentions = async (
  content: string,
  client: Client
): Promise<string> => {
  let parsed = content;

  // User mentions: <@USER_ID> or <@!USER_ID>
  const userMentionRegex = /<@!?(\d+)>/g;
  const userMatches = Array.from(content.matchAll(userMentionRegex));

  for (const match of userMatches) {
    const userId = match[1];
    try {
      const user = await client.users.fetch(userId);
      parsed = parsed.replace(match[0], `@${user.username}`);
    } catch {
      parsed = parsed.replace(match[0], `@unknown-user`);
    }
  }

  // Channel mentions: <#CHANNEL_ID>
  const channelMentionRegex = /<#(\d+)>/g;
  const channelMatches = Array.from(content.matchAll(channelMentionRegex));

  for (const match of channelMatches) {
    const channelId = match[1];
    try {
      const channel = await client.channels.fetch(channelId);
      if (channel && "name" in channel) {
        parsed = parsed.replace(match[0], `#${channel.name}`);
      }
    } catch {
      parsed = parsed.replace(match[0], `#unknown-channel`);
    }
  }

  // Role mentions: <@&ROLE_ID>
  const roleMentionRegex = /<@&(\d+)>/g;
  const roleMatches = Array.from(content.matchAll(roleMentionRegex));

  for (const match of roleMatches) {
    const roleId = match[1];
    try {
      // Role fetching requires guild context, so we attempt to find it
      const guild = client.guilds.cache.first();
      if (guild) {
        const role = await guild.roles.fetch(roleId);
        if (role) {
          parsed = parsed.replace(match[0], `@${role.name}`);
        }
      }
    } catch {
      parsed = parsed.replace(match[0], `@unknown-role`);
    }
  }

  // Handle @everyone and @here
  parsed = parsed.replace(/@everyone/g, "@everyone");
  parsed = parsed.replace(/@here/g, "@here");

  return parsed;
};

/**
 * Quick helper to remove bot mentions from content (keep original format)
 */
export const stripBotMention = (content: string, botId: string): string => {
  return content.replace(new RegExp(`<@!?${botId}>`, "g"), "").trim();
};
