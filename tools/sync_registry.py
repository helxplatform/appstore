#!/usr/bin/env python3
"""Sync an app-registry repo from GitHub to a local directory (PVC).

Clones (or pulls) a git repository containing the app registry and
app specs, placing the contents at a target directory that appstore
reads from at runtime (typically a PVC mount).

Usage::

    # Full clone to PVC mount
    python -m tools.sync_registry \\
        --repo  https://github.com/helxplatform/helx-apps.git \\
        --branch master \\
        --dir   app-specs \\
        --target /data/registry

    # Result on the PVC:
    #   /data/registry/app-registry.yaml
    #   /data/registry/app-defaults.yaml   (if present)
    #   /data/registry/app-specs/
    #       jupyter-ds/docker-compose.yaml
    #       jupyter-ds/icon.png
    #       rstudio/docker-compose.yaml
    #       ...

Appstore reads from the PVC via environment variables::

    APP_REGISTRY_PATH=/data/registry/app-registry.yaml
    APP_DEFAULTS_PATH=/data/registry/app-defaults.yaml

Volume / mount (to be configured in the appstore Deployment):

    Volume:
        name: app-registry
        persistentVolumeClaim:
            claimName: app-registry-pvc

    VolumeMount:
        name: app-registry
        mountPath: /data/registry
        readOnly: true     # appstore only reads

This script is intended to run as an init-container or a CronJob
that populates the PVC before (or alongside) the appstore pod.
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import subprocess
import sys
import tempfile

logger = logging.getLogger(__name__)

# Files to copy from the repo root to the target directory.
_REGISTRY_FILES = [
    "app-registry.yaml",
    "app-defaults.yaml",
]


def git(*args: str, cwd: str | None = None) -> str:
    """Run a git command, return stdout."""
    cmd = ["git"] + list(args)
    logger.debug("$ %s", " ".join(cmd))
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def sync(
    repo: str,
    branch: str,
    specs_dir: str,
    target: str,
    migrate: bool = False,
    sparse: bool = True,
) -> None:
    """Clone the repo and copy registry files + specs to *target*.

    :param repo: Git clone URL.
    :param branch: Branch name to checkout.
    :param specs_dir: Subdirectory within the repo that contains app
        spec directories (e.g. ``app-specs``).
    :param target: Local directory to populate (the PVC mount point).
    :param migrate: If True, run v1→v2 migration on the registry YAML
        after copying.
    :param sparse: If True, use sparse checkout to only fetch the
        files we need (faster for large repos).
    """
    os.makedirs(target, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="registry-sync-") as tmp:
        logger.info("Cloning %s (branch: %s) into %s", repo, branch, tmp)

        if sparse:
            git("init", cwd=tmp)
            git("remote", "add", "origin", repo, cwd=tmp)
            git("config", "core.sparseCheckout", "true", cwd=tmp)
            sparse_file = os.path.join(tmp, ".git", "info", "sparse-checkout")
            with open(sparse_file, "w") as f:
                # Fetch registry files at root + the specs directory
                for name in _REGISTRY_FILES:
                    f.write(f"{name}\n")
                f.write(f"{specs_dir}/\n")
            git("fetch", "--depth=1", "origin", branch, cwd=tmp)
            git("checkout", f"origin/{branch}", cwd=tmp)
        else:
            git(
                "clone",
                "--depth=1",
                "--branch", branch,
                "--single-branch",
                repo,
                tmp,
            )

        # Copy registry files
        for name in _REGISTRY_FILES:
            src = os.path.join(tmp, name)
            if os.path.isfile(src):
                dst = os.path.join(target, name)
                shutil.copy2(src, dst)
                logger.info("Copied %s → %s", name, dst)
            else:
                logger.debug("Optional file %s not found in repo, skipping", name)

        # Copy specs directory
        src_specs = os.path.join(tmp, specs_dir)
        dst_specs = os.path.join(target, specs_dir)
        if os.path.isdir(src_specs):
            if os.path.exists(dst_specs):
                shutil.rmtree(dst_specs)
            shutil.copytree(src_specs, dst_specs)
            count = sum(1 for _, _, files in os.walk(dst_specs) for _ in files)
            logger.info("Copied %s/ → %s (%d files)", specs_dir, dst_specs, count)
        else:
            logger.warning(
                "Specs directory %r not found in repo — "
                "check --dir argument",
                specs_dir,
            )

    # Optionally migrate v1 → v2
    if migrate:
        _run_migration(target, specs_dir)

    logger.info("Sync complete.  Target: %s", target)


def _run_migration(target: str, specs_dir: str) -> None:
    """Run the v1→v2 migration on the registry file in *target*."""
    from tools.migrate_registry import migrate_registry

    import yaml

    reg_path = os.path.join(target, "app-registry.yaml")
    if not os.path.isfile(reg_path):
        logger.warning("No app-registry.yaml found at %s — skipping migration", target)
        return

    with open(reg_path) as f:
        v1 = yaml.safe_load(f) or {}

    # Already v2?
    if v1.get("api") == "Tycho" and v1.get("spec_dir"):
        logger.info("Registry already appears to be v2 format, skipping migration")
        return

    # Load and bake in defaults if present
    defaults = None
    defaults_path = os.path.join(target, "app-defaults.yaml")
    if os.path.isfile(defaults_path):
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}

    v2 = migrate_registry(v1, defaults=defaults, spec_dir=specs_dir)
    with open(reg_path, "w") as f:
        yaml.dump(v2, f, default_flow_style=False, sort_keys=False)
    logger.info("Migrated %s to v2 format", reg_path)

    # Remove defaults file — values are now baked into the registry
    if defaults is not None:
        os.remove(defaults_path)
        logger.info("Removed %s (defaults baked into registry)", defaults_path)


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Sync an app-registry GitHub repo to a local PVC directory.",
    )
    parser.add_argument(
        "--repo", "-r",
        required=True,
        help="Git clone URL (e.g. https://github.com/helxplatform/helx-apps.git)",
    )
    parser.add_argument(
        "--branch", "-b",
        default="master",
        help="Branch to checkout (default: master)",
    )
    parser.add_argument(
        "--dir", "-d",
        default="app-specs",
        help="Subdirectory in repo containing app specs (default: app-specs)",
    )
    parser.add_argument(
        "--target", "-t",
        required=True,
        help="Local directory to populate (the PVC mount point)",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Run v1→v2 migration on the registry YAML after syncing",
    )
    parser.add_argument(
        "--no-sparse",
        action="store_true",
        help="Use full clone instead of sparse checkout",
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

    sync(
        repo=args.repo,
        branch=args.branch,
        specs_dir=args.dir,
        target=args.target,
        migrate=args.migrate,
        sparse=not args.no_sparse,
    )


if __name__ == "__main__":
    main()
