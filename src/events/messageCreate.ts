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
        const response = await generateResponse(groqMessages, lastMessage.author.id, imageUrl);

        let contentToSend = "";
        if (typeof response === 'string') {
            contentToSend = response;
        } else if (response?.content) {
            contentToSend = response.content;
        } else {
            contentToSend = "I'm speechless.";
        }

        // Dynamic delay for natural feeling (20ms per character)
        const typingDelay = contentToSend.length * 20;
        if (typingDelay > 0) {
          if ('sendTyping' in lastMessage.channel) {
            await lastMessage.channel.sendTyping();
          }
          await new Promise((resolve) => setTimeout(resolve, typingDelay));
        }

        // Send response (reply to the last message)
        await lastMessage.reply({
          content: contentToSend,
          allowedMentions: { repliedUser: false },
        });

        // Save data after replying (fire-and-forget)
        const now = Date.now();
        
        // Save user message (combined)
        const rawStripped = stripBotMention(
          combinedText, // This already has mentions parsed, so we might be double parsing if we strip mention again, but stripBotMention expects raw content usually.
                        // Actually parseMentions returns cleaned content. stripBotMention removes <@ID>.
                        // Let's use the combinedText which is already cleaned by parseMentions.
                        // Wait, parseMentions replaces <@ID> with @Name. 
                        // stripBotMention removes <@BotID> specifically.
                        // If we already ran parseMentions, the bot mention is now @BotName.
                        // So stripBotMention might not work as expected if called on cleanedContent.
                        // Let's reconstruct raw content or just use combinedText as is for memory.
                        // Usually we want memory to be readable. combinedText is readable.
                        // Let's just verify if we need to strip the bot name if it was a mention.
                        // If the user said "@Gridgeist hello", parseMentions makes it "@Gridgeist hello".
                        // We might want to remove "@Gridgeist" for cleaner memory.
          lastMessage.client.user?.id || ""
        );
        
        // Actually, let's iterate and clean raw content for memory to be safe, 
        // or just use the combinedText which is already human readable.
        // The previous logic did: stripBotMention -> parseMentions.
        // Here we did parseMentions first on all messages. 
        // Let's just use combinedText, but maybe remove the bot name if it starts with it?
        // Simpler: Just store combinedText. It's human readable.
        
        let storedContent = combinedText;

        // Append image placeholder to stored memory
        if (imageUrl) {
          storedContent = storedContent ? `${storedContent} [user sent an image: ${imageUrl}]` : `[user sent an image: ${imageUrl}]`;
        }

        ShortTermMemory.addMessage(lastMessage.channelId, {
          author: lastMessage.author.username,
          content: storedContent,
          timestamp: now,
        });

        ShortTermMemory.addMessage(lastMessage.channelId, {
          author: "Gridgeist",
          content: contentToSend,
          timestamp: now + 1,
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
