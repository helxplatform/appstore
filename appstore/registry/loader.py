"""Load YAML configs and docker-compose specs from the local filesystem."""

from __future__ import annotations

import os
import re

import yaml
from jinja2 import Environment, Undefined

# Matches Go template expressions: {{ ... }} that contain a dot or a
# function call the controller resolves at deploy time.  These must be
# preserved verbatim through Jinja2 rendering and passed to the CRD.
# Jinja2 raises a syntax error on expressions like {{ .system.UserName }}
# because the leading dot is not valid Jinja2 syntax.
_GO_TEMPLATE_RE = re.compile(r"\{\{[^{}]*\.[^{}]*\}\}")


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

        Go template expressions (``{{ .system.UserName }}``, etc.) are
        controller-time placeholders and must not be touched by Jinja2.
        They are protected with unique sentinels before rendering and
        restored verbatim in the output.

        Available Jinja2 variables:
          - ``system_port``: first service port declared in the app registry
          - Any key under the registry-level ``settings:`` block
        """
        with open(spec_path) as f:
            raw = f.read()

        # Protect Go template expressions from Jinja2.
        sentinels: dict[str, str] = {}
        def _sentinel(m: re.Match) -> str:
            key = f"__GO_{len(sentinels)}__"
            sentinels[key] = m.group(0)
            return key
        protected = _GO_TEMPLATE_RE.sub(_sentinel, raw)

        rendered = _jinja_env.from_string(protected).render(settings)

        # Restore Go template expressions.
        for key, original in sentinels.items():
            rendered = rendered.replace(key, original)

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
