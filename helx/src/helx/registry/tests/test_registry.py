"""Integration tests for the AppRegistry facade."""

import os
import tempfile

import pytest
import yaml

from helx.registry import AppRegistry, RegistryError, SpecLoadError


def _write_registry(tmp_path, registry_dict, defaults_dict=None):
    """Write registry and optional defaults YAML, return paths."""
    reg_path = tmp_path / "registry.yaml"
    reg_path.write_text(yaml.dump(registry_dict))
    def_path = None
    if defaults_dict is not None:
        def_path = tmp_path / "defaults.yaml"
        def_path.write_text(yaml.dump(defaults_dict))
    return str(reg_path), str(def_path) if def_path else None


def _write_compose(tmp_path, spec_dir, app_id, compose_dict, env_text=None):
    """Write a docker-compose.yaml (and optional .env) for an app."""
    app_dir = tmp_path / spec_dir / app_id
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "docker-compose.yaml").write_text(yaml.dump(compose_dict))
    if env_text is not None:
        (app_dir / ".env").write_text(env_text)


@pytest.fixture
def simple_registry(tmp_path):
    """A simple registry with one context and two apps."""
    registry = {
        "spec_dir": "specs",
        "settings": {"registry": "containers.renci.org"},
        "contexts": {
            "common": {
                "apps": {
                    "jupyter": {
                        "name": "Jupyter Notebook",
                        "description": "A notebook",
                        "details": "Detailed info",
                        "docs": "https://jupyter.org",
                        "services": {"jupyter": "8888"},
                        "count": 1,
                    },
                    "filebrowser": {
                        "name": "File Browser",
                        "description": "Browse files",
                        "details": "Browse details",
                        "docs": "https://filebrowser.org",
                        "services": {"filebrowser": "8888"},
                        "count": 1,
                    },
                }
            }
        },
    }
    reg_path, _ = _write_registry(tmp_path, registry)

    # Write compose files
    _write_compose(tmp_path, "specs", "jupyter", {
        "services": {
            "jupyter": {
                "image": "{{ registry }}/jupyter:latest",
                "ports": ["8888:8888"],
            }
        }
    })
    _write_compose(tmp_path, "specs", "filebrowser", {
        "services": {
            "filebrowser": {
                "image": "filebrowser/filebrowser:latest",
                "ports": ["8888"],
            }
        }
    })
    return reg_path


class TestListApps:
    def test_returns_all(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        apps = reg.list_apps()
        assert len(apps) == 2
        ids = {a.app_id for a in apps}
        assert ids == {"jupyter", "filebrowser"}


class TestGetApp:
    def test_metadata(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        app = reg.get_app("jupyter")
        assert app.name == "Jupyter Notebook"
        assert app.description == "A notebook"
        assert app.docs_url == "https://jupyter.org"
        assert app.services == {"jupyter": 8888}

    def test_proxy_rewrite_metadata(self, tmp_path):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "common": {
                    "apps": {
                        "pgadmin": {
                            "name": "pgAdmin",
                            "services": {"pgadmin": "8080"},
                            "proxy-rewrite-rule": True,
                        },
                    }
                }
            },
        }
        reg_path, _ = _write_registry(tmp_path, registry)
        _write_compose(tmp_path, "specs", "pgadmin", {
            "services": {
                "pgadmin": {
                    "image": "pgadmin4:latest",
                    "ports": ["8080"],
                }
            }
        })
        reg = AppRegistry(reg_path, product="common")
        app = reg.get_app("pgadmin")
        assert app.proxy_rewrite_enabled is True
        assert app.proxy_rewrite_target is None

    def test_connect_path_metadata(self, tmp_path):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "common": {
                    "apps": {
                        "pgadmin": {
                            "name": "pgAdmin",
                            "services": {"pgadmin": "8080"},
                            "connectPath": "browser/",
                        },
                    }
                }
            },
        }
        reg_path, _ = _write_registry(tmp_path, registry)
        _write_compose(tmp_path, "specs", "pgadmin", {
            "services": {
                "pgadmin": {
                    "image": "pgadmin4:latest",
                    "ports": ["8080"],
                }
            }
        })
        reg = AppRegistry(reg_path, product="common")
        app = reg.get_app("pgadmin")
        assert app.connect_path == "browser/"

    def test_missing_raises(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        with pytest.raises(KeyError):
            reg.get_app("nonexistent")


class TestGetSpec:
    def test_loads_and_renders(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        spec = reg.get_spec("jupyter")
        assert spec["services"]["jupyter"]["image"] == "containers.renci.org/jupyter:latest"

    def test_caches(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        spec1 = reg.get_spec("jupyter")
        spec2 = reg.get_spec("jupyter")
        assert spec1 is spec2

    def test_missing_spec_raises(self, tmp_path):
        registry = {
            "spec_dir": "nonexistent",
            "contexts": {
                "common": {"apps": {"app1": {"name": "App", "services": {"app1": "80"}}}}
            },
        }
        reg_path, _ = _write_registry(tmp_path, registry)
        reg = AppRegistry(reg_path, product="common")
        with pytest.raises(SpecLoadError):
            reg.get_spec("app1")


class TestGetSettings:
    def test_loads_env_file(self, tmp_path):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "common": {
                    "apps": {
                        "myapp": {
                            "name": "My App",
                            "services": {"myapp": "80"},
                            "env": {"EXTRA": "val"},
                        }
                    }
                }
            },
        }
        reg_path, _ = _write_registry(tmp_path, registry)
        _write_compose(
            tmp_path, "specs", "myapp",
            {"services": {"myapp": {"image": "myapp:latest"}}},
            env_text="FOO=bar\nBAZ=qux\n",
        )
        reg = AppRegistry(reg_path, product="common")
        settings = reg.get_settings("myapp")
        assert settings["FOO"] == "bar"
        assert settings["BAZ"] == "qux"
        assert settings["EXTRA"] == "val"

    def test_missing_env_returns_registry_env_only(self, tmp_path):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "common": {
                    "apps": {
                        "myapp": {
                            "name": "App",
                            "services": {"myapp": "80"},
                            "env": {"KEY": "value"},
                        }
                    }
                }
            },
        }
        reg_path, _ = _write_registry(tmp_path, registry)
        _write_compose(
            tmp_path, "specs", "myapp",
            {"services": {"myapp": {"image": "myapp:latest"}}},
        )
        reg = AppRegistry(reg_path, product="common")
        settings = reg.get_settings("myapp")
        assert settings == {"KEY": "value"}


