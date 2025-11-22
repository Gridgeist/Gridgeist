import { z } from "zod";
import dotenv from "dotenv";

dotenv.config();

const envSchema = z.object({
  DISCORD_TOKEN: z.string().min(1, "DISCORD_TOKEN is missing"),
  DISCORD_CLIENT_ID: z.string().min(1, "DISCORD_CLIENT_ID is missing"),
  GROQ_API_KEY: z.string().min(1, "GROQ_API_KEY is missing"),
  MEMORY_API_URL: z.string().url().default("http://127.0.0.1:8000"),
  MODAL_FLUX_GEN_URL: z.string().url("MODAL_FLUX_GEN_URL must be a valid URL"),
  MODAL_FLUX_EDIT_URL: z.string().url("MODAL_FLUX_EDIT_URL must be a valid URL"),
});

const env = envSchema.parse(process.env);

export const Config = {
  ...env,
  MAX_SHORT_TERM_MEMORY: 10,
  EMBEDDING_DIMENSION: 384,
} as const;
