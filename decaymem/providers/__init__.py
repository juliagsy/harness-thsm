from decaymem.providers.cached import CachedProvider
from decaymem.providers.scripted import ScriptedProvider


def make_provider(cfg: dict):
    """Build a provider from a config dict: {name, model, cache_dir, ...}."""
    name = cfg.get("name", "scripted")
    if name == "scripted":
        base = ScriptedProvider(
            policy=cfg.get("policy", "naive"), model=cfg.get("model", "scripted")
        )
    elif name == "anthropic":
        from decaymem.providers.anthropic_provider import AnthropicProvider

        base = AnthropicProvider(
            model=cfg.get("model", "claude-opus-5"),
            effort=cfg.get("effort", "low"),
            max_tokens=cfg.get("max_tokens", 2048),
        )
    else:
        raise ValueError(f"unknown provider {name}")
    if cfg.get("cache", True) and cfg.get("cache_dir"):
        return CachedProvider(base, cfg["cache_dir"])
    return base


__all__ = ["CachedProvider", "ScriptedProvider", "make_provider"]
