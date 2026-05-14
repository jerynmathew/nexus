# Design: Hierarchical Model Routing

> Status: Approved — ready for implementation
> Priority: High — enables multi-model flexibility
> Depends on: M2.3 (LLM Gateway), M5.0 (Extension system)

---

## Problem

Currently Nexus has two hardcoded model tiers:

```python
_CHEAP_TASKS = frozenset({"CLASSIFY", "SUMMARIZE", "FORMAT", "SKILL_EXEC"})
```

Everything is either `llm.model` (default) or `llm.cheap_model`. No way to:
- Use different models per extension (e.g., GPT-4o for finance research, local Llama for action extraction)
- Use different models per skill (e.g., coding model for code review skill)
- Override models at runtime (e.g., switch to cheaper model during high-load periods)
- Mix paid and OSS models by use case

## Design: Default at Top, Override Locally

Model resolution follows a hierarchy — most specific wins:

```
skill.model → extension config model → cheap_model (if cheap task) → llm.model
```

### Config Structure

```yaml
# Top-level defaults
llm:
  model: "claude-sonnet-4-20250514"          # default for everything
  cheap_model: "claude-haiku-4-5-20251001"   # default for cheap tasks (classify, summarize)

# Extension-level overrides (in their own config section)
extensions:
  nexus-finance:
    model: "gpt-4o"                          # all nexus-finance LLM calls use gpt-4o
  nexus-work:
    model: "claude-sonnet-4-20250514"        # explicit — same as default, but locked
```

### Skill-Level Override (in SKILL.md frontmatter)

```yaml
---
name: mf-research
description: Research and compare mutual funds
model: "gpt-4o"                              # this specific skill uses gpt-4o
execution: sequential
tool_groups: [finance, search]
---
```

### Resolution Order

```
1. Skill model          — skill.model field in SKILL.md frontmatter
2. Extension model      — extensions.<name>.model in config.yaml
3. Task-type model      — cheap_model if task in CHEAP_TASKS
4. Default model        — llm.model
```

First non-None value wins.

### Runtime Override

A mutable override table on `LLMClient` for dynamic changes:

```python
# Set at runtime via command or signal
llm_client.set_model_override("nexus-finance", "gpt-4o-mini")
llm_client.set_model_override("work-action-extract", "llama3:8b")

# Clear override (falls back to config)
llm_client.clear_model_override("nexus-finance")
```

Stored in-memory on `LLMClient._model_overrides: dict[str, str]`. Not persisted — resets on restart. Frozen config unchanged.

---

## Implementation Plan

### 1. Skill Parser — Add `model` field

```python
# src/nexus/skills/parser.py
@dataclass
class Skill:
    name: str
    model: str | None = None          # NEW — optional model override
    description: str = ""
    execution: str = "sequential"
    # ... existing fields
```

Parse from SKILL.md frontmatter: `model = meta.get("model")`.

### 2. LLMClient — Replace `model_for_task()` with `resolve_model()`

```python
# src/nexus/llm/client.py
class LLMClient:
    def __init__(self, ...):
        self._model_overrides: dict[str, str] = {}    # runtime overrides

    def resolve_model(
        self,
        task: str = "",
        skill_model: str | None = None,
        extension_model: str | None = None,
    ) -> str:
        # 1. Skill-level (most specific)
        if skill_model:
            return skill_model

        # 2. Runtime override by scope name (skill name or extension name)
        # Caller passes the scope, we check overrides
        # (handled by caller passing the right skill_model/extension_model)

        # 3. Extension-level
        if extension_model:
            return extension_model

        # 4. Task-type
        if task.upper() in _CHEAP_TASKS:
            return self._cheap_model

        # 5. Default
        return self._default_model

    def set_model_override(self, scope: str, model: str) -> None:
        self._model_overrides[scope] = model

    def clear_model_override(self, scope: str) -> None:
        self._model_overrides.pop(scope, None)

    # Keep model_for_task() for backward compat, delegate to resolve_model()
    def model_for_task(self, task: str) -> str:
        return self.resolve_model(task=task)
```

### 3. NexusContext — Per-extension model awareness

**Problem identified:** NexusContext is a singleton shared across all extensions. It doesn't know which extension is calling.

**Solution:** Store the extension name on NexusContext at load time, and create a lightweight per-extension wrapper.

