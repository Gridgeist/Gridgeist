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
    try {
      const response = await fetch(`${Config.MEMORY_API_URL}/upsert`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, user_id: userId }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] Upsert failed: ${response.status} ${response.statusText}`);
        return false;
      }
      return true;
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (upsert): ${error instanceof Error ? error.message : String(error)}`);
      return false;
    }
  }

  /**
   * Searches for context relevant to the query.
   * @param query The search query
   */
  static async searchContext(query: string): Promise<SearchResult[]> {
    try {
      const response = await fetch(`${Config.MEMORY_API_URL}/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] Search failed: ${response.status} ${response.statusText}`);
        return [];
      }

      const data = (await response.json()) as SearchResponse;
      return data.results || [];
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (search): ${error instanceof Error ? error.message : String(error)}`);
      return [];
    }
  }
}
