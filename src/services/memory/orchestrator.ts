import { ShortTermMemory } from "./shortTerm";
import { VectorStore } from "./vectorStore";

export const MemoryOrchestrator = {
  /**
   * Retrieves both long-term vector memories and short-term conversation history
   * to build a context block for the AI.
   * 
   * @param channelId The Discord channel ID for short-term context
   * @param userQuery The current user message to search against in vector store
   * @returns Formatted string containing both context sources
   */
  getContextBlock: async (channelId: string, userQuery: string): Promise<string> => {
    // Run vector search and short-term retrieval in parallel
    const [vectorResults, recentMessages] = await Promise.all([
      VectorStore.searchContext(userQuery),
      ShortTermMemory.getRecentMessages(channelId),
    ]);

    // Format vector results
    const formattedMemories = vectorResults.length > 0
      ? vectorResults.map((res) => `- ${res.text}`).join("\n")
      : "No relevant past memories found.";

    const formattedConversation = recentMessages.length > 0
      ? recentMessages
      : "No recent conversation.";

    return `[RELEVANT PAST MEMORIES]
${formattedMemories}

[CURRENT CONVERSATION]
${formattedConversation}`;
  },
};
