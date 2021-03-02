from dataclasses import dataclass


@dataclass
class Service:
    """Tycho service attributes."""
    name: str
    docs: str
    identifier: str
    service_id: str
    creation_time: str
    cpu: int
    gpu: int
    memory: float


@dataclass
class App:
    """Tycho app attributes."""
    name: str
    app_id: str
    description: str
    detail: str
    docs: str
    spec: str
