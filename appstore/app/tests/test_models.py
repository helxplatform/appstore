"""Tests for app.models — data model behavior."""

from app.models import (
    ComposeApp,
    ComposeService,
    ResourceBound,
    ResourceBounds,
    VolumeMount,
)


class TestVolumeMount:
    def test_to_dsl_simple(self):
        v = VolumeMount(source="pvc", mount_path="/data")
        assert v.to_dsl_string() == "pvc:/data"

    def test_to_dsl_subpath(self):
        v = VolumeMount(source="pvc", mount_path="/data", sub_path="sub")
        assert v.to_dsl_string() == "pvc:/data#sub"

    def test_to_dsl_options(self):
        v = VolumeMount(
            source="pvc", mount_path="/data",
            options={"rwx": "", "retain": ""},
        )
        assert v.to_dsl_string() == "pvc:/data,rwx,retain"

    def test_to_dsl_subpath_and_options(self):
        v = VolumeMount(
            source="pvc", mount_path="/data", sub_path="work",
            options={"rwx": ""},
        )
        assert v.to_dsl_string() == "pvc:/data#work,rwx"

    def test_to_dsl_kv_options(self):
        v = VolumeMount(
            source="pvc", mount_path="/data",
            options={"mode": "rw"},
        )
        assert v.to_dsl_string() == "pvc:/data,mode=rw"


class TestComposeApp:
    def test_get_service(self):
        svc = ComposeService(name="web", image="img:latest")
        app = ComposeApp(services=[svc])
        assert app.get_service("web") is svc

    def test_get_service_missing(self):
        app = ComposeApp(services=[ComposeService(name="web", image="img")])
        assert app.get_service("db") is None


class TestResourceBound:
    def test_defaults(self):
        rb = ResourceBound()
        assert rb.min is None
        assert rb.max is None
        assert rb.default_request is None
        assert rb.default_limit is None
        assert rb.resource_name is None


class TestResourceBounds:
    def test_lock_default(self):
        rb = ResourceBounds()
        assert rb.lock is False
