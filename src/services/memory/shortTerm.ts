import { Config } from "../../config";

export interface ShortTermMessage {
  author: string;
  content: string;
  timestamp: number;
}

// Key: Channel ID, Value: Array of recent messages
const memoryCache = new Map<string, ShortTermMessage[]>();

export const ShortTermMemory = {
  /**
   * Adds a message to the short-term memory cache for a specific channel.
   * Maintains a maximum limit of messages per channel (FIFO).
   * @param channelId The ID of the Discord channel
   * @param message The message object containing author, content, and timestamp
   */
  addMessage: (channelId: string, message: ShortTermMessage) => {
    const currentHistory = memoryCache.get(channelId) || [];
    
    currentHistory.push(message);

    // Enforce limit
    if (currentHistory.length > Config.MAX_SHORT_TERM_MEMORY) {
      currentHistory.shift(); // Remove oldest
    }

    memoryCache.set(channelId, currentHistory);
  },

  /**
   * Retrieves the recent messages for a channel, formatted as a string for AI prompts.
   * @param channelId The ID of the Discord channel
   * @returns A single string with lines in "Author: Content" format
   */
  getRecentMessages: (channelId: string): string => {
    const history = memoryCache.get(channelId) || [];
    
    if (history.length === 0) {
      return "";
    }

    return history
      .map((msg) => `${msg.author}: ${msg.content}`)
      .join("\n");
  },
  
  /**
   * Helper to get the raw array if needed
   */
  getRawMessages: (channelId: string): ShortTermMessage[] => {
    return memoryCache.get(channelId) || [];
  }
};
