"""Compose resource names -> Kubernetes resource names."""

from __future__ import annotations

from appspec.models import ComposeResources, ResourceBounds, ResourceBound
from kube.models import ResourceSpec


def to_k8s_resources(compose: ComposeResources) -> ResourceSpec:
    """Convert compose resource names to kube.models.ResourceSpec."""
    return ResourceSpec(
        cpu=compose.cpu,
        memory=compose.memory,
        gpu=compose.gpu,
        ephemeral_storage=compose.ephemeral_storage,
    )


def extract_gpu_from_devices(devices: list[dict]) -> str | None:
    """Extract GPU count from compose devices list."""
    for dev in devices:
        caps = dev.get("capabilities", [])
        if "gpu" in caps:
            count = dev.get("count")
            return str(count) if count is not None else "1"
    return None


def bounds_to_resource_bounds(bounds: ResourceBounds) -> dict:
    """Convert ResourceBounds to the dict structure for HelxApp CRD.

    Output shape matches AppServiceSpec.resource_bounds.
    """
    result: dict = {}

    if bounds.cpu is not None:
        result["cpu"] = _bound_to_dict(bounds.cpu)
    if bounds.memory is not None:
        result["memory"] = _bound_to_dict(bounds.memory)
    if bounds.gpu is not None:
        key = bounds.gpu.resource_name or "nvidia.com/gpu"
        result[key] = _bound_to_dict(bounds.gpu)
    if bounds.ephemeral_storage is not None:
        result["ephemeral-storage"] = _bound_to_dict(bounds.ephemeral_storage)

    result["lock"] = bounds.lock
    return result


def bounds_to_default_resources(
    bounds: ResourceBounds,
) -> tuple[ComposeResources, ComposeResources]:
    """Extract default request/limit from bounds as ComposeResources pair.

    Returns (requests, limits).
    """
    requests = ComposeResources(
        cpu=bounds.cpu.default_request if bounds.cpu else None,
        memory=bounds.memory.default_request if bounds.memory else None,
        gpu=bounds.gpu.default_request if bounds.gpu else None,
        ephemeral_storage=bounds.ephemeral_storage.default_request if bounds.ephemeral_storage else None,
    )
    limits = ComposeResources(
        cpu=bounds.cpu.default_limit if bounds.cpu else None,
        memory=bounds.memory.default_limit if bounds.memory else None,
        gpu=bounds.gpu.default_limit if bounds.gpu else None,
        ephemeral_storage=bounds.ephemeral_storage.default_limit if bounds.ephemeral_storage else None,
    )
    return requests, limits


def _bound_to_dict(bound: ResourceBound) -> dict:
    d: dict = {}
    if bound.min is not None:
        d["min"] = bound.min
    if bound.max is not None:
        d["max"] = bound.max
    if bound.default_request is not None:
        d["defaultRequest"] = bound.default_request
    if bound.default_limit is not None:
        d["defaultLimit"] = bound.default_limit
    return d
