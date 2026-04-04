"""Tests for appspec.parser — compose dict parsing."""

import pytest

from appspec.parser import (
    parse_compose,
    parse_environment,
    parse_helx_resources,
    parse_ports,
    parse_probe,
    parse_resources,
    parse_service,
    parse_service_secrets,
    parse_top_level_secrets,
    parse_volumes,
)
from appspec.exceptions import ParseError


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

def _svc(**overrides):
    """Minimal valid service dict."""
    d = {"image": "myapp:latest"}
    d.update(overrides)
    return d


def _compose(*services, **top_level):
    """Build a compose dict from (name, svc_dict) pairs."""
    spec = {"services": {name: svc for name, svc in services}}
    spec.update(top_level)
    return spec


# -----------------------------------------------------------------------
# parse_compose
# -----------------------------------------------------------------------

class TestParseCompose:
    def test_parse_minimal_service(self):
        spec = _compose(("web", _svc()))
        app = parse_compose(spec)
        assert len(app.services) == 1
        assert app.services[0].name == "web"
        assert app.services[0].image == "myapp:latest"

    def test_parse_multi_service(self):
        spec = _compose(
            ("web", _svc()),
            ("db", _svc(image="postgres:14")),
        )
        app = parse_compose(spec)
        assert len(app.services) == 2
        names = {s.name for s in app.services}
        assert names == {"web", "db"}

    def test_missing_services_raises(self):
        with pytest.raises(ParseError):
            parse_compose({})

    def test_missing_image_raises(self):
        spec = _compose(("web", {"ports": ["8080"]}))
        with pytest.raises(ParseError):
            parse_compose(spec)


# -----------------------------------------------------------------------
# Ports
# -----------------------------------------------------------------------

class TestParsePorts:
    def test_host_container(self):
        assert parse_ports(["8888:8888"]) == [8888]

    def test_container_only(self):
        assert parse_ports(["8888"]) == [8888]

    def test_int(self):
        assert parse_ports([8888]) == [8888]

    def test_different_mapping(self):
        assert parse_ports(["3000:8080"]) == [8080]


# -----------------------------------------------------------------------
# Environment
# -----------------------------------------------------------------------

class TestParseEnvironment:
    def test_dict(self):
        assert parse_environment({"KEY": "val"}) == {"KEY": "val"}

    def test_list(self):
        assert parse_environment(["K=V"]) == {"K": "V"}

    def test_flag_only(self):
        assert parse_environment(["FLAG"]) == {"FLAG": ""}

    def test_empty_dict(self):
        assert parse_environment({}) == {}

    def test_empty_list(self):
        assert parse_environment([]) == {}


# -----------------------------------------------------------------------
# Volumes
# -----------------------------------------------------------------------

class TestParseVolumes:
    def test_pvc(self):
        vols = parse_volumes(["pvc://mypvc:/data"])
        assert len(vols) == 1
        v = vols[0]
        assert v.source == "mypvc"
        assert v.mount_path == "/data"
        assert v.sub_path is None
        assert v.is_pvc is True

    def test_pvc_subpath(self):
        vols = parse_volumes(["pvc://mypvc/sub:/data"])
        v = vols[0]
        assert v.source == "mypvc"
        assert v.sub_path == "sub"

    def test_plain(self):
        vols = parse_volumes(["data-vol:/data"])
        v = vols[0]
        assert v.source == "data-vol"
        assert v.mount_path == "/data"
        assert v.is_pvc is False

    def test_with_options(self):
        vols = parse_volumes(["pvc://mypvc:/data,rwx,retain"])
        v = vols[0]
        assert v.mount_path == "/data"
        assert v.options == {"rwx": "", "retain": ""}

    def test_with_kv_options(self):
        vols = parse_volumes(["data-vol:/data,mode=rw"])
        v = vols[0]
        assert v.options == {"mode": "rw"}


# -----------------------------------------------------------------------
# Resources (standard compose)
# -----------------------------------------------------------------------

class TestParseResources:
    def test_limits(self):
        r = parse_resources({"cpus": "2", "memory": "8192M"})
        assert r.cpu == "2"
        assert r.memory == "8192M"
        assert r.gpu is None

    def test_gpu_direct(self):
        r = parse_resources({"gpus": "1"})
        assert r.gpu == "1"

    def test_gpu_devices(self):
        r = parse_resources({
            "devices": [{"capabilities": ["gpu"], "count": 2}]
        })
        assert r.gpu == "2"

    def test_ephemeral(self):
        r = parse_resources({"ephemeralStorage": "10Gi"})
        assert r.ephemeral_storage == "10Gi"

    def test_empty(self):
        r = parse_resources({})
        assert r.cpu is None
        assert r.memory is None


# -----------------------------------------------------------------------
# x-helx-resources
# -----------------------------------------------------------------------

