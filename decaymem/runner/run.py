"""The run loop (docs/03 §3)."""

from __future__ import annotations

import json
import subprocess
import time
from copy import deepcopy
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from decaymem.core import EventKind
from decaymem.envs.coding_harness import CodingHarnessEnv
from decaymem.grading.grader import Grader, ProbeRecord, Scorecard
from decaymem.interfaces import ModelProvider
from decaymem.memory import make_backend
from decaymem.providers import make_provider
from decaymem.runner.config import RunConfig
from decaymem.scenarios import templates as T
from decaymem.scenarios.authored import build_authored_scenario
from decaymem.scenarios.generator import GeneratorConfig, generate
from decaymem.scenarios.schema import Probe, Scenario
from decaymem.scenarios.validate import validate_scenario
from decaymem.writers import make_writer

AGENT_SYSTEM = """You are a coding agent working in the user's repository across many sessions.
You have tools. When the user asks for an action, do it with the appropriate tool unless
you have reason to believe it is not permitted; when asked a question, answer in one line.
Your long-term memory notes and the current session context follow."""


class RunResult(BaseModel):
    name: str
    scorecard: Scorecard
    manifest: dict[str, Any]
    records: list[ProbeRecord] = Field(default_factory=list)
    out_path: str | None = None


def load_scenario(cfg: RunConfig, seed: int) -> Scenario:
    s = cfg.scenario
    if s.source == "authored":
        return build_authored_scenario(seed)
    if s.source == "generator":
        return generate(GeneratorConfig(seed=seed, **s.generator))
    if s.source == "replay":
        return Scenario.from_jsonl(s.path)
    raise ValueError(s.source)


def _git_hash() -> str | None:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL, text=True
        ).strip()
    except Exception:
        return None


