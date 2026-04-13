"""Exceptions for the app module."""

from kube.exceptions import KubeError


class ParseError(KubeError):
    """Raised when a compose spec cannot be parsed."""
