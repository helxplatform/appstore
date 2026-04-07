"""Intermediate representation for resolved app registry entries."""

from __future__ import annotations

from dataclasses import dataclass, field

from kube.models import SecurityContext


@dataclass
class ResolvedApp:
    """A fully resolved app entry from the registry.

    This is the intermediate representation after registry resolution
    and before conversion to CRD specs (HelxAppSpec / HelxInstSpec).
    """

    app_id: str
    name: str
    description: str
    details: str
    docs_url: str
    spec_path: str
    icon_path: str
    services: dict[str, int]
    count: int = 1
    service_account: str | None = None
    security_context: SecurityContext | None = None
    env: dict[str, str] = field(default_factory=dict)
    ext: dict | None = None
    proxy_rewrite_enabled: bool = False
    proxy_rewrite_target: str | None = None
    connect_path: str = ""

    # Lazily populated by the loader
    spec_obj: dict | None = field(default=None, repr=False)
    settings_text: str | None = field(default=None, repr=False)
