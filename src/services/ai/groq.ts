import Groq from "groq-sdk";
import { Config } from "../../config";

const groq = new Groq({
  apiKey: Config.GROQ_API_KEY,
});

export async function generateResponse(messages: any[], imageUrl?: string): Promise<string> {
  try {
    let formattedMessages = [...messages];

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

    const completion = await groq.chat.completions.create({
      messages: formattedMessages,
      model: "meta-llama/llama-4-scout-17b-16e-instruct",
      temperature: 0.7,
      max_tokens: 500,
    });

    return completion.choices[0]?.message?.content || "i'm not sure what to say.";
  } catch (error) {
    console.error("Groq API error:", error);
    return "my brain is offline. try again in a bit.";
  }
}
