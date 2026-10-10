"""Versioned prompt templates shipped with the package (vio/llm/prompts/*.md)."""

import importlib.resources


def load_prompt(name: str) -> str:
    return importlib.resources.files("vio.llm").joinpath(f"prompts/{name}").read_text("utf-8")
