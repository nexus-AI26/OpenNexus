# OpenNexus

> AI assistant for developers and ethical hackers — multi-interface, autonomous, and extensible.

OpenNexus includes a **Web UI** and a **Telegram bot** sharing the same conversation state (when both run). The agent loop can emit `<execute>command</execute>` to run real shell commands on the host and reason over the output.

---

## Features

* **Telegram + Web UI** — default mode runs the bot and serves the Web UI on port **8000** in the background (same process)
* **Web UI modules** — chat (with `/stop` and `/wait`), model/provider switch, system prompt (session), context stats, DuckDuckGo search, skills, history, command reference
* **Autonomous agent loop** — `<execute>` tags, real command output fed back to the model
* **Multi-provider** — Anthropic, OpenAI, OpenRouter, Groq, Ollama, custom (OpenAI-compatible)
* **Skills** — locally stored, auto-generated hints from repeated tasks
* **Streaming** — live responses in Telegram and the browser
* **Access control** — Telegram whitelist; Web UI uses configured `owner_id` context
* **File ingestion** (Telegram) — `.py`, `.sh`, `.txt`, `.md`, `.json`, `.log`
* **Command allowlist + logging** — configurable `allowed_commands` and execution logs

---

## Requirements

* Python 3.11+
* **Telegram** — `bot_token` only required for `bot` or `all` with Telegram enabled (`all` without a token falls back to Web UI only)
* **`access.owner_id`** and **`access.allowed_users`** — required for startup validation (Web UI uses `owner_id` for the chat session)
* At least one provider API key, or Ollama reachable at your configured `base_url`

---

## Installation

### Quick install (Debian / Ubuntu–style, uses `apt-get`)

```bash
curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash
```

On other Linux distros, macOS, or Windows, use **manual installation** below (or adapt package commands for `git` / `python3` / `venv`).

### Manual installation

```bash
git clone https://github.com/nexus-AI26/OpenNexus.git
cd OpenNexus

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -e .

mkdir -p ~/.opennexus
cp config.toml.example ~/.opennexus/config.toml
```

Edit `~/.opennexus/config.toml`: set `access.owner_id`, `access.allowed_users`, and provider keys. Set `bot_token` if you use Telegram.

---

## Usage

| Mode | Command | Behavior |
|------|---------|----------|
| **Default** | `python main.py` or `opennexus` | Telegram (if `bot_token` set) **and** Web UI at `http://0.0.0.0:8000` (Web runs in a background thread) |
| Web only | `python main.py web` or `opennexus web` | FastAPI UI only on port 8000 |
| Bot only | `python main.py bot` or `opennexus bot` | Telegram only; requires `bot_token` |

Open the UI locally: [http://localhost:8000](http://localhost:8000). If you run on a remote server, open port **8000** in your firewall or bind/reverse-proxy as needed.

---

## Configuration

Path: `~/.opennexus/config.toml` (overrides via env vars where documented in `config.py`).

| Field | Env (examples) | Description |
|-------|----------------|-------------|
| `bot_token` | `OPENNEXUS_BOT_TOKEN` | Telegram bot token |
| `access.owner_id` | — | Admin Telegram user ID; Web UI session user |
| `access.allowed_users` | — | Allowed Telegram user IDs |
| `providers.default` | — | Default provider name |
| `providers.<name>.api_key` | `OPENNEXUS_<NAME>_API_KEY` | Provider key |
| `security.allowed_commands` | — | Allowlisted shell commands for `<execute>` / `/run` |
| `system_prompt` | — | Base system prompt (Web can override per session in the UI) |

---

## Telegram commands

| Command | Description |
|---------|-------------|
| `/start`, `/help` | Help and command list |
| `/clear` | Clear conversation context |
| `/model <provider> <model>` | Switch provider and model |
| `/skills` | List skills |
| `/skill show <id>`, `/skill delete <id>` | Show or delete a skill |
| `/search <query>` | Web search |
| `/export` | Export chat as Markdown |
| `/system`, `/system set <text>` | Show or override system prompt (session) |
| `/tokens` | Approximate context size |
| `/raw` | Toggle raw API-style replies |
| `/stop` | Stop the current streamed reply |
| `/wait <text>` | Inject a note during generation (model continues) |
| `/run <command>` | Run shell (owner only; same allowlist as `<execute>`) |

---

## Autonomous execution flow

1. User sends a request.
2. The model may output `<execute>command</execute>`.
3. The host runs the command (allowlist / owner rules apply).
4. Output is injected into context as a system message.
5. The model continues with the real output.

---

## Security notes

* Only commands in `allowed_commands` run (plus owner-only `/run` / `<execute>` rules as implemented).
* Executions are logged under `~/.opennexus/logs/`.
* Use least-privilege API keys and run in a VM or container when exposing port 8000.

---

## License

See `LICENSE`.
