"""App registry module — resolves the YAML app registry into typed specs."""

from __future__ import annotations

import os

from kube.models import HelxAppSpec, HelxInstSpec, SecurityContext
from registry.exceptions import RegistryError, SpecLoadError
from registry.loader import RegistryLoader
from registry.models import ResolvedApp
from registry.resolver import resolve_apps
from registry.spec_builder import build_helxapp_spec, build_helxinst_spec


def _to_resolved_app(app_id: str, raw: dict) -> ResolvedApp:
    """Convert a raw resolved app dict to a ResolvedApp dataclass."""
    sc_raw = raw.get("securityContext")
    security_context = None
    if sc_raw and isinstance(sc_raw, dict):
        security_context = SecurityContext(
            run_as_user=_int_or_none(sc_raw.get("runAsUser")),
            run_as_group=_int_or_none(sc_raw.get("runAsGroup")),
            fs_group=_int_or_none(sc_raw.get("fsGroup")),
        )

    services = raw.get("services", {})
    services = {k: int(v) for k, v in services.items()}

    return ResolvedApp(
        app_id=app_id,
        name=raw.get("name", app_id),
        description=raw.get("description", ""),
        details=raw.get("details", ""),
        docs_url=raw.get("docs", ""),
        spec_path=raw.get("spec", ""),
        icon_path=raw.get("icon", ""),
        services=services,
        count=raw.get("count", 1),
        service_account=raw.get("serviceAccount"),
        security_context=security_context,
        env=raw.get("env", {}),
        ext=raw.get("ext"),
    )


def _int_or_none(val) -> int | None:
    """Convert to int, treating empty strings and None as None."""
    if val is None or val == "":
        return None
    return int(val)


class AppRegistry:
    """Facade for app-registry processing.

    Replaces TychoContext for app-catalog concerns.  Loads the registry
    YAML, resolves the product context, and provides access to resolved
    apps plus CRD spec builders.
    """

    def __init__(
        self,
        registry_path: str = "app-registry.yaml",
        defaults_path: str | None = None,
        product: str = "common",
    ):
        self.loader = RegistryLoader()
        raw_registry = self.loader.load_config(registry_path)
        registry_dir = os.path.dirname(os.path.abspath(registry_path))

        raw_defaults: dict = {}
        if defaults_path and os.path.isfile(defaults_path):
            raw_defaults = self.loader.load_config(defaults_path)

        self.settings = raw_registry.get("settings", {})
        self._raw_apps = resolve_apps(
            raw_registry, raw_defaults, product, registry_dir
        )
        self.apps: dict[str, ResolvedApp] = {
            k: _to_resolved_app(k, v) for k, v in self._raw_apps.items()
        }

    def get_app(self, app_id: str) -> ResolvedApp:
        """Return a resolved app by ID, or raise KeyError."""
        return self.apps[app_id]

    def list_apps(self) -> list[ResolvedApp]:
        """Return all resolved apps."""
        return list(self.apps.values())

    def get_spec(self, app_id: str) -> dict:
        """Lazy-load and cache the docker-compose spec from disk."""
        app = self.get_app(app_id)
        if app.spec_obj is not None:
            return app.spec_obj

        # Build template context: registry settings + per-app variables.
        # Compose specs may use Jinja2 macros like {{ system_port }},
        # {{ helx_registry }}, etc.
        context = dict(self.settings)
        if app.services:
            # system_port = first service port (matches legacy tycho behaviour)
            first_port = next(iter(app.services.values()), None)
            context["system_port"] = first_port if first_port is not None else 8000
        else:
            context["system_port"] = 8000

        try:
            spec = self.loader.load_spec(app.spec_path, context)
        except FileNotFoundError as exc:
            raise SpecLoadError(
                f"Spec file not found for {app_id!r}: {app.spec_path}",
                details=str(exc),
            ) from exc
        app.spec_obj = spec
        return spec

    def get_settings(self, app_id: str) -> dict[str, str]:
        """Lazy-load the .env, merge registry env, return as dict."""
        app = self.get_app(app_id)
        if app.settings_text is None:
            app.settings_text = self.loader.load_settings(app.spec_path)

        settings: dict[str, str] = {}
        # Parse .env text into a dict
        for line in app.settings_text.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                settings[k.strip()] = v.strip()

        # Merge registry-level env overrides (app wins)
        if app.env:
            settings.update(app.env)
        return settings

    def build_helxapp(self, app_id: str) -> HelxAppSpec:
        """Load spec, convert to HelxAppSpec."""
        app = self.get_app(app_id)
        compose = self.get_spec(app_id)
        return build_helxapp_spec(app, compose)

    def build_helxinst(
        self,
        app_id: str,
        username: str,
        resource_request: dict | None = None,
        security_context: SecurityContext | None = None,
        environment: dict[str, str] | None = None,
    ) -> HelxInstSpec:
        """Build a HelxInstSpec for launching.

        :param environment: Per-instance environment variables (e.g.
            ``NB_PREFIX``, ``GUID``, ``ACCESS_TOKEN``).  The controller
            merges these with app-level env; instance values win.
        """
        app = self.get_app(app_id)
        return build_helxinst_spec(
            app, username, resource_request, security_context, environment
        )


_registry_instance: AppRegistry | None = None


def get_registry() -> AppRegistry:
    """Return the process-wide AppRegistry singleton.

    Reads configuration from environment variables / Django settings on
    first call; subsequent calls return the cached instance.

    Environment variables:
        ``APP_REGISTRY_PATH`` — directory containing ``app-registry.yaml``
            and the ``app-specs/`` subdirectory (default: ``"."``).

    Falls back to Django ``settings.APPLICATION_BRAND`` for the product
    context, defaulting to ``"common"``.
    """
    global _registry_instance
    if _registry_instance is not None:
        return _registry_instance

    try:
        from django.conf import settings as django_settings
        product = getattr(django_settings, "APPLICATION_BRAND", "common")
    except Exception:
        product = os.environ.get("APPLICATION_BRAND", "common")

    registry_dir = os.environ.get("APP_REGISTRY_PATH", ".")
    _registry_instance = AppRegistry(
        registry_path=os.path.join(registry_dir, "app-registry.yaml"),
        defaults_path=os.path.join(registry_dir, "app-defaults.yaml"),
        product=product,
    )
    return _registry_instance


__all__ = [
    "AppRegistry",
    "ResolvedApp",
    "RegistryError",
    "SpecLoadError",
    "get_registry",
]
