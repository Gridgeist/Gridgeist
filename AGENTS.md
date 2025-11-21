# AI Agent Directives: Discord Companion Bot

## 1. Tech Stack
- **Runtime:** Bun (TypeScript).
- **Discord:** `discord.js` (Latest).
- **AI Inference:** `groq-sdk` (Model: `llama-4-scout-17b-16e-instruct`).
- **Memory Backend:** Python on Modal.com (`modal`, `lancedb`, `sentence-transformers`).
- **Utilities:** `zod` (Validation), `dotenv`.

## 2. Architectural Rules
- **Separation of Concerns:**
  - `src/core`: Discord client and event loaders.
  - `src/services`: Business logic (AI, Memory, Utilities).
  - `modal_backend`: Python code isolated from the main Bun app.
- **Memory Strategy:**
  - **Short-term:** In-memory array (last 10 msgs).
  - **Long-term:** Vector RAG via Modal API (LanceDB).
- **Performance:**
  - Saving memories must be **fire-and-forget** (do not await saving before replying).
  - AI generation triggers a "Typing..." indicator immediately.

## 3. Coding Standards
- **TypeScript:** Strict typing. Define interfaces in `src/types.ts`.
- **Error Handling:** **NEVER** let the bot crash. Wrap external API calls (Groq, Modal) in try/catch blocks. Fallback gracefully (e.g., "My brain is offline").
- **Config:** All environment variables must be validated via Zod in `src/config.ts`.
- **Style:** Functional composition over deep OOP inheritance. Keep files small and focused.
- Automatically use context7 for code generation and library documentation.

## 4. File Structure Target
```text
/
├── modal_backend/      # Python Vector Store
│   └── app.py
├── src/
│   ├── main.ts         # Entry Point
│   ├── config.ts       # Env Validation
│   ├── core/           # Client & Loader
│   ├── services/       # AI, Memory, Orchestrator
│   └── events/         # messageCreate, ready
└── .env
```


