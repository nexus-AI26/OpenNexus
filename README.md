# OpenNexus

> AI assistant for developers and ethical hackers — multi-interface, autonomous, and extensible.

A security-hardened AI assistant built for technical users. OpenNexus includes a **modern Web UI** and an **Autonomous Agent Loop** capable of executing real system commands (e.g., `nmap`, `grep`, `whoami`) and reasoning over their output.

---

## Features

* **Dual interface** — interact via **Telegram** or the built-in **Web UI** (eco-minimalist dark mode)
* **Autonomous agent loop** — executes commands via `<execute>` tags and processes real output
* **Multi-provider support** — Anthropic, OpenAI, OpenRouter, Groq, Ollama, and custom providers
* **Dynamic model switching** — change models mid-session with `/model`
* **Self-extending skill system** — generates and stores reusable skills locally
* **Isolated user contexts** — per-user conversation separation
* **Streaming responses** — live output with message updates
* **Access control** — whitelist-based user restrictions
* **File ingestion** — supports `.py`, `.sh`, `.txt`, `.md`, `.json`, `.log`
* **Sandboxed shell execution** — with audit logging
* **Privacy-first** — no telemetry, no cloud sync; all data stays local

---

## Requirements

* Python 3.11+
* Telegram bot token (optional, for bot mode)
* At least one AI provider API key or a running Ollama instance

---

## Installation

### Quick Install (Linux/macOS)

```bash
curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash
```

### Manual Installation

```bash
git clone https://github.com/nexus-AI26/OpenNexus.git
cd OpenNexus

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -e .

mkdir -p ~/.opennexus
cp config.toml.example ~/.opennexus/config.toml
```

Edit `~/.opennexus/config.toml` and configure your bot token, user IDs, and API keys.

---

## Usage

### Web UI (Recommended)

```bash
opennexus web
```

Open: [http://localhost:8000](http://localhost:8000)

### Telegram Bot

```bash
opennexus bot
```

---

## Configuration

All configuration is stored in:

```
~/.opennexus/config.toml
```

Environment variables override config values.

### Core Fields

| Field                       | Env Variable               | Description            |
| --------------------------- | -------------------------- | ---------------------- |
| `bot_token`                 | `OPENNEXUS_BOT_TOKEN`      | Telegram bot token     |
| `access.owner_id`           | —                          | Admin Telegram user ID |
| `access.allowed_users`      | —                          | Allowed user IDs       |
| `providers.default`         | —                          | Default provider       |
| `providers.<name>.api_key`  | `OPENNEXUS_<NAME>_API_KEY` | Provider API key       |
| `security.allowed_commands` | —                          | Allowed shell commands |
| `system_prompt`             | —                          | Core system behavior   |

---

## Telegram Commands

| Command                     | Description                        |
| --------------------------- | ---------------------------------- |
| `/start`                    | Show help message                  |
| `/clear`                    | Reset conversation                 |
| `/model <provider> <model>` | Switch model                       |
| `/skills`                   | List learned skills                |
| `/export`                   | Export chat as `.md`               |
| `/run <command>`            | Execute shell command (owner only) |

---

## Autonomous Execution Flow

When a task requires system interaction:

1. User request triggers execution intent
2. Model emits:

   ```xml
   <execute>command</execute>
   ```
3. System executes the command
4. Output is returned to the model
5. Model responds with analysis

---

## Security Notes

* Only commands defined in `allowed_commands` are executable
* All executions are logged
* Use minimal permissions for API keys
* Run inside a controlled environment (VM recommended)

---

## License

`LICENSE`