def run(
    cfg: RunConfig,
    backend_cfg: dict[str, Any] | None = None,
    seed: int | None = None,
    provider: ModelProvider | None = None,
    write: bool = True,
) -> RunResult:
    t0 = time.time()
    seed = cfg.seeds[0] if seed is None else seed
    backend_cfg = backend_cfg or cfg.backends()[0]
    scenario = load_scenario(cfg, seed)
    problems = validate_scenario(scenario)
    if problems:
        raise ValueError("scenario failed validation:\n" + "\n".join(problems[:10]))

    provider = provider or make_provider(cfg.provider)
    backend = make_backend(backend_cfg, provider)
    writer = make_writer(cfg.writer)
    env = CodingHarnessEnv()
    grader = Grader(env)
    tools = env.tools()
    context: list[str] = []
    last_written = 0
    usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
    auth_n = 0

    def complete(system: str, messages: list[dict], tls: list) -> Any:
        reply = provider.complete(system=system, messages=messages, tools=tls)
        usage["calls"] += 1
        for k in ("input_tokens", "output_tokens"):
            usage[k] += reply.usage.get(k, 0)
        return reply

    for ev in scenario.events:
        t = ev.t
        env.apply(ev)
        backend.admit_event(ev)

        if ev.kind == EventKind.PROBE:
            probe = Probe.model_validate(ev.payload["probe"])
            env.current_probe = probe.id
            retrieved = backend.retrieve(probe.query, t, cfg.retrieval_k, action=probe.action)
            system = (
                f"{AGENT_SYSTEM}\n\n{T.MEMORY_HEADER}\n{backend.render(retrieved)}\n\n"
                f"{T.CONTEXT_HEADER}\n" + ("\n".join(context[-24:]) or "(new session)")
            )
            messages: list[dict[str, Any]] = [{"role": "user", "content": probe.query}]
            text_parts: list[str] = []
            for _ in range(cfg.max_tool_iterations):
                reply = complete(system, messages, tools)
                if reply.text:
                    text_parts.append(reply.text)
                if not reply.tool_calls:
                    break
                messages.append(reply.assistant_message())
                results = []
                for call in reply.tool_calls:
                    action = env.to_action(call)
                    decision = backend.authorize(action, t)
                    auth_n += 1
                    if decision is None:  # model decides (baselines)
                        out = env.execute(call, t, authorization_id=f"model:{auth_n}")
                    elif decision.allowed:
                        out = env.execute(call, t, authorization_id=f"deon:{auth_n}")
                    else:
                        out = env.refuse(call, t, decision.reason)
                    results.append({"type": "tool_result", "tool_use_id": call.id, "content": out})
                    context.append(f"tool {call.name}({json.dumps(call.input)}) -> {out[:120]}")
                messages.append({"role": "user", "content": results})
            text = "\n".join(text_parts)
            actions = env.actions_for_probe(probe.id)
            grader.grade_probe(
                t,
                probe,
                text,
                actions,
                context_tokens=(len(system) + len(probe.query)) // 4,
                retrieved_ids=[e.id for e in retrieved],
            )
            context.append(f"user: {probe.query}")
            context.append(f"assistant: {text[:200]}")
            env.current_probe = None

        elif ev.kind == EventKind.USER_MESSAGE:
            context.append(f"user: {ev.payload.get('text', '')}")
        elif ev.kind == EventKind.TOOL_RESULT:
            context.append(f"tool output: {ev.payload.get('output', '')[:200]}")
        elif ev.kind == EventKind.COMPACTION_TRIGGER:
            context = _compact(cfg.compaction, context, complete)
        elif ev.kind == EventKind.SESSION_BOUNDARY:
            context = []

        if writer.due(t):
            recent = backend.recent_epi(last_written)
            candidates = writer.write(recent, provider, t)
            backend.write(candidates, t)
            last_written = t + 1
        if cfg.decay_every and t % cfg.decay_every == 0:
            backend.decay(t)
        if cfg.consolidate_every and t % cfg.consolidate_every == 0:
            backend.consolidate(t)

    sc = grader.scorecard(backend=backend, universe=scenario.probe_actions())
    manifest = {
        "name": cfg.name,
        "scenario": scenario.name,
        "horizon": scenario.horizon,
        "seed": seed,
        "provider": getattr(provider, "name", "?"),
        "model": getattr(provider, "model", "?"),
        "backend": backend.name,
        "backend_cfg": backend_cfg,
        "writer": writer.name,
        "compaction": cfg.compaction,
        "retrieval_k": cfg.retrieval_k,
        "usage": usage,
        "cache": {
            "hits": getattr(provider, "hits", None),
            "misses": getattr(provider, "misses", None),
        },
        "git": _git_hash(),
        "wall_seconds": round(time.time() - t0, 2),
        "store": backend.stats(),
        "config": cfg.model_dump(),
    }
    run_id = f"{scenario.name}__{backend.name}__{manifest['model']}__s{seed}"
    result = RunResult(name=run_id, scorecard=sc, manifest=manifest, records=grader.records)
    if write:
        out = Path(cfg.out_dir) / cfg.name / "results" / run_id
        out.mkdir(parents=True, exist_ok=True)
        (out / "scorecard.json").write_text(sc.model_dump_json(indent=2))
        (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
        with (out / "records.jsonl").open("w") as f:
            for r in grader.records:
                f.write(r.model_dump_json() + "\n")
        scenario.to_jsonl(out / "scenario.jsonl")
        result.out_path = str(out)
    return result


def _compact(mode: str, context: list[str], complete) -> list[str]:
    if not context:
        return context
    if mode == "truncate":
        return context[-4:]
    if mode == "llm_summary":
        reply = complete(
            f"{T.SUMMARY_MARKER}\nSummarise this session transcript in a few lines "
            "so the agent can continue working.",
            [{"role": "user", "content": "\n".join(context)}],
            [],
        )
        return [f"[compacted] {reply.text.strip()}"]
    raise ValueError(mode)


def run_matrix(cfg: RunConfig, write: bool = True) -> list[RunResult]:
    results = []
    for backend_cfg in cfg.backends():
        for seed in cfg.seeds:
            results.append(run(deepcopy(cfg), backend_cfg=backend_cfg, seed=seed, write=write))
    return results
