"""
HelxInst CRD management.

A HelxInst is a per-user instantiation request: "run this app for this
user."  Creating a HelxInst is the *trigger* for workload creation —
once the controller sees a matching HelxApp + HelxUser, it generates
the Deployment, Services, and PVCs.
"""

from __future__ import annotations

import logging

from kubernetes.client import CustomObjectsApi
from kubernetes.client.rest import ApiException

from helx.kube import crd
from helx.kube.exceptions import InstanceError
from helx.kube.models import HelxInstSpec

logger = logging.getLogger(__name__)

PLURAL = "helxinsts"


class HelxInstManager:
    """CRUD for HelxInst custom resources."""

    def __init__(self, custom_api: CustomObjectsApi, namespace: str):
        self._api = custom_api
        self._ns = namespace

    def create(self, name: str, spec: HelxInstSpec) -> dict:
        """Create a HelxInst.  This triggers workload creation."""
        try:
            return crd.create_crd(
                self._api, self._ns, PLURAL, name, spec.to_dict()
            )
        except ApiException as exc:
            raise InstanceError(
                f"Failed to create HelxInst {name}", details=str(exc)
            ) from exc

    def get(self, name: str) -> dict | None:
        try:
            return crd.get_crd(self._api, self._ns, PLURAL, name)
        except ApiException as exc:
            raise InstanceError(
                f"Failed to get HelxInst {name}", details=str(exc)
            ) from exc

    def update(self, name: str, spec: HelxInstSpec) -> dict:
        """Update resources or security context on an existing instance."""
        try:
            return crd.update_crd(
                self._api, self._ns, PLURAL, name, spec.to_dict()
            )
        except ApiException as exc:
            raise InstanceError(
                f"Failed to update HelxInst {name}", details=str(exc)
            ) from exc

    def delete(self, name: str) -> None:
        """Delete a HelxInst.

        Owner-reference GC will clean up the Deployment, Services, and
        non-retained PVCs.
        """
        try:
            crd.delete_crd(self._api, self._ns, PLURAL, name)
            logger.info("Deleted HelxInst %s", name)
        except ApiException as exc:
            raise InstanceError(
                f"Failed to delete HelxInst {name}", details=str(exc)
            ) from exc

    def list(self, label_selector: str = "") -> list[dict]:
        try:
            return crd.list_crds(
                self._api, self._ns, PLURAL, label_selector
            )
        except ApiException as exc:
            raise InstanceError(
                "Failed to list HelxInsts", details=str(exc)
            ) from exc

    def get_uuid(self, name: str) -> str | None:
        """Read the controller-assigned UUID from an instance's status.

        The controller sets ``status.uuid`` on first reconciliation;
        this UUID labels all derived Kubernetes objects.
        """
        obj = self.get(name)
        if obj is None:
            return None
        return obj.get("status", {}).get("uuid")
