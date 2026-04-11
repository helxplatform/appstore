"""Tests for kube.models data classes."""

import pytest

from kube.models import (
    AmbassadorSpec,
    AppServiceSpec,
    ContainerResources,
    HelxAppSpec,
    HelxInstSpec,
    HelxUserSpec,
    InstanceStatus,
    PortSpec,
    ProbeSpec,
    ResourceSpec,
    SecurityContext,
)


class TestResourceSpec:
    def test_to_dict_full(self):
        r = ResourceSpec(cpu="2", memory="4Gi", gpu="1", ephemeral_storage="10Gi")
        d = r.to_dict()
        assert d == {
            "cpu": "2",
            "memory": "4Gi",
            "nvidia.com/gpu": "1",
            "ephemeral-storage": "10Gi",
        }

    def test_to_dict_partial(self):
        r = ResourceSpec(cpu="500m", memory="1Gi")
        d = r.to_dict()
        assert d == {"cpu": "500m", "memory": "1Gi"}
        assert "nvidia.com/gpu" not in d

    def test_to_dict_empty(self):
        r = ResourceSpec()
        assert r.to_dict() == {}


class TestSecurityContext:
    def test_to_dict_full(self):
        sc = SecurityContext(
            run_as_user=1000,
            run_as_group=2000,
            fs_group=3000,
            supplemental_groups=[4000, 5000],
        )
        d = sc.to_dict()
        assert d["runAsUser"] == 1000
        assert d["runAsGroup"] == 2000
        assert d["fsGroup"] == 3000
        assert d["supplementalGroups"] == [4000, 5000]

    def test_to_dict_partial(self):
        sc = SecurityContext(run_as_user=1000)
        d = sc.to_dict()
        assert d == {"runAsUser": 1000}

    def test_to_dict_empty(self):
        sc = SecurityContext()
        assert sc.to_dict() == {}


class TestHelxAppSpec:
    def test_to_dict(self):
        spec = HelxAppSpec(
            app_class_name="JupyterLab",
            services=[
                AppServiceSpec(
                    name="main",
                    image="jupyter/minimal-notebook:latest",
                    ports=[PortSpec(container_port=8888, port=8888)],
                    environment={"NB_PREFIX": "/"},
                ),
            ],
        )
        d = spec.to_dict()
        assert d["appClassName"] == "JupyterLab"
        assert len(d["services"]) == 1
        assert d["services"][0]["name"] == "main"
        assert d["services"][0]["ports"] == [
            {"containerPort": 8888, "port": 8888}
        ]
        assert d["services"][0]["environment"] == {"NB_PREFIX": "/"}

    def test_service_with_volumes(self):
        spec = AppServiceSpec(
            name="main",
            image="img:1",
            volumes={"home": "user-home:/home/user,rwx,retain"},
        )
        d = spec.to_dict()
        assert d["volumes"]["home"] == "user-home:/home/user,rwx,retain"

    def test_service_with_init(self):
        spec = AppServiceSpec(name="setup", image="busybox", init=True)
        d = spec.to_dict()
        assert d["init"] is True

    def test_service_minimal(self):
        spec = AppServiceSpec(name="app", image="nginx")
        d = spec.to_dict()
        assert d == {"name": "app", "image": "nginx"}

    def test_service_with_secrets_from(self):
        spec = AppServiceSpec(
            name="pgadmin",
            image="pgadmin4:latest",
            secrets_from=["pgadmin-env"],
        )
        d = spec.to_dict()
        assert d["secretsFrom"] == ["pgadmin-env"]

    def test_service_secrets_from_empty_omitted(self):
        spec = AppServiceSpec(name="app", image="nginx")
        d = spec.to_dict()
        assert "secretsFrom" not in d

    def test_service_with_ambassador(self):
        spec = AppServiceSpec(
            name="main",
            image="app:latest",
            ambassador=AmbassadorSpec(
                prefix="/private/MyApp/alice/",
            ),
        )
        d = spec.to_dict()
        assert d["ambassador"] == {"prefix": "/private/MyApp/alice/"}

    def test_service_ambassador_with_id_and_rewrite(self):
        spec = AppServiceSpec(
            name="main",
            image="app:latest",
            ambassador=AmbassadorSpec(
                prefix="/private/MyApp/alice/",
                ambassador_id="edge-stack",
                proxy_rewrite="/",
            ),
        )
        d = spec.to_dict()
        assert d["ambassador"]["ambassadorId"] == "edge-stack"
        assert d["ambassador"]["proxyRewrite"] == "/"

    def test_service_no_ambassador_omitted(self):
        spec = AppServiceSpec(name="app", image="nginx")
        d = spec.to_dict()
        assert "ambassador" not in d

    def test_service_with_liveness_probe(self):
        spec = AppServiceSpec(
            name="app",
            image="jupyter:latest",
            liveness_probe=ProbeSpec(
                probe_type="exec",
                command=["pgrep", "jupyter"],
                delay=5,
                period=5,
            ),
        )
        d = spec.to_dict()
        assert d["livenessProbe"]["exec"]["command"] == ["pgrep", "jupyter"]
        assert d["livenessProbe"]["initialDelaySeconds"] == 5
        assert d["livenessProbe"]["periodSeconds"] == 5

    def test_service_with_readiness_probe_http(self):
        spec = AppServiceSpec(
            name="app",
            image="rstudio:latest",
            readiness_probe=ProbeSpec(
                probe_type="httpGet",
                path="/",
                port=8787,
                delay=10,
                period=10,
            ),
        )
        d = spec.to_dict()
        assert d["readinessProbe"]["httpGet"]["path"] == "/"
        assert d["readinessProbe"]["httpGet"]["port"] == 8787
        assert d["readinessProbe"]["initialDelaySeconds"] == 10

    def test_service_no_probes_omitted(self):
        spec = AppServiceSpec(name="app", image="nginx")
        d = spec.to_dict()
        assert "livenessProbe" not in d
        assert "readinessProbe" not in d


