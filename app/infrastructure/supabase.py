"""
Adaptadores Supabase (API REST / PostgREST): implementam as portas
MachineRepository e TelemetryRepository usando HTTP.
"""

import time

import requests

from app.domain.entities import Machine, TelemetryEvent
from app.infrastructure.config import Settings


def build_http_session(settings: Settings) -> requests.Session:
    """Sessao HTTP reutilizada (keep-alive) com as credenciais do Supabase."""
    session = requests.Session()
    session.headers.update(
        {
            "apikey": settings.supabase_key or "",
            "Authorization": f"Bearer {settings.supabase_key}" if settings.supabase_key else "",
            "Content-Type": "application/json",
        }
    )
    return session


class SupabaseMachineRepository:
    def __init__(self, settings: Settings, http: requests.Session):
        self._rest_base = f"{settings.supabase_url}/rest/v1" if settings.supabase_url else None
        self._configured = bool(self._rest_base and settings.supabase_key)
        self._timeout = settings.http_timeout
        self._http = http

    def find_by_code(self, machine_code: str) -> Machine | None:
        if not self._configured:
            print("[REST] SUPABASE_URL/SUPABASE_KEY nao configurados no .env")
            return None

        try:
            resp = self._http.get(
                f"{self._rest_base}/machines",
                params={
                    "machine_code": f"eq.{machine_code}",
                    "select": "id,tenant_id,status",
                    "limit": "1",
                },
                timeout=self._timeout,
            )
            if resp.status_code != 200:
                print(
                    f"[REST] Falha ao consultar machines: HTTP {resp.status_code} {resp.text[:200]}"
                )
                return None
            rows = resp.json()
        except requests.RequestException as exc:
            print(f"[REST] Erro de rede consultando machines: {exc}")
            return None

        if not rows:
            return None

        row = rows[0]
        return Machine(
            id=row["id"],
            machine_code=machine_code,
            tenant_id=row.get("tenant_id"),
        )

    def ensure_by_code(self, machine_code: str) -> Machine | None:
        """Retorna a maquina; se nao existir, auto-registra como pendente."""
        existing = self.find_by_code(machine_code)
        if existing is not None:
            return existing

        if not self._configured:
            return None

        # Auto-registro: cria a maquina 'pendente' (sem cliente). O upsert com
        # merge-duplicates trata corrida entre mensagens da mesma maquina nova.
        body = {"machine_code": machine_code, "status": "unassigned"}
        try:
            resp = self._http.post(
                f"{self._rest_base}/machines",
                params={"on_conflict": "machine_code"},
                json=body,
                headers={
                    "Prefer": "resolution=merge-duplicates,return=representation",
                },
                timeout=self._timeout,
            )
            if resp.status_code not in (200, 201):
                print(
                    f"[REST] Falha ao auto-registrar maquina: HTTP {resp.status_code} {resp.text[:200]}"
                )
                # Pode ter sido criada em paralelo; tenta ler de novo.
                return self.find_by_code(machine_code)
            rows = resp.json()
        except requests.RequestException as exc:
            print(f"[REST] Erro de rede auto-registrando maquina: {exc}")
            return None

        if not rows:
            return self.find_by_code(machine_code)

        row = rows[0]
        print(f"[NOVA] Maquina auto-registrada (pendente): {machine_code!r}")
        return Machine(id=row["id"], machine_code=machine_code, tenant_id=row.get("tenant_id"))


class SupabaseTelemetryRepository:
    def __init__(self, settings: Settings, http: requests.Session):
        self._rest_base = f"{settings.supabase_url}/rest/v1" if settings.supabase_url else None
        self._timeout = settings.http_timeout
        self._http = http

    def save(self, event: TelemetryEvent) -> bool:
        body = {
            "tenant_id": event.tenant_id,
            "machine_id": event.machine_id,
            "category": event.category,
            "topic": event.topic,
            "qos": event.qos,
            "retain": event.retain,
            "received_at": event.received_at.isoformat(),
            "payload": event.payload,
        }
        for attempt in (1, 2, 3):
            try:
                resp = self._http.post(
                    f"{self._rest_base}/telemetry",
                    json=body,
                    headers={"Prefer": "return=minimal"},
                    timeout=self._timeout,
                )
                if resp.status_code in (200, 201, 204):
                    return True
                print(f"[REST] insert telemetry HTTP {resp.status_code}: {resp.text[:300]}")
                if 400 <= resp.status_code < 500:
                    return False
            except requests.RequestException as exc:
                print(f"[REST] Erro de rede no insert (tentativa {attempt}): {exc}")
            time.sleep(1.5 * attempt)
        print("[REST] Telemetria NAO gravada apos retries.")
        return False


class SupabaseAlarmRepository:
    """Grava ativacoes de alarme na tabela dedicada `alarms`. Best-effort:
    problemas aqui nao devem impedir a gravacao normal da telemetria."""

    def __init__(self, settings: Settings, http: requests.Session):
        self._rest_base = f"{settings.supabase_url}/rest/v1" if settings.supabase_url else None
        self._timeout = settings.http_timeout
        self._http = http

    def save(
        self,
        tenant_id: str | None,
        machine_id: str,
        code: str | None,
        description: str | None,
        activated_at,
        source_id: int | None = None,
    ) -> bool:
        if not self._rest_base:
            return False
        body = {
            "tenant_id": tenant_id,
            "machine_id": machine_id,
            "code": code,
            "description": description,
            "activated_at": activated_at.isoformat(),
            "source_id": source_id,
        }
        for attempt in (1, 2):
            try:
                resp = self._http.post(
                    f"{self._rest_base}/alarms",
                    json=body,
                    headers={"Prefer": "return=minimal"},
                    timeout=self._timeout,
                )
                if resp.status_code in (200, 201, 204):
                    return True
                print(f"[REST] insert alarm HTTP {resp.status_code}: {resp.text[:200]}")
                if 400 <= resp.status_code < 500:
                    return False
            except requests.RequestException as exc:
                print(f"[REST] Erro de rede no insert de alarme (tentativa {attempt}): {exc}")
            time.sleep(1.0 * attempt)
        return False
