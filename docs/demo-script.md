# Nexus Demo Script

Five scenarios demonstrating Nexus's core capabilities. Each is self-contained and demoable in 2-3 minutes.

---

## Demo 1: Crash Recovery (M1)

**What it proves:** Civitas supervision is real. Kill an agent, watch it restart.

### Script

1. Show `http://localhost:8080` — all agents running, green dots
2. Send a message on Telegram — get a response
3. Kill the conversation_manager: `docker compose exec nexus kill -9 $(pgrep -f conversation)`
4. Dashboard shows agent crashed (red dot), then restarted (green dot)
5. Send another message on Telegram — response works normally
6. Show restart count incremented in dashboard

**Key point:** "No manual intervention. The supervision tree restarted the agent automatically."

---

## Demo 2: Governance + Trust Arc (M3)

**What it proves:** Agent earns trust over time. Governance is dynamic, not static.

### Script

1. Ask Nexus to send an email: "Send an email to Sarah about the meeting"
2. Nexus shows the draft + approval buttons (trust < 0.8 for email.write)
3. Approve the email — trust score increases
4. Show trust score in dashboard
5. Approve 3-4 more emails
6. Ask to send another email — this time it sends autonomously (trust > 0.8)
7. Reject one email — trust drops back, next email requires approval again

**Key point:** "The agent earns your trust through a track record, not a config toggle."

---

## Demo 3: Finance Intelligence (M5)

**What it proves:** Extensions add domain-specific intelligence.

### Script

1. `/portfolio` — show holdings summary with P&L and allocation
2. `/holdings add FD principal=500000 rate=7.1 bank=HDFC` — add a manual holding
3. `/portfolio` again — FD appears in holdings, allocation updated
4. `/fire config monthly_expenses=100000 target_years=15` — set FIRE target
5. `/fire` — show FIRE progress bar, SIP projections
6. `/rebalance` — show current vs target allocation with delta
7. Open `http://localhost:8080/dashboard/finance` — full visual dashboard

**Key point:** "This is a pip-installable extension. The core didn't change."

---

## Demo 4: Work Intelligence (M5)

**What it proves:** Nexus manages your workload, not just answers questions.

### Script

1. `/actions add Review Sarah's PR #234 due=tomorrow priority=high` — create action
2. `/delegate add Raj Cache redesign due=Friday` — create delegation
3. `/meetings add 1:1 with Raj date=tomorrow attendees=Raj` — track meeting
4. `/next` — shows "Review Sarah's PR" as highest priority
5. `/actions` — full list with priority scores
6. `/actions block 1 Sarah's merge` — mark as blocking
7. `/next` again — score jumps higher
8. `/actions done 1` — mark complete
9. Open `http://localhost:8080/dashboard/work` — full work dashboard

**Key point:** "Every commitment is tracked. Nothing falls through the cracks."

---

## Demo 5: Multi-Transport + Persona (M4)

**What it proves:** Same assistant, different interfaces, consistent personality.

### Script

1. Message Nexus on Telegram: "What's my name?"
2. Nexus responds using the configured persona, knows your name from memory
3. Message the same Nexus on Discord: "What did I just ask you on Telegram?"
4. Nexus recalls the conversation (shared memory across transports)
5. Show `personas/default.md` — the personality definition
6. "Change your personality to be more formal" — persona rebuilds on the fly
7. Next message uses the updated persona

**Key point:** "One brain, many interfaces. The persona follows you everywhere."

---

## Demo Flow (Full, 12 min)

For a comprehensive demo, run all five scenarios in order:

1. **Crash Recovery** (2 min) — establishes reliability
2. **Governance** (3 min) — establishes trust model
3. **Finance** (3 min) — shows extension system + domain depth
4. **Work** (2 min) — shows practical daily-driver value
5. **Multi-Transport** (2 min) — shows platform breadth

Close with: "This is a self-hosted personal AI assistant. It runs on your hardware, governs its own actions, and extends to whatever domains you care about."
