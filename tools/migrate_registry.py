#!/usr/bin/env python3
"""Migrate a Tycho v1 registry directory to Registry v2 format.

Operates on an entire directory:

    v1-input/
        app-registry.yaml
        app-defaults.yaml        (optional — merged into registry)
        app-specs/               (or whatever the repo's spec dir is)
            jupyter-ds/
                docker-compose.yaml
                icon.png
            rstudio/
                docker-compose.yaml
                ...

Produces:

    v2-output/
        app-registry.yaml        (v2 format, defaults baked in, pruned to context)
        app-specs/
            jupyter-ds/
                docker-compose.yaml
                icon.png
            ...                  (only apps reachable from the target context)

Transforms applied:
  - ``repositories`` → ``spec_dir``
  - ``mixin`` → folded into ``extends``
  - ``securityContext.uid/gid`` → ``runAsUser/runAsGroup``
  - ``app-defaults.yaml`` merged into every app (no separate file in output)
  - Contexts pruned to only the target context and its ancestors
  - Only app-spec directories for apps in the resolved context are copied

Usage::

    python -m tools.migrate_registry \\
        --input  /path/to/v1-dir \\
        --output /path/to/v2-dir \\
        --context braini
"""

from __future__ import annotations

import argparse
import copy
import logging
import os
import shutil
import sys

import yaml

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------
# Security-context key mapping (v1 → v2)
# -----------------------------------------------------------------------

_SC_KEY_MAP = {
    "uid": "runAsUser",
    "gid": "runAsGroup",
    "runAsUser": "runAsUser",
    "runAsGroup": "runAsGroup",
    "fsGroup": "fsGroup",
    "supplementalGroups": "supplementalGroups",
}


def migrate_security_context(sc: dict) -> dict:
    """Convert a v1 securityContext dict to v2 format."""
    out: dict = {}
    for k, v in sc.items():
        new_key = _SC_KEY_MAP.get(k)
        if new_key:
            out[new_key] = v
        else:
            logger.warning("Unknown securityContext key %r — passing through", k)
            out[k] = v
    return out


# -----------------------------------------------------------------------
# Per-app migration
# -----------------------------------------------------------------------

def migrate_app(app_id: str, app: dict) -> dict:
    """Migrate a single app definition."""
    app = copy.deepcopy(app)

    if "securityContext" in app and isinstance(app["securityContext"], dict):
        app["securityContext"] = migrate_security_context(app["securityContext"])

    # Remove remote spec/icon URLs — v2 synthesises paths from spec_dir
    if "spec" in app:
        spec = app["spec"]
        if isinstance(spec, str) and spec.startswith("http"):
            del app["spec"]

    if "icon" in app:
        icon = app["icon"]
        if isinstance(icon, str) and icon.startswith("http"):
            del app["icon"]

    return app


# -----------------------------------------------------------------------
# Context migration
# -----------------------------------------------------------------------

_CTX_RESERVED = {"extends", "apps", "name", "description", "mixin"}


def migrate_context(name: str, ctx: dict) -> dict:
    """Migrate a single context definition."""
    ctx = copy.deepcopy(ctx)

    # Fold ``mixin`` into ``extends``
    mixins = ctx.pop("mixin", [])
    extends = ctx.get("extends", [])
    for m in mixins:
        if m not in extends:
            extends.append(m)
    if extends:
        ctx["extends"] = extends

    if "apps" in ctx:
        ctx["apps"] = {
            aid: migrate_app(aid, adef)
            for aid, adef in ctx["apps"].items()
        }

    # Migrate bare-key per-app overrides
    for key in list(ctx.keys()):
        if key not in _CTX_RESERVED and isinstance(ctx[key], dict):
            if "securityContext" in ctx[key]:
                ctx[key]["securityContext"] = migrate_security_context(
                    ctx[key]["securityContext"]
                )

    return ctx


# -----------------------------------------------------------------------
# Ancestor collection — walk the extends/mixin chain
# -----------------------------------------------------------------------

def collect_ancestors(
    contexts: dict[str, dict],
    context_name: str,
    collected: set[str] | None = None,
) -> set[str]:
    """Return the set of context names reachable from *context_name*
    via ``extends`` and ``mixin`` chains (inclusive of *context_name*)."""
    if collected is None:
        collected = set()
    if context_name in collected:
        return collected
    collected.add(context_name)
    ctx = contexts.get(context_name, {})
    for parent in ctx.get("extends", []) + ctx.get("mixin", []):
        collect_ancestors(contexts, parent, collected)
    return collected


