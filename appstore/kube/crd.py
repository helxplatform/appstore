"""
Low-level helpers for CRD CRUD via the CustomObjects API.

All three CRD managers (apps, instances, users) delegate here.
"""

from __future__ import annotations

import logging
from typing import Any

from kubernetes.client import CustomObjectsApi
from kubernetes.client.rest import ApiException

from kube.client import API_GROUP, API_VERSION

logger = logging.getLogger(__name__)


def create_crd(
    api: CustomObjectsApi,
    namespace: str,
    plural: str,
    name: str,
    spec: dict,
    labels: dict[str, str] | None = None,
) -> dict:
    """Create a namespaced custom resource."""
    metadata: dict[str, Any] = {"name": name}
    if labels:
        metadata["labels"] = labels
    body: dict[str, Any] = {
        "apiVersion": f"{API_GROUP}/{API_VERSION}",
        "kind": _kind_from_plural(plural),
        "metadata": metadata,
        "spec": spec,
    }
    return api.create_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=namespace,
        plural=plural,
        body=body,
    )


def get_crd(
    api: CustomObjectsApi,
    namespace: str,
    plural: str,
    name: str,
) -> dict | None:
    """Get a namespaced custom resource, or None if not found."""
    try:
        return api.get_namespaced_custom_object(
            group=API_GROUP,
            version=API_VERSION,
            namespace=namespace,
            plural=plural,
            name=name,
        )
    except ApiException as exc:
        if exc.status == 404:
            return None
        raise


def update_crd(
    api: CustomObjectsApi,
    namespace: str,
    plural: str,
    name: str,
    spec: dict,
) -> dict:
    """Replace the spec of a namespaced custom resource."""
    existing = api.get_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=namespace,
        plural=plural,
        name=name,
    )
    existing["spec"] = spec
    return api.replace_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=namespace,
        plural=plural,
        name=name,
        body=existing,
    )


def delete_crd(
    api: CustomObjectsApi,
    namespace: str,
    plural: str,
    name: str,
) -> None:
    """Delete a namespaced custom resource."""
    api.delete_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=namespace,
        plural=plural,
        name=name,
    )


def list_crds(
    api: CustomObjectsApi,
    namespace: str,
    plural: str,
    label_selector: str = "",
) -> list[dict]:
    """List namespaced custom resources, optionally filtered by label."""
    resp = api.list_namespaced_custom_object(
        group=API_GROUP,
        version=API_VERSION,
        namespace=namespace,
        plural=plural,
        label_selector=label_selector,
    )
    return resp.get("items", [])


def _kind_from_plural(plural: str) -> str:
    """Map plural resource name to CRD Kind."""
    return {
        "helxapps": "HelxApp",
        "helxinsts": "HelxInst",
        "helxusers": "HelxUser",
    }[plural]
