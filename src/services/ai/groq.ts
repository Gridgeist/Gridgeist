import Groq from "groq-sdk";
import { Config } from "../../config";

const groq = new Groq({
  apiKey: Config.GROQ_API_KEY,
});

export async function generateResponse(messages: any[]): Promise<string> {
  try {
    const completion = await groq.chat.completions.create({
      messages,
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
