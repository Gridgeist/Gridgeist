import { Config } from "../../config";
import fs from "node:fs/promises";
import path from "node:path";
import os from "node:os";
import { randomUUID } from "node:crypto";

export class ImageGenerator {
  /**
   * Generates an image from a prompt.
   * Payload: { prompt, aspect_ratio }
   * Expects a Base64 string in response (or JSON with base64).
   */
  async generate(prompt: string, aspectRatio: string): Promise<Buffer> {
    const response = await fetch(Config.MODAL_FLUX_GEN_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ prompt, aspect_ratio: aspectRatio }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to generate image: ${response.status} ${response.statusText} - ${errorText}`);
    }

    return this.parseResponse(response);
  }

  /**
   * Edits an image.
   * Payload: { prompt, image_b64, mask_b64 }
   * Returns a Buffer of the edited image.
   */
  async edit(prompt: string, sourceImageBuffer: Buffer, maskBuffer?: Buffer): Promise<Buffer> {
    const image_b64 = sourceImageBuffer.toString("base64");
    const mask_b64 = maskBuffer ? maskBuffer.toString("base64") : undefined;

    const payload: any = {
      prompt,
      image_b64,
    };
    
    if (mask_b64) {
      payload.mask_b64 = mask_b64;
    }

    const response = await fetch(Config.MODAL_FLUX_EDIT_URL, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`Failed to edit image: ${response.status} ${response.statusText} - ${errorText}`);
    }

    return this.parseResponse(response);
  }

  /**
   * Helper to parse response based on content type.
   * Handles direct Binary (image/*), JSON with image_b64, or raw Base64 text.
   */
  private async parseResponse(response: Response): Promise<Buffer> {
    const contentType = response.headers.get("content-type");

    // Handle binary response directly
    if (contentType?.startsWith("image/")) {
      const arrayBuffer = await response.arrayBuffer();
      return Buffer.from(arrayBuffer);
    }

    const text = await response.text();

    // Try parsing as JSON
    try {
      const json = JSON.parse(text);
      if (json.image_b64) {
        return Buffer.from(json.image_b64, "base64");
      }
      if (json.image) { // Fallback
         return Buffer.from(json.image, "base64");
      }
    } catch (e) {
      // Not JSON, proceed to treat as raw base64
    }

    // Treat as raw base64 string
    return Buffer.from(text, "base64");
  }

  /**
   * Writes the buffer to a temporary local file and returns the path.
   */
  async saveTempImage(buffer: Buffer): Promise<string> {
    const tempDir = os.tmpdir();
    const filename = `${randomUUID()}.png`;
    const filePath = path.join(tempDir, filename);
    await fs.writeFile(filePath, buffer);
    return filePath;
  }
}
