"""
Writer de auditoria: grava cada evento como uma LINHA JSON (JSON Lines) num
arquivo por data_type — ex: data/Dados-Motor-Diesel.jsonl.

Agrupar por data_type deixa poucos arquivos (um por tipo) e facilita estudar
como cada tipo chega e e parseado. Cada linha e um JSON completo do evento.
Implementa a porta TelemetryFallbackWriter.
"""

import json
import re
from pathlib import Path

from app.domain.entities import TelemetryEvent


def _safe_filename_part(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_") or "root"


class JsonFileWriter:
    def __init__(self, output_dir: str):
        self._dir = Path(output_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def write(self, event: TelemetryEvent) -> None:
        # Um arquivo .jsonl por data_type (category). Nome saneado.
        name = _safe_filename_part(event.category or "sem_categoria")
        path = self._dir / f"{name}.jsonl"

        record = {
            "received_at": event.received_at.isoformat(),
            "topic": event.topic,
            "machine_id": event.machine_id,
            "tenant_id": event.tenant_id,
            "category": event.category,
            "qos": event.qos,
            "retain": event.retain,
            "payload": event.payload,
        }
        line = json.dumps(record, ensure_ascii=False)
        # append: cada mensagem vira uma linha; nada e sobrescrito.
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
