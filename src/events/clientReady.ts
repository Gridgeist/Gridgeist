import { Client } from "discord.js";
import { Config } from "../config";

export default {
  name: "clientReady",
  execute: async (client: Client) => {
    console.log(`✅ Logged in as ${client.user?.tag}`);

    try {
      await fetch(Config.MEMORY_API_URL);
      console.log("🟢 Memory Server is reachable");
    } catch {
      console.log("🔴 Memory Server is unreachable");
    }
  },
};
