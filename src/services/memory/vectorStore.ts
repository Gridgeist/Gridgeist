import { Config } from "../../config";
import { Logger } from "../utils/logger";

export interface SearchResult {
  id: string;
  text: string;
  user_id: string;
  created_at: number;
  last_modified?: number;
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
   * @param metadata Optional metadata (category, importance, etc.)
   */
  static async storeInteraction(text: string, userId: string, metadata?: Record<string, any>): Promise<boolean> {
    const requestId = crypto.randomUUID();
    try {
      Logger.info(`[VectorStore] Upsert Request ${requestId} -> ${Config.MEMORY_API_URL}/upsert`);
      const response = await fetch(`${Config.MEMORY_API_URL}/upsert`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Request-ID": requestId
        },
        body: JSON.stringify({ 
          text, 
          user_id: userId,
          metadata 
        }),
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

  /**
   * Deletes a memory by ID.
   * @param memoryId The ID of the memory to delete
   */
  static async deleteInteraction(memoryId: string): Promise<boolean> {
    const requestId = crypto.randomUUID();
    try {
      Logger.info(`[VectorStore] Delete Request ${requestId} -> ${Config.MEMORY_API_URL}/delete`);
      const response = await fetch(`${Config.MEMORY_API_URL}/delete`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Request-ID": requestId
        },
        body: JSON.stringify({ memory_id: memoryId }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] Delete failed: ${response.status} ${response.statusText} (ReqID: ${requestId})`);
        return false;
      }
      return true;
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (delete): ${error instanceof Error ? error.message : String(error)} (ReqID: ${requestId})`);
      return false;
    }
  }

  /**
   * Updates a memory's text content.
   * @param memoryId The ID of the memory to update
   * @param newText The new text content
   */
  static async updateInteraction(memoryId: string, newText: string): Promise<boolean> {
    const requestId = crypto.randomUUID();
    try {
      Logger.info(`[VectorStore] Update Request ${requestId} -> ${Config.MEMORY_API_URL}/update`);
      const response = await fetch(`${Config.MEMORY_API_URL}/update`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Request-ID": requestId
        },
        body: JSON.stringify({ memory_id: memoryId, new_text: newText }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] Update failed: ${response.status} ${response.statusText} (ReqID: ${requestId})`);
        return false;
      }
      return true;
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (update): ${error instanceof Error ? error.message : String(error)} (ReqID: ${requestId})`);
      return false;
    }
  }

  /**
   * Fetches memories by their IDs.
   * @param memoryIds List of memory IDs
   */
  static async fetchInteractions(memoryIds: string[]): Promise<SearchResult[]> {
    const requestId = crypto.randomUUID();
    try {
      Logger.info(`[VectorStore] FetchByIds Request ${requestId} -> ${Config.MEMORY_API_URL}/fetch_by_ids`);
      const response = await fetch(`${Config.MEMORY_API_URL}/fetch_by_ids`, {
        method: "POST",
        headers: { 
          "Content-Type": "application/json",
          "X-Request-ID": requestId
        },
        body: JSON.stringify({ memory_ids: memoryIds }),
      });

      if (!response.ok) {
        Logger.warn(`[VectorStore] FetchByIds failed: ${response.status} ${response.statusText} (ReqID: ${requestId})`);
        return [];
      }

      const data = (await response.json()) as SearchResponse;
      return data.results || [];
    } catch (error) {
      Logger.warn(`[VectorStore] Connection error (fetch_by_ids): ${error instanceof Error ? error.message : String(error)} (ReqID: ${requestId})`);
      return [];
    }
  }
}
