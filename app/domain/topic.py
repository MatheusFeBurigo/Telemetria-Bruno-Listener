"""
Regra de dominio: como um topico MQTT identifica maquina e tipo de dado.

Padrao real dos dispositivos TITAN: {machine_code}/{data_type}
  ex: "TITAN-Maquina Nao Identificad/Dados Motor Diesel"
O 1o nivel e o machine_code (identificador do dispositivo, usado no cadastro);
o restante e o data_type (tipo do dado). O tenant NAO vem do topico:
vem do cadastro da maquina (machines.tenant_id).
"""

import re
from dataclasses import dataclass

_TOPIC_RE = re.compile(r"^([^/]+)/(.+)$")


@dataclass(frozen=True)
class ParsedTopic:
    machine_code: str
    data_type: str


def parse_topic(topic: str) -> ParsedTopic | None:
    """Extrai (machine_code, data_type) do topico, ou None se nao casar.

    O machine_code e sanitizado (strip de \\r, \\n e espacos nas pontas): os
    dispositivos as vezes publicam com carriage return no fim do nome
    (ex: 'THOR - Serie BF0304\\r'), o que criaria uma maquina fantasma.
    """
    m = _TOPIC_RE.match(topic)
    if not m:
        return None
    machine_code = m.group(1).strip().strip("\r\n").strip()
    if not machine_code:
        return None
    return ParsedTopic(machine_code=machine_code, data_type=m.group(2))
