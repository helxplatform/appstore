"""Tests for the registry resolution algorithm — pure logic, no I/O."""

import pytest

from helx.registry.exceptions import RegistryError
from helx.registry.resolver import (
    apply_defaults,
    resolve_apps,
    resolve_context,
    resolve_paths,
)


# -- Fixtures: synthetic registries ------------------------------------------

def _registry(*context_items, spec_dir="."):
    """Build a minimal registry dict."""
    return {
        "spec_dir": spec_dir,
        "contexts": dict(context_items),
    }


class TestResolveContext:
    def test_extends_single_base(self):
        contexts = {
            "base": {"apps": {"app1": {"name": "App One", "port": 8080}}},
            "child": {"extends": ["base"]},
        }
        apps = resolve_context(contexts, "child")
        assert "app1" in apps
        assert apps["app1"]["name"] == "App One"

    def test_extends_chain(self):
        contexts = {
            "grandparent": {"apps": {"a": {"level": "gp"}}},
            "parent": {"extends": ["grandparent"], "apps": {"b": {"level": "p"}}},
            "child": {"extends": ["parent"], "apps": {"c": {"level": "c"}}},
        }
        apps = resolve_context(contexts, "child")
        assert set(apps) == {"a", "b", "c"}
        assert apps["a"]["level"] == "gp"

    def test_extends_child_overrides_parent(self):
        contexts = {
            "base": {"apps": {"app1": {"name": "Base", "port": 80}}},
            "child": {
                "extends": ["base"],
                "apps": {"app1": {"name": "Child"}},
            },
        }
        apps = resolve_context(contexts, "child")
        assert apps["app1"]["name"] == "Child"
        # port inherited from base via deep merge
        assert apps["app1"]["port"] == 80

    def test_extends_deep_merges_properties(self):
        """Parent defines probes, child defines ports — both present."""
        contexts = {
            "sys": {
                "apps": {
                    "jupyter": {
                        "ext": {"kube": {"livenessProbe": {"cmd": ["pgrep"]}}},
                    }
                }
            },
            "child": {
                "extends": ["sys"],
                "apps": {
                    "jupyter": {
                        "name": "Jupyter",
                        "services": {"jupyter": "8888"},
                    }
                },
            },
        }
        apps = resolve_context(contexts, "child")
        assert apps["jupyter"]["name"] == "Jupyter"
        assert apps["jupyter"]["services"] == {"jupyter": "8888"}
        assert apps["jupyter"]["ext"]["kube"]["livenessProbe"]["cmd"] == ["pgrep"]

    def test_extends_overlay_context(self):
        """A context with only overlays (like legacy sys) works via extends."""
        contexts = {
            "sys": {"apps": {"app1": {"ext": {"kube": {"probe": True}}}}},
            "main": {"apps": {"app1": {"name": "App", "port": 80}}},
            "product": {"extends": ["sys", "main"]},
        }
        apps = resolve_context(contexts, "product")
        assert apps["app1"]["name"] == "App"
        assert apps["app1"]["ext"]["kube"]["probe"] is True

    def test_extends_overlay_adds_new_app(self):
        """An overlay context with an app not in child — app appears."""
        contexts = {
            "extra": {"apps": {"bonus": {"name": "Bonus App"}}},
            "main": {"apps": {"app1": {"name": "Main"}}},
            "product": {"extends": ["extra", "main"]},
        }
        apps = resolve_context(contexts, "product")
        assert "bonus" in apps
        assert "app1" in apps

    def test_extends_order_matters(self):
        """extends: [a, b] — b's values override a's for the same field."""
        contexts = {
            "a": {"apps": {"app1": {"name": "From A", "source": "a"}}},
            "b": {"apps": {"app1": {"name": "From B"}}},
            "child": {"extends": ["a", "b"]},
        }
        apps = resolve_context(contexts, "child")
        assert apps["app1"]["name"] == "From B"
        assert apps["app1"]["source"] == "a"  # only in a, not overridden

    def test_context_override_security_context(self):
        """Bare keys matching app IDs are merged as overrides."""
        contexts = {
            "base": {"apps": {"jupyter": {"name": "Jupyter", "port": 8888}}},
            "product": {
                "extends": ["base"],
                "jupyter": {
                    "securityContext": {"runAsUser": 1000, "fsGroup": 1000},
                },
            },
        }
        apps = resolve_context(contexts, "product")
        assert apps["jupyter"]["securityContext"]["runAsUser"] == 1000
        assert apps["jupyter"]["name"] == "Jupyter"

    def test_cycle_detection(self):
        contexts = {
            "a": {"extends": ["b"]},
            "b": {"extends": ["a"]},
        }
        with pytest.raises(RegistryError, match="Cycle"):
            resolve_context(contexts, "a")

    def test_self_cycle_detection(self):
        contexts = {"a": {"extends": ["a"]}}
        with pytest.raises(RegistryError, match="Cycle"):
            resolve_context(contexts, "a")

    def test_reserved_keys_not_treated_as_overrides(self):
        """Keys like 'name' and 'description' should not be merged as app overrides."""
        contexts = {
            "product": {
                "name": "My Product",
                "description": "A product",
                "apps": {"name": {"port": 80}},  # app named "name" — tricky
            },
        }
        apps = resolve_context(contexts, "product")
        # The app "name" should exist with just {port: 80}, not merged
        # with the context's "name" string (which isn't a dict anyway)
        assert apps["name"]["port"] == 80