class TestProbeSpec:
    def test_exec_to_dict(self):
        p = ProbeSpec(probe_type="exec", command=["pgrep", "nb"], delay=5, period=5)
        d = p.to_dict()
        assert d == {
            "exec": {"command": ["pgrep", "nb"]},
            "initialDelaySeconds": 5,
            "periodSeconds": 5,
        }

    def test_http_get_to_dict(self):
        p = ProbeSpec(probe_type="httpGet", path="/health", port=8080, delay=0, period=10)
        d = p.to_dict()
        assert d["httpGet"] == {"path": "/health", "port": 8080}
        assert d["initialDelaySeconds"] == 0
        assert d["periodSeconds"] == 10

    def test_http_get_with_headers(self):
        p = ProbeSpec(
            probe_type="httpGet",
            path="/",
            port=80,
            http_headers=[{"name": "X-Custom", "value": "test"}],
        )
        d = p.to_dict()
        assert d["httpGet"]["httpHeaders"] == [{"name": "X-Custom", "value": "test"}]

    def test_tcp_socket_to_dict(self):
        p = ProbeSpec(probe_type="tcpSocket", port=5432, delay=3, period=10)
        d = p.to_dict()
        assert d["tcpSocket"] == {"port": 5432}
        assert d["initialDelaySeconds"] == 3

    def test_failure_threshold(self):
        p = ProbeSpec(probe_type="exec", command=["true"], threshold=3)
        d = p.to_dict()
        assert d["failureThreshold"] == 3

    def test_no_threshold_omitted(self):
        p = ProbeSpec(probe_type="exec", command=["true"])
        d = p.to_dict()
        assert "failureThreshold" not in d

    def test_template_port_preserved(self):
        # ports may be Go template strings resolved by the controller
        p = ProbeSpec(probe_type="httpGet", path="/", port="{{ .system.Port }}")
        d = p.to_dict()
        assert d["httpGet"]["port"] == "{{ .system.Port }}"


class TestAmbassadorSpec:
    def test_minimal(self):
        a = AmbassadorSpec(prefix="/private/app/user/")
        assert a.to_dict() == {"prefix": "/private/app/user/"}

    def test_full(self):
        a = AmbassadorSpec(
            prefix="/private/app/user/",
            ambassador_id="edge-stack",
            proxy_rewrite="/",
        )
        d = a.to_dict()
        assert d["prefix"] == "/private/app/user/"
        assert d["ambassadorId"] == "edge-stack"
        assert d["proxyRewrite"] == "/"

    def test_optional_fields_omitted(self):
        a = AmbassadorSpec(prefix="/private/app/user/")
        d = a.to_dict()
        assert "ambassadorId" not in d
        assert "proxyRewrite" not in d



class TestHelxInstSpec:
    def test_to_dict_full(self):
        spec = HelxInstSpec(
            app_name="jupyterlab",
            user_name="jeffw",
            resources={
                "main": ContainerResources(
                    request=ResourceSpec(cpu="2", memory="1G"),
                    limit=ResourceSpec(cpu="2", memory="1.1G"),
                )
            },
            security_context=SecurityContext(run_as_user=1000, fs_group=2000),
        )
        d = spec.to_dict()
        assert d["appName"] == "jupyterlab"
        assert d["userName"] == "jeffw"
        assert d["resources"]["main"]["request"]["cpu"] == "2"
        assert d["resources"]["main"]["limit"]["memory"] == "1.1G"
        assert d["securityContext"]["runAsUser"] == 1000

    def test_to_dict_minimal(self):
        spec = HelxInstSpec(app_name="app", user_name="bob")
        d = spec.to_dict()
        assert d == {"appName": "app", "userName": "bob"}

    def test_to_dict_with_reference_id(self):
        spec = HelxInstSpec(
            app_name="app",
            user_name="bob",
            reference_id="ref-123",
        )
        d = spec.to_dict()
        assert d["referenceID"] == "ref-123"


class TestHelxUserSpec:
    def test_with_handle(self):
        spec = HelxUserSpec(user_handle="http://ldap/user/jeffw")
        d = spec.to_dict()
        assert d == {"userHandle": "http://ldap/user/jeffw"}

    def test_empty(self):
        spec = HelxUserSpec()
        assert spec.to_dict() == {}


class TestContainerResources:
    def test_to_dict(self):
        cr = ContainerResources(
            request=ResourceSpec(cpu="1"),
            limit=ResourceSpec(cpu="2", memory="4Gi"),
        )
        d = cr.to_dict()
        assert d["request"] == {"cpu": "1"}
        assert d["limit"] == {"cpu": "2", "memory": "4Gi"}

    def test_empty(self):
        cr = ContainerResources()
        assert cr.to_dict() == {}
