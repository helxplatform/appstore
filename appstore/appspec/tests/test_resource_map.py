"""Tests for appspec.resource_map — compose -> K8s translation."""

from appspec.models import ComposeResources, ResourceBound, ResourceBounds
from appspec.resource_map import (
    bounds_to_default_resources,
    bounds_to_resource_bounds,
    extract_gpu_from_devices,
    to_k8s_resources,
)


class TestToK8sResources:
    def test_full(self):
        cr = ComposeResources(cpu="2", memory="8Gi", gpu="1", ephemeral_storage="10Gi")
        rs = to_k8s_resources(cr)
        assert rs.cpu == "2"
        assert rs.memory == "8Gi"
        assert rs.gpu == "1"
        assert rs.ephemeral_storage == "10Gi"

    def test_partial(self):
        cr = ComposeResources(cpu="1")
        rs = to_k8s_resources(cr)
        assert rs.cpu == "1"
        assert rs.memory is None
        d = rs.to_dict()
        assert "memory" not in d

    def test_empty(self):
        cr = ComposeResources()
        rs = to_k8s_resources(cr)
        assert rs.to_dict() == {}


class TestExtractGpuFromDevices:
    def test_gpu_device(self):
        assert extract_gpu_from_devices(
            [{"capabilities": ["gpu"], "count": 2}]
        ) == "2"

    def test_no_gpu_device(self):
        assert extract_gpu_from_devices(
            [{"capabilities": ["tpu"], "count": 1}]
        ) is None

    def test_empty(self):
        assert extract_gpu_from_devices([]) is None

    def test_no_count_defaults_to_1(self):
        assert extract_gpu_from_devices(
            [{"capabilities": ["gpu"]}]
        ) == "1"


class TestBoundsToResourceBounds:
    def test_full(self):
        bounds = ResourceBounds(
            cpu=ResourceBound(min="0.5", max="8", default_request="1", default_limit="4"),
            memory=ResourceBound(min="512Mi", max="32Gi"),
            gpu=ResourceBound(min="0", max="2", resource_name="nvidia.com/gpu"),
            ephemeral_storage=ResourceBound(min="1Gi", max="50Gi"),
        )
        d = bounds_to_resource_bounds(bounds)
        assert "cpu" in d
        assert d["cpu"]["min"] == "0.5"
        assert d["cpu"]["defaultRequest"] == "1"
        assert "memory" in d
        assert "nvidia.com/gpu" in d
        assert "ephemeral-storage" in d
        assert d["lock"] is False

    def test_gpu_custom_name(self):
        bounds = ResourceBounds(
            gpu=ResourceBound(min="0", max="1", resource_name="amd.com/gpu"),
        )
        d = bounds_to_resource_bounds(bounds)
        assert "amd.com/gpu" in d
        assert "nvidia.com/gpu" not in d

    def test_gpu_default_name(self):
        bounds = ResourceBounds(
            gpu=ResourceBound(min="0", max="1"),
        )
        d = bounds_to_resource_bounds(bounds)
        assert "nvidia.com/gpu" in d

    def test_lock(self):
        bounds = ResourceBounds(lock=True)
        d = bounds_to_resource_bounds(bounds)
        assert d["lock"] is True

    def test_partial(self):
        bounds = ResourceBounds(
            cpu=ResourceBound(min="1", max="4"),
        )
        d = bounds_to_resource_bounds(bounds)
        assert "cpu" in d
        assert "memory" not in d
        assert "nvidia.com/gpu" not in d

    def test_empty(self):
        bounds = ResourceBounds()
        d = bounds_to_resource_bounds(bounds)
        assert d == {"lock": False}


class TestBoundsToDefaultResources:
    def test_full(self):
        bounds = ResourceBounds(
            cpu=ResourceBound(default_request="1", default_limit="4"),
            memory=ResourceBound(default_request="1Gi", default_limit="4Gi"),
        )
        requests, limits = bounds_to_default_resources(bounds)
        assert requests.cpu == "1"
        assert limits.cpu == "4"
        assert requests.memory == "1Gi"
        assert limits.memory == "4Gi"

    def test_partial(self):
        bounds = ResourceBounds(
            cpu=ResourceBound(default_request="1"),
        )
        requests, limits = bounds_to_default_resources(bounds)
        assert requests.cpu == "1"
        assert limits.cpu is None
        assert requests.memory is None
