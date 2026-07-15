"""
Repositorio de telemetria no-op: nao persiste em lugar nenhum, apenas reporta
sucesso. Usado no modo "so arquivo" (TELEMETRY_SINK=file), em que a gravacao
oficial vai para arquivos .jsonl locais via JsonFileWriter, sem tocar no banco.
"""

from app.domain.entities import TelemetryEvent


class NullTelemetryRepository:
    def save(self, event: TelemetryEvent) -> bool:
        return True
