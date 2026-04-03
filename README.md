# OpenNexus

> AI assistant for developers and ethical hackers. Telegram-only. Self-contained.
> Multi-provider. Builds its own skills. Web search built in.

A security-hardened AI assistant running as a Telegram bot on your own machine.
No web UI. No browser. No Electron. No telemetry. Just a fast, capable AI in
your Telegram client, running on whatever model you want.

---

## Features

- Telegram-only interface — access from any device via Telegram
- Multi-provider: Anthropic, OpenAI, OpenRouter, Groq, Ollama, Custom endpoints
- Switch models mid-session with /model
- Web search via DuckDuckGo — automatic intent detection or forced with /search
- Autonomous skill system — generates and stores reusable skills locally
- Per-user isolated conversation contexts with streaming responses
- Whitelist-based access control — unlisted users are silently dropped
- File ingestion (.py, .sh, .txt, .md, .json, .log)
- Export conversations as Markdown with /export
- Shell execution sandboxing with audit log
- Startup secrets scanner
- Runs as a systemd background service
- No telemetry, no cloud sync, all data stays local

---

## Requirements

- Linux (Debian/Ubuntu/Kali recommended)
- Python 3.11+
- A Telegram bot token (create via @BotFather)
- Your Telegram user ID (get from @userinfobot)
- At least one AI provider API key, or a running Ollama instance

---

## Installation

### Automatic
```bash
curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash
```

If you get a permission error on /opt, run:
```bash
sudo rm -rf /opt/opennexus
curl -fsSL https://raw.githubusercontent.com/nexus-AI26/OpenNexus/main/install.sh | bash
```

If python3-venv is missing:
```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
```
Then re-run the installer.

### Manual
```bash
git clone https://github.com/nexus-AI26/OpenNexus.git /opt/opennexus
cd /opt/opennexus
python3 -m venv venv
venv/bin/pip install -r requirements.txt
mkdir -p ~/.opennexus/skills ~/.opennexus/logs
cp config.toml.example ~/.opennexus/config.toml
nano ~/.opennexus/config.toml
venv/bin/python main.py
```

---

## Configuration

Edit `~/.opennexus/config.toml`:
```toml
bot_token = "YOUR_BOT_TOKEN_FROM_BOTFATHER"

[access]
owner_id = 123456789        # your Telegram user ID from @userinfobot
allowed_users = [123456789] # list of permitted user IDs

[providers]
default = "openrouter"

[providers.anthropic]
api_key = ""
default_model = "claude-opus-4-5"

[providers.openai]
api_key = ""
default_model = "gpt-4o"

[providers.openrouter]
api_key = ""
default_model = "anthropic/claude-opus-4-5"

[providers.groq]
api_key = ""
default_model = "llama-3.3-70b-versatile"

[providers.ollama]
base_url = "http://localhost:11434"
default_model = "llama3"

[providers.custom]
base_url = ""
api_key = ""
auth_header = "Authorization"
auth_prefix = "Bearer"
default_model = ""
```

> Never commit config.toml — it contains your API keys and bot token.
> If you accidentally expose your bot token, revoke it immediately via
> @BotFather → /mybots → your bot → API Token → Revoke.

---

## Commands

| Command | Description |
|---|---|
| /start | Greeting and command list |
| /clear | Clear current conversation context |
| /model \<provider\> \<model\> | Switch provider and model for this session |
| /search \<query\> | Force a web search and return raw results |
| /websearch on\|off | Toggle automatic web search injection |
| /skills | List all locally stored auto-generated skills |
| /skill show \<id\> | Show a skill's full JSON |
| /skill delete \<id\> | Delete a skill |
| /export | Export conversation as a .md file |
| /system | Show current system prompt |
| /system set \<text\> | Override system prompt for this session |
| /tokens | Show approximate token count of current context |
| /raw | Toggle raw API response mode |
| /adduser \<id\> | Owner only: add user to whitelist |
| /removeuser \<id\> | Owner only: remove user from whitelist |
| /help | Full command reference |

---

## Running as a Service

Install and enable the systemd service:
```bash
cat > /etc/systemd/system/opennexus.service << 'EOF'
[Unit]
Description=OpenNexus Telegram AI Assistant
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/opennexus
ExecStart=/opt/opennexus/venv/bin/python /opt/opennexus/main.py
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable opennexus
systemctl start opennexus
```

Useful commands:
```bash
systemctl status opennexus        # check status
systemctl restart opennexus       # restart after config changes
systemctl stop opennexus          # stop
journalctl -u opennexus -f        # follow logs
```

---

## Autonomous Skills System

OpenNexus watches your usage patterns and automatically generates reusable skills
stored locally in `~/.opennexus/skills/` as JSON files. When your input matches
a skill's trigger keywords, that skill's context is injected into the AI prompt
automatically.

Skills are never shared or synced — they are personal to your instance.

Manage skills via Telegram:
- `/skills` — list all skills
- `/skill show <id>` — inspect a skill
- `/skill delete <id>` — remove a skill

---

## Web Search

OpenNexus uses DuckDuckGo for web search — no API key required.

- Automatic: enabled by default, triggers on search-intent keywords
- Manual: `/search <query>` returns raw results without AI processing
- Toggle: `/websearch off` to disable automatic injection

Search results are injected into the AI context before generating a response,
giving the model access to current information.

---

## Security

- **Whitelist enforcement** — checked on every message, reloaded from disk live
- **Input sanitization** — prompt injection patterns stripped before AI processing
- **Startup secrets scan** — warns if secrets are found outside config.toml
  (false positives from venv library test files are expected and safe to ignore)
- **Shell sandboxing** — exec calls validated against allowlist, logged to
  `~/.opennexus/logs/exec.log`
- **HTTPS enforced** — all outbound calls use TLS (Ollama localhost excepted)
- **Local only** — no telemetry, no cloud sync, all data on disk

---

## Providers

| Provider | Format | Notes |
|---|---|---|
| Anthropic | Native Messages API | claude-opus-4-5, claude-sonnet-4-6 |
| OpenAI | OpenAI-compatible | gpt-4o, gpt-4-turbo |
| OpenRouter | OpenAI-compatible | Access to 100+ models |
| Groq | OpenAI-compatible | Fast inference |
| Ollama | OpenAI-compatible | Local models, no API key needed |
| Custom | OpenAI-compatible | Any compatible endpoint |

Switch mid-session: `/model groq llama-3.3-70b-versatile`

---

## Troubleshooting

**python3-venv not available**
```bash
sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
```

**Permission denied on /opt**
```bash
sudo rm -rf /opt/opennexus
# then re-run installer or manual install steps
```

**Bot token exposed**
Revoke immediately: @BotFather → /mybots → your bot → API Token → Revoke
Update ~/.opennexus/config.toml with the new token and restart.

**Security warning about venv test files**
Expected false positive from tornado library test files. Safe to ignore.

**Config errors on startup**
Make sure owner_id and allowed_users are set in ~/.opennexus/config.toml.
Get your Telegram ID from @userinfobot.

---

## License

MIT
