import "dotenv/config";
import { Config } from "./config";
import { getDiscordClient } from "./core/client";
import { loadEvents } from "./core/loader";

const main = async () => {
  const client = getDiscordClient();

  await loadEvents(client);

  await client.login(Config.DISCORD_TOKEN);
};

main().catch((error) => {
  console.error("Failed to start bot:", error);
  process.exit(1);
});
