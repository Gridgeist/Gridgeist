import { VectorStore } from "./vectorStore";

export class MemoryTools {
  /**
   * Saves a new memory.
   */
  static async saveMemory(userId: string, content: string, category: string, importance: string): Promise<string> {
    const success = await VectorStore.storeInteraction(content, userId, { category, importance });
    return success ? "Memory saved successfully." : "Failed to save memory.";
  }

  /**
   * Searches for memories.
   */
  static async searchMemories(query: string): Promise<string> {
    const results = await VectorStore.searchContext(query);
    if (results.length === 0) return "No relevant memories found.";
    return JSON.stringify(results.map(r => ({ 
      id: r.id, 
      content: r.text, 
      created_at: new Date(r.created_at * 1000).toISOString() 
    })));
  }

  /**
   * Deletes a memory by ID.
   */
  static async deleteMemory(id: string): Promise<string> {
    const success = await VectorStore.deleteInteraction(id);
    return success ? `Memory ${id} deleted.` : `Failed to delete memory ${id}.`;
  }

  /**
   * Updates a memory's content.
   */
  static async updateMemory(id: string, content: string): Promise<string> {
    const success = await VectorStore.updateInteraction(id, content);
    return success ? `Memory ${id} updated.` : `Failed to update memory ${id}.`;
  }

  /**
   * Merges multiple memories into one.
   * Deletes the old IDs and saves the new content.
   */
  static async mergeMemories(userId: string, ids: string[], content: string, category: string = "merged", importance: string = "medium"): Promise<string> {
    // Delete old memories
    const deletePromises = ids.map(id => VectorStore.deleteInteraction(id));
    await Promise.all(deletePromises);

    // Save new merged memory
    const success = await VectorStore.storeInteraction(content, userId, { category, importance });
    return success ? "Memories merged successfully." : "Failed to save merged memory (old memories were deleted).";
  }
}

export const MEMORY_TOOL_DEFINITIONS = [
  {
    type: "function",
    function: {
      name: "save_memory",
      description: "Save a new specific detail or interaction to long-term memory. Use this when the user explicitly asks you to remember something or provides important personal information.",
      parameters: {
        type: "object",
        properties: {
          content: { 
            type: "string", 
            description: "The specific content to remember." 
          },
          category: { 
            type: "string", 
            description: "Category of the memory (e.g., 'user_preference', 'personal_detail', 'project_context', 'factual_correction')." 
          },
          importance: { 
            type: "string", 
            enum: ["low", "medium", "high"], 
            description: "The importance level of this memory." 
          }
        },
        required: ["content", "category", "importance"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "search_memories",
      description: "Search for specific past memories when the current context is insufficient. This performs a semantic vector search.",
      parameters: {
        type: "object",
        properties: {
          query: { 
            type: "string", 
            description: "The search query to find relevant memories." 
          }
        },
        required: ["query"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "delete_memory",
      description: "Delete a specific memory by its ID. Use this when a memory is incorrect or the user asks to forget something.",
      parameters: {
        type: "object",
        properties: {
          id: { 
            type: "string", 
            description: "The UUID of the memory to delete." 
          }
        },
        required: ["id"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "update_memory",
      description: "Update the content of an existing memory. Use this to correct or refine a specific memory.",
      parameters: {
        type: "object",
        properties: {
          id: { 
            type: "string", 
            description: "The UUID of the memory to update." 
          },
          content: { 
            type: "string", 
            description: "The new text content for the memory." 
          }
        },
        required: ["id", "content"]
      }
    }
  },
  {
    type: "function",
    function: {
      name: "merge_memories",
      description: "Merge multiple existing memories into a single new memory. Use this to consolidate fragmented or duplicate information.",
      parameters: {
        type: "object",
        properties: {
          ids: { 
            type: "array", 
            items: { type: "string" },
            description: "List of memory UUIDs to merge (these will be deleted)." 
          },
          content: { 
            type: "string", 
            description: "The combined/summarized content to save as the new memory." 
          },
          category: { 
            type: "string", 
            description: "Category for the new merged memory." 
          },
          importance: { 
            type: "string", 
            enum: ["low", "medium", "high"], 
            description: "Importance of the new merged memory." 
          }
        },
        required: ["ids", "content"]
      }
    }
  }
];
