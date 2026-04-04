# OpenNexus

> AI assistant for developers and ethical hackers. Multi-interface. Autonomous.
> Multi-provider. Builds its own skills.

A security-hardened AI assistant rebuilt from the ground up for technical users.
OpenNexus now features a **Premium Web UI** and an **Autonomous Agent Loop** to execute real system commands (like `nmap`, `grep`, `whoami`) directly on your machine.

---

## Features

- **Dual-Interface support** — use it via **Telegram** or the new **Web UI** (Eco-Minimalist Dark Mode).
- **Autonomous Agent Loop** — the AI can now *actually* run commands. It outputs `<execute>command</execute>`, runs it, and reads the real output before responding.
- **Multi-provider support**: Anthropic, OpenAI, OpenRouter, Groq, Ollama, Custom
- **Switch models mid-session** with `/model`
- **Autonomous skill system** — generates and stores reusable skills locally as it learns your usage patterns.
- **Per-user isolated conversation contexts**
- **Streaming responses** with live message editing
- **Whitelist-based access control**
- **File ingestion** (`.py`, `.sh`, `.txt`, `.md`, `.json`, `.log`)
- **Shell execution sandboxing** with audit log
- **No telemetry, no cloud sync** — all data stays local

---

## Requirements

- Python 3.11+
- A Telegram bot token (if using the bot)
- At least one AI provider API key, or a running [Ollama](https://ollama.com) instance

---

## Installation

```bash
git clone https://github.com/nexus-AI26/OpenNexus.git
cd OpenNexus

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # Or venv\Scripts\activate on Windows

# Install in editable mode
pip install -e .

# Setup config
mkdir ~/.opennexus
cp config.toml.example ~/.opennexus/config.toml
# Edit ~/.opennexus/config.toml — fill in bot_token, owner_id, allowed_users, and API keys
```

---

## Usage

You can run OpenNexus in two modes:

### Web UI Mode (Recommended)
```bash
opennexus web
```
Then visit `http://localhost:8000` in your browser.

### Telegram Bot Mode
```bash
opennexus bot
```
Start chatting with your bot on Telegram.

---

## Configuration

All configuration lives in `~/.opennexus/config.toml`. Environment variables override config file values.

| Field | Env Var Override | Description |
|---|---|---|
| `bot_token` | `OPENNEXUS_BOT_TOKEN` | Telegram bot token from @BotFather |
| `access.owner_id` | — | Your Telegram user ID (admin) |
| `access.allowed_users` | — | List of Telegram user IDs allowed |
| `providers.default` | — | Default provider name |
| `providers.<name>.api_key` | `OPENNEXUS_<NAME>_API_KEY` | API key for the provider |
| `security.allowed_commands` | — | Shell commands permitted for execution |

---

## Commands (Telegram)

| Command | Description |
|---|---|
| `/start` | Greeting and command list |
| `/clear` | Clear conversation context |
| `/model <provider> <model>` | Switch AI provider/model |
| `/skills` | List stored skills |
| `/export` | Export conversation as `.md` |
| `/run <command>` | (Owner) Manually run a shell command |

---

## Autonomous Agent Execution

The AI is instructed to use the tool loop when needed. To trigger a command:
1. Ask the AI: *"Scan my local network with nmap"*
2. The AI will output: `<execute>nmap -sn 192.168.1.0/24</execute>`
3. The system captures this, runs it, and sends the result back.
4. The AI provides the analyzed final answer.

---

## License

MIT
