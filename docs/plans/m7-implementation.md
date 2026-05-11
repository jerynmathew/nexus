# M7 Implementation Plan — Presence: "It lives where you are"

> Version: 1.0
> Created: 2026-05-11
> Status: Designed (not scheduled)
> Depends on: M6 complete (production-ready platform)

---

## Vision

Nexus graduates from "text in a chat window" to a present, visual, voice-capable assistant. You see Dross, hear Dross, talk to Dross — across browser, phone, and homelab.

---

## Components

### M7.1 — Progressive Web App (PWA)

A full chat interface in the browser, replacing Telegram as the primary interaction surface for users who prefer web.

**What it does:**
- Real-time chat via WebSocket
- Message history with search
- Media rendering (images, charts, documents)
- Typing indicators, read receipts
- Dashboard integration (conversation + agent health in one UI)
- Push notifications via service worker
- Installable on mobile (PWA)
- Works offline for cached data

**Architecture:**
- Backend: extends existing HTTPGateway on :8080
- WebSocket endpoint: `/ws` for real-time messaging
- REST: `/api/messages` for history
- Static: `/chat` serves the PWA
- Transport: `WebTransport` implementing BaseTransport

**Tech stack options (decide when building):**

| Option | Bundle | Build step | Complexity | DX |
|---|---|---|---|---|
| Vanilla JS | 0KB | None | High for chat UI | Low |
| Preact | ~3KB | Optional | Medium | Good |
| Svelte | ~5KB | Yes (simple) | Low | Best |
| React | ~40KB | Yes | Low | Good |

Recommendation: Preact or Svelte. Vanilla JS worked for the dashboard (static content) but a chat UI with WebSocket, message list, input, media rendering, and notifications is too complex without components.

### M7.2 — Mobile App

A companion app for Android (and optionally iOS).

**What it does:**
- Chat interface mirroring the PWA
- Push notifications (Firebase Cloud Messaging)
- Voice input/output (STT/TTS on device or via Nexus backend)
- Device pairing: QR code or manual URL + token
- Background service for persistent WebSocket connection

**Tech stack options (decide when building):**

| Option | Platforms | Codebase | Push | Effort |
|---|---|---|---|---|
| Capacitor (PWA wrapper) | Android + iOS | Same as PWA | Yes (via plugin) | Low |
| Flutter | Android + iOS | Dart | Yes (firebase_messaging) | Medium |
| Kotlin native | Android only | Kotlin | Yes (FCM) | High |
| React Native | Android + iOS | JS/TS | Yes | Medium |

Recommendation: Capacitor — wraps the PWA in a native shell with push notifications and device APIs. Single codebase. If PWA is good, this is essentially free.

### M7.3 — Animated Avatar + Voice-First ("Dross Mode")

The assistant has a visual presence — not just text, but a character that reacts.

**What it does:**
- Animated persona with states: idle, listening, thinking, speaking
- Avatar style tied to SOUL.md (different personas = different avatars)
- Voice input: push-to-talk or wake word ("Hey Dross")
- Voice output: TTS with voice cloning (when GPU available)
- Rendered in PWA and optionally in mobile app

**Avatar rendering options (decide when building):**

| Option | Weight | Expressiveness | Effort | Works offline |
|---|---|---|---|---|
| CSS + SVG | ~0KB | Low (state transitions) | Low | Yes |
| Lottie | ~50KB | High (After Effects animations) | Medium (needs assets) | Yes |
| Canvas 2D | ~5KB | Medium (programmatic) | Medium | Yes |
| Three.js (3D) | ~150KB | Highest | High | Yes |
| Video/GIF loop | ~1MB | Medium | Low (pre-rendered) | Yes |

Recommendation: start with CSS + SVG for v1 (state-based transitions, persona-colored). Upgrade to Lottie or Canvas for expressiveness in v2.

**Voice interaction options:**

| Mode | How | Privacy | Battery | UX |
|---|---|---|---|---|
| Push-to-talk | Button held → STT → process → TTS | Good (explicit) | Good | Requires interaction |
| Wake word | "Hey Dross" triggers listening | Lower (always listening) | Higher | Hands-free |
| Always listening | Continuous STT | Lowest | Highest | Most natural |

Recommendation: push-to-talk for v1 (privacy-first, simplest). Wake word as opt-in v2.

---

## Backend Changes

### WebSocket Transport

```python
class WebTransport:
    """WebSocket transport for PWA/mobile chat."""

    async def start(self) -> None:
        # Registers WebSocket handler on HTTPGateway

    async def send_text(self, channel_id: str, text: str) -> None:
        # Send via WebSocket connection

    async def send_typing(self, channel_id: str) -> None:
        # Send typing indicator via WebSocket
```

### API Endpoints

| Endpoint | Method | Purpose |
|---|---|---|
| `/ws` | WebSocket | Real-time bidirectional messaging |
| `/api/messages` | GET | Message history for a session |
| `/api/sessions` | GET | List active/recent sessions |
| `/chat` | GET | Serve PWA static files |
| `/chat/manifest.json` | GET | PWA manifest |
| `/chat/sw.js` | GET | Service worker for push + offline |

### Push Notifications

For PWA: Web Push API (VAPID keys).
For mobile: Firebase Cloud Messaging (via Capacitor plugin).

Nexus sends push when:
- Heartbeat has something actionable
- Morning briefing arrives
- Approval request waiting
- Delegated task is stale (nexus-work)

---

## Implementation Phases

### Phase 1: WebSocket Transport + Basic Chat UI
- WebSocket endpoint on HTTPGateway
- `WebTransport` implementing BaseTransport
- Minimal chat HTML (messages, input, send button)
- Message history via REST
- **Delivers: browser-based chat works**

### Phase 2: PWA Features
- Service worker for offline caching
- Push notifications
- Installable (manifest.json)
- Media rendering (images, voice messages, documents)
- **Delivers: installable web app with push**

### Phase 3: Avatar v1
- CSS + SVG avatar with idle/thinking/speaking states
- Persona-driven colors and style
- Rendered alongside chat messages
- **Delivers: Dross has a face**

### Phase 4: Voice Interaction
- Push-to-talk button in chat UI
- Browser MediaRecorder → STT (Whisper via Nexus backend)
- TTS response playback (when TTS backend available)
- **Delivers: talk to Dross**

### Phase 5: Mobile App
- Capacitor wrapper around PWA
- Push notifications via FCM
- Device pairing flow
- **Delivers: Nexus on your phone**

### Phase 6: Avatar v2 + Wake Word (stretch)
- Lottie or Canvas animations for richer expression
- Wake word detection (browser or on-device)
- Continuous conversation mode
- **Delivers: "Hey Dross" and full Dross mode**

---

## Open Questions

1. **PWA vs native**: Is the PWA good enough for mobile, or does native add meaningful value?
2. **Avatar assets**: Who creates the avatar designs? Each persona needs its own visual identity.
3. **Wake word**: Browser wake word detection is limited. On-device (mobile) is better. Worth the effort?
4. **Multi-device**: Can you talk to Dross on your phone while the dashboard shows on your desk? Session routing?
5. **Voice conversation mode**: Continuous back-and-forth voice (like a phone call). Significant latency challenge.
6. **Accessibility**: Screen reader support, keyboard navigation, reduced motion preferences.
