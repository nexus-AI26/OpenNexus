# OpenNexus

> AI assistant for developers and ethical hackers. Telegram-only. Self-contained.
> Multi-provider. Builds its own skills.

A security-hardened fork of OpenClaw, rebuilt from the ground up for technical users.
No web UI. No community features. No telemetry. Just a fast, capable AI assistant
in your Telegram client, running on whatever model you want.

---

## Features

- **Telegram-only interface** — no browser, no Electron, no web server
- **Multi-provider support**: Anthropic, OpenAI, OpenRouter, Groq, Ollama, Custom
- **Switch models mid-session** with `/model`
- **Autonomous skill system** — generates and stores reusable skills locally as it learns your usage patterns, no community hub involved
- **Per-user isolated conversation contexts**
- **Streaming responses** with live message editing
- **Whitelist-based access control**
- **File ingestion** (`.py`, `.sh`, `.txt`, `.md`, `.json`, `.log`)
- **Export conversations** as Markdown
- **Shell execution sandboxing** with audit log
- **No telemetry, no cloud sync** — all data stays local

---

## Requirements

- Python 3.11+
- A Telegram bot token (create one via [@BotFather](https://t.me/BotFather))
- At least one AI provider API key, or a running [Ollama](https://ollama.com) instance

---

## Installation

### One-liner (Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash
```

With systemd service (run as root):

```bash
curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | sudo bash -s -- --service
```

### Manual install

```bash
git clone https://github.com/nexus-AI26/OpenNexus.git
cd OpenNexus

python3.11 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

mkdir -p ~/.opennexus
cp config.toml.example ~/.opennexus/config.toml
# Edit ~/.opennexus/config.toml — fill in bot_token, owner_id, allowed_users, and at least one provider API key

python main.py
```

### install.sh flags

| Flag | Description |
|---|---|
| *(none)* | Install to `/opt/opennexus`, create venv, install launcher at `~/.local/bin/opennexus` |
| `--service` | Also install and enable systemd service (requires root) |

---

## Configuration

All configuration lives in `~/.opennexus/config.toml`. Environment variables override config file values where supported.

| Field | Env Var Override | Description |
|---|---|---|
| `bot_token` | `OPENNEXUS_BOT_TOKEN` | Telegram bot token from @BotFather |
| `access.owner_id` | — | Your Telegram user ID (admin) |
| `access.allowed_users` | — | List of Telegram user IDs allowed to use the bot |
| `providers.default` | — | Default provider name |
| `providers.<name>.api_key` | `OPENNEXUS_<NAME>_API_KEY` | API key for the provider |
| `providers.<name>.default_model` | — | Default model for the provider |
| `providers.<name>.base_url` | — | API base URL (rarely needs changing) |
| `security.allowed_commands` | — | Shell commands permitted for execution |
| `security.destructive_patterns` | — | Patterns triggering destructive command confirmation |

Full example with all fields: see [`config.toml.example`](config.toml.example).

---

## Commands

| Command | Description |
|---|---|
| `/start` | Greeting and list of available commands |
| `/clear` | Clear current conversation context |
| `/model <provider> <model>` | Switch active provider and model for this session |
| `/skills` | List all locally stored auto-generated skills |
| `/skill show <id>` | Show a skill's full JSON |
| `/skill delete <id>` | Delete a skill by ID |
| `/export` | Export current conversation as a `.md` file |
| `/system` | Show the current system prompt |
| `/system set <text>` | Override the system prompt for this session |
| `/tokens` | Show approximate token count of current context |
| `/raw` | Toggle raw API response mode |
| `/adduser <id>` | Owner only: add a user to the whitelist |
| `/removeuser <id>` | Owner only: remove a user from the whitelist |
| `/help` | Full command reference |

---

## Autonomous Skills System

OpenNexus automatically generates reusable skills as it detects recurring task patterns.

### How it works

1. Every user message is tracked. When a recurring request pattern is detected (≥3 similar tasks), OpenNexus generates a skill using the active AI provider.
2. Skills are stored as individual `.json` files in `~/.opennexus/skills/`.
3. On each incoming message, trigger keywords from all stored skills are matched against the input. Matching skills inject their `system_prompt_injection` into the AI context.

### Skill schema

```json
{
  "id": "uuid-v4",
  "name": "string",
  "description": "string",
  "trigger_keywords": ["array", "of", "strings"],
  "system_prompt_injection": "string",
  "created_at": "ISO timestamp",
  "source": "auto-generated",
  "use_count": 0
}
```

### Management

- `/skills` — list all skills with ID, name, and use count
- `/skill show <id>` — print the full JSON of a skill (prefix match)
- `/skill delete <id>` — delete a skill file permanently

---

## Security

### Whitelist enforcement
Every incoming message is checked against the whitelist in `config.toml`. The whitelist is reloaded from disk on every message, so edits take effect without restart. Non-whitelisted users receive "Access denied." and nothing else.

### Input sanitization
All user inputs are scanned for prompt injection patterns (e.g., "ignore previous instructions", role-override attempts) before being sent to the AI provider. Detected patterns are replaced with `[FILTERED]`.

### Shell execution sandboxing
- Configurable allowlist of permitted commands in `config.toml`
- Every executed command is logged to `~/.opennexus/logs/exec.log` with timestamp and user ID
- Destructive commands (rm, dd, chmod 777, etc.) require explicit confirmation

### API key security
- Keys are stored in `config.toml` or environment variables only
- Keys are never logged, displayed, or transmitted beyond the provider API call
- On startup, source code is scanned for hardcoded key patterns

### Secrets scanning
On startup, `~/.opennexus/` is scanned for common secret patterns (API keys, private keys, JWTs) in files outside `config.toml`. Warnings are logged if found.

### HTTPS enforcement
All outbound HTTP calls must use HTTPS. Non-HTTPS endpoints are rejected with a loud error. The only exception is Ollama on localhost.

### Local-only data
All data — skills, logs, conversation history — stays on disk. No cloud sync. No telemetry. No phone-home behavior.

---

## Running as a Service

OpenNexus includes a script to automatically configure a systemd service that will run invisibly in the background on Linux boot.

From the application root directory, grant execution permissions and run it with `sudo`:

```bash
chmod +x deploy/install_service.sh
sudo ./deploy/install_service.sh
```

The script will map the current path and virtual environment automatically. You can check the status at any time with:

```bash
sudo systemctl status opennexus.service
sudo journalctl -u opennexus.service -f
```

---

## Providers

| Provider | Base URL | Auth | Model Example |
|---|---|---|---|
| Anthropic | `https://api.anthropic.com/v1` | `x-api-key` header | `claude-opus-4-5` |
| OpenAI | `https://api.openai.com/v1` | `Authorization: Bearer` | `gpt-4o` |
| OpenRouter | `https://openrouter.ai/api/v1` | `Authorization: Bearer` | `anthropic/claude-opus-4-5` |
| Groq | `https://api.groq.com/openai/v1` | `Authorization: Bearer` | `llama-3.3-70b-versatile` |
| Ollama | `http://localhost:11434/v1` | None | `llama3` |
| Custom | User-defined | User-defined | User-defined |

### Anthropic
Uses the native Messages API format. Set `api_key` under `[providers.anthropic]`.

### OpenAI / OpenRouter / Groq
All use the OpenAI-compatible `/v1/chat/completions` format. Set `api_key` under the respective `[providers.*]` section.

### Ollama
For local models. No API key needed. Make sure Ollama is running (`ollama serve`) and the model is pulled (`ollama pull llama3`).

### Custom
Define any OpenAI-compatible endpoint. Set `base_url`, `api_key`, `auth_header`, `auth_prefix`, and `default_model` under `[providers.custom]`.

---

## License

MIT
