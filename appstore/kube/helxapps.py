"""
HelxApp CRD management.

A HelxApp defines *what* an application is: container images, ports,
environment, volumes, and security context.
"""

from __future__ import annotations

import logging
import time

from kubernetes.client import CustomObjectsApi
from kubernetes.client.rest import ApiException

from kube import crd
from kube.exceptions import AppError
from kube.models import HelxAppSpec

logger = logging.getLogger(__name__)

PLURAL = "helxapps"


class HelxAppManager:
    """CRUD for HelxApp custom resources."""

    def __init__(self, custom_api: CustomObjectsApi, namespace: str):
        self._api = custom_api
        self._ns = namespace

    def create(self, name: str, spec: HelxAppSpec) -> dict:
        """Create a HelxApp CR."""
        try:
            return crd.create_crd(
                self._api, self._ns, PLURAL, name, spec.to_dict()
            )
        except ApiException as exc:
            raise AppError(
                f"Failed to create HelxApp {name}", details=str(exc)
            ) from exc

    def get(self, name: str) -> dict | None:
        """Get a HelxApp by name, or None if not found."""
        try:
            return crd.get_crd(self._api, self._ns, PLURAL, name)
        except ApiException as exc:
            raise AppError(
                f"Failed to get HelxApp {name}", details=str(exc)
            ) from exc

    def update(self, name: str, spec: HelxAppSpec) -> dict:
        """Replace the spec of an existing HelxApp."""
        try:
            return crd.update_crd(
                self._api, self._ns, PLURAL, name, spec.to_dict()
            )
        except ApiException as exc:
            raise AppError(
                f"Failed to update HelxApp {name}", details=str(exc)
            ) from exc

    def delete(self, name: str) -> None:
        """Delete a HelxApp.  The controller will cascade-delete workloads."""
        try:
            crd.delete_crd(self._api, self._ns, PLURAL, name)
            logger.info("Deleted HelxApp %s", name)
        except ApiException as exc:
            raise AppError(
                f"Failed to delete HelxApp {name}", details=str(exc)
            ) from exc

    def list(self, label_selector: str = "") -> list[dict]:
        """List all HelxApps in the namespace."""
        try:
            return crd.list_crds(
                self._api, self._ns, PLURAL, label_selector
            )
        except ApiException as exc:
            raise AppError(
                "Failed to list HelxApps", details=str(exc)
            ) from exc

    def ensure(self, name: str, spec: HelxAppSpec) -> dict:
        """Create or update a HelxApp (idempotent)."""
        existing = self.get(name)
        if existing is None:
            return self.create(name, spec)
        return self.update(name, spec)

    def wait_for_reconcile(self, name: str, timeout: float = 30.0, interval: float = 0.5) -> None:
        """Block until the controller has reconciled this HelxApp.

        After an update the controller bumps ``status.observedGeneration`` to
        match ``metadata.generation``.  Submitting a HelxInst before that
        happens causes the HelxInst reconciler to see the HelxApp in a
        mid-reconcile state and exit without creating a Deployment.
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            obj = self.get(name)
            if obj is not None:
                generation = obj.get("metadata", {}).get("generation", 0)
                observed = obj.get("status", {}).get("observedGeneration", 0)
                if generation == observed:
                    return
            time.sleep(interval)
        logger.warning(
            "HelxApp %s did not reach observedGeneration within %.1fs; proceeding anyway",
            name, timeout,
        )
