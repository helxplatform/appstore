"""helx — create HelxApp/HelxInst/HelxUser workloads via helxapp-controller.

Typical script usage::

    import helx

    client   = helx.connect(namespace="my-ns")
    registry = helx.load_registry("/path/to/app-registry.yaml")

    app_spec  = registry.build_helxapp("jupyter-ai-notebook")
    inst_spec = registry.build_helxinst(
        "jupyter-ai-notebook", username="alice", reference_id="run-001"
    )

    client.helxapps.ensure("jupyter-ai-notebook", app_spec)
    client.helxapps.wait_for_reconcile("jupyter-ai-notebook")
    client.helxusers.ensure("alice", user_spec)
    client.helxinsts.create("jupyter-ai-notebook-run-001", inst_spec)
"""

from helx.kube import KubeClient
from helx.kube.models import HelxUserSpec
from helx.registry import AppRegistry


def connect(namespace: str | None = None) -> KubeClient:
    """Return a KubeClient using in-cluster credentials or local kubeconfig."""
    return KubeClient(namespace=namespace)


def load_registry(
    registry_path: str,
    defaults_path: str | None = None,
    product: str = "common",
) -> AppRegistry:
    """Load an app registry from a YAML file on disk."""
    return AppRegistry(
        registry_path=registry_path,
        defaults_path=defaults_path,
        product=product,
    )


__all__ = [
    "connect",
    "load_registry",
    "KubeClient",
    "HelxUserSpec",
    "AppRegistry",
]
