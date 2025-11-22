import { Message } from "discord.js";

type Timer = ReturnType<typeof setTimeout>;

interface BufferValue {
  messages: Message[];
  timer: Timer;
  userId: string;
  callback: (messages: Message[]) => void;
}

export class MessageBuffer {
  private buffers = new Map<string, BufferValue>();

  /**
   * Adds a message to the buffer.
   * If a buffer exists, it clears the timer and adds the message.
   * If no buffer exists, it creates one with a 2500ms timer.
   */
  public add(
    channelId: string,
    message: Message,
    callback: (messages: Message[]) => void
  ): void {
    const existingBuffer = this.buffers.get(channelId);

    if (existingBuffer) {
      // Clear existing timer
      clearTimeout(existingBuffer.timer);
      
      // Add message and update callback to the latest one
      existingBuffer.messages.push(message);
      existingBuffer.callback = callback;

      // Reset timer to 2500ms
      existingBuffer.timer = setTimeout(() => {
        console.log(`[${new Date().toISOString()}] [Buffer] Timer expired. Flushing ${existingBuffer.messages.length} messages.`);
        this.flush(channelId);
      }, 2500);
      console.log(`[${new Date().toISOString()}] [Buffer] Message added. Timer reset for 2.5s.`);
    } else {
      // Create new buffer
      const buffer: BufferValue = {
        messages: [message],
        timer: setTimeout(() => {
          console.log(`[${new Date().toISOString()}] [Buffer] Timer expired. Flushing 1 messages.`);
          this.flush(channelId);
        }, 2500),
        userId: message.author.id,
        callback,
      };
      this.buffers.set(channelId, buffer);
      console.log(`[${new Date().toISOString()}] [Buffer] Message added. Timer started for 2.5s.`);
    }
  }

  /**
   * Extends the timer if the user is still typing.
   * Resets timer to 4000ms.
   */
  public handleTyping(channelId: string, userId: string): void {
    const buffer = this.buffers.get(channelId);

    // Only extend if it's the same user typing
    if (buffer && buffer.userId === userId) {
      console.log(`[${new Date().toISOString()}] [Buffer] Typing detected. Extending timer to 4s.`);
      clearTimeout(buffer.timer);
      buffer.timer = setTimeout(() => {
        console.log(`[${new Date().toISOString()}] [Buffer] Timer expired (after typing). Flushing ${buffer.messages.length} messages.`);
        this.flush(channelId);
      }, 4000);
    }
  }

  /**
   * Executes the callback with combined text and clears the buffer.
   */
  private flush(channelId: string): void {
    const buffer = this.buffers.get(channelId);
    if (!buffer) return;
    
    // Execute callback
    buffer.callback(buffer.messages);

    // Remove buffer
    this.buffers.delete(channelId);
  }
}

export const messageBuffer = new MessageBuffer();
