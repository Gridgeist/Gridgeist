import { Client, GatewayIntentBits, Partials } from "discord.js";

let clientInstance: Client | null = null;

export const getDiscordClient = (): Client => {
  if (!clientInstance) {
    clientInstance = new Client({
      intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent,
        GatewayIntentBits.DirectMessages,
        GatewayIntentBits.GuildMessageTyping,
        GatewayIntentBits.DirectMessageTyping,
      ],
      partials: [Partials.Channel],
    });
  }
  return clientInstance;
};