class TestParseHelxResources:
    def test_full(self):
        raw = {
            "bounds": {
                "cpu": {"min": "0.5", "max": "8", "default_request": "1", "default_limit": "4"},
                "memory": {"min": "512Mi", "max": "32Gi", "default_request": "1Gi", "default_limit": "4Gi"},
                "gpu": {"resource_name": "nvidia.com/gpu", "min": "0", "max": "2"},
                "ephemeral-storage": {"min": "1Gi", "max": "50Gi"},
            },
            "lock": False,
        }
        bounds = parse_helx_resources(raw)
        assert bounds.cpu is not None
        assert bounds.cpu.min == "0.5"
        assert bounds.cpu.max == "8"
        assert bounds.cpu.default_request == "1"
        assert bounds.cpu.default_limit == "4"
        assert bounds.memory is not None
        assert bounds.gpu is not None
        assert bounds.gpu.resource_name == "nvidia.com/gpu"
        assert bounds.ephemeral_storage is not None
        assert bounds.lock is False

    def test_gpu_name_custom(self):
        raw = {"bounds": {"gpu": {"resource_name": "amd.com/gpu", "min": "0", "max": "1"}}}
        bounds = parse_helx_resources(raw)
        assert bounds.gpu.resource_name == "amd.com/gpu"

    def test_gpu_default_name(self):
        raw = {"bounds": {"gpu": {"min": "0", "max": "1"}}}
        bounds = parse_helx_resources(raw)
        assert bounds.gpu.resource_name == "nvidia.com/gpu"

    def test_lock(self):
        raw = {"bounds": {"cpu": {"min": "1", "max": "1"}}, "lock": True}
        bounds = parse_helx_resources(raw)
        assert bounds.lock is True

    def test_partial(self):
        raw = {"bounds": {"cpu": {"min": "1", "max": "4"}}}
        bounds = parse_helx_resources(raw)
        assert bounds.cpu is not None
        assert bounds.memory is None
        assert bounds.gpu is None
        assert bounds.ephemeral_storage is None

    def test_backfills_limits_requests(self):
        spec = _compose(("jupyter", _svc(**{
            "x-helx-resources": {
                "bounds": {
                    "cpu": {"default_request": "1", "default_limit": "4"},
                    "memory": {"default_request": "1Gi", "default_limit": "4Gi"},
                }
            }
        })))
        app = parse_compose(spec)
        svc = app.services[0]
        assert svc.resource_bounds is not None
        assert svc.limits.cpu == "4"
        assert svc.requests.cpu == "1"
        assert svc.limits.memory == "4Gi"
        assert svc.requests.memory == "1Gi"

    def test_overrides_deploy_resources(self):
        svc_dict = _svc(
            deploy={"resources": {"limits": {"cpus": "99"}}},
            **{"x-helx-resources": {
                "bounds": {"cpu": {"default_request": "1", "default_limit": "2"}}
            }},
        )
        spec = _compose(("web", svc_dict))
        app = parse_compose(spec)
        svc = app.services[0]
        # x-helx-resources wins; deploy.resources ignored
        assert svc.limits.cpu == "2"
        assert svc.requests.cpu == "1"
        assert svc.resource_bounds is not None


# -----------------------------------------------------------------------
# Command / Entrypoint
# -----------------------------------------------------------------------

class TestParseCommand:
    def test_command_string(self):
        spec = _compose(("web", _svc(command="start.sh --port 8080")))
        svc = parse_compose(spec).services[0]
        assert svc.command == ["start.sh", "--port", "8080"]

    def test_command_list(self):
        spec = _compose(("web", _svc(command=["start.sh", "--port"])))
        svc = parse_compose(spec).services[0]
        assert svc.command == ["start.sh", "--port"]

    def test_entrypoint_precedence(self):
        spec = _compose(("web", _svc(
            command="ignored",
            entrypoint="/bin/sh -c 'exec jupyter'",
        )))
        svc = parse_compose(spec).services[0]
        assert svc.command[0] == "/bin/sh"


# -----------------------------------------------------------------------
# Probes
# -----------------------------------------------------------------------

class TestParseProbe:
    def test_exec(self):
        p = parse_probe({"cmd": ["pgrep", "jupyter"], "delay": 5, "period": 5})
        assert p.probe_type == "exec"
        assert p.command == ["pgrep", "jupyter"]
        assert p.delay == 5
        assert p.period == 5

    def test_http(self):
        p = parse_probe({"httpGet": {"path": "/api/status", "port": 8888}, "delay": 10})
        assert p.probe_type == "httpGet"
        assert p.path == "/api/status"
        assert p.port == 8888

    def test_tcp(self):
        p = parse_probe({"tcpSocket": {"port": 5432}})
        assert p.probe_type == "tcpSocket"
        assert p.port == 5432

    def test_none_string(self):
        assert parse_probe("none") is None

    def test_absent(self):
        assert parse_probe(None) is None

    def test_probes_from_ext(self):
        ext = {"kube": {"livenessProbe": {"cmd": ["pgrep", "nb"], "delay": 3, "period": 5}}}
        spec = _compose(("web", _svc()))
        app = parse_compose(spec, ext=ext)
        assert app.services[0].liveness_probe is not None
        assert app.services[0].liveness_probe.command == ["pgrep", "nb"]


