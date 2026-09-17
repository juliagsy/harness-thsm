from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class ScenarioCfg(BaseModel):
    source: str = "authored"  # authored | generator | replay
    path: str | None = None
    seed: int = 0
    generator: dict[str, Any] = Field(default_factory=dict)


class RunConfig(BaseModel):
    name: str = "smoke"
    scenario: ScenarioCfg = Field(default_factory=ScenarioCfg)
    provider: dict[str, Any] = Field(default_factory=lambda: {"name": "scripted"})
    backend: dict[str, Any] | list[dict[str, Any]] = Field(
        default_factory=lambda: {"name": "flat_vector"}
    )
    writer: dict[str, Any] = Field(default_factory=lambda: {"name": "llm_freeform", "every_n": 10})
    compaction: str = "truncate"  # truncate | llm_summary
    retrieval_k: int = 8
    max_tool_iterations: int = 4
    decay_every: int = 5
    consolidate_every: int = 10
    seeds: list[int] = Field(default_factory=lambda: [0])
    out_dir: str = "experiments"
    # optional sweep: {backends: [names], params: {key: [values]}, base_params: {...}}
    sweep: dict[str, Any] | None = None

    def backends(self) -> list[dict[str, Any]]:
        if self.sweep:
            import itertools

            names = self.sweep.get("backends", [])
            grid = self.sweep.get("params", {})
            base = self.sweep.get("base_params", {})
            keys = list(grid)
            out = []
            for name in names:
                for combo in itertools.product(*(grid[k] for k in keys)):
                    out.append(
                        {"name": name, "params": {**base, **dict(zip(keys, combo, strict=True))}}
                    )
            return out
        return self.backend if isinstance(self.backend, list) else [self.backend]


def load_config(path: str | Path) -> RunConfig:
    return RunConfig.model_validate(yaml.safe_load(Path(path).read_text()))
