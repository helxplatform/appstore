"""
HelxUser CRD management.

A HelxUser represents a platform user.  Optional ``userHandle`` URL
provides security context via HTTP GET.
"""

from __future__ import annotations

import logging

from kubernetes.client import CustomObjectsApi
from kubernetes.client.rest import ApiException

from kube import crd
from kube.exceptions import UserError
from kube.models import HelxUserSpec

logger = logging.getLogger(__name__)

PLURAL = "helxusers"


class HelxUserManager:
    """CRUD for HelxUser custom resources."""

    def __init__(self, custom_api: CustomObjectsApi, namespace: str):
        self._api = custom_api
        self._ns = namespace

    def create(self, name: str, spec: HelxUserSpec) -> dict:
        try:
            return crd.create_crd(
                self._api, self._ns, PLURAL, name, spec.to_dict()
            )
        except ApiException as exc:
            raise UserError(
                f"Failed to create HelxUser {name}", details=str(exc)
            ) from exc

    def get(self, name: str) -> dict | None:
        try:
            return crd.get_crd(self._api, self._ns, PLURAL, name)
        except ApiException as exc:
            raise UserError(
                f"Failed to get HelxUser {name}", details=str(exc)
            ) from exc

    def delete(self, name: str) -> None:
        """Delete a HelxUser.  The controller will cascade-delete workloads."""
        try:
            crd.delete_crd(self._api, self._ns, PLURAL, name)
            logger.info("Deleted HelxUser %s", name)
        except ApiException as exc:
            raise UserError(
                f"Failed to delete HelxUser {name}", details=str(exc)
            ) from exc

    def list(self, label_selector: str = "") -> list[dict]:
        try:
            return crd.list_crds(
                self._api, self._ns, PLURAL, label_selector
            )
        except ApiException as exc:
            raise UserError(
                "Failed to list HelxUsers", details=str(exc)
            ) from exc

    def ensure(self, name: str, spec: HelxUserSpec) -> dict:
        """Create or update a HelxUser (idempotent)."""
        existing = self.get(name)
        if existing is None:
            return self.create(name, spec)
        # Update — replace spec
        try:
            return crd.update_crd(
                self._api, self._ns, PLURAL, name, spec.to_dict()
            )
        except ApiException as exc:
            raise UserError(
                f"Failed to update HelxUser {name}", details=str(exc)
            ) from exc
