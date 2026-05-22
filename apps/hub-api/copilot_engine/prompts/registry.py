"""
Versioned prompt registry.

All copilot prompts are registered here at import time.
Templates use Python str.format_map() with a safe defaultdict so missing
variables silently become empty strings rather than raising KeyError.
"""
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class PromptTemplate:
    name: str
    version: str
    system_template: str
    user_template: str
    description: str
    input_vars: list[str]
    copilot_type: str

    def render_system(self, **kwargs) -> str:
        return self.system_template.format_map(defaultdict(str, **kwargs))

    def render_user(self, **kwargs) -> str:
        return self.user_template.format_map(defaultdict(str, **kwargs))


class PromptRegistry:
    def __init__(self):
        self._store: dict[str, PromptTemplate] = {}

    def register(self, prompt: PromptTemplate) -> None:
        self._store[prompt.name] = prompt

    def get(self, name: str) -> PromptTemplate:
        if name not in self._store:
            raise KeyError(f"Prompt '{name}' not registered")
        return self._store[name]

    def list_all(self) -> list[dict]:
        return [
            {
                "name": p.name,
                "version": p.version,
                "description": p.description,
                "copilot_type": p.copilot_type,
                "input_vars": p.input_vars,
            }
            for p in self._store.values()
        ]

    def count(self) -> int:
        return len(self._store)


# Process-level singleton — all prompt modules register to this
registry = PromptRegistry()
