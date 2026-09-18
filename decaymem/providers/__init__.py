from decaymem.providers.cached import CachedProvider
from decaymem.providers.scripted import ScriptedProvider

OPENAI_COMPAT_NAMES = {"openai_compat", "openrouter", "openai", "ollama", "vllm"}


def make_provider(cfg: dict):
    """Build a provider from a config dict: {name, model, cache_dir, ...}."""
    from decaymem.dotenv import load_dotenv

    load_dotenv()
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
    elif name in OPENAI_COMPAT_NAMES:
        from decaymem.providers.openai_compat import OpenAICompatProvider

        base = OpenAICompatProvider(
            model=cfg["model"],
            preset=None if name == "openai_compat" else name,
            base_url=cfg.get("base_url"),
            api_key_env=cfg.get("api_key_env"),
            headers=cfg.get("headers"),
            max_tokens=cfg.get("max_tokens", 1024),
            temperature=cfg.get("temperature", 0.0),
            extra_body=cfg.get("extra_body"),
        )
    else:
        raise ValueError(f"unknown provider {name}")
    if cfg.get("cache", True) and cfg.get("cache_dir"):
        return CachedProvider(base, cfg["cache_dir"])
    return base


__all__ = ["CachedProvider", "ScriptedProvider", "make_provider"]
