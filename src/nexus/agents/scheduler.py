from __future__ import annotations

import logging
from typing import Any

from civitas.messages import Message
from civitas.process import AgentProcess

logger = logging.getLogger(__name__)


class SchedulerAgent(AgentProcess):
    def __init__(self, name: str, **kwargs: Any) -> None:
        super().__init__(name, **kwargs)
        self._state_loaded = False

    async def on_start(self) -> None:
        self._state_loaded = False

    async def handle(self, message: Message) -> Message | None:
        if not self._state_loaded:
            self._state_loaded = True

        action = message.payload.get("action")
        if action == "status":
            return self.reply({"status": "running", "state_loaded": self._state_loaded})

        return None
