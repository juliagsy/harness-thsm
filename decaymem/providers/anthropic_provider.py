"""Anthropic Messages API provider (manual tool loop is driven by the runner)."""

from __future__ import annotations

from typing import Any

from decaymem.interfaces import ModelReply, ToolCall, ToolSpec


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self, model: str = "claude-opus-5", effort: str = "low", max_tokens: int = 2048
    ) -> None:
        import anthropic  # optional dependency: uv sync --extra anthropic

        self.client = anthropic.Anthropic()
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> ModelReply:
        kwargs: dict[str, Any] = dict(
            model=self.model,
            max_tokens=self.max_tokens,
            system=system,
            messages=messages,
            output_config={"effort": self.effort},
        )
        if tools:
            kwargs["tools"] = [t.model_dump() for t in tools]
        resp = self.client.messages.create(**kwargs)
        if resp.stop_reason == "refusal":
            return ModelReply(
                text="[refused]",
                stop_reason="refusal",
                usage={
                    "input_tokens": resp.usage.input_tokens,
                    "output_tokens": resp.usage.output_tokens,
                },
            )
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                calls.append(ToolCall(id=block.id, name=block.name, input=dict(block.input)))
        return ModelReply(
            text="\n".join(text_parts),
            tool_calls=calls,
            raw_content=[b.model_dump(mode="json") for b in resp.content],
            usage={
                "input_tokens": resp.usage.input_tokens,
                "output_tokens": resp.usage.output_tokens,
            },
            stop_reason=resp.stop_reason or "end_turn",
        )