# -----------------------------------------------------------------------
# Defaults merging
# -----------------------------------------------------------------------

def merge_defaults_into_contexts(contexts: dict, defaults: dict) -> dict:
    """Deep-merge defaults into the apps of every context, returning new contexts.

    After this, defaults are baked in and no separate defaults file is needed.
    """
    if not defaults:
        return contexts

    migrated_defaults = copy.deepcopy(defaults)
    if "securityContext" in migrated_defaults and isinstance(
        migrated_defaults["securityContext"], dict
    ):
        migrated_defaults["securityContext"] = migrate_security_context(
            migrated_defaults["securityContext"]
        )

    result = copy.deepcopy(contexts)
    for ctx_name, ctx in result.items():
        if "apps" not in ctx:
            continue
        for app_id, app_def in ctx["apps"].items():
            # defaults provide the base; app values win
            merged = copy.deepcopy(migrated_defaults)
            merged.update(app_def)
            ctx["apps"][app_id] = merged
    return result


# -----------------------------------------------------------------------
# Collect resolved app IDs (to know which spec dirs to copy)
# -----------------------------------------------------------------------

def collect_app_ids(contexts: dict, context_name: str) -> set[str]:
    """Return the set of app IDs reachable from *context_name* after
    walking the full extends/mixin chain.

    This is a lightweight version of the full resolver — just collects
    app keys without merging definitions.
    """
    ancestors = collect_ancestors(contexts, context_name)
    app_ids: set[str] = set()
    for name in ancestors:
        ctx = contexts.get(name, {})
        app_ids.update(ctx.get("apps", {}).keys())
    return app_ids


# -----------------------------------------------------------------------
# Top-level migration
# -----------------------------------------------------------------------

def migrate_registry(
    v1: dict,
    defaults: dict | None = None,
    spec_dir: str = "app-specs",
    context: str | None = None,
) -> dict:
    """Convert a complete v1 registry dict to v2 format.

    :param v1: Parsed v1 app-registry.yaml.
    :param defaults: Parsed v1 app-defaults.yaml (merged into apps).
    :param spec_dir: Name of the specs subdirectory in the output.
    :param context: If provided, prune to only this context and its
        ancestors.  Otherwise keep all contexts.
    :returns: New dict suitable for writing as v2 app-registry.yaml.
    """
    v2: dict = {}

    v2["api"] = "Tycho"
    v2["version"] = "0.0.2"

    if "metadata" in v1:
        v2["metadata"] = copy.deepcopy(v1["metadata"])
    else:
        v2["metadata"] = {
            "id": "helx-app-registry",
            "name": "HeLx Application Registry",
        }

    v2["spec_dir"] = spec_dir

    if "repositories" in v1:
        logger.info(
            "Replacing 'repositories' with spec_dir=%r", spec_dir,
        )

    if "settings" in v1:
        v2["settings"] = copy.deepcopy(v1["settings"])

    # Merge defaults into contexts before migrating
    v1_contexts = v1.get("contexts", {})
    if defaults:
        v1_contexts = merge_defaults_into_contexts(v1_contexts, defaults)

    # Prune to target context + ancestors
    if context:
        keep = collect_ancestors(v1_contexts, context)
        logger.info(
            "Pruning to context %r — keeping: %s",
            context,
            ", ".join(sorted(keep)),
        )
        v1_contexts = {k: v for k, v in v1_contexts.items() if k in keep}

    v2["contexts"] = {
        name: migrate_context(name, ctx)
        for name, ctx in v1_contexts.items()
    }

    return v2


# -----------------------------------------------------------------------
# Directory-level migration
# -----------------------------------------------------------------------

