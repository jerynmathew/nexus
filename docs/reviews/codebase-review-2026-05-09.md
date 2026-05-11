# Codebase Review — 2026-05-09

> Reviewer: Sisyphus (AI agent)
> Scope: Full codebase audit against AGENTS.md, security, OSS readiness
> Verdict: **12 issues found (5 high, 4 medium, 3 low)**

---

## CRITICAL / HIGH

### H1. Function-level imports violate AGENTS.md rule

**Files affected:** 6 files, 13 violations

```
src/nexus/mcp/manager.py:52-54,77-78   — mcp imports inside _create_client()
src/nexus/runtime.py:133,137,146        — media imports inside _setup_media_handler()
src/nexus/dashboard/gateway.py:149      — uvicorn inside start()
src/nexus/media/handler.py:135,141      — pdfplumber, io inside _extract_pdf_text()
src/nexus/media/stt.py:23               — faster_whisper inside _ensure_model()
```

**Rule:** "All imports at module level, unless there is no other way to escape circular dependency."

**Assessment:** Some of these are legitimate optional-dependency guards (pdfplumber, faster_whisper, uvicorn). The `mcp` imports in manager.py and the `io` import in handler.py have no such justification.

**Fix required:**
- Move `import io` to module level in handler.py (trivial)
- Move `mcp` imports to module level in manager.py (mcp is a hard dependency)
- Keep pdfplumber/faster_whisper/uvicorn as lazy imports — document each with a comment explaining why

---

### H2. Dependencies not pinned — supply chain risk

**File:** `pyproject.toml`

All 18 dependencies use `>=` (minimum version) instead of pinned versions:
```
"httpx>=0.28.0"     # allows any 0.28+, including breaking changes
"pydantic>=2.12.0"  # allows pydantic 3.x if released
```

**Risk:** A compromised or yanked upstream version gets auto-installed. The `uv.lock` mitigates this for reproducible installs, but `pip install nexus` from PyPI would resolve to latest.

**Fix required:**
- Pin to compatible ranges: `"httpx>=0.28.0,<1.0"` (upper bound)
- Or use exact pins: `"httpx==0.28.1"` (strictest)
- Recommended: compatible release (`~=`): `"httpx~=0.28.0"` (allows 0.28.x but not 0.29)
- Ensure `uv.lock` is committed (already done ✅)

---

### H3. Subprocess call without input validation

**File:** `src/nexus/media/handler.py:121`

```python
subprocess.run(
    ["ffmpeg", "-y", "-loglevel", "error", *args],
    check=True, capture_output=True, timeout=60,
)
```

The `args` list is constructed from internal paths (tempfile), not user input. However:
- `shell=False` is correctly used (implicit default) ✅
- `timeout=60` prevents hangs ✅
- But if a user sends a crafted video filename via Telegram, it goes into the temp path — **no risk** since we generate the tempfile path ourselves

**Assessment:** Low actual risk. The subprocess is sandboxed correctly. Document the decision.

---

### H4. Content viewer path traversal — partial mitigation

**File:** `src/nexus/dashboard/gateway.py:82-83`

```python
view_id = path.removeprefix("/view/").strip("/")
if not view_id or not view_id.isalnum():
```

The `isalnum()` check prevents `../` traversal ✅. But `ContentStore.get()` doesn't independently validate:

```python
def get(self, view_id: str) -> str | None:
    path = self._views_dir / f"{view_id}.html"  # No validation here
```

**Fix required:** Add validation in `ContentStore.get()` as defense-in-depth:
```python
if not view_id.isalnum() or ".." in view_id:
    return None
```

---

### H5. Broad `except Exception` in hot paths

**Files:** conversation.py:172, conversation.py:503, mcp/manager.py:127, dashboard/gateway.py:76

These catch `Exception` broadly. While they log the error, they swallow potential bugs:
- `conversation.py:172` — LLM call failure → returns error message (acceptable)
- `conversation.py:503` — Skill section failure → returns warning (acceptable)
- `mcp/manager.py:127` — MCP tool call → reconnect attempt (acceptable)
- `dashboard/gateway.py:76` — API error → returns 500 (acceptable)

**Assessment:** All are at system boundaries where resilience > strictness. Acceptable for a supervised agent architecture. Each logs the exception. **No fix required**, but consider narrowing to specific exception types where possible.

---

## MEDIUM

### M1. `import io` at function level (handler.py)

**File:** `src/nexus/media/handler.py:141`

`import io` is a stdlib module. No reason for lazy import.

**Fix:** Move to module level.

---

### M2. MCP imports at function level (manager.py)

