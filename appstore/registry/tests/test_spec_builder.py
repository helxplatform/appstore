"""Tests for spec_builder — converting resolved apps to CRD specs."""

import pytest

from kube.models import SecurityContext
from registry.models import ResolvedApp
from registry.spec_builder import build_helxapp_spec, build_helxinst_spec


def _app(**overrides) -> ResolvedApp:
    defaults = dict(
        app_id="jupyter",
        name="Jupyter",
        description="A notebook",
        details="Details",
        docs_url="https://docs",
        spec_path="/specs/jupyter/docker-compose.yaml",
        icon_path="/specs/jupyter/icon.png",
        services={"jupyter": 8888},
        count=1,
    )
    defaults.update(overrides)
    return ResolvedApp(**defaults)


def _compose(**service_overrides) -> dict:
    svc = {"image": "jupyter/scipy:latest", "ports": ["8888:8888"]}
    svc.update(service_overrides)
    return {"services": {"jupyter": svc}}


class TestBuildHelxappSpec:
    def test_basic_compose(self):
        app = _app()
        spec = build_helxapp_spec(app, _compose())
        assert spec.app_class_name == "jupyter"
        assert len(spec.services) == 1
        svc = spec.services[0]
        assert svc.name == "jupyter"
        assert svc.image == "jupyter/scipy:latest"
        assert svc.ports[0].container_port == 8888
        assert svc.ports[0].port == 8888

    def test_with_environment(self):
        compose = _compose(environment={"NB_USER": "alice", "NB_UID": "1000"})
        spec = build_helxapp_spec(_app(), compose)
        assert spec.services[0].environment["NB_USER"] == "alice"
        assert spec.services[0].environment["NB_UID"] == "1000"

    def test_with_environment_list(self):
        compose = _compose(environment=["NB_USER=alice", "NB_UID=1000"])
        spec = build_helxapp_spec(_app(), compose)
        assert spec.services[0].environment["NB_USER"] == "alice"

    def test_with_command_string(self):
        compose = _compose(command="start-notebook.sh --no-browser")
        spec = build_helxapp_spec(_app(), compose)
        assert spec.services[0].command == ["start-notebook.sh", "--no-browser"]

    def test_with_command_list(self):
        compose = _compose(command=["start.sh", "--port=8888"])
        spec = build_helxapp_spec(_app(), compose)
        assert spec.services[0].command == ["start.sh", "--port=8888"]

    def test_with_volumes(self):
        compose = _compose(volumes=["data:/home/jovyan", "scratch:/tmp"])
        spec = build_helxapp_spec(_app(), compose)
        assert spec.services[0].volumes == {"data": "data:/home/jovyan", "scratch": "scratch:/tmp"}

    def test_with_security_context(self):
        sc = SecurityContext(run_as_user=1000, fs_group=100)
        app = _app(security_context=sc)
        spec = build_helxapp_spec(app, _compose())
        assert spec.services[0].security_context.run_as_user == 1000

    def test_multiple_services(self):
        compose = {
            "services": {
                "jupyter": {"image": "jupyter:latest", "ports": ["8888"]},
                "sidecar": {"image": "sidecar:latest"},
            }
        }
        app = _app(services={"jupyter": 8888})
        spec = build_helxapp_spec(app, compose)
        assert len(spec.services) == 2
        names = {s.name for s in spec.services}
        assert names == {"jupyter", "sidecar"}

    def test_secrets_become_secrets_from(self):
        compose = {
            "services": {
                "jupyter": {
                    "image": "jupyter:latest",
                    "ports": ["8888"],
                    "secrets": ["db-creds"],
                },
            },
            "secrets": {
                "db-creds": {"external": True},
            },
        }
        app = _app()
        spec = build_helxapp_spec(app, compose)
        assert spec.services[0].secrets_from == ["db-creds"]

    def test_secrets_from_in_to_dict(self):
        compose = {
            "services": {
                "jupyter": {
                    "image": "jupyter:latest",
                    "secrets": ["pgadmin-env"],
                },
            },
            "secrets": {
                "pgadmin-env": {"external": True},
            },
        }
        app = _app()
        spec = build_helxapp_spec(app, compose)
        d = spec.to_dict()
        assert d["services"][0]["secretsFrom"] == ["pgadmin-env"]

    def test_no_secrets_omits_secrets_from(self):
        spec = build_helxapp_spec(_app(), _compose())
        d = spec.to_dict()
        assert "secretsFrom" not in d["services"][0]

    def test_ambassador_added_for_service_with_port(self):
        spec = build_helxapp_spec(_app(), _compose())
        svc = spec.services[0]
        assert svc.ambassador is not None
        assert "{{ .system.AppClassName }}" in svc.ambassador.prefix
        assert "{{ .system.UserName }}" in svc.ambassador.prefix

    def test_ambassador_in_to_dict(self):
        spec = build_helxapp_spec(_app(), _compose())
        d = spec.to_dict()
        assert "ambassador" in d["services"][0]
        assert d["services"][0]["ambassador"]["prefix"].startswith("/private/")

    def test_ambassador_only_on_first_service_with_port(self):
        compose = {
            "services": {
                "main": {"image": "app:latest", "ports": ["8888"]},
                "sidecar": {"image": "sidecar:latest", "ports": ["9090"]},
            }
        }
        app = _app(services={"main": 8888, "sidecar": 9090})
        spec = build_helxapp_spec(app, compose)
        services_by_name = {s.name: s for s in spec.services}
        assert services_by_name["main"].ambassador is not None
        assert services_by_name["sidecar"].ambassador is None

    def test_no_ambassador_for_service_without_port(self):
        compose = {"services": {"worker": {"image": "worker:latest"}}}
        app = _app(services={})
        spec = build_helxapp_spec(app, compose)
        assert spec.services[0].ambassador is None


class TestBuildHelxinstSpec:
    def test_basic(self):
        app = _app()
        spec = build_helxinst_spec(app, "alice")
        assert spec.app_name == "jupyter"
        assert spec.user_name == "alice"
        assert spec.resources == {}
        assert spec.security_context is None

    def test_with_resources(self):
        app = _app()
        spec = build_helxinst_spec(
            app, "alice", resource_request={"cpu": "2", "memory": "4Gi"}
        )
        assert "jupyter" in spec.resources
        assert spec.resources["jupyter"].request.cpu == "2"
        assert spec.resources["jupyter"].request.memory == "4Gi"

    def test_instance_security_context_overrides_app(self):
        app_sc = SecurityContext(run_as_user=1000)
        inst_sc = SecurityContext(run_as_user=2000)
        app = _app(security_context=app_sc)
        spec = build_helxinst_spec(app, "alice", security_context=inst_sc)
        assert spec.security_context.run_as_user == 2000

    def test_falls_back_to_app_security_context(self):
        app_sc = SecurityContext(run_as_user=1000)
        app = _app(security_context=app_sc)
        spec = build_helxinst_spec(app, "alice")
        assert spec.security_context.run_as_user == 1000

    def test_with_gpu(self):
        app = _app()
        spec = build_helxinst_spec(
            app, "alice", resource_request={"cpu": "1", "gpu": "1"}
        )
        assert spec.resources["jupyter"].request.gpu == "1"
