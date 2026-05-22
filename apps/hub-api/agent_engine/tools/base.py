from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    data: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_audit_entry(self) -> dict:
        return {
            "tool": self.tool_name,
            "success": self.success,
            "latency_ms": self.latency_ms,
            "error": self.error,
        }


class AgentTool(ABC):
    name: str
    description: str

    @abstractmethod
    async def execute(self, **kwargs) -> ToolResult:
        ...

    async def safe_execute(self, **kwargs) -> ToolResult:
        start = time.monotonic()
        try:
            result = await self.execute(**kwargs)
            result.latency_ms = (time.monotonic() - start) * 1000
            return result
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                success=False,
                error=str(exc),
                latency_ms=(time.monotonic() - start) * 1000,
            )