**File:** `src/nexus/mcp/manager.py:52-54, 77-78`

`mcp` is a hard dependency in `pyproject.toml`. No need for lazy import.

**Fix:** Move `from mcp import ClientSession, StdioServerParameters` and client imports to module level.

---

### M3. `_process_media` accesses private `_vision` attribute

**File:** `src/nexus/agents/conversation.py` (in `_process_media`)

```python
if frames and self._media_handler._vision:
```

Accessing `_vision` (private attribute) of MediaHandler from outside the class. Violates encapsulation.

**Fix:** Add `has_vision` property to MediaHandler, or pass frames to a public method.

---

### M4. No rate limiting on dashboard API

**File:** `src/nexus/dashboard/gateway.py`

The dashboard API has no authentication or rate limiting. Anyone on the network can query `/api/*` and `/view/*`.

**Risk:** Information disclosure (agent names, activity, trust scores). Not critical on a homelab LAN but matters if exposed to the internet.

**Fix:** Add optional basic auth or token auth for the dashboard. Document as a known limitation for now.

---

## LOW

### L1. `assert isinstance(conv, ConversationManager)` in runtime

**File:** `src/nexus/runtime.py:220`

`assert` is stripped with `python -O`. AGENTS.md anti-pattern #9: "assert for runtime validation".

**Fix:** Replace with `if not isinstance(conv, ConversationManager): raise TypeError(...)`

---

### L2. No `__all__` in any `__init__.py`

All package `__init__.py` files are either empty or have a single docstring. No explicit `__all__` exports.

**Risk:** Star imports pull in everything. Not a security issue but a public API clarity issue for OSS.

**Fix:** Add `__all__` to at least the top-level `src/nexus/__init__.py`.

---

### L3. Audit log — argument values not fully redacted

**File:** `src/nexus/governance/audit.py`

`summarize_arguments()` shows key names but not values. However, the full `arguments` dict is not logged. This is correct ✅.

But the `detail` field in AuditEntry can contain trust scores and other metadata:
```python
detail=f"trust={trust_score:.2f}",
```

**Assessment:** No sensitive data leaks. Trust scores are not secrets. **No fix required.**

---

## GOOD PRACTICES CONFIRMED

| Practice | Status |
|---|---|
| No `eval()` or `exec()` | ✅ Clean |
| No `pickle` | ✅ Clean |
| No hardcoded secrets | ✅ Clean |
| No `os.environ[]` direct access (uses config) | ✅ Clean |
| No SQL injection (all parameterized queries) | ✅ Clean |
| No `shell=True` in subprocess | ✅ Clean |
| No test files accessing real APIs | ✅ Clean |
| No sensitive data in test files | ✅ Clean |
| `uv.lock` tracked in git | ✅ |
| Dockerfile runs as non-root | ✅ |
| `.env` in `.gitignore` | ✅ |
| `gitleaks` in pre-commit | ✅ |
| `config.yaml` in `.gitignore` | ✅ |
| Content viewer validates view_id (isalnum) | ✅ |
| Audit log redacts argument values | ✅ |
| OTEL disabled in production by default | ✅ |

---

## DEPENDENCY AUDIT

| Dependency | Risk | Notes |
|---|---|---|
| `civitas` | Low | First-party, same org |
| `python-telegram-bot` | Low | 25K+ stars, well-maintained |
| `httpx` | Low | Major project, Encode team |
| `pydantic` | Low | Industry standard |
| `typer` | Low | Tiangolo (FastAPI author) |
| `rich` | Low | Will McGugan, widely used |
| `croniter` | Low | Mature, small surface |
| `aiosqlite` | Low | Wrapper over stdlib sqlite3 |
| `mcp` | Medium | Anthropic SDK, newer project |
| `faster-whisper` | Medium | Optional, pulls in onnxruntime (large) |
| `pdfplumber` | Low | Optional, well-maintained |

No known CVEs in current versions. No typosquatting risk (all well-known packages).

---

## RECOMMENDATIONS (priority order)

1. **Pin dependency upper bounds** in pyproject.toml (H2)
2. **Move `import io` and `mcp` imports to module level** (M1, M2)
3. **Add path validation in ContentStore.get()** (H4)
4. **Replace `assert isinstance` with explicit check** (L1)
5. **Add `has_vision` property to MediaHandler** (M3)
6. **Document lazy imports with why-comments** for pdfplumber/faster_whisper/uvicorn (H1)
7. **Add `__all__` to top-level __init__.py** (L2)
8. **Consider dashboard auth** for non-LAN deployments (M4)
