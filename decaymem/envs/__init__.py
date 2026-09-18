from decaymem.envs.base import BaseEnv, ExecutedAction, TaskState
from decaymem.envs.coding_harness import CodingHarnessEnv
from decaymem.envs.procurement import ProcurementEnv

ENVS = {"coding_harness": CodingHarnessEnv, "procurement": ProcurementEnv}


def make_env(domain: str = "coding_harness") -> BaseEnv:
    if domain not in ENVS:
        raise ValueError(f"unknown domain {domain}; known: {sorted(ENVS)}")
    return ENVS[domain]()


__all__ = [
    "BaseEnv",
    "CodingHarnessEnv",
    "ExecutedAction",
    "ProcurementEnv",
    "TaskState",
    "make_env",
]
