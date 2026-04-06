"""
Query status of derived Kubernetes objects.

After the helxapp-controller reconciles a HelxInst, it creates
Deployments labelled with ``helx.renci.org/id: <UUID>``.  This module
reads those Deployments to report readiness, resource usage, and
timestamps — the same information that tycho's ``status()`` provided.
"""

from __future__ import annotations

import logging

from kubernetes.client import AppsV1Api
from kubernetes.client.rest import ApiException

from kube import labels as L
from kube.exceptions import StatusError
from kube.models import InstanceStatus

logger = logging.getLogger(__name__)


class StatusQuery:
    """Query derived Deployments for instance status."""

    def __init__(self, apps_api: AppsV1Api, namespace: str):
        self._api = apps_api
        self._ns = namespace

    def by_instance_id(self, instance_id: str) -> list[InstanceStatus]:
        """Get status for a specific appstore instance ID.

        The helxapp-controller assigns its own UUID (``helx.renci.org/id``),
        which differs from the appstore's instance ID. We recover the
        appstore ID from the injected ``GUID`` environment variable when
        available, falling back to the ``helx.renci.org/instance-name`` label.
        We query all managed deployments and filter client-side.
        """
        all_managed = self._list(L.selector_all_managed())
        return [s for s in all_managed if s.instance_id == instance_id]

    def by_username(self, username: str) -> list[InstanceStatus]:
        """Get status for all instances belonging to a user."""
        return self._list(L.selector_by_username(username))

    def by_controller_id(self, controller_id: str) -> list[InstanceStatus]:
        """Get status for a specific controller-assigned UUID."""
        return self._list(L.selector_by_id(controller_id))

    def all_managed(self) -> list[InstanceStatus]:
        """Get status for all controller-managed instances."""
        return self._list(L.selector_all_managed())

    def _extract_appstore_instance_id(self, labels: dict[str, str], containers) -> str:
        """Recover the AppStore instance ID for a deployment.

        The controller labels derived workloads with its own UUID, but AppStore
        injects the launch GUID into the HelxInst environment. Prefer that
        stable AppStore GUID when present so lookups by ``sid`` match the ID
        returned from ``POST /instances/`` and used by ``is_ready`` polling.
        """
        for container in containers or []:
            for env_var in getattr(container, "env", None) or []:
                if getattr(env_var, "name", None) == "GUID":
                    value = getattr(env_var, "value", None)
                    if value:
                        return value

        # Fall back to deriving the ID from controller-applied labels.
        inst_name_label = labels.get(L.INSTANCE_NAME, "")
        app_name = labels.get(L.APP_NAME, "")
        if app_name and inst_name_label.startswith(app_name + "-"):
            return inst_name_label[len(app_name) + 1:]
        return inst_name_label or labels.get(L.ID, "")

    def _list(self, label_selector: str) -> list[InstanceStatus]:
        try:
            resp = self._api.list_namespaced_deployment(
                namespace=self._ns, label_selector=label_selector
            )
        except ApiException as exc:
            raise StatusError(
                "Failed to list deployments", details=str(exc)
            ) from exc

        results: list[InstanceStatus] = []
        for item in resp.items:
            labels = item.metadata.labels or {}
            c_time = item.metadata.creation_timestamp
            time_str = (
                f"{c_time.month}-{c_time.day}-{c_time.year} "
                f"{c_time.hour}:{c_time.minute}:{c_time.second}"
                if c_time
                else None
            )
            desired = item.status.replicas or 0
            ready = item.status.ready_replicas or 0

            containers = item.spec.template.spec.containers or []
            resource_usage: dict[str, dict[str, str]] = {}
            for c in containers:
                if c.resources and c.resources.limits:
                    resource_usage[c.name] = dict(c.resources.limits)

            app_name = labels.get(L.APP_NAME, "")
            instance_id = self._extract_appstore_instance_id(labels, containers)

            results.append(
                InstanceStatus(
                    name=item.metadata.name,
                    instance_id=instance_id,
                    controller_id=labels.get(L.ID, ""),
                    app_name=app_name,
                    username=labels.get(L.USERNAME),
                    creation_time=time_str,
                    is_ready=(ready == desired and desired > 0),
                    replicas=desired,
                    ready_replicas=ready,
                    resource_usage=resource_usage,
                    workspace_name=app_name,
                )
            )
        return results
