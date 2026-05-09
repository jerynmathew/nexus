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
        llm_max_tokens=config.llm.max_tokens,
        personas_dir=config.persona_dir,
        users_dir=config.users_dir,
    )

    scheduler = SchedulerAgent(name="scheduler")

    root = Supervisor(
        name="root",
        children=[memory, conversation, scheduler],
        strategy="ONE_FOR_ALL",
        max_restarts=5,
        restart_window=60.0,
        backoff="CONSTANT",
        backoff_base=0.5,
    )

    runtime = Runtime(supervisor=root)

    agents = {
        "memory": memory,
        "conversation_manager": conversation,
        "scheduler": scheduler,
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


async def run_nexus(config: NexusConfig) -> None:
    """Start and run Nexus until interrupted."""
    runtime, agents = build_runtime(config)

    await runtime.start()
    logger.info("Nexus runtime started")
    logger.info("\n%s", runtime.print_tree())

    await seed_on_start(runtime, config)

    conv = agents["conversation_manager"]

    if config.telegram:
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
    else:
        logger.info("No transport configured — running headless")

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)

    logger.info("Nexus is ready")
    await stop_event.wait()

    logger.info("Shutting down...")
    if config.telegram:
        await transport.stop()  # type: ignore[possibly-undefined]
    await runtime.stop()
    logger.info("Nexus stopped")
