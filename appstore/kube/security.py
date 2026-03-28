"""
Security context resolution.

Implements the helxapp-controller three-tier priority:

1. Explicit per-instance override (highest priority)
2. HTTP GET to a user-handle URL
3. Omitted (no security context)
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from kube.exceptions import SecurityContextError
from kube.models import SecurityContext

logger = logging.getLogger(__name__)


def resolve_security_context(
    instance_override: SecurityContext | None = None,
    user_handle_url: str | None = None,
    timeout: float = 5.0,
) -> SecurityContext | None:
    """Return the effective security context using priority rules.

    :param instance_override: Explicit values from the instance request.
    :param user_handle_url: URL to GET for user-level context.
    :param timeout: HTTP timeout in seconds.
    :returns: Resolved :class:`SecurityContext` or ``None``.
    """
    if instance_override is not None:
        return instance_override

    if user_handle_url:
        return _fetch_security_context(user_handle_url, timeout)

    return None


def _fetch_security_context(url: str, timeout: float) -> SecurityContext | None:
    """Fetch security context from a user-handle URL."""
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return SecurityContext(
            run_as_user=_int_or_none(data.get("runAsUser")),
            run_as_group=_int_or_none(data.get("runAsGroup")),
            fs_group=_int_or_none(data.get("fsGroup")),
            supplemental_groups=[
                int(g) for g in data.get("supplementalGroups", [])
            ]
            or None,
        )
    except Exception as exc:
        raise SecurityContextError(
            message=f"Failed to fetch security context from {url}",
            details=str(exc),
        ) from exc


def _int_or_none(val: Any) -> int | None:
    if val is None:
        return None
    return int(val)
