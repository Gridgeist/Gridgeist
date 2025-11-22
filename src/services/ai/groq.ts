import Groq from "groq-sdk";
import { Config } from "../../config";
import { MemoryTools } from "../memory/tools";

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
];

export async function generateResponse(messages: any[], userId: string, imageUrl?: string): Promise<any> {
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
      return generateResponse(formattedMessages, userId);
    }

    // No tool calls, return the standard message
    return responseMessage;
    
  } catch (error) {
    console.error("Groq API error:", error);
    return { content: "my brain is offline. try again in a bit.", role: "assistant" };
  }
}
