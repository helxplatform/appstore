"""Load YAML configs and docker-compose specs from the local filesystem."""

from __future__ import annotations

import os

import yaml
from jinja2 import Environment, Undefined


class _KeepUndefined(Undefined):
    """Render undefined Jinja2 variables as empty strings.

    Compose specs may reference variables (``{{ azure_registry }}``, etc.)
    that are only meaningful at deploy time.  Rather than crashing on
    parse, we treat them as blank so the YAML is still structurally valid.
    """

    def __str__(self):
        return ""

    def __iter__(self):
        return iter([])

    def __bool__(self):
        return False


_jinja_env = Environment(undefined=_KeepUndefined)


class RegistryLoader:
    """Loads registry configs, docker-compose specs, and .env files."""

    def load_config(self, path: str) -> dict:
        """Load and parse a YAML file from disk."""
        with open(path) as f:
            return yaml.safe_load(f) or {}

    def load_spec(self, spec_path: str, settings: dict) -> dict:
        """Read a docker-compose file, render Jinja2 templates, parse YAML.

        The double-pass is intentional: the raw file may contain Jinja2
        expressions like ``{{ helx_registry }}``.  We render those first,
        then parse the result as YAML.  Unknown variables are rendered as
        empty strings so the spec is still structurally parseable.
        """
        with open(spec_path) as f:
            raw = f.read()
        rendered = _jinja_env.from_string(raw).render(settings)
        return yaml.safe_load(rendered) or {}

    def load_settings(self, spec_path: str) -> str:
        """Read the .env sibling of a spec path.

        Returns empty string if the file does not exist.
        """
        env_path = os.path.join(os.path.dirname(spec_path), ".env")
        if not os.path.isfile(env_path):
            return ""
        with open(env_path) as f:
            return f.read()
