# Design: Scheduler

> Cron engine, skill triggering, state persistence, and tenant iteration.

**Status:** Draft
**Module:** `src/nexus/agents/scheduler.py`
**Type:** `AgentProcess`
**Supervisor:** root (ONE_FOR_ALL)

---

## Responsibility

SchedulerAgent owns time-based automation. It:

- Runs a tick loop (every 60 seconds)
- Evaluates cron expressions against current time
- Triggers skills via ConversationManager when schedules are due
- Persists next-run state to MemoryAgent (survives restarts)
- Iterates all eligible tenants for each scheduled task
- Discovers scheduled skills (skills with `schedule:` in frontmatter)

It does **not** own: skill execution (ConversationManager), LLM calls, or MCP tool calls. The scheduler is a trigger, not an executor.

---

## Schedule Sources

Two sources of schedules, merged at startup:

### 1. Config-defined (YAML)

```yaml
scheduler:
  timezone: "Asia/Kolkata"
  tasks:
    - name: morning_briefing
      skill: morning-briefing     # skill name to trigger
      cron: "0 7 * * *"
      tenants: admin              # "admin" | "all" | [specific tenant IDs]
    - name: health_check
      skill: service-health
      cron: "*/15 * * * *"
      tenants: admin
```

### 2. Skill-declared (SKILL.md frontmatter)

```markdown
---
name: morning-briefing
schedule: "0 7 * * *"             # ← skill declares its own schedule
---
```

Skills with a `schedule:` field are auto-registered as cron tasks at startup. Config-defined tasks take precedence on conflict (same skill, different cron).

---

## Data Model

```python
@dataclass
class ScheduleEntry:
    name: str                      # unique identifier
    skill_name: str                # skill to trigger
    cron: str                      # cron expression
    tenants: str | list[str]       # "admin" | "all" | ["tenant_id_1", ...]
    timezone: ZoneInfo             # from config
    last_run: datetime | None      # persisted to MemoryAgent
    next_run: datetime | None      # computed from cron + last_run
    source: str                    # "config" | "skill"

    def compute_next_run(self) -> None:
        base = self.last_run or datetime.now(tz=self.timezone)
        # Use naive datetime for croniter, then localize
        naive_base = base.replace(tzinfo=None)
        cron = croniter(self.cron, naive_base)
        naive_next = cron.get_next(datetime)
        self.next_run = naive_next.replace(tzinfo=self.timezone, fold=1)

    def is_due(self, now: datetime) -> bool:
        return self.next_run is not None and now >= self.next_run
```

**Timezone handling:** `croniter` operates on naive datetimes. We strip timezone before computing, then re-apply with `fold=1` to handle DST transitions correctly. (Learned from Vigil issue I3.)

---

## Tick Loop

```python
class SchedulerAgent(AgentProcess):

    async def on_start(self) -> None:
        self._schedules: list[ScheduleEntry] = []
        self._state_restored = False
        # DO NOT call self.ask() here — MessageBus not ready
        # State restoration deferred to first tick

    async def handle(self, message: Message) -> Message | None:
        action = message.payload.get("action")
        if action == "tick":
            await self._tick()
        elif action == "list":
            return self.reply({"schedules": [s.to_dict() for s in self._schedules]})
        elif action == "trigger":
            skill_name = message.payload.get("skill")
            await self._trigger_skill(skill_name, message.payload.get("tenant_id"))
        return None

    async def _tick(self) -> None:
        if not self._state_restored:
            await self._restore_state()
            self._state_restored = True

        now = datetime.now(tz=self._timezone)
        for schedule in self._schedules:
            if schedule.is_due(now):
                await self._execute_schedule(schedule, now)

    async def _execute_schedule(self, schedule: ScheduleEntry, now: datetime) -> None:
        tenants = await self._resolve_tenants(schedule.tenants)

        for tenant_id in tenants:
            await self.send("conversation_manager", {
                "action": "execute_skill",
                "skill_name": schedule.skill_name,
                "tenant_id": tenant_id,
                "triggered_by": "scheduler",
                "schedule_name": schedule.name,
            })

        schedule.last_run = now
        schedule.compute_next_run()
        await self._persist_state()
```

**Key behaviors:**
- Tick every 60 seconds (driven by a background `asyncio.Task` with `asyncio.sleep(60)`)
- State restored on first tick, not `on_start()` (MessageBus not ready)
- Each tenant gets their own skill execution (not one shared call)
- State persisted after each execution (survives restart)

---

## Tenant Resolution

```python
async def _resolve_tenants(self, tenants_spec: str | list[str]) -> list[str]:
    if tenants_spec == "admin":
        result = await self.ask("memory", {
            "action": "list_tenants", "filter_role": "admin",
        })
        return result.payload.get("tenant_ids", [])
    elif tenants_spec == "all":
        result = await self.ask("memory", {
            "action": "list_tenants",
        })
        return result.payload.get("tenant_ids", [])
    elif isinstance(tenants_spec, list):
        return tenants_spec
    return []
```

**No hardcoded `users[0]`.** Learned from Vigil issue A3.

---

## State Persistence

Next-run timestamps are persisted to MemoryAgent to prevent double-execution on restart:

```python
async def _persist_state(self) -> None:
    state = {
        entry.name: {
            "last_run": entry.last_run.isoformat() if entry.last_run else None,
            "next_run": entry.next_run.isoformat() if entry.next_run else None,
        }
        for entry in self._schedules
    }
    await self.send("memory", {
        "action": "config_set",
        "tenant_id": "__system__",
        "namespace": "scheduler",
        "key": "state",
        "value": json.dumps(state),
    })

async def _restore_state(self) -> None:
    # 1. Load schedules from config + skill frontmatter
    self._schedules = self._load_schedules_from_config()
    self._schedules.extend(self._discover_skill_schedules())

    # 2. Restore last-run state from MemoryAgent
    result = await self.ask("memory", {
        "action": "config_get",
        "tenant_id": "__system__",
        "namespace": "scheduler",
        "key": "state",
    })
    saved = json.loads(result.payload.get("value", "{}"))

    for entry in self._schedules:
        if entry.name in saved and saved[entry.name].get("last_run"):
            entry.last_run = datetime.fromisoformat(saved[entry.name]["last_run"])
        entry.compute_next_run()

    # 3. Check for missed executions (restart after scheduled time)
    now = datetime.now(tz=self._timezone)
    for entry in self._schedules:
        if entry.is_due(now):
            logger.info("Missed schedule '%s' during downtime, executing now", entry.name)
            await self._execute_schedule(entry, now)
```

---

## Manual Trigger

Skills can be triggered manually via Telegram:

```
User: "Run my morning briefing"
  → IntentClassifier detects skill request → ConversationManager
  → OR: nexus CLI: nexus skills run morning-briefing
  → OR: SchedulerAgent handle(action="trigger", skill="morning-briefing")
```

All three paths converge on ConversationManager's `_execute_skill()`.

---

## Dashboard Integration

SchedulerAgent sends status updates to DashboardServer:

```python
async def _execute_schedule(self, schedule: ScheduleEntry, now: datetime) -> None:
    # ... execute ...
    await self.send("dashboard", {
        "action": "schedule_executed",
        "schedule_name": schedule.name,
        "executed_at": now.isoformat(),
        "tenants": tenants,
    })
```

Dashboard shows: next scheduled task, last execution time, execution history.
