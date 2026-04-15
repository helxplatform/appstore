"""
Kubernetes API client initialization.

Handles in-cluster vs out-of-cluster configuration and exposes typed
API handles used by the CRD managers and status queries.
"""

from __future__ import annotations

import logging
import os

from kubernetes import client as k8s_client, config as k8s_config
from kubernetes.client.rest import ApiException  # noqa: F401 — re-exported

logger = logging.getLogger(__name__)

API_GROUP = "helx.renci.org"
API_VERSION = "v1"


class KubeClient:
    """Thin wrapper around the kubernetes-client API handles.

    Automatically detects in-cluster vs local kubeconfig and resolves the
    active namespace from the downward API or the ``NAMESPACE`` env var.
    """

    def __init__(self, namespace: str | None = None):
        if os.getenv("KUBERNETES_SERVICE_HOST"):
            k8s_config.load_incluster_config()
        else:
            k8s_config.load_kube_config()

        api_client = k8s_client.ApiClient()
        self.core = k8s_client.CoreV1Api(api_client)
        self.apps = k8s_client.AppsV1Api(api_client)
        self.custom = k8s_client.CustomObjectsApi(api_client)

        self.namespace = namespace or self._resolve_namespace()
        logger.debug("KubeClient using namespace: %s", self.namespace)

    @staticmethod
    def _resolve_namespace() -> str:
        """Resolve namespace: env var > downward API > 'default'."""
        ns = os.environ.get("NAMESPACE")
        if ns:
            return ns
        try:
            with open(
                "/var/run/secrets/kubernetes.io/serviceaccount/namespace"
            ) as fh:
                return fh.read().strip()
        except OSError:
            return "default"
