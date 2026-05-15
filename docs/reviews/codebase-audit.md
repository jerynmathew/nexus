# Codebase Audit: AGENTS.md Compliance

> Audited: 2026-05-14
> Scope: src/nexus/ and tests/ against AGENTS.md coding discipline + Karpathy guidelines
> Methodology: AST analysis, grep patterns, manual review

---

## Summary

| Category | Issues Found | Severity |
|---|---|---|
| Function length (>50 lines) | 9 functions | Medium |
| Over-broad exception handling | 20 `except Exception:` | Medium |
| Non-top-level imports (tests) | 85 instances | Low |
| Non-top-level imports (extensions) | 2 instances | Low |
| Tests without assertions | 15 tests | Medium |
| ConversationManager god object | 1091 lines, 40+ methods | High |
| Duplicate logic across extensions | 2 near-identical param parsers | Low |
| Gateway API handlers too long | 2 functions (100+ lines) | Medium |

---

## Issue 1: ConversationManager God Object (HIGH)

**File:** `src/nexus/agents/conversation.py` — 1091 lines, 40+ methods

**Karpathy #2 violation:** Simplicity first. One class doing routing, LLM calls, tool execution, session management, transport management, help commands, skill execution, governance, media processing, and status reporting.

**Plan:**
1. Extract `ToolExecutor` — `_tool_use_loop`, `_execute_tool_with_governance`, `_extract_action_urls` → separate module
2. Extract `SessionManager` — `_get_or_create_session`, `_checkpoint_session`, `_handle_checkpoint`, `_handle_rollback` → separate module
3. Extract `ResponseFormatter` — `_send_response_with_viewer`, `_markdown_to_html` logic → separate module
4. Keep ConversationManager as thin orchestrator: receive message → classify → delegate → respond

**Effort:** Medium. No behavioral change, pure structural refactor.
**Verification:** All existing tests pass unchanged.

---

## Issue 2: Over-Broad Exception Handling (MEDIUM)

**20 instances of `except Exception:` across core codebase.**

Most are intentionally defensive (agent resilience — don't crash on one failure). But some silently swallow errors that should be logged or narrowed:

**Plan:**
1. Audit each instance. Categorize as:
   - **Correct** — agent resilience pattern (supervisor restart is worse than swallowing)
   - **Too broad** — should catch specific exceptions (httpx.HTTPError, json.JSONDecodeError, etc.)
   - **Missing logging** — at least `logger.debug` for visibility
2. Fix the "too broad" and "missing logging" cases

**Key files:**
- `conversation.py` — 12 instances (most are correct resilience pattern)
- `mcp/manager.py` — 2 instances (should be more specific)
- `scheduler.py` — 2 instances (correct — state loading resilience)

**Effort:** Low. One-by-one review.
**Verification:** Tests pass. No new exceptions bubble up.

---

## Issue 3: Long Functions (MEDIUM)

**9 functions exceed the 50-line limit set in pyproject.toml.**

| File | Function | Lines | Action |
|---|---|---|---|
| `conversation.py` | `_tool_use_loop` | 79 | Extract URL capture and fallback to helpers |
| `conversation.py` | `_handle_inbound` | 63 | Extract rate limit check, help check to pre-processors |
| `conversation.py` | `_handle_rollback` | 55 | Acceptable — mostly DB operations |
| `conversation.py` | `_handle_transport_callback` | 51 | Acceptable — approval flow |
| `gateway.py` | `_handle_finance_api` | 100 | Extract DB queries to helper functions |
| `gateway.py` | `_handle_work_api` | 78 | Extract DB queries to helper functions |
| `cli.py` | `setup()` | 58 | CLI wizard — acceptable for interactive flow |
| `discord.py` | `start()` | 70 | Event handler registration — acceptable |
| `intent.py` | `classify()` | 60 | Regex classifier — mostly pattern data |

**Plan:** Focus on the gateway API handlers and conversation.py. The rest are acceptable.
**Effort:** Low-medium.

---

## Issue 4: Tests Without Assertions (MEDIUM)

**15 test functions have no assert statements.** These test "doesn't crash" rather than "produces correct output."

Examples:
- `test_clear_nonexistent()` — calls `limiter.reset("nobody")`, no assertion
- `test_no_handler()` — calls `await t.stop()`, no assertion
- `test_no_op()` — calls `await t.send_typing()`, no assertion
- `test_on_unload()` — calls unload, no assertion

**Plan:** Add explicit assertions to each. Even for "doesn't crash" tests, assert the post-condition:
```python
# Before
def test_clear_nonexistent(self):
    limiter.reset("nobody")

# After
def test_clear_nonexistent(self):
    limiter.reset("nobody")
    assert limiter.remaining("nobody") == limiter._max
```

**Effort:** Low. 15 one-line additions.

---

## Issue 5: Non-Top-Level Imports in Tests (LOW)

**85 inline imports across test files.** AGENTS.md says "Imports: top-level only."

Most are `from unittest.mock import patch` or `import pytest` inside test methods. Some are pre-existing from before the AGENTS.md enforcement pass.

**Plan:** Move all to top-level. Batch operation with `ruff` auto-fix where possible.
**Effort:** Low. Mechanical.

---

## Issue 6: Extension `__version__` Imports (LOW)

Both extensions have `from nexus_finance import __version__` inside the `version` property method. This is a pre-existing pattern to avoid circular imports.

**Plan:** Accept as-is. The circular import risk is real. Document as an accepted exception in AGENTS.md.
**Effort:** None.

---

## Issue 7: Duplicate Param Parsing Logic (LOW)

`_parse_key_value_params()` in nexus-finance and `_extract_inline_params()` in nexus-work are nearly identical — both parse `key=value` tokens from text.

**Plan:** Extract to a shared utility in nexus core (`nexus.utils.parse_key_value_params`). Both extensions import from there.
**Effort:** Low. Move + update imports.

---

## Issue 8: Gateway API Handlers (MEDIUM)

`_handle_finance_api` (100 lines) and `_handle_work_api` (78 lines) in `gateway.py` are long because they construct multiple DB queries inline.

**Plan:** Extract each query into a named helper:
- `_query_latest_snapshot()`, `_query_holdings()`, `_query_fire_config()`, `_query_snapshot_history()`
- `_query_open_actions()`, `_query_active_delegations()`, `_query_recent_meetings()`

**Effort:** Low. Pure extraction, no logic change.

---

## Priority Order

1. **Tests without assertions** — quick wins, improves test quality immediately
2. **Non-top-level imports in tests** — mechanical, removes AGENTS.md violation
3. **Gateway API handler extraction** — reduces function length, easy refactor
4. **Over-broad exception handling audit** — one-by-one review
5. **ConversationManager decomposition** — biggest impact, highest effort
6. **Duplicate param parser extraction** — minor cleanup
7. **Extension `__version__`** — accept as exception, document

---

## Not Issues

The following were checked and found to be conformant:

- **No empty stubs** — all functions have implementations
- **No TODO/FIXME/HACK markers** — clean codebase
- **No bare `except:` blocks** — all have `Exception` or specific types
- **Magic numbers** — all are at module level as named constants with clear context
- **Type hints** — present on all public functions (mypy strict passes)
- **Import sorting** — ruff enforces
- **Line length** — ruff enforces 100 char limit
