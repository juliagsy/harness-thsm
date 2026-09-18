"""Domain content pools for the scenario generator. Each domain module exposes a
`DOMAIN` dict with: task_tool, task_arg, FACT_POOL, TASK_POOL, GRANT_POOL, DENY_POOL,
NEVER_POOL, CHATTER, NOISE, INJECTIONS."""

from decaymem.scenarios.domains import coding, procurement

DOMAINS = {"coding_harness": coding.DOMAIN, "procurement": procurement.DOMAIN}


def get_domain(name: str) -> dict:
    if name not in DOMAINS:
        raise ValueError(f"unknown domain {name}; known: {sorted(DOMAINS)}")
    return DOMAINS[name]


__all__ = ["DOMAINS", "get_domain"]