class TestBuildHelxapp:
    def test_end_to_end(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        spec = reg.build_helxapp("jupyter")
        assert spec.app_class_name == "jupyter"
        assert len(spec.services) == 1
        assert spec.services[0].image == "containers.renci.org/jupyter:latest"
        assert spec.services[0].ports[0].container_port == 8888


class TestBuildHelxinst:
    def test_basic(self, simple_registry):
        reg = AppRegistry(simple_registry, product="common")
        spec = reg.build_helxinst("jupyter", "alice", {"cpu": "2", "memory": "4Gi"})
        assert spec.app_name == "jupyter"
        assert spec.user_name == "alice"
        assert spec.resources["jupyter"].request.cpu == "2"


class TestInheritance:
    def test_extends_product(self, tmp_path):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "sys": {
                    "apps": {
                        "jupyter": {
                            "ext": {"kube": {"livenessProbe": {"cmd": ["pgrep"]}}},
                        }
                    }
                },
                "common": {
                    "extends": ["sys"],
                    "apps": {
                        "jupyter": {
                            "name": "Jupyter",
                            "description": "Notebook",
                            "details": "Info",
                            "docs": "https://jupyter.org",
                            "services": {"jupyter": "8888"},
                            "count": 1,
                        },
                    },
                },
                "braini": {
                    "extends": ["common"],
                    "jupyter": {
                        "securityContext": {
                            "runAsUser": 1000,
                            "runAsGroup": 1000,
                            "fsGroup": 1000,
                        },
                    },
                },
            },
        }
        reg_path, _ = _write_registry(tmp_path, registry)
        _write_compose(tmp_path, "specs", "jupyter", {
            "services": {"jupyter": {"image": "jupyter:latest", "ports": ["8888"]}}
        })
        reg = AppRegistry(reg_path, product="braini")
        app = reg.get_app("jupyter")
        assert app.name == "Jupyter"
        assert app.security_context.run_as_user == 1000
        assert app.ext["kube"]["livenessProbe"]["cmd"] == ["pgrep"]


class TestDefaults:
    def test_defaults_applied(self, tmp_path):
        registry = {
            "spec_dir": "specs",
            "contexts": {
                "common": {
                    "apps": {
                        "app1": {"name": "App", "services": {"app1": "80"}},
                    }
                }
            },
        }
        defaults = {"count": 3, "details": "default details"}
        reg_path, def_path = _write_registry(tmp_path, registry, defaults)
        _write_compose(tmp_path, "specs", "app1", {
            "services": {"app1": {"image": "app:latest"}}
        })
        reg = AppRegistry(reg_path, defaults_path=def_path, product="common")
        app = reg.get_app("app1")
        assert app.count == 3
        assert app.details == "default details"
