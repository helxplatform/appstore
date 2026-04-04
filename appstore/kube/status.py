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
        which differs from the appstore's instance ID.  The appstore ID is
        embedded in the ``helx.renci.org/instance-name`` label as the suffix
        after ``{app_id}-``.  We query all managed deployments and filter
        client-side.
        """
        all_managed = self._list(L.selector_all_managed())
        return [s for s in all_managed if s.instance_id == instance_id]

    def by_username(self, username: str) -> list[InstanceStatus]:
        """Get status for all instances belonging to a user."""
        return self._list(L.selector_by_username(username))

    def all_managed(self) -> list[InstanceStatus]:
        """Get status for all controller-managed instances."""
        return self._list(L.selector_all_managed())

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

            resource_usage: dict[str, dict[str, str]] = {}
            for c in item.spec.template.spec.containers:
                if c.resources and c.resources.limits:
                    resource_usage[c.name] = dict(c.resources.limits)

            # Derive the appstore instance_id from the instance-name label.
            # The controller's helx.renci.org/id is its own UUID, not ours.
            # The instance-name label is the HelxInst CR name: "{app_id}-{instance_id}".
            inst_name_label = labels.get(L.INSTANCE_NAME, "")
            app_name = labels.get(L.APP_NAME, "")
            if app_name and inst_name_label.startswith(app_name + "-"):
                instance_id = inst_name_label[len(app_name) + 1:]
            else:
                # Fallback: use the full instance-name or controller UUID
                instance_id = inst_name_label or labels.get(L.ID, "")

            results.append(
                InstanceStatus(
                    name=item.metadata.name,
                    instance_id=instance_id,
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
