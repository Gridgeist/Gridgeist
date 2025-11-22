import { Typing } from "discord.js";
import { messageBuffer } from "../services/utils/messageBuffer";

export default {
  name: "typingStart",
  execute: async (typing: Typing) => {
    // Ignore bots
    if (typing.user.bot) return;

    // Signal to the buffer that typing is happening
    // This will extend the wait time if a buffer exists for this user
    messageBuffer.handleTyping(typing.channel.id, typing.user.id);
  },
};
