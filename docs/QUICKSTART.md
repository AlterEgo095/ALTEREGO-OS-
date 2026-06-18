# Quick start — ALTEREGO OS V1

## Prerequisites

- Python 3.11+
- An LLM endpoint (one of):
  - **OpenAI API key** (recommended for V1) — set `OPENAI_API_KEY` in `.env`
  - **Ollama local** — install from ollama.com, run `ollama pull llama3.2`, leave `OPENAI_API_KEY` empty

## Install

```bash
cd alterego-os
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
playwright install chromium   # for the browser plugin (optional)
```

## Configure

```bash
cp .env.example .env
# Edit .env — at minimum set OPENAI_API_KEY (or use Ollama local)
```

For GitHub/Docker/SSH/Postgres/Mongo/Email/Telegram plugins, set the relevant env vars.

## Run

```bash
# Smoke test (no API key needed — uses mock LLM)
PYTHONPATH=. python3 scripts/smoke_test.py

# Single mission
alterego run "Hello ALTEREGO, what can you do?"

# Interactive chat
alterego chat

# Inspect loaded plugins
alterego plugins list
alterego plugins capabilities

# Health check all plugins
alterego health
```

## Run tests

```bash
pytest
```

## Architecture (V1)

```
User → ChiefOfStaff → MissionEngine → DecisionEngine → Planner
                                                  ↓
                                          CapabilityRegistry (selects capability, NOT plugin)
                                                  ↓
                                          PluginManager (picks best plugin)
                                                  ↓
                                          10 Plugins (bridges)
                                                  ↓
                                          External Tools
```

All other components (Memory, EventBus) are present but invisible to the user.

## 10 plugins V1

| Plugin      | Capability        | Library            |
|-------------|-------------------|--------------------|
| github      | `github`          | PyGithub           |
| docker      | `docker`          | docker-py          |
| ssh         | `ssh`             | paramiko           |
| browser     | `browser`         | Playwright         |
| filesystem  | `filesystem`      | stdlib             |
| postgres    | `database.sql`    | asyncpg            |
| mongo       | `database.nosql`  | motor              |
| llm         | `llm.chat`        | openai SDK         |
| email       | `email`           | aiosmtplib         |
| telegram    | `telegram`        | httpx (Bot API)    |

## Next step — Phase 3 use case

The next milestone is implementing the real use case:

> « Analyse un dépôt GitHub, corrige les erreurs, lance les tests et propose une Pull Request. »

This will exercise: github.clone → filesystem.read → llm.chat (analysis) → filesystem.write (fix) → github.commit → github.create_pull_request.

## Builder — long-term

The Builder is NOT in V1. It will be extracted from observed repetitive patterns
after several manual plugin integrations. **The Builder is a consequence, not a starting point.**
