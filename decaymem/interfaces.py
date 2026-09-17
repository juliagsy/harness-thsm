"""Plugin protocols shared by providers, backends, writers, environments (docs/03)."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, Field


class ToolSpec(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    input: dict[str, Any] = Field(default_factory=dict)


class ModelReply(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    # Provider-native assistant content blocks to echo back on the next turn (thinking
    # blocks must round-trip unchanged). Empty = runner synthesises text + tool_use blocks.
    raw_content: list[dict[str, Any]] = Field(default_factory=list)
    usage: dict[str, int] = Field(default_factory=dict)
    stop_reason: str = "end_turn"
    cached: bool = False

    def assistant_message(self) -> dict[str, Any]:
        if self.raw_content:
            return {"role": "assistant", "content": self.raw_content}
        blocks: list[dict[str, Any]] = []
        if self.text:
            blocks.append({"type": "text", "text": self.text})
        for c in self.tool_calls:
            blocks.append({"type": "tool_use", "id": c.id, "name": c.name, "input": c.input})
        if not blocks:
            blocks.append({"type": "text", "text": ""})
        return {"role": "assistant", "content": blocks}


@runtime_checkable
class ModelProvider(Protocol):
    name: str
    model: str

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> ModelReply: ...


def last_user_text(messages: list[dict[str, Any]]) -> str:
    for m in reversed(messages):
        if m.get("role") != "user":
            continue
        c = m.get("content")
        if isinstance(c, str):
            return c
        if isinstance(c, list):
            texts = [b.get("text", "") for b in c if b.get("type") == "text"]
            if texts:
                return "\n".join(texts)
    return ""


def has_tool_results(messages: list[dict[str, Any]]) -> bool:
    m = messages[-1] if messages else {}
    c = m.get("content")
    return isinstance(c, list) and any(b.get("type") == "tool_result" for b in c)
