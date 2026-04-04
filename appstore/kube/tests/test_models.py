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
