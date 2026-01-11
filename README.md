# 👻 Gridgeist

![Python Version](https://img.shields.io/badge/python-3.12%2B-blue?style=flat&logo=python)
![Package Manager](https://img.shields.io/badge/package_manager-uv-purple?style=flat)
![Status](https://img.shields.io/badge/status-active-success?style=flat)

**Gridgeist** is an intelligent Discord bot powered by AI. Unlike standard chatbots that reset after every conversation, Gridgeist features **long-term memory persistence**. This allows it to store context, recall past interactions, and retrieve information arbitrarily for an indefinite amount of time, creating a more personal and continuous user experience.

## ✨ Features

*   **🧠 Long-Term Memory:** Remembers user details and context across different sessions.
*   **💬 Natural Conversations:** Powered by LLMs for human-like interaction.
*   **⚡ Fast & Efficient:** Built using modern Python tooling.

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine. Also ensure that you configure a Qdrant vector store server using Docker or your own way of setting it up...
The bot will try to connect to Qdrant at `http://localhost:6333`. The URL can be modified in the projects `.env`.

### Prerequisites

*   Python 3.12 or higher
*   [uv](https://github.com/astral-sh/uv) (An extremely fast Python package installer and resolver)
*   A Discord Bot Token ([Get one here](https://discord.com/developers/applications))

### 🛠️ Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/gridgeist.git
    cd gridgeist
    ```

2.  **Create a Virtual Environment**
    We use `uv` for fast environment management.
    ```bash
    uv venv
    ```

3.  **Activate the Environment**
    *   **Linux/macOS:**
        ```bash
        source .venv/bin/activate
        ```
    *   **Windows:**
        ```powershell
        .venv\Scripts\activate
        ```

4.  **Install Dependencies**
    ```bash
    uv pip install -r requirements.txt
    ```

### ⚙️ Configuration

Before running the bot, you must set up your environment variables.

1.  Create a `.env` file in the root directory.
2.  Add your API keys and configuration (example below):

```ini
# Discord
DISCORD_TOKEN=
GROQ_API_KEY=
OWNER_ID=

# Qdrant
QDRANT_URL=
QDRANT_COLLECTION=
QDRANT_API_KEY=
```

### ▶️ Running the Bot

Once configured, launch Gridgeist:

```bash
python main.py
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📄 License

[MIT](LICENSE)