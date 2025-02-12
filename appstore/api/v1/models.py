import logging
import os
from dataclasses import dataclass, InitVar, field

logger = logging.getLogger(__name__)


@dataclass
class Resources:
    cpus: float
    gpus: int
    memory: str
    ephemeralStorage: str


@dataclass
class App:
    """Tycho app attributes."""

    name: str
    app_id: str
    description: str
    detail: str
    docs: str
    spec: str
    count: int
    minimum_resources: dict
    maximum_resources: dict


@dataclass
class Instance:
    """Tycho instance attributes."""

    name: str
    docs: str
    aid: str
    sid: str
    fqsid: str
    workspace_name: str
    creation_time: str
    cpus: float
    gpus: int
    memory: float
    ephemeralStorage: str
    host: InitVar[str]
    username: InitVar[str]
    is_ready: bool
    url: str = field(init=False)
    status: str = field(init=False)
    protocol: InitVar[str] = os.environ.get("ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http")

    def __post_init__(self, host, username, protocol):
        # TODO use urllib to confirm construction of a valid resource path
        # http://0.0.0.0:8000/private/jupyter-ds/admin/018b22862f8b44858cca6ad84430b364
        self.url = (
            f"{self.protocol}://{host}/private/{self.aid}/" f"{username}/{self.sid}/"
        )

        # Would be better to get this from tycho per app based on the pod status
        # in kubernetes. That could then be provided via the rest endpoint to a
        # client, or using sockets a notification on pod status change.
        if self.aid is None or "None" in self.url:
            self.status = "starting"
        else:
            self.status = "ready"

        logger.debug(f"{self.name} app-networking constructed url: {self.url}")


@dataclass
class ResourceRequest:
    """Resource request spec."""

    app_id: str
    cpus: float
    gpus: int
    memory: str
    ephemeralStorage: str = ""
    resources: dict = None

    def __post_init__(self):
        
        # Dividing resources by 2 for reservations
        # This helps in cloud scenarios to reduce costs.
        if self.cpus >= 0.5:
            self.cpus_reservation = self.cpus / 2  # Allow fractional CPU reservation
        else:
            self.cpus_reservation = self.cpus
        self.gpus_reservation = self.gpus
        # self.gpus_reservation = self.gpus // 2  # Use floor division for integer GPUs
        self.memory_reservation = self._divide_memory(self.memory)
        
        self.resources = {
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": self.cpus,
                        "memory": self.memory,
                        "gpus": self.gpus,
                        "ephemeralStorage": self.ephemeralStorage,
                    },
                    "reservations": {
                        "cpus": self.cpus_reservation,
                        "memory": self.memory_reservation,
                        "gpus": self.gpus_reservation,
                        "ephemeralStorage": self.ephemeralStorage,
                    },
                }
            }
        }
        
    def _divide_memory(self, memory: str) -> str:
        """Helper method to divide memory by 2 (converting G to M and ensuring result is never less than 100M)."""
        # Case for G (Gigabytes) - SI prefix
        if memory.endswith("G"):
            value = float(memory[:-1])  # Extract numeric value (removes 'G' suffix)
            # Convert G (Gigabytes) to M (Megabytes) - SI (1 GB = 1000 MB)
            value_in_m = value * 1000
            # Divide the value by 2
            divided_value = value_in_m / 2
            # Ensure the result is not less than 100M
            if divided_value < 100:
                divided_value = 100
            return f"{int(divided_value)}M"
        
        # Case for M (Megabytes) - SI prefix
        elif memory.endswith("M"):
            value = float(memory[:-1])  # Extract numeric value (removes 'M' suffix')
            # Divide the value by 2
            divided_value = value / 2
            # Ensure the result is not less than 100M
            if divided_value < 100:
                divided_value = 100
            return f"{int(divided_value)}M"
        
        # Case for Gi (Gibibytes) - IEC prefix
        elif memory.endswith("Gi"):
            value = float(memory[:-2])  # Extract numeric value (removes 'Gi' suffix)
            # Convert Gi (Gibibytes) to Mi (Mebibytes) - IEC (1 Gi = 1024 Mi)
            value_in_mi = value * 1024
            # Divide the value by 2
            divided_value = value_in_mi / 2
            # Ensure the result is not less than 100Mi
            if divided_value < 100:
                divided_value = 100
            return f"{int(divided_value)}Mi"
        
        # Case for Mi (Mebibytes) - IEC prefix
        elif memory.endswith("Mi"):
            value = float(memory[:-2])  # Extract numeric value (removes 'Mi' suffix)
            # Divide the value by 2
            divided_value = value / 2
            # Ensure the result is not less than 100Mi
            if divided_value < 100:
                divided_value = 100
            return f"{int(divided_value)}Mi"
        # Default case for unrecognized memory format
        else:
            return memory  # Return as is if the format is not recognized



@dataclass
class InstanceSpec:
    """App instance spec submitted to tycho."""

    username: str
    app_id: str
    name: str
    host: str
    resources: dict
    ip: InitVar[str]
    port: InitVar[int]
    svc_id: InitVar[str]
    sys_id: InitVar[str]
    url: str = field(init=False)
    sid: str = field(init=False)
    protocol: str = os.environ.get("ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http")

    def __post_init__(self, ip, port, svc_id, sys_id):
        logger.debug(f'{"Finishing spec construction."}')

        if ip:
            self.url = f"http://{ip}:{port}"
        elif sys_id:
            self.url = (
                f"{self.protocol}://{self.host}/private/{self.app_id}/"
                f"{self.username}/{sys_id}/"
            )
        else:
            self.url = (
                f"{self.protocol}://{self.host}/private/{self.app_id}/"
                f"{self.username}/{svc_id}/"
            )
        self.sid = sys_id
        logger.debug(f"-- app-networking constructed url: {self.url}")


@dataclass
class LoginProvider:
    """Login provider attributes."""

    name: str
    url: str

@dataclass
class User:
    REMOTE_USER: str
    ACCESS_TOKEN: str
    SESSION_TIMEOUT: int