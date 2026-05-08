# Design: Persona System

> SOUL.md, USER.md, prompt assembly, and the conversational persona builder.

**Status:** Draft
**Module:** `src/nexus/persona/`
**First implementation:** M1.4

---

## Concept

Two identity files per tenant interaction:

| File | Defines | Scope | Answers |
|---|---|---|---|
| **SOUL.md** | The agent's personality | Shared (per persona, multiple tenants can use same one) | "How should I talk?" |
| **USER.md** | The user's context | Per-tenant | "What do I know about this person?" |

The persona (SOUL.md) is the agent's voice. The user context (USER.md) is what the agent knows about you. Both are injected into every LLM system prompt, but they're separate concerns — changing the persona doesn't lose user facts, and user facts don't alter personality.

---

## Ownership Model

Two distinct scopes:

| File | Belongs to | Scope | Storage | Version-controlled? |
|---|---|---|---|---|
| **SOUL.md** | A persona (shared) | Any tenant can select it | `~/.nexus/personas/{name}.md` (Docker volume) | Repo ships defaults; runtime copies are user-owned |
| **USER.md** | A tenant (private) | One tenant only | `~/.nexus/users/{tenant_id}/USER.md` (Docker volume) + SQLite backup | No — runtime data |

**SOUL.md is per-persona, not per-tenant.** A persona named "dross" lives at `~/.nexus/personas/dross.md`. Multiple tenants can select the same persona. Changing the persona file changes the personality for all tenants using it.

**USER.md is per-tenant.** Each tenant has their own file with their facts and preferences. Completely isolated — tenant A's USER.md is invisible to tenant B.

**Neither is git-tracked at runtime.** The repo ships `personas/default.md` as a version-controlled starting point. At first boot, this is copied to `~/.nexus/personas/default.md`. After that, all persona and user files live on the Docker volume — user-owned, backed up via SQLite and optional `nexus export`.

## SOUL.md Format

Plain markdown. No YAML frontmatter required (but supported for metadata).

```markdown
# Dross

You are Dross, a personal AI assistant with strong opinions and dry wit.

## Personality

- Direct and concise — never hedge, never pad
- Witty but not sarcastic — humor is a tool, not a weapon
- Opinionated — when asked for a recommendation, give one and say why
- Admit uncertainty immediately — "I don't know" is always acceptable

## Communication Style

- Match the user's energy: brief question → brief answer, detailed question → detailed answer
- Use plain language — no corporate speak, no "I'd be happy to"
- When delivering bad news, lead with it — don't bury it
- Numbers and data over adjectives

## Values

- Reliability over speed — correct and slightly late beats fast and wrong
- Privacy is non-negotiable — never volunteer one user's info to another
- Transparency — say what you did and why

## Constraints

- Never send email, accept invite, or delete anything without approval
- Prefer reversible actions: archive over delete, draft over send
- If uncertain about user intent, ask — don't guess
```

### Storage & Discovery

```
# Repo (version-controlled, shipping defaults):
personas/
  default.md              ← copied to runtime on first boot

# Runtime (Docker volume, user-owned):
~/.nexus/personas/
  default.md              ← copied from repo on first boot
  dross.md                ← user-created via CLI or manually
  friday.md               ← user-created
```

### Per-Tenant Selection

Stored in `user_config` table:

```
(tenant_id, "persona", "persona_name", "dross")
```

`TenantContext.persona_name` → loads `~/.nexus/personas/dross.md`.

If file not found → falls back to `default.md` with a warning log.

### Runtime Onboarding

When a new tenant is onboarded (first message from an unknown user):

1. Transport resolves their user ID → no tenant found in DB
2. **If their ID is in `seed.users` config** → auto-create tenant with configured persona name
3. **If admin has enabled open registration** → create tenant with `default` persona
4. **Otherwise** → reject ("you're not authorized")
5. USER.md starts empty — populated over time from conversations (Dream extraction)
6. Tenant can select a different persona later ("use Friday for me") → updates `user_config`
7. Tenant can create a new persona via `nexus setup-persona` or conversational builder

---

## USER.md Format

Per-tenant markdown file. Not the agent's personality — the user's facts and preferences.

```markdown
# Jeryn

## Facts

- Vegetarian
- Based in Bangalore, IST timezone
- Partner: [name]
- Boss: Sarah Chen (sarah.chen@company.com)

## Preferences

- Morning person — prefers meetings before noon
- Likes concise emails — bullet points over paragraphs
- Prefers Hindi greetings in the morning

## Contacts

- Sarah Chen: sarah.chen@company.com (boss, work profile)
- [Partner name]: [email] (personal profile)
```

### Storage

```
~/.nexus/users/{tenant_id}/USER.md     ← Docker volume, per-tenant
```

