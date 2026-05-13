# Quickstart: Nexus in 15 Minutes

Get Nexus running on your homelab with Telegram, email, and calendar integration.

---

## Prerequisites

- Docker + Docker Compose
- Telegram account (for bot creation)
- Google account (for email/calendar)
- An LLM API key (Anthropic recommended)

---

## 1. Clone and Configure (3 min)

```bash
git clone https://github.com/jerynmathew/nexus.git
cd nexus
cp config.example.yaml config.yaml
```

Edit `config.yaml`:

```yaml
llm:
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4-20250514"

telegram:
  bot_token: "${TELEGRAM_BOT_TOKEN}"

seed_users:
  - name: "Your Name"
    tenant_id: "you"
    role: "admin"
    persona: "default"
    timezone: "Asia/Kolkata"    # Your timezone
    telegram_user_id: 123456789  # Your Telegram user ID
```

Create `.env`:

```bash
ANTHROPIC_API_KEY=sk-ant-...
TELEGRAM_BOT_TOKEN=1234567890:ABC...
```

---

## 2. Create a Telegram Bot (2 min)

1. Message [@BotFather](https://t.me/BotFather) on Telegram
2. Send `/newbot`, follow prompts, get the bot token
3. Send `/setcommands` and set:
   ```
   status - Check Nexus health
   portfolio - Portfolio summary (requires nexus-finance)
   actions - Work action items (requires nexus-work)
   ```
4. Get your user ID: message [@userinfobot](https://t.me/userinfobot)
5. Put both in your `.env` and `config.yaml`

---

## 3. Start Nexus (2 min)

```bash
docker compose up -d
```

This starts:
- **Nexus** — the AI assistant
- **AgentGateway** — LLM proxy on port 4000

Check it's running:

```bash
docker compose logs nexus --tail 20
# Should see: "Nexus is ready"
```

---

## 4. Talk to Nexus (1 min)

Open Telegram, message your bot:

```
Hello!
```

Nexus responds with the configured persona. Try:

```
What can you do?
/status
```

---

## 5. Add Google Workspace (5 min, optional)

```bash
docker compose --profile google up -d
```

Then run the OAuth setup:

```bash
docker compose exec nexus nexus setup google
```

Follow the URL to authenticate. After setup:

```
What's on my calendar today?
Summarize my unread emails
```

---

## 6. Add Extensions (2 min, optional)

### nexus-finance (FIRE personal finance)

```bash
docker compose --profile finance up -d
pip install -e ./extensions/nexus-finance
```

Commands: `/portfolio`, `/fire`, `/rebalance`, `/research`, `/gold`, `/holdings`

### nexus-work (work intelligence)

```bash
pip install -e ./extensions/nexus-work
```

Commands: `/actions`, `/delegate`, `/meetings`, `/next`

Both extensions are auto-discovered via Python entry_points.

---

## 7. Web Dashboard

Open `http://localhost:8080` for the homelab infrastructure dashboard.

For user-facing dashboards:
- `http://localhost:8080/dashboard/finance` — portfolio, allocation, FIRE progress
- `http://localhost:8080/dashboard/work` — action items, delegations, meetings

---

## What's Next

- **Customize your persona**: edit `personas/default.md` or create a new one
- **Add skills**: create SKILL.md files in `~/.nexus/skills/`
- **Enable more MCP servers**: uncomment entries in `config.yaml`
- **Webhook mode**: set `telegram.webhook_url` in config for production
- **JSON logging**: `NEXUS_JSON_LOGS=true` for log aggregation

See [Extension Development Guide](extension-development.md) for building your own extensions.
