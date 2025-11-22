import { Config } from "../../config";
import { Logger } from "../utils/logger";

export interface SearchResult {
  id: string;
  text: string;
  user_id: string;
  timestamp: number;
  _distance?: number;
}

interface SearchResponse {
  results: SearchResult[];
}

export class VectorStore {
  /**
   * Stores an interaction in the vector database.
   * @param text The text content to store
   * @param userId The ID of the user associated with the text
   */
  static async storeInteraction(text: string, userId: string): Promise<boolean> {
    const requestId = crypto.randomUUID();
    try {
      Logger.info(`[VectorStore] Upsert Request ${requestId} -> ${Config.MEMORY_API_URL}/upsert`);
      const response = await fetch(`${Config.MEMORY_API_URL}/upsert`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Request-ID": requestId
        },
        body: JSON.stringify({ text, user_id: userId }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] Upsert failed: ${response.status} ${response.statusText} (ReqID: ${requestId})`);
        return false;
      }
      return true;
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (upsert): ${error instanceof Error ? error.message : String(error)} (ReqID: ${requestId})`);
      return false;
    }
  }

  /**
   * Searches for context relevant to the query.
   * @param query The search query
   */
  static async searchContext(query: string): Promise<SearchResult[]> {
    const requestId = crypto.randomUUID();
    try {
      Logger.info(`[VectorStore] Search Request ${requestId} -> ${Config.MEMORY_API_URL}/search`);
      const response = await fetch(`${Config.MEMORY_API_URL}/search`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Request-ID": requestId
        },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] Search failed: ${response.status} ${response.statusText} (ReqID: ${requestId})`);
        return [];
      }

      const data = (await response.json()) as SearchResponse;
      return data.results || [];
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (search): ${error instanceof Error ? error.message : String(error)} (ReqID: ${requestId})`);
      return [];
    }
  }
}