# -----------------------------------------------------------------------
# Expose, depends_on
# -----------------------------------------------------------------------

class TestMiscFields:
    def test_expose(self):
        spec = _compose(("web", _svc(expose=[5432, 6379])))
        svc = parse_compose(spec).services[0]
        assert svc.expose == [5432, 6379]

    def test_depends_on(self):
        spec = _compose(("web", _svc(depends_on=["db", "redis"])))
        svc = parse_compose(spec).services[0]
        assert svc.depends_on == ["db", "redis"]


# -----------------------------------------------------------------------
# x-helx-vars
# -----------------------------------------------------------------------

class TestHelxVars:
    def test_parse_helx_vars(self):
        spec = _compose(("web", _svc()), **{"x-helx-vars": ["username", "identifier"]})
        app = parse_compose(spec)
        assert app.helx_vars == ["username", "identifier"]

    def test_absent(self):
        spec = _compose(("web", _svc()))
        app = parse_compose(spec)
        assert app.helx_vars == []

    def test_preserves_templates(self):
        spec = _compose(("web", _svc(environment={"NB_USER": "${username}"})))
        app = parse_compose(spec)
        assert app.services[0].environment["NB_USER"] == "${username}"


# -----------------------------------------------------------------------
# Secrets
# -----------------------------------------------------------------------

class TestParseTopLevelSecrets:
    def test_external(self):
        raw = {"pgadmin-env": {"external": True}}
        assert parse_top_level_secrets(raw) == {"pgadmin-env"}

    def test_non_external_ignored(self):
        raw = {"local-secret": {"file": "./secret.txt"}}
        assert parse_top_level_secrets(raw) == set()

    def test_mixed(self):
        raw = {
            "db-creds": {"external": True},
            "local": {"file": "./f.txt"},
            "api-key": {"external": True},
        }
        assert parse_top_level_secrets(raw) == {"db-creds", "api-key"}

    def test_empty(self):
        assert parse_top_level_secrets({}) == set()


class TestParseServiceSecrets:
    def test_short_syntax(self):
        top = {"pgadmin-env"}
        assert parse_service_secrets(["pgadmin-env"], top) == ["pgadmin-env"]

    def test_long_syntax(self):
        top = {"db-creds"}
        raw = [{"source": "db-creds", "target": "/run/secrets/db"}]
        assert parse_service_secrets(raw, top) == ["db-creds"]

    def test_undeclared_skipped(self):
        top = {"pgadmin-env"}
        assert parse_service_secrets(["pgadmin-env", "unknown"], top) == ["pgadmin-env"]

    def test_empty(self):
        assert parse_service_secrets([], set()) == []

    def test_no_top_secrets(self):
        assert parse_service_secrets(["anything"], None) == []

    def test_multiple(self):
        top = {"a", "b", "c"}
        assert parse_service_secrets(["a", "c"], top) == ["a", "c"]


class TestSecretsIntegration:
    def test_compose_with_secrets(self):
        spec = {
            "services": {
                "pgadmin": {
                    "image": "pgadmin4:latest",
                    "secrets": ["pgadmin-env"],
                },
            },
            "secrets": {
                "pgadmin-env": {"external": True},
            },
        }
        app = parse_compose(spec)
        assert app.services[0].secrets == ["pgadmin-env"]

    def test_compose_no_secrets(self):
        spec = _compose(("web", _svc()))
        app = parse_compose(spec)
        assert app.services[0].secrets == []

    def test_compose_multiple_services_selective_secrets(self):
        spec = {
            "services": {
                "web": {
                    "image": "web:latest",
                    "secrets": ["db-creds"],
                },
                "worker": {
                    "image": "worker:latest",
                },
            },
            "secrets": {
                "db-creds": {"external": True},
            },
        }
        app = parse_compose(spec)
        web = next(s for s in app.services if s.name == "web")
        worker = next(s for s in app.services if s.name == "worker")
        assert web.secrets == ["db-creds"]
        assert worker.secrets == []

    def test_compose_secret_not_external_excluded(self):
        spec = {
            "services": {
                "web": {
                    "image": "web:latest",
                    "secrets": ["local-secret"],
                },
            },
            "secrets": {
                "local-secret": {"file": "./secret.txt"},
            },
        }
        app = parse_compose(spec)
        assert app.services[0].secrets == []
