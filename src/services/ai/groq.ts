import Groq from "groq-sdk";
import { Config } from "../../config";
import { MemoryTools } from "../memory/tools";
import { ImageGenerator } from "../image/generator";
import { getDiscordClient } from "../../core/client";
import { TextChannel, DMChannel } from "discord.js";

const groq = new Groq({
  apiKey: Config.GROQ_API_KEY,
});

const AVAILABLE_TOOLS = [
  {
    type: "function" as const,
    function: {
      name: "save_memory",
      description: "Save important facts/preferences to long-term storage",
      parameters: {
        type: "object",
        properties: {
          content: { type: "string", description: "The information to save" },
          category: { type: "string", description: "Category of the memory" },
          importance: { 
            type: "string", 
            enum: ["low", "medium", "high"],
            description: "Importance level" 
          },
        },
        required: ["content", "category", "importance"],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "search_memories",
      description: "Explicitly search for past info",
      parameters: {
        type: "object",
        properties: {
          query: { type: "string", description: "The search query" },
        },
        required: ["query"],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "update_memory",
      description: "Correction/update of a specific memory",
      parameters: {
        type: "object",
        properties: {
          memory_id: { type: "string", description: "ID of the memory to update" },
          updated_content: { type: "string", description: "The new content" },
        },
        required: ["memory_id", "updated_content"],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "delete_memory",
      description: "Remove incorrect info",
      parameters: {
        type: "object",
        properties: {
          memory_id: { type: "string", description: "ID of the memory to delete" },
        },
        required: ["memory_id"],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "generate_image",
      description: "Generate a brand new image from scratch.",
      parameters: {
        type: "object",
        properties: {
          prompt: { type: "string", description: "Description of the image to generate" },
          aspect_ratio: { type: "string", description: "Aspect ratio (e.g., '1:1', '16:9')" },
        },
        required: ["prompt", "aspect_ratio"],
      },
    },
  },
  {
    type: "function" as const,
    function: {
      name: "edit_image",
      description: "Modify an existing image using Flux Kontext. Use this when the user wants to change something in a picture.",
      parameters: {
        type: "object",
        properties: {
          prompt: { type: "string", description: "Description of the change to apply" },
          image_reference: { type: "string", description: "Reference to the image (usually 'last_image')" },
        },
        required: ["prompt", "image_reference"],
      },
    },
  },
];

export async function generateResponse(
  messages: any[], 
  userId: string, 
  channelId: string,
  imageUrl?: string,
  generatedFiles: string[] = []
): Promise<{ content: string; files: string[] }> {
  try {
    let formattedMessages = [...messages];

    // Handle optional image URL attachment
    if (imageUrl) {
      const lastUserIndex = formattedMessages.reduce((lastIndex, msg, index) => 
        msg.role === "user" ? index : lastIndex, -1
      );

      if (lastUserIndex !== -1) {
        const lastMsg = formattedMessages[lastUserIndex];
        if (typeof lastMsg.content === "string") {
          formattedMessages[lastUserIndex] = {
            ...lastMsg,
            content: [
              { type: "text", text: lastMsg.content },
              { type: "image_url", image_url: { url: imageUrl } },
            ],
          };
        }
      }
    }

    // Initial call to Groq
    const completion = await groq.chat.completions.create({
      messages: formattedMessages,
      model: "meta-llama/llama-4-scout-17b-16e-instruct",
      temperature: 0.7,
      max_tokens: 500,
      tools: AVAILABLE_TOOLS,
      tool_choice: "auto",
    });

    const responseMessage = completion.choices[0]?.message;

    // If there are tool calls, handle them
    if (responseMessage && responseMessage.tool_calls) {
      // Add the assistant's response (with tool calls) to history
      formattedMessages.push(responseMessage);

      for (const toolCall of responseMessage.tool_calls) {
        const functionName = toolCall.function.name;
        const functionArgs = JSON.parse(toolCall.function.arguments);
        let functionResult = "";

        try {
          if (functionName === "save_memory") {
             functionResult = await MemoryTools.saveMemory(
               userId, 
               functionArgs.content, 
               functionArgs.category, 
               String(functionArgs.importance)
             );
          } else if (functionName === "search_memories") {
            functionResult = await MemoryTools.searchMemories(functionArgs.query);
          } else if (functionName === "update_memory") {
            functionResult = await MemoryTools.updateMemory(functionArgs.memory_id, functionArgs.updated_content);
          } else if (functionName === "delete_memory") {
            functionResult = await MemoryTools.deleteMemory(functionArgs.memory_id);
          } else if (functionName === "generate_image") {
            const generator = new ImageGenerator();
            const buffer = await generator.generate(functionArgs.prompt, functionArgs.aspect_ratio);
            const path = await generator.saveTempImage(buffer);
            generatedFiles.push(path);
            functionResult = "Image generated successfully and prepared for sending.";
          } else if (functionName === "edit_image") {
            const client = getDiscordClient();
            const channel = await client.channels.fetch(channelId) as TextChannel | DMChannel;
            
            if (!channel) {
              throw new Error("Channel not found");
            }

            // Fetch recent messages to find the last image
            const messages = await channel.messages.fetch({ limit: 20 });
            const lastImageMsg = messages.find(m => m.attachments.size > 0 && m.attachments.first()?.contentType?.startsWith("image/"));
            
            if (!lastImageMsg) {
               throw new Error("No recent image found in this channel to edit.");
            }

            const attachmentUrl = lastImageMsg.attachments.first()?.url;
            if (!attachmentUrl) throw new Error("Could not get attachment URL");

            const imageResponse = await fetch(attachmentUrl);
            const arrayBuffer = await imageResponse.arrayBuffer();
            const sourceBuffer = Buffer.from(arrayBuffer);

            const generator = new ImageGenerator();
            const buffer = await generator.edit(functionArgs.prompt, sourceBuffer);
            const path = await generator.saveTempImage(buffer);
            generatedFiles.push(path);
            functionResult = "Image edited successfully and prepared for sending.";
          } else {
            functionResult = `Error: Unknown tool ${functionName}`;
          }
        } catch (e) {
          functionResult = `Error executing ${functionName}: ${e}`;
        }

        // Append the tool result to history
        formattedMessages.push({
          tool_call_id: toolCall.id,
          role: "tool",
          name: functionName,
          content: functionResult,
        });
      }

      // Recursive call to generate final response with tool outputs
      return generateResponse(formattedMessages, userId, channelId, undefined, generatedFiles);
    }

    // No tool calls, return the standard message and any files generated
    return {
      content: responseMessage.content || "",
      files: generatedFiles
    };
    
  } catch (error) {
    console.error("Groq API error:", error);
    return { content: "my brain is offline. try again in a bit.", files: generatedFiles };
  }
}
