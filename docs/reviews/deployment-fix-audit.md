# M6.2.1 Deployment Fix Audit

> Audited: 2026-05-14
> Scope: Commit f78162d and subsequent fixes verified against upstream docs

---

## 1. AgentGateway Config

**Fix:** Simplified to passthrough `anthropic: {}`, later upgraded to v1.1.0 with `llm:` format.

**Upstream docs:** [agentgateway.dev/docs/llm/providers/anthropic](https://agentgateway.dev/docs/llm/providers/anthropic/)

**Verdict: ✅ CONFORMANT.** The `llm:` format with `name: "claude-*"` for model-name routing and `hostOverride` for Ollama exactly matches the documented patterns. Pinning to v1.1.0 instead of `:latest` (which is v0.12.0) is correct — `:latest` doesn't support the `llm:` format.

**Action:** Update docker-compose comment to explain why we pin v1.1.0.

---

## 2. Anthropic Empty Content Blocks

**Fix:** Omit `content` field from assistant messages when LLM returns only tool_calls with no text.

**Upstream docs:** [platform.claude.com/docs/en/api/openai-sdk](https://platform.claude.com/docs/en/api/openai-sdk)

The OpenAI SDK compatibility page states:
- `content` (string): "Fully supported"
- `content` (array, type "text"): "Fully supported"
- `tool_calls`: "Fully supported"

The error message was `"messages: text content blocks must be non-empty"`. This is Anthropic's native API rejecting empty text blocks when AgentGateway translates from OpenAI format to Anthropic format. In OpenAI format, `content: ""` with `tool_calls` is valid. In Anthropic's native format, content blocks must be non-empty.

**Verdict: ✅ CONFORMANT.** Omitting `content` when empty is the correct approach. This is an AgentGateway translation gap — it should drop empty content when converting to Anthropic format. Our fix works around it correctly. Not a hack.

**Action:** None. Consider filing an issue on AgentGateway repo.

---

## 3. MCP Tool Error Handling

**Fix:** `except Exception` catches tool call failures, strips ANSI codes, truncates to 2000 chars.

**Upstream docs:** [MCP SDK — CallToolResult](https://modelcontextprotocol.io/docs)

The MCP SDK's `call_tool()` returns a `CallToolResult` which has an `isError` flag. When a tool raises an exception, the MCP server framework catches it and returns `isError: true` with the error in the content. However, the Google Workspace MCP server raises `GoogleAuthenticationError` which the `fastmcp` framework catches at a higher level — the exception propagates through the MCP transport and arrives as a Python exception in our client, not as an `isError` result.

**Verdict: ⚠️ WORKAROUND.** Our `except Exception` path handles a real case — MCP server exceptions that propagate through the transport. The `isError` path in `_parse_tool_result` handles errors the server catches. Both paths are needed. The ANSI stripping is a workaround for the Google MCP server using Rich for error formatting.

**Action:** The ANSI stripping should stay. File an issue on google_workspace_mcp about ANSI codes in error responses.

---

## 4. Telegram HTML Rendering

**Fix:** Extract markdown links before `html.escape()`, convert `##` headings to `<b>`, convert `- ` lists to `• `.

**Upstream docs:** [Telegram Bot API — HTML style](https://core.telegram.org/bots/api#html-style)

Telegram supports: `<b>`, `<strong>`, `<i>`, `<em>`, `<u>`, `<ins>`, `<s>`, `<strike>`, `<del>`, `<span class="tg-spoiler">`, `<tg-spoiler>`, `<b>`, `<a href="">`, `<tg-emoji>`, `<code>`, `<pre>`, `<pre><code class="">`, `<blockquote>`.

No `<h1>`-`<h6>`, no `<ul>`, `<li>`, no `<p>`.

**Verdict: ✅ CONFORMANT.** Converting `##` to `<b>` and `-` to `•` (Unicode bullet) is the correct approach for Telegram. The link extraction before escaping prevents double-encoding of `&` in URLs. Telegram's HTML parser is strict — malformed tags cause fallback to plain text, which our `except` handler covers.

**Action:** None. Could add `<blockquote>` support for `> ` markdown quotes.

---

## 5. Google OAuth URL Passthrough

**Fix:** Extract OAuth URLs from tool results and append to response if LLM omits them.

**Upstream docs:** Google Workspace MCP server returns auth URLs as part of the error message, with explicit instructions: "LLM, please present this exact authorization URL to the user as a clickable hyperlink."

**Verdict: ⚠️ WORKAROUND.** The MCP server's intended flow is: tool returns error with URL → LLM presents URL to user. Our fix handles the case where the LLM paraphrases instead of passing through the URL. This is a model quality issue (especially with smaller models like qwen3:8b). The URL capture is a safety net, not the primary flow.

**Action:** Keep as safety net. With better models (Claude Sonnet), the LLM correctly passes through the link. The fix helps with smaller/local models.

---

## 6. Session History with Empty Content

**Fix:** `_build_messages` filters out messages with empty content. Stale sessions with empty assistant messages from previous bugs don't break subsequent conversations.

**Upstream docs:** Anthropic requires non-empty content in all messages. OpenAI format allows empty strings.

**Verdict: ✅ CONFORMANT.** Filtering empty messages from history is defensive programming, not a hack. Even without the Anthropic constraint, empty messages in conversation history serve no purpose.

**Action:** None.

---

## 7. Tool Loop Fallback

**Fix:** When LLM hits MAX_TOOL_ITERATIONS without producing text, extract last tool result as fallback response.

**Upstream docs:** No specific guidance. This is application-level logic.

**Verdict: ✅ CORRECT DESIGN.** Without this, users get empty responses when the LLM loops on tool calls (observed with qwen3:8b repeatedly calling `get_events`). The fallback ensures users always see something.

**Action:** None. Could add a system prompt instruction to limit tool call repetition.

---

## 8. Think Tag Stripping

**Fix:** Strip `<think>...</think>` tags from LLM responses for models using thinking mode (Qwen3).

**Upstream docs:** Ollama's Qwen3 models include thinking in `<think>` tags within content. This is by design — the model's chain-of-thought reasoning.

**Verdict: ✅ CONFORMANT.** Stripping think tags is the documented approach for models with thinking mode. The alternative (custom modelfile with `/no_think`) broke tool calling. Stripping in the response parser is cleaner and model-agnostic.

**Action:** None.

---

## Summary

| Fix | Verdict | Action Needed |
|---|---|---|
| AgentGateway config | ✅ Conformant | Add docker-compose comment |
| Empty content blocks | ✅ Conformant | Consider filing AgentGateway issue |
| MCP tool error handling | ⚠️ Workaround | File issue on google_workspace_mcp |
| Telegram HTML rendering | ✅ Conformant | Could add blockquote support |
| Google OAuth passthrough | ⚠️ Workaround (safety net) | Keep — helps with small models |
| Session empty content | ✅ Conformant | None |
| Tool loop fallback | ✅ Correct design | None |
| Think tag stripping | ✅ Conformant | None |

**6 of 8 fixes are conformant with upstream docs. 2 are workarounds for upstream issues (MCP ANSI codes, LLM not passing through URLs). No hacks.**
