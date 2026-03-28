"""Exceptions for the registry module."""

from kube.exceptions import KubeError


class RegistryError(KubeError):
    """Raised when registry resolution fails."""


class SpecLoadError(KubeError):
    """Raised when loading a docker-compose spec fails."""
