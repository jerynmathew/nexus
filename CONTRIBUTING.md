# Contributing to Nexus

Nexus is part of the [civitas-io](https://github.com/civitas-io) ecosystem. Contributions are welcome.

## Getting Started

```bash
git clone https://github.com/jerynmathew/nexus.git
cd nexus
uv sync --all-extras
uv run pre-commit install
```

## Development Workflow

1. Create a branch from `main`
2. Make your changes
3. Run the checks: `uv run ruff check . && uv run mypy src/nexus/ && OTEL_SDK_DISABLED=true uv run pytest tests/ -q`
4. Commit (pre-commit hooks run automatically)
5. Open a PR against `main`

## Code Standards

This project holds code to a high standard. The codebase is meant to be easy to review and maintain.

### Rules

- **All imports at module level.** No function-level imports unless escaping circular dependencies.
- **Functions under 50 statements.** Cyclomatic complexity under 12.
- **PEP 8 naming.** Enforced by ruff N rules.
- **Type hints on all public functions.** mypy strict mode.
- **Google-style docstrings** on public classes and functions only. No unnecessary comments.
- **No `print()` in source code.** Use `logging`. Exception: CLITransport (stdout is the output).
- **No `as any` or `type: ignore`** without a specific error code and justification.
- **No bare `except:`** or `except Exception: pass`. Use `contextlib.suppress` or handle specifically.
- **`asyncio.Event` over busy-wait.** Never `while True: sleep(1)`.
- **`aiosqlite` over `sqlite3`.** All database access is async.
- **Test every public method.** No code without tests. Target: 85% coverage.

### Ruff Rule Sets

The project enforces 17 ruff rule sets: E, W, F, I, UP, B, ASYNC, C4, SIM, RET, PTH, T20, N, C90, PLR, RUF.

### Pre-commit Hooks

On every commit:
- trailing whitespace, end-of-file, YAML/TOML validation
- ruff lint + format
- gitleaks secret scanning
- mypy type checking

On push:
- full unit test suite

## Testing

```bash
# Run all tests (~2 seconds)
OTEL_SDK_DISABLED=true uv run pytest tests/ -q

# Run specific test file
OTEL_SDK_DISABLED=true uv run pytest tests/unit/test_memory.py -v

# Run with coverage
OTEL_SDK_DISABLED=true uv run pytest tests/ --cov=nexus
```

Tests are split into:
- `tests/unit/` — no network, no API keys, mock everything external
- `tests/integration/` — full Civitas runtime, real SQLite, mock LLM

Test files mirror source: `src/nexus/agents/memory.py` → `tests/unit/test_memory.py`

## Architecture

Read [AGENTS.md](AGENTS.md) for the full project reference — conventions, key decisions, anti-patterns, and API signatures.

Key things to know:

- **ConversationManager** is the central agent. All user I/O flows through it.
- **MemoryAgent** owns all persistent state. Other agents query it via message passing.
- **Never send messages from `on_start()`.** The MessageBus isn't ready. Use deferred initialization.
- **`self.reply()` is NOT async.** It returns a Message directly.
- **Skills are SKILL.md files**, not code. Code handles deterministic transforms; skills handle LLM-driven procedures.
- **MCP servers run as Docker sidecars**, not Civitas agents. They have independent lifecycles.

## Adding a New Integration

### Via MCP (preferred)

1. Find or build an MCP server for the service
2. Add it as a Docker sidecar in `docker-compose.yaml`
3. Add the server config to `config.example.yaml`
4. Add intent patterns to `src/nexus/agents/intent.py` if needed
5. No other code changes — tools are auto-discovered

### Via Skill

1. Create `skills/your-skill/SKILL.md` with YAML frontmatter
2. Define the procedure in markdown
3. The skill is automatically loaded by SkillManager

### Via Custom Agent (exception)

Only for services that need stateful connections or custom rendering. Subclass `AgentProcess`, add to the supervision tree.

## Adding a New Transport

1. Implement the `BaseTransport` protocol in `src/nexus/transport/`
2. Handle native events → convert to `InboundMessage`
3. Implement `send_text()`, `send_buttons()`, `send_typing()`
4. Wire in `runtime.py`
5. No changes to ConversationManager needed

## PR Checklist

- [ ] `uv run ruff check .` passes
- [ ] `uv run ruff format --check .` no diff
- [ ] `uv run mypy src/nexus/` passes
- [ ] `OTEL_SDK_DISABLED=true uv run pytest tests/` passes
- [ ] Type hints on all new public functions
- [ ] Tests for all new functionality
- [ ] AGENTS.md updated if layout or conventions changed
- [ ] CHANGELOG.md updated for user-visible changes

## License

By contributing, you agree that your contributions will be licensed under the Apache 2.0 License.
