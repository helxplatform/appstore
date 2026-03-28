"""
kube - Client library for the helxapp-controller.

Manages HelxApp, HelxInst, and HelxUser CRDs and queries the derived
Kubernetes objects (Deployments, Services, PVCs) that the controller
creates.
"""

from kube.client import KubeClient
from kube.helxapps import HelxAppManager
from kube.helxinsts import HelxInstManager
from kube.helxusers import HelxUserManager
from kube.status import StatusQuery
from kube.exceptions import (
    KubeError,
    AppError,
    InstanceError,
    UserError,
    SecurityContextError,
    VolumeDSLError,
    StatusError,
)

__all__ = [
    "KubeClient",
    "HelxAppManager",
    "HelxInstManager",
    "HelxUserManager",
    "StatusQuery",
    "KubeError",
    "AppError",
    "InstanceError",
    "UserError",
    "SecurityContextError",
    "VolumeDSLError",
    "StatusError",
]
