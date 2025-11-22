import { Message } from "discord.js";
import { MemoryOrchestrator } from "../services/memory/orchestrator";
import { generateResponse } from "../services/ai/groq";
import { SYSTEM_PROMPT } from "../services/ai/prompts";
import { ShortTermMemory } from "../services/memory/shortTerm";
import { VectorStore } from "../services/memory/vectorStore";
import { parseMentions, stripBotMention } from "../services/utils/helpers";

const WHITELISTED_CHANNELS: string[] = [];

export default {
  name: "messageCreate",
  execute: async (message: Message) => {
    // Ignore bots
    if (message.author.bot) return;

    // Check if bot is mentioned or in whitelisted channel
    const isBotMentioned = message.mentions.has(message.client.user?.id || "");
    const isWhitelisted = WHITELISTED_CHANNELS.includes(message.channelId);

    if (!isBotMentioned && !isWhitelisted) return;

    // Immediate feedback
    await message.channel.sendTyping();

    try {
      // Parse mentions to plaintext so AI can read them
      const cleanedContent = await parseMentions(message.content, message.client);

      // Get context
      const contextBlock = await MemoryOrchestrator.getContextBlock(
        message.channelId,
        cleanedContent
      );

      // Build messages for Groq
      const messages = [
        {
          role: "system",
          content: SYSTEM_PROMPT,
        },
        {
          role: "user",
          content: `${contextBlock}\n\n${message.author.username}: ${cleanedContent}`,
        },
      ];

      // Generate response
      const response = await generateResponse(messages);

      // Send response
      await message.reply({
        content: response,
        allowedMentions: { repliedUser: false },
      });

      // Save data after replying (fire-and-forget)
      const storedContent = stripBotMention(
        cleanedContent,
        message.client.user?.id || ""
      );

      const now = Date.now();

      ShortTermMemory.addMessage(message.channelId, {
        author: message.author.username,
        content: storedContent,
        timestamp: now,
      });

      ShortTermMemory.addMessage(message.channelId, {
        author: "Gridgeist",
        content: response,
        timestamp: now + 1,
      });

      VectorStore.storeInteraction(storedContent, message.author.id);
    } catch (error) {
      console.error("Error handling message:", error);
      await message.reply({
        content: "something went wrong. try again?",
        allowedMentions: { repliedUser: false },
      });
    }
  },
};
