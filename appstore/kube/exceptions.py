"""Exception hierarchy for kube library."""


class KubeError(Exception):
    """Base exception for all kube operations."""

    def __init__(self, message, details=""):
        super().__init__(message)
        self.details = details


class AppError(KubeError):
    """Raised when a HelxApp operation fails."""


class InstanceError(KubeError):
    """Raised when a HelxInst operation fails."""


class UserError(KubeError):
    """Raised when a HelxUser operation fails."""


class SecurityContextError(KubeError):
    """Raised when security context resolution fails."""


class VolumeDSLError(KubeError):
    """Raised when volume DSL parsing fails."""


class StatusError(KubeError):
    """Raised when querying status of derived objects fails."""
