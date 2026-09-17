"""OpenAI-compatible chat-completions provider (OpenRouter, OpenAI, vLLM, Ollama, ...).

Our canonical message shape is the Anthropic one (text / tool_use / tool_result blocks);
this adapter translates both ways so the runner and cache never see a difference.
"""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from decaymem.interfaces import ModelReply, ToolCall, ToolSpec

PRESETS: dict[str, dict[str, Any]] = {
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "headers": {"HTTP-Referer": "https://localhost/decaymem", "X-Title": "decaymem"},
    },
    "openai": {"base_url": "https://api.openai.com/v1", "api_key_env": "OPENAI_API_KEY"},
    "ollama": {"base_url": "http://localhost:11434/v1", "api_key_env": None},
    "vllm": {"base_url": "http://localhost:8000/v1", "api_key_env": None},
}


def to_openai_messages(system: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = [{"role": "system", "content": system}] if system else []
    for m in messages:
        role, content = m["role"], m["content"]
        if isinstance(content, str):
            out.append({"role": role, "content": content})
            continue
        if role == "assistant":
            text = "\n".join(b.get("text", "") for b in content if b.get("type") == "text")
            calls = [
                {
                    "id": b["id"],
                    "type": "function",
                    "function": {"name": b["name"], "arguments": json.dumps(b.get("input", {}))},
                }
                for b in content
                if b.get("type") == "tool_use"
            ]
            msg: dict[str, Any] = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:  # user: text blocks and/or tool results
            for b in content:
                if b.get("type") == "tool_result":
                    c = b.get("content", "")
                    out.append(
                        {
                            "role": "tool",
                            "tool_call_id": b["tool_use_id"],
                            "content": c if isinstance(c, str) else json.dumps(c),
                        }
                    )
                elif b.get("type") == "text":
                    out.append({"role": "user", "content": b.get("text", "")})
    return out


def to_openai_tools(tools: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.input_schema,
            },
        }
        for t in tools
    ]


def parse_openai_response(data: dict[str, Any]) -> ModelReply:
    choice = data["choices"][0]
    msg = choice.get("message", {})
    calls: list[ToolCall] = []
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function", {})
        try:
            args = json.loads(fn.get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {"_raw": fn.get("arguments")}
        calls.append(
            ToolCall(
                id=tc.get("id") or f"call_{len(calls)}",
                name=fn.get("name", ""),
                input=args if isinstance(args, dict) else {"value": args},
            )
        )
    usage = data.get("usage") or {}
    return ModelReply(
        text=msg.get("content") or "",
        tool_calls=calls,
        usage={
            "input_tokens": int(usage.get("prompt_tokens", 0)),
            "output_tokens": int(usage.get("completion_tokens", 0)),
        },
        stop_reason="tool_use" if calls else str(choice.get("finish_reason") or "end_turn"),
    )


class OpenAICompatProvider:
    def __init__(
        self,
        model: str,
        base_url: str | None = None,
        api_key_env: str | None = None,
        api_key: str | None = None,
        headers: dict[str, str] | None = None,
        preset: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float = 120.0,
        extra_body: dict[str, Any] | None = None,
    ) -> None:
        cfg = dict(PRESETS.get(preset or "", {}))
        self.name = preset or "openai_compat"
        self.model = model
        self.base_url = (base_url or cfg.get("base_url") or "").rstrip("/")
        if not self.base_url:
            raise ValueError("openai_compat provider needs base_url or a preset")
        env = api_key_env if api_key_env is not None else cfg.get("api_key_env")
        key = api_key or (os.environ.get(env) if env else None)
        if env and not key:
            raise RuntimeError(f"{self.name}: set {env} in the environment")
        self.headers = {
            "Content-Type": "application/json",
            **cfg.get("headers", {}),
            **(headers or {}),
        }
        if key:
            self.headers["Authorization"] = f"Bearer {key}"
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.extra_body = extra_body or {}
        self._client = httpx.Client(timeout=timeout)

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> ModelReply:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": to_openai_messages(system, messages),
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            **self.extra_body,
        }
        if tools:
            body["tools"] = to_openai_tools(tools)
            body["tool_choice"] = "auto"
        r = self._client.post(f"{self.base_url}/chat/completions", headers=self.headers, json=body)
        if r.status_code >= 400:
            raise RuntimeError(f"{self.name} {r.status_code}: {r.text[:500]}")
        return parse_openai_response(r.json())
