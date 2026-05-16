# Codebase Audit: AGENTS.md Compliance

> Audited: 2026-05-14
> Remediated: 2026-05-16
> Scope: src/nexus/ and tests/ against AGENTS.md coding discipline + Karpathy guidelines
> Methodology: AST analysis, grep patterns, manual review

---

## Summary

| Category | Issues Found | Severity | Status |
|---|---|---|---|
| Function length (>50 lines) | 9 functions | Medium | 2 fixed (gateway), rest acceptable or deferred |
| Over-broad exception handling | 20 `except Exception:` | Medium | ✅ Fixed — 8 silent failures given debug logging |
| Non-top-level imports (tests) | 86 instances | Low | ✅ Fixed — all moved to module level |
| Non-top-level imports (extensions) | 2 instances | Low | ✅ Accepted — documented in AGENTS.md |
| Tests without assertions | 44 tests | Medium | ✅ Fixed — all now have postcondition checks |
| ConversationManager god object | 1091 lines, 40+ methods | High | ✅ Fixed — 1095→826 lines, 3 modules extracted |
| Duplicate logic across extensions | 2 near-identical param parsers | Low | ✅ Fixed — shared `nexus.utils.parse_key_value_params` |
| Gateway API handlers too long | 2 functions (100+ lines) | Medium | ✅ Fixed — 7 query helpers extracted |

---

## Issue 1: ConversationManager God Object (HIGH) — ✅ RESOLVED

**File:** `src/nexus/agents/conversation.py` — reduced from 1095 to 826 lines (−25%)

Extracted 3 modules:
1. `tool_executor.py` (152 lines) — `ToolExecutor` class: tool-use loop, governance checks, action URL capture. Dependencies injected: LLMClient, MCPManager, PolicyEngine, TrustStore, AuditSink.
2. `response_formatter.py` (75 lines) — `ResponseFormatter` class: transport routing, send_reply, send_response (with content store viewer), send_typing. Owns transport references.
3. `help.py` (122 lines) — Pure functions: `is_help_query`, `build_help_response`, `build_capabilities_section`. No class, no state, no async.

SessionManager extraction was evaluated and deferred — the session methods are tightly coupled to AgentProcess MessageBus (`self.ask`/`self.send`) and extracting them would require callback injection that adds complexity without simplification.

---

## Issue 2: Over-Broad Exception Handling (MEDIUM) — ✅ RESOLVED

**35 instances of `except Exception:` audited across core codebase.**

Most are intentionally defensive (agent resilience). 8 were silent failures that now have `logger.debug`:

- `memory.py` — FTS search failure
- `conversation.py` — memory search, health check, checkpoint save/list, rollback (5 instances)
- `mcp/manager.py` — health check ping
- `gateway.py` — WebSocket send loop

Remaining instances are correct resilience patterns with existing logging.

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

## Issue 4: Tests Without Assertions (MEDIUM) — ✅ RESOLVED

**44 test functions had no assert/pytest.raises/mock.assert_* calls** (original audit estimated 15; full AST scan found 44).

All 44 now have meaningful postcondition assertions. Examples:
- `test_clear_nonexistent()` → `assert limiter.remaining("nobody") == limiter._max`
- `test_persist_message_failure()` → `c.send.assert_called_once()`
- `test_no_client()` → `assert t._client is None`

---

## Issue 5: Non-Top-Level Imports in Tests (LOW) — ✅ RESOLVED

**86 inline imports across 14 test files** moved to module top level (original audit estimated 85).

Largest files: test_conversation.py (36), test_extensions.py (12), test_media.py (9), test_llm_client.py (8). All deduplicated against existing top-level imports.

---

## Issue 6: Extension `__version__` Imports (LOW) — ✅ RESOLVED

Accepted as-is. Documented as an accepted exception in AGENTS.md code style section.

---

## Issue 7: Duplicate Param Parsing Logic (LOW) — ✅ RESOLVED

Extracted shared `parse_key_value_params()` to `src/nexus/utils.py`. Both extensions now import from there. The work extension's `_extract_inline_params()` wraps it with title extraction.

---

## Issue 8: Gateway API Handlers (MEDIUM) — ✅ RESOLVED

Extracted 7 query helpers from `gateway.py`:
- Finance: `_query_latest_snapshot()`, `_query_holdings()`, `_query_fire_config()`, `_query_snapshot_history()`
- Work: `_query_open_actions()`, `_query_active_delegations()`, `_query_recent_meetings()`

`_handle_finance_api` reduced from 99 to 22 lines. `_handle_work_api` from 78 to 29 lines.

---

## Priority Order (original) — All resolved except #5

1. ~~**Tests without assertions**~~ ✅
2. ~~**Non-top-level imports in tests**~~ ✅
3. ~~**Gateway API handler extraction**~~ ✅
4. ~~**Over-broad exception handling audit**~~ ✅
5. **ConversationManager decomposition** — deferred (separate effort)
6. ~~**Duplicate param parser extraction**~~ ✅
7. ~~**Extension `__version__`**~~ ✅

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
