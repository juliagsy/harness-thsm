"""Zero-cost scripted provider: a deterministic 'naive agent' for dry runs.

It parses the probe templates emitted by the scenario builder (see
decaymem/scenarios/templates.py), calls the requested tool without judgement, and
answers knowledge questions from the first retrieved memory note that mentions the
key. For writer prompts it echoes each event as a note, which reproduces the
laundering vector (permission events become plain memory text).
"""

from __future__ import annotations

import re
from typing import Any

from decaymem.interfaces import ModelReply, ToolCall, ToolSpec, has_tool_results, last_user_text
from decaymem.scenarios import templates as T


class ScriptedProvider:
    name = "scripted"

    def __init__(self, policy: str = "naive", model: str = "scripted") -> None:
        self.policy = policy
        self.model = model
        self._n = 0

    def _id(self) -> str:
        self._n += 1
        return f"call_{self._n}"

    def complete(
        self, *, system: str, messages: list[dict[str, Any]], tools: list[ToolSpec]
    ) -> ModelReply:
        if T.WRITER_MARKER in system:
            return self._write_notes(last_user_text(messages))
        if T.SUMMARY_MARKER in system:
            text = last_user_text(messages)
            return ModelReply(text="Summary: " + " | ".join(text.splitlines()[-8:])[:800])
        if has_tool_results(messages):
            return ModelReply(text="Done.")
        q = last_user_text(messages)
        action = T.parse_action_request(q)
        if action is not None:
            tool, inp = action
            if self.policy == "refuse_all":
                return ModelReply(text="I won't do that.")
            return ModelReply(
                tool_calls=[ToolCall(id=self._id(), name=tool, input=inp)], stop_reason="tool_use"
            )
        key = T.parse_knowledge_question(q)
        if key is not None:
            return ModelReply(text=self._answer_from_memory(system, key))
        desc = T.parse_task_request(q)
        if desc is not None:
            cmd = T.find_command_in_notes(self._memory_section(system), desc)
            if cmd is None:
                return ModelReply(text="I don't know how to do that here.")
            if self.policy == "refuse_all":
                return ModelReply(text="I won't do that.")
            return ModelReply(
                tool_calls=[ToolCall(id=self._id(), name="run_cmd", input={"cmd": cmd})],
                stop_reason="tool_use",
            )
        return ModelReply(text="Okay.")

    @staticmethod
    def _memory_section(system: str) -> str:
        return system.split(T.MEMORY_HEADER, 1)[-1].split(T.CONTEXT_HEADER, 1)[0]

    @staticmethod
    def _answer_from_memory(system: str, key: str) -> str:
        mem = ScriptedProvider._memory_section(system)
        needle = key.replace("_", " ")
        for line in mem.splitlines():
            low = line.lower()
            if "?" in low:
                continue  # echoed questions carry no answer
            if needle in low or key in low:
                return line.strip("- ").strip()
        return "I don't know."

    @staticmethod
    def _write_notes(events_text: str) -> ModelReply:
        notes = []
        for line in events_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.match(r"^\[[^\]]*\]\s*(.*)$", line)
            notes.append(m.group(1) if m else line)
        return ModelReply(text="\n".join(f"- {n}" for n in notes[:12]))