```python
# src/nexus/extensions.py
class NexusContext:
    def __init__(self, ..., extension_name: str = ""):
        self._extension_name = extension_name

    def resolve_model(self, task: str = "", skill_model: str | None = None) -> str:
        ext_model = self._extensions_config.get(self._extension_name, {}).get("model")
        override = self._llm._model_overrides.get(self._extension_name) if self._llm else None
        return self._llm.resolve_model(
            task=task,
            skill_model=skill_model,
            extension_model=override or ext_model,
        )
```

**Per-extension wrapper:** During extension loading, create a scoped NexusContext per extension:

```python
# src/nexus/extensions.py — ExtensionLoader._load_pip_extensions()
ext = ext_cls()
scoped_ctx = nexus_ctx.scoped(extension_name=ext.name)
await ext.on_load(scoped_ctx)
```

Where `scoped()` returns a new NexusContext that shares the same runtime/llm/mcp but carries the extension name. This is a shallow copy, not a deep one — no extra resource cost.

### 4. ConversationManager — Pass skill model through

```python
# src/nexus/agents/conversation.py — _execute_skill()
async def _execute_skill(self, skill, tenant, channel_id):
    model = self._llm.resolve_model(
        task="SKILL_EXEC",
        skill_model=skill.model,
    )
    # ... pass to parallel/sequential execution
```

### 5. Extension LLM calls — Use ctx.resolve_model()

```python
# Extension code (e.g., nexus-finance commands.py)
model = nexus_context.resolve_model(task="RESEARCH")
response = await nexus_context.llm.chat(messages=[...], model=model)
```

### 6. Conversation path — No change

The main conversation loop (`_llm_respond` → `_tool_use_loop`) continues to use `self._default_model`. Conversations don't have extension scope — the user talks to Nexus, not to an extension. The intent classifier routes to tools, but model selection stays at the default.

This is intentional: the conversation model is the "voice" of Nexus. Extensions get their own model overrides for their background/command work, but the conversational personality stays consistent.

---

## Call Sites to Update

| File | Line | Current | After |
|---|---|---|---|
| `conversation.py` | 535 | `model_for_task("SKILL_EXEC")` | `resolve_model(task="SKILL_EXEC", skill_model=skill.model)` |
| `compressor.py` | 128 | `model_for_task("SUMMARIZE")` | `resolve_model(task="SUMMARIZE")` (no change in behavior) |
| `signals.py` | 85 | `ctx.llm.chat(...)` (no model) | `ctx.llm.chat(..., model=ctx.resolve_model())` |
| `commands.py` (finance) | 383 | `ctx.llm.chat(...)` (no model) | `ctx.llm.chat(..., model=ctx.resolve_model())` |
| `vision.py` | 41 | `self._llm.chat(...)` (no model) | No change (vision always uses default — it's a core capability) |

---

## What This Does NOT Change

- **Conversation model**: the main chat always uses `llm.model`. No extension override for conversations.
- **AgentGateway**: no changes. It routes based on model name in the request — we just send different model names.
- **Frozen config**: `NexusConfig` stays frozen. Runtime overrides live on `LLMClient._model_overrides` (mutable dict, resets on restart).
- **Cost tracking**: AgentGateway already tracks cost per model via OTEL. Different models = different cost lines automatically.

---

## Config Example

```yaml
llm:
  base_url: "http://localhost:4000"
  api_key: "${ANTHROPIC_API_KEY}"
  model: "claude-sonnet-4-20250514"
  cheap_model: "claude-haiku-4-5-20251001"

extensions:
  nexus-finance:
    model: "gpt-4o"                    # finance extension uses GPT-4o for all its LLM calls
    kite_api_key: "${KITE_API_KEY}"
  nexus-work:
    # no model override — uses llm.model default
```

```yaml
# SKILL.md frontmatter
---
name: mf-research
model: "gpt-4o"                        # this skill overrides even the extension model
---
```

---

## Testing

1. `resolve_model()` with all combinations: skill only, extension only, task only, all three, none
2. `set_model_override` / `clear_model_override` runtime mutation
3. Skill parser extracts `model` field from frontmatter
4. Scoped NexusContext carries extension name correctly
5. `model_for_task()` backward compatibility (delegates to `resolve_model`)