class TestApplyDefaults:
    def test_defaults_merged(self):
        apps = {
            "app1": {"name": "App"},
            "app2": {"name": "App2"},
        }
        defaults = {"count": 1, "details": "default details"}
        apply_defaults(apps, defaults)
        assert apps["app1"]["count"] == 1
        assert apps["app1"]["details"] == "default details"
        assert apps["app2"]["count"] == 1

    def test_app_wins_on_conflict(self):
        apps = {"app1": {"name": "MyApp", "count": 5}}
        defaults = {"name": "Default", "count": 1}
        apply_defaults(apps, defaults)
        assert apps["app1"]["name"] == "MyApp"
        assert apps["app1"]["count"] == 5


class TestResolvePaths:
    def test_relative_spec_dir(self):
        apps = {"myapp": {"name": "Test"}}
        resolve_paths(apps, "app-specs", "/opt/registry")
        assert apps["myapp"]["spec"] == "/opt/registry/app-specs/myapp/docker-compose.yaml"
        assert apps["myapp"]["icon"] == "/opt/registry/app-specs/myapp/icon.png"

    def test_absolute_spec_dir(self):
        apps = {"myapp": {"name": "Test"}}
        resolve_paths(apps, "/data/specs", "/opt/registry")
        assert apps["myapp"]["spec"] == "/data/specs/myapp/docker-compose.yaml"

    def test_explicit_spec_not_overwritten(self):
        apps = {"myapp": {"spec": "/custom/path/compose.yaml"}}
        resolve_paths(apps, "app-specs", "/opt")
        assert apps["myapp"]["spec"] == "/custom/path/compose.yaml"
        assert apps["myapp"]["icon"] == "/custom/path/icon.png"


class TestResolveApps:
    def test_unknown_product_raises(self):
        registry = {"contexts": {"common": {"apps": {}}}}
        with pytest.raises(RegistryError, match="Unknown product"):
            resolve_apps(registry, {}, "nonexistent")

    def test_full_pipeline(self):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "base": {"apps": {"app1": {"name": "App One"}}},
                "product": {
                    "extends": ["base"],
                    "apps": {"app2": {"name": "App Two"}},
                },
            },
        }
        defaults = {"count": 1}
        apps = resolve_apps(registry, defaults, "product", "/opt")
        assert "app1" in apps
        assert "app2" in apps
        assert apps["app1"]["count"] == 1
        assert apps["app1"]["spec"] == "/opt/specs/app1/docker-compose.yaml"
