import { Message, ChannelType } from "discord.js";
import { generateResponse } from "../services/ai/groq";
import { SYSTEM_PROMPT } from "../services/ai/prompts";
import { ShortTermMemory } from "../services/memory/shortTerm";
import { MemoryOrchestrator } from "../services/memory/orchestrator";
import { parseMentions, stripBotMention } from "../services/utils/helpers";
import { messageBuffer } from "../services/utils/messageBuffer";

const WHITELISTED_CHANNELS: string[] = [];

export default {
  name: "messageCreate",
  execute: async (message: Message) => {
    // Ignore bots
    if (message.author.bot) return;

    // Check if bot is mentioned or in whitelisted channel or is a DM
    const isBotMentioned = message.mentions.has(message.client.user?.id || "");
    const isWhitelisted = WHITELISTED_CHANNELS.includes(message.channelId);
    const isDM = message.channel.type === ChannelType.DM;

    if (!isBotMentioned && !isWhitelisted && !isDM) return;

    // Add to buffer instead of processing immediately
    messageBuffer.add(message.channelId, message, async (messages: Message[]) => {
      const lastMessage = messages[messages.length - 1];
      
      // Immediate feedback (on the last message)
      if ('sendTyping' in lastMessage.channel) {
        await lastMessage.channel.sendTyping();
      }

      try {
        // Combine contents and process mentions
        const combinedContentPromises = messages.map(m => parseMentions(m.content, m.client));
        const cleanedContents = await Promise.all(combinedContentPromises);
        const combinedText = cleanedContents.join("\n");

        // Get context using Orchestrator
        const contextBlock = await MemoryOrchestrator.getContextBlock(lastMessage.channelId, combinedText);
        
        // Check for image attachments in ANY of the messages
        let imageUrl: string | undefined;
        for (const msg of messages) {
          const attachment = msg.attachments.first();
          if (attachment?.contentType?.startsWith("image/")) {
            imageUrl = attachment.url;
            break; // Use the first image found
          }
        }

        // If user sent an image, append it to their message content in the prompt so AI knows
        let userMessageContent = `${contextBlock}\n\n${lastMessage.author.username}: ${combinedText}`;
        if (imageUrl) {
          userMessageContent += `\n[Attached Image: ${imageUrl}]`;
        }

        // Build messages for Groq
        const groqMessages = [
          {
            role: "system",
            content: SYSTEM_PROMPT,
          },
          {
            role: "user",
            content: userMessageContent,
          },
        ];

        // Generate response
        const { content, files } = await generateResponse(
          groqMessages, 
          lastMessage.author.id, 
          lastMessage.channelId,
          imageUrl
        );

        const contentToSend = content || (files.length > 0 ? "" : "I'm speechless.");

        // Dynamic delay for natural feeling (20ms per character)
        const typingDelay = contentToSend.length * 20;
        if (typingDelay > 0) {
          if ('sendTyping' in lastMessage.channel) {
            await lastMessage.channel.sendTyping();
          }
          await new Promise((resolve) => setTimeout(resolve, typingDelay));
        }

        // Send response (reply to the last message)
        const sentMessage = await lastMessage.reply({
          content: contentToSend,
          files: files,
          allowedMentions: { repliedUser: false },
        });

        // Save data after replying (fire-and-forget)
        const now = Date.now();
        
        // Save user message (combined)
        const rawStripped = stripBotMention(
          combinedText, 
          lastMessage.client.user?.id || ""
        );
        
        let storedContent = combinedText;

        // Append image placeholder to stored memory
        if (imageUrl) {
          storedContent = storedContent ? `${storedContent} [user sent an image: ${imageUrl}]` : `[user sent an image: ${imageUrl}]`;
        }

        ShortTermMemory.addMessage(lastMessage.channelId, {
          author: lastMessage.author.username,
          content: storedContent,
          timestamp: now,
          imageUrl: imageUrl,
        });

        const botImageUrl = sentMessage.attachments.first()?.url;

        ShortTermMemory.addMessage(lastMessage.channelId, {
          author: "Gridgeist",
          content: contentToSend,
          timestamp: now + 1,
          imageUrl: botImageUrl,
        });

      } catch (error) {
        console.error("Error handling message:", error);
        await lastMessage.reply({
          content: "something went wrong. try again?",
          allowedMentions: { repliedUser: false },
        });
      }
    });
  },
};
