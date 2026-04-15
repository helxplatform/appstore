"""Pure-function resolution algorithm for the app registry.

Operates on dicts parsed from YAML — no I/O.
"""

from __future__ import annotations

import copy
import os

from deepmerge import Merger

_RESERVED_KEYS = {"extends", "apps", "name", "description"}

_merger = Merger(
    [(list, ["override"]), (dict, ["merge"]), (set, ["union"])],
    ["override"],
    ["override"],
)


def deep_merge(base: dict, override: dict) -> dict:
    """Deep-merge *override* into *base*, returning the merged result.

    Lists override, dicts merge recursively, scalars override.
    """
    return _merger.merge(base, override)


def resolve_apps(
    registry: dict,
    defaults: dict,
    product: str,
    registry_dir: str = ".",
) -> dict[str, dict]:
    """Execute the full resolution algorithm.

    1. Select product context
    2. Resolve apps (single recursive pass over extends chain)
    3. Merge defaults
    4. Resolve spec/icon paths

    :param registry: Parsed registry YAML.
    :param defaults: Parsed defaults YAML (may be empty dict).
    :param product: Context name to resolve.
    :param registry_dir: Directory containing the registry file,
        used to resolve relative ``spec_dir``.
    :raises RegistryError: On unknown product or cycle in extends.
    """
    from helx.registry.exceptions import RegistryError

    contexts = registry.get("contexts", {})
    if product not in contexts:
        raise RegistryError(
            f"Unknown product {product!r}",
            details=f"Available contexts: {', '.join(contexts)}",
        )

    apps = resolve_context(contexts, product)
    if defaults:
        apply_defaults(apps, defaults)
    resolve_paths(apps, registry.get("spec_dir", "."), registry_dir)
    return apps


def resolve_context(
    contexts: dict,
    context_name: str,
    apps: dict[str, dict] | None = None,
    _visited: set[str] | None = None,
) -> dict[str, dict]:
    """Depth-first deep-merge of apps across the extends chain.

    At each level: recurse into parents, deep-merge this context's
    apps, then apply bare-key overrides.

    :raises RegistryError: On cycle detection.
    """
    from helx.registry.exceptions import RegistryError

    if apps is None:
        apps = {}
    if _visited is None:
        _visited = set()

    if context_name in _visited:
        raise RegistryError(
            f"Cycle detected in extends chain: {context_name!r}",
            details=f"Visited: {_visited}",
        )
    _visited = _visited | {context_name}  # new set per branch

    context = contexts[context_name]

    # Recurse into parents first — earliest ancestor's apps land first
    for base_name in context.get("extends", []):
        resolve_context(contexts, base_name, apps, _visited)

    # Deep-merge this context's apps on top (child fields win)
    for app_id, app_def in context.get("apps", {}).items():
        if app_id in apps:
            apps[app_id] = deep_merge(apps[app_id], copy.deepcopy(app_def))
        else:
            apps[app_id] = copy.deepcopy(app_def)

    # Apply context-level per-app overrides (bare keys matching app IDs)
    for key, value in context.items():
        if key not in _RESERVED_KEYS and key in apps and isinstance(value, dict):
            apps[key] = deep_merge(apps[key], copy.deepcopy(value))

    return apps


def apply_defaults(apps: dict[str, dict], defaults: dict) -> None:
    """Deep-merge defaults into each app (in place).

    Defaults provide the base layer; app values always win on conflict.
    """
    for app_id in apps:
        apps[app_id] = deep_merge(copy.deepcopy(defaults), apps[app_id])


def resolve_paths(
    apps: dict[str, dict],
    spec_dir: str,
    registry_dir: str,
) -> None:
    """Synthesize spec and icon filesystem paths (in place)."""
    if not os.path.isabs(spec_dir):
        spec_dir = os.path.join(registry_dir, spec_dir)
    spec_dir = os.path.normpath(spec_dir)

    for app_id, app in apps.items():
        if "spec" not in app:
            app["spec"] = os.path.join(spec_dir, app_id, "docker-compose.yaml")
        app["icon"] = os.path.join(os.path.dirname(app["spec"]), "icon.png")