def migrate_directory(
    input_dir: str,
    output_dir: str,
    context: str | None = None,
    spec_dir_name: str = "app-specs",
) -> None:
    """Migrate an entire v1 directory to v2 format.

    Reads ``app-registry.yaml`` and optionally ``app-defaults.yaml``
    from *input_dir*.  Writes a single ``app-registry.yaml`` (with
    defaults baked in) to *output_dir*, and copies only the app-spec
    subdirectories that are reachable from the target context.
    """
    reg_path = os.path.join(input_dir, "app-registry.yaml")
    if not os.path.isfile(reg_path):
        raise FileNotFoundError(f"No app-registry.yaml in {input_dir}")

    with open(reg_path) as f:
        v1 = yaml.safe_load(f) or {}

    # Load defaults (will be merged, not copied)
    defaults: dict | None = None
    defaults_path = os.path.join(input_dir, "app-defaults.yaml")
    if os.path.isfile(defaults_path):
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
        logger.info("Loaded app-defaults.yaml — will merge into registry")

    # Detect the v1 spec directory name
    # v1 uses "repositories" whose URL often ends with the dir name,
    # but locally the specs are in a subdirectory.  Try common names.
    v1_spec_dir = _detect_spec_dir(input_dir, v1)
    logger.info("Detected v1 spec directory: %s", v1_spec_dir or "(none found)")

    # Migrate the registry YAML
    v2 = migrate_registry(v1, defaults=defaults, spec_dir=spec_dir_name, context=context)

    # Determine which app IDs are in the output
    v1_contexts = v1.get("contexts", {})
    if defaults:
        v1_contexts = merge_defaults_into_contexts(v1_contexts, defaults)
    if context:
        app_ids = collect_app_ids(v1_contexts, context)
    else:
        # All apps across all contexts
        app_ids = set()
        for ctx in v1_contexts.values():
            app_ids.update(ctx.get("apps", {}).keys())

    logger.info("Apps to include: %s", ", ".join(sorted(app_ids)))

    # Write output
    os.makedirs(output_dir, exist_ok=True)

    out_reg = os.path.join(output_dir, "app-registry.yaml")
    with open(out_reg, "w") as f:
        yaml.dump(v2, f, default_flow_style=False, sort_keys=False)
    logger.info("Wrote %s", out_reg)

    # Copy app-spec directories for reachable apps
    if v1_spec_dir:
        out_specs = os.path.join(output_dir, spec_dir_name)
        os.makedirs(out_specs, exist_ok=True)
        copied = 0
        for app_id in sorted(app_ids):
            src = os.path.join(v1_spec_dir, app_id)
            dst = os.path.join(out_specs, app_id)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
                copied += 1
                logger.debug("Copied spec dir: %s", app_id)
            else:
                logger.warning(
                    "No spec directory found for %s at %s", app_id, src
                )
        logger.info("Copied %d app-spec directories to %s", copied, out_specs)
    else:
        logger.warning(
            "Could not find v1 spec directory in %s — "
            "spec files not copied.  Copy them manually.",
            input_dir,
        )


def _detect_spec_dir(input_dir: str, v1: dict) -> str | None:
    """Try to find the local spec directory within the v1 input dir.

    Checks: explicit spec_dir in v1, common names, repository URL hints.
    """
    # Already v2-style spec_dir?
    if "spec_dir" in v1:
        candidate = os.path.join(input_dir, v1["spec_dir"])
        if os.path.isdir(candidate):
            return candidate

    # Common directory names
    for name in ("app-specs", "app_specs", "specs"):
        candidate = os.path.join(input_dir, name)
        if os.path.isdir(candidate):
            return candidate

    # Check repository URLs for hints
    repos = v1.get("repositories", {})
    for _name, repo in repos.items():
        url = repo.get("url", "") if isinstance(repo, dict) else str(repo)
        # e.g. "https://github.com/.../raw/master/app-specs" → "app-specs"
        last_segment = url.rstrip("/").rsplit("/", 1)[-1]
        candidate = os.path.join(input_dir, last_segment)
        if os.path.isdir(candidate):
            return candidate

    return None


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Migrate a Tycho v1 registry directory to v2 format.",
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to v1 registry directory (contains app-registry.yaml)",
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path for v2 output directory",
    )
    parser.add_argument(
        "--context", "-c",
        default=None,
        help=(
            "Target context/product (e.g. 'braini').  "
            "Only this context and its ancestors are included in the output."
        ),
    )
    parser.add_argument(
        "--spec-dir",
        default="app-specs",
        help="Name of the specs subdirectory in the output (default: app-specs)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    migrate_directory(
        input_dir=args.input,
        output_dir=args.output,
        context=args.context,
        spec_dir_name=args.spec_dir,
    )


if __name__ == "__main__":
    main()
