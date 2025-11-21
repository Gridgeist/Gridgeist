import { Client, GatewayIntentBits } from "discord.js";

let clientInstance: Client | null = null;

export const getDiscordClient = (): Client => {
  if (!clientInstance) {
    clientInstance = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
      ],
    });
  }
  return clientInstance;
};