Also backed up in `memories` table as structured key-value pairs (extracted by Dream consolidation). The markdown file is the human-readable authoritative version. The DB entries enable FTS5 search.

**Not git-tracked.** USER.md contains personal data (preferences, contacts, habits). It lives on the Docker volume and is backed up to SQLite. For migration, `nexus export` includes all user data.

### Auto-Population

USER.md starts empty when a tenant is first created. Gets populated from:
1. **Explicit statements:** "I'm vegetarian" → user_stated, confidence 1.0
2. **Dream extraction:** session summary analysis → inferred, confidence 0.5
3. **Manual editing:** user edits the file directly
4. **Persona builder:** `nexus setup-persona` can also populate initial user preferences

---

## Prompt Assembly

```python
class PersonaLoader:
    """Loads SOUL.md and USER.md, assembles the identity portion of system prompt."""

    def __init__(self, personas_dir: Path, users_dir: Path) -> None:
        self._personas_dir = personas_dir
        self._users_dir = users_dir
        self._cache: dict[str, str] = {}  # persona_name → content

    async def load_system_identity(self, tenant: TenantContext) -> str:
        parts = []

        # 1. SOUL.md
        soul = self._load_persona(tenant.persona_name)
        parts.append(soul)

        # 2. USER.md
        user_md = self._load_user_context(tenant.tenant_id)
        if user_md:
            parts.append(f"# About {tenant.name}\n\n{user_md}")

        # 3. Runtime context
        parts.append(self._build_runtime_context(tenant))

        return "\n\n---\n\n".join(parts)

    def _load_persona(self, name: str) -> str:
        if name in self._cache:
            return self._cache[name]

        path = self._personas_dir / f"{name}.md"
        if not path.exists():
            logger.warning("Persona '%s' not found, using default", name)
            path = self._personas_dir / "default.md"

        content = path.read_text()
        self._cache[name] = content
        return content

    def _load_user_context(self, tenant_id: str) -> str | None:
        path = self._users_dir / tenant_id / "USER.md"
        if path.exists():
            return path.read_text()
        return None

    def _build_runtime_context(self, tenant: TenantContext) -> str:
        now = datetime.now(tz=ZoneInfo(tenant.timezone))
        return (
            f"Current time: {now.strftime('%A, %B %d, %Y %I:%M %p %Z')}\n"
            f"User: {tenant.name} (role: {tenant.role})\n"
            f"Timezone: {tenant.timezone}"
        )
```

### Token Budget

System identity (SOUL.md + USER.md + runtime) targets **~1K tokens**. Persona files should be concise — personality in 200-400 words, not multi-page essays. The rest of the system prompt budget (~3K tokens) is for memories, skills, and session history.

---

## Persona Builder CLI

Interactive CLI for creating new personas:

```bash
nexus setup-persona
```

### Flow

```
$ nexus setup-persona

Welcome! Let's create a persona for your assistant.

What should your assistant be called? > Dross

Describe Dross's personality in a few words
(e.g., "witty, direct, helpful"): > dry wit, opinionated, concise

How formal should Dross be?
  [1] Very casual (friend)
  [2] Casual-professional
  [3] Professional
  [4] Very formal
> 2

Any specific quirks or rules?
(leave blank to skip): > Always gives a recommendation when asked.
Never says "I'd be happy to".

Generating persona...

✔ Created: ~/.nexus/personas/dross.md

Preview:
─────────────────────────────
# Dross
You are Dross, a personal AI assistant with dry wit...
─────────────────────────────

Use this persona? [Y/n] > y
✔ Set as your default persona.
```

### Conversational Rebuild (via Telegram)

Users can also modify their persona through conversation:

```
User: "Change your personality to be more formal"
Nexus: "I'll update my persona. Here's what I'd change:
        - Communication style: more structured language, fewer contractions
        - Remove casual humor
        Should I apply this? [Apply] [Preview Full] [Cancel]"
User: [Apply]
Nexus: "Updated. My persona file has been modified. 
        This change is logged in your audit trail."
```

**Governance:** Persona changes are logged in the audit trail with before/after diff. This enables Presidium to detect personality drift.

---

## Alternatives Considered

1. **Persona as config field** (Vigil M1.8 approach) — Rejected. A single `personality: "helpful, concise"` string is too limited. SOUL.md allows rich, structured personality definition with values, constraints, and quirks.

2. **Persona as database rows** — Rejected. Markdown files are human-readable, git-trackable, and editable with any text editor. DB rows are opaque and require tooling to modify.

3. **Single identity file (combined SOUL+USER)** — Rejected. Persona and user context have different lifecycles. You might share a persona across users but never share user facts. Separation enables persona reuse.

4. **LLM-generated persona from scratch** — Considered for the builder, but the CLI uses structured prompts with user input, not open-ended generation. This avoids the "AI wrote my AI's personality" recursion and gives users direct control.
