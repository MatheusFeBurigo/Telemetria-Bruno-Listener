"""
Caso de uso central do Listener: ingerir uma mensagem MQTT.

Fluxo:
  1. Faz parse do topico ({machine_code}/{data_type}).
  2. Resolve a maquina (via MachineRepository); auto-registra como pendente
     (sem cliente) se ainda nao existir. So falha se o repositorio cair.
  3. Monta o TelemetryEvent e persiste (via TelemetryRepository).

Nao conhece MQTT, HTTP nem banco: recebe dados crus e fala com portas.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable

from app.application.ports import (
    AlarmRepository,
    MachineRepository,
    TelemetryFallbackWriter,
    TelemetryRepository,
)
from app.domain.alarm import ALARM_CATEGORY, alarm_from_payload
from app.domain.entities import TelemetryEvent
from app.domain.payload import decode_payload
from app.domain.topic import parse_topic


class IngestStatus(Enum):
    SAVED = "saved"
    INVALID_TOPIC = "invalid_topic"
    UNKNOWN_MACHINE = "unknown_machine"
    SAVE_FAILED = "save_failed"


@dataclass(frozen=True)
class IngestResult:
    status: IngestStatus
    event: TelemetryEvent | None = None
    machine_code: str | None = None


class IngestTelemetry:
    def __init__(
        self,
        machines: MachineRepository,
        telemetry: TelemetryRepository,
        fallback: TelemetryFallbackWriter | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
        alarms: AlarmRepository | None = None,
    ):
        self._machines = machines
        self._telemetry = telemetry
        self._fallback = fallback
        self._clock = clock
        self._alarms = alarms

    def execute(self, topic: str, payload: bytes, qos: int, retain: bool) -> IngestResult:
        parsed = parse_topic(topic)
        if parsed is None:
            return IngestResult(IngestStatus.INVALID_TOPIC)

        # Auto-registra a maquina se ela ainda nao existir (status pendente,
        # sem cliente). None aqui = falha de rede/config, nao "desconhecida".
        machine = self._machines.ensure_by_code(parsed.machine_code)
        if machine is None:
            return IngestResult(
                IngestStatus.UNKNOWN_MACHINE, machine_code=parsed.machine_code
            )

        event = TelemetryEvent(
            tenant_id=machine.tenant_id,
            machine_id=machine.id,
            category=parsed.data_type,
            topic=topic,
            qos=qos,
            retain=retain,
            received_at=self._clock(),
            payload=decode_payload(payload, parsed.data_type),
        )

        saved = self._telemetry.save(event)
        if self._fallback is not None:
            self._fallback.write(event)

        # Alarme: se esta linha e uma ATIVACAO, grava tambem na tabela dedicada
        # `alarms`. Best-effort e isolado — falha aqui nao afeta a telemetria.
        if self._alarms is not None and event.category == ALARM_CATEGORY:
            alarm = alarm_from_payload(event.payload, event.received_at)
            if alarm is not None:
                self._alarms.save(
                    tenant_id=event.tenant_id,
                    machine_id=event.machine_id,
                    code=alarm.code,
                    description=alarm.description,
                    activated_at=alarm.activated_at,
                )

        status = IngestStatus.SAVED if saved else IngestStatus.SAVE_FAILED
        return IngestResult(status, event=event, machine_code=parsed.machine_code)
