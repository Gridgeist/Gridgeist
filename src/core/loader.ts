import { Client } from "discord.js";
import { readdirSync } from "fs";
import { join } from "path";
import { fileURLToPath } from "url";

const __dirname = fileURLToPath(new URL(".", import.meta.url));

export async function loadEvents(client: Client): Promise<void> {
  const eventsPath = join(__dirname, "../events");
  const eventFiles = readdirSync(eventsPath).filter((file) =>
    file.endsWith(".ts")
  );

  for (const file of eventFiles) {
    const filePath = join(eventsPath, file);
    const eventModule = await import(filePath);
    const event = eventModule.default || eventModule;

    if (event.name && event.execute) {
      client.on(event.name, (...args) => event.execute(...args));
    }
  }
}
