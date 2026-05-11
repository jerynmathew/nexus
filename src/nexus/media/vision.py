from __future__ import annotations

import base64
import logging
from typing import Any

from nexus.llm.client import LLMClient

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = "Describe this image in detail. What do you see?"


class ClaudeVision:
    def __init__(self, llm: LLMClient) -> None:
        self._llm = llm

    async def describe(self, image_bytes: bytes, prompt: str = "") -> str:
        image_b64 = base64.b64encode(image_bytes).decode()
        mime_type = _detect_mime(image_bytes)
        user_prompt = prompt or _DEFAULT_PROMPT

        messages: list[dict[str, Any]] = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{image_b64}",
                        },
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            },
        ]

        response = await self._llm.chat(messages=messages, max_tokens=1024)
        return response.content


def _detect_mime(image_bytes: bytes) -> str:
    if image_bytes[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if image_bytes[:2] == b"\xff\xd8":
        return "image/jpeg"
    if image_bytes[:4] == b"GIF8":
        return "image/gif"
    if image_bytes[:4] == b"RIFF" and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
