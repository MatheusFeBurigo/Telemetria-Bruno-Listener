"""
Entidades do dominio. Sem dependencia de framework, banco ou broker —
apenas dados e regras que valem em qualquer contexto.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Machine:
    """Maquina pre-cadastrada. tenant_id None = ainda sem cliente atribuido."""

    id: str
    machine_code: str
    tenant_id: str | None


@dataclass(frozen=True)
class TelemetryEvent:
    """Uma mensagem de telemetria pronta para ser persistida."""

    tenant_id: str | None
    machine_id: str
    category: str
    topic: str
    qos: int
    retain: bool
    received_at: datetime
    payload: dict
