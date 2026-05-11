from __future__ import annotations

import asyncio
import logging
import signal
from pathlib import Path
from typing import Any

from civitas.process import AgentProcess
from civitas.runtime import Runtime
from civitas.supervisor import Supervisor

from nexus.agents.conversation import ConversationManager
from nexus.agents.memory import MemoryAgent
from nexus.agents.scheduler import SchedulerAgent
from nexus.config import NexusConfig
from nexus.dashboard.gateway import DashboardApp
from nexus.dashboard.server import DashboardServer
from nexus.dashboard.views import ContentStore
from nexus.mcp.manager import MCPManager
from nexus.transport.telegram import TelegramTransport

logger = logging.getLogger(__name__)


def build_runtime(config: NexusConfig) -> tuple[Runtime, dict[str, AgentProcess]]:
    """Build the Civitas runtime from NexusConfig.

    Returns (Runtime, {name: agent}) for transport wiring.
    """
    db_path = config.memory.db_path
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    memory = MemoryAgent(name="memory", db_path=db_path)

    conversation = ConversationManager(
        name="conversation_manager",
        llm_base_url=config.llm.base_url,
        llm_api_key=config.llm.api_key,
        llm_model=config.llm.model,
        llm_cheap_model=config.llm.cheap_model,
        llm_max_tokens=config.llm.max_tokens,
        personas_dir=config.persona_dir,
        users_dir=config.users_dir,
        skills_dir=config.skills_dir,
        audit_path=config.governance.audit_path,
    )

    scheduler = SchedulerAgent(name="scheduler", skills_dir=config.skills_dir)

    dashboard = DashboardServer(name="dashboard")

    root = Supervisor(
        name="root",
        children=[memory, conversation, scheduler, dashboard],
        strategy="ONE_FOR_ALL",
        max_restarts=5,
        restart_window=60.0,
        backoff="CONSTANT",
        backoff_base=0.5,
    )

    runtime = Runtime(supervisor=root)

    agents: dict[str, AgentProcess] = {
        "memory": memory,
        "conversation_manager": conversation,
        "scheduler": scheduler,
        "dashboard": dashboard,
    }

    return runtime, agents


async def seed_on_start(
    runtime: Runtime,
    config: NexusConfig,
) -> None:
    """Seed tenants from config after runtime starts."""
    if not config.seed_users:
        return

    users = [
        {
            "name": u.name,
            "tenant_id": u.tenant_id,
            "role": u.role,
            "persona": u.persona,
            "timezone": u.timezone,
            "telegram_user_id": u.telegram_user_id,
        }
        for u in config.seed_users
    ]

    await runtime.send(
        "memory",
        {
            "action": "seed_tenants",
            "users": users,
        },
    )
    logger.info("Seeded %d tenant(s)", len(users))


_AGENT_TYPES = {
    "memory": "AgentProcess",
    "conversation_manager": "AgentProcess",
    "scheduler": "AgentProcess",
    "dashboard": "GenServer",
}


async def _register_agents_with_dashboard(
    runtime: Runtime,
    agents: dict[str, AgentProcess],
) -> None:
    for name, agent in agents.items():
        await runtime.cast(
            "dashboard",
            {
                "action": "agent_health",
                "agent": name,
                "type": _AGENT_TYPES.get(name, "AgentProcess"),
                "status": agent.status.value.lower()
                if hasattr(agent.status, "value")
                else "unknown",
                "restart_count": 0,
            },
        )


def _setup_media_handler(conv: ConversationManager) -> None:
    from nexus.media.handler import MediaHandler

    stt = None
    try:
        from nexus.media.stt import WhisperSTT

        stt = WhisperSTT()
        logger.info("STT: faster-whisper enabled")
    except Exception:
        logger.info("STT: not available (install nexus[voice] for voice support)")

    vision = None
    if conv._llm:
        from nexus.media.vision import ClaudeVision

        vision = ClaudeVision(conv._llm)
        logger.info("Vision: Claude enabled via AgentGateway")

    handler = MediaHandler(stt=stt, vision=vision)
    conv.set_media_handler(handler)


async def _start_mcp(
    config: NexusConfig,
    conv: ConversationManager,
) -> MCPManager | None:
    if not config.mcp.servers:
        return None
    mcp_manager = MCPManager()
    await mcp_manager.connect_all(config.mcp.servers)
    conv.set_mcp_manager(mcp_manager)
    logger.info("MCP: %d server(s) configured", len(config.mcp.servers))
    return mcp_manager


async def _start_dashboard(
    config: NexusConfig,
    runtime: Runtime,
    agents: dict[str, AgentProcess],
    conv: ConversationManager,
    mcp_manager: MCPManager | None,
) -> DashboardApp | None:
    if not config.dashboard.enabled:
        return None
    content_store = ContentStore(views_dir=config.dashboard.views_dir)
    dashboard_app = DashboardApp(
        runtime=runtime,
        content_store=content_store,
        port=config.dashboard.port,
    )
    conv.set_content_store(content_store, config.dashboard)
    await dashboard_app.start()
    await _register_agents_with_dashboard(runtime, agents)
    if mcp_manager:
        for name, healthy in (await mcp_manager.health_check()).items():
            await runtime.cast(
                "dashboard",
                {
                    "action": "mcp_status",
                    "server": name,
                    "connected": healthy,
                    "tool_count": len(mcp_manager.filter_tools([name])),
                },
            )
    logger.info("Dashboard at http://0.0.0.0:%d", config.dashboard.port)
    return dashboard_app


async def _start_telegram(
    config: NexusConfig,
    runtime: Runtime,
    conv: ConversationManager,
) -> TelegramTransport | None:
    if not config.telegram:
        logger.info("No transport configured — running headless")
        return None

    tenant_map: dict[str, str] = {}
    for u in config.seed_users:
        if u.telegram_user_id is not None:
            tenant_map[str(u.telegram_user_id)] = u.tenant_id

    def resolve_tenant(user_id: str) -> str | None:
        return tenant_map.get(user_id)

    async def send_to_conv(payload: dict[str, Any]) -> None:
        await runtime.send("conversation_manager", payload)

    transport = TelegramTransport(
        bot_token=config.telegram.bot_token,
        conversation_manager_send=send_to_conv,
        tenant_resolver=resolve_tenant,
    )
    conv.set_transport(transport)
    await transport.start()
    logger.info("Telegram transport started")
    return transport


async def run_nexus(config: NexusConfig) -> None:
    """Start and run Nexus until interrupted."""
    runtime, agents = build_runtime(config)

    await runtime.start()
    logger.info("Nexus runtime started")
    logger.info("\n%s", runtime.print_tree())

    await seed_on_start(runtime, config)

    conv = agents["conversation_manager"]
    assert isinstance(conv, ConversationManager)

    mcp_manager = await _start_mcp(config, conv)
    _setup_media_handler(conv)
    dashboard_app = await _start_dashboard(config, runtime, agents, conv, mcp_manager)
    transport = await _start_telegram(config, runtime, conv)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info("Nexus is ready")
    await stop_event.wait()

    logger.info("Shutting down...")
    for name, coro in [
        ("transport", transport.stop() if transport else None),
        ("dashboard", dashboard_app.stop() if dashboard_app else None),
        ("runtime", runtime.stop()),
    ]:
        if coro is None:
            continue
        try:
            await coro
        except Exception:
            logger.debug("Error stopping %s", name, exc_info=True)
    logger.info("Nexus stopped")
