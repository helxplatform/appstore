import logging
import os
from dataclasses import dataclass, InitVar

logger = logging.getLogger(__name__)


@dataclass
class Resources:
    cpus: float
    gpus: int
    memory: str


@dataclass
class App:
    """Tycho app attributes."""

    name: str
    app_id: str
    description: str
    detail: str
    docs: str
    spec: str
    minimum_resources: dict
    maximum_resources: dict


@dataclass
class Service:
    """Tycho service attributes."""

    name: str
    docs: str
    sid: str
    fqsid: str
    creation_time: str
    cpus: float
    gpus: int
    memory: float


@dataclass
class ResourceRequest:
    """Resource request spec."""

    app_id: str
    cpus: float
    gpus: int
    memory: str
    resources: dict = None

    def __post_init__(self):
        self.resources = {
            "deploy": {
                "resources": {
                    "limits": {
                        "cpus": self.cpus,
                        "memory": self.memory,
                        "gpus": self.gpus,
                    },
                    "reservations": {
                        "cpus": self.cpus,
                        "memory": self.memory,
                        "gpus": self.gpus,
                    },
                }
            }
        }


@dataclass
class ServiceSpec:
    """Service spec submitted to tycho."""

    username: str
    app_id: str
    name: str
    host: str
    resources: dict
    url: str
    ip: InitVar[str] = None
    port: InitVar[int] = None
    svc_id: InitVar[str] = None
    sys_id: InitVar[str] = None
    protocol: str = os.environ.get("ACCOUNT_DEFAULT_HTTP_PROTOCOL", "http")

    def __post_init__(self, ip, port, svc_id, sys_id):
        logger.debug(f"Finishing spec construction.")

        if ip:
            self.url = f"http://{self.ip}:{port}"
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
        logger.debug(f"-- app-networking constructed url: {self.url}")


@dataclass
class LoginProvider:
    """Login provider attributes."""

    name: str
    url: str
    redirect: str = None
