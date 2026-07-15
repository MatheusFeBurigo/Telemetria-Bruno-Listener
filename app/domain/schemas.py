"""
Mapa de schemas dos payloads TITAN (CSV posicional).

Fonte: levantamento feito em Excel a partir dos dados REAIS do broker
(o Excel e so o estudo; a fonte de dados continua sendo o broker MQTT).

Cada data_type mapeia para a lista ORDENADA de nomes de campo, incluindo o
1o campo de timestamp ("HoraData"). fields_for() so aplica o schema se o
numero de colunas do payload bater com o esperado — se o dispositivo mudar o
layout, caimos no fallback generico (col_1..N) em vez de nomear errado.

Tipos que chegam como quase-JSON (ex: "Dados Motor Diesel") NAO precisam de
schema aqui: ja vem com os campos nomeados pelo proprio dispositivo.

NOTA: onde a ordem exata das colunas do CSV ainda nao foi confirmada contra o
dado real, o schema fica AUSENTE de proposito (melhor col_N honesto do que um
nome errado). Preencher conforme os payloads reais forem observados com valores
nao-nulos (a maquina estava parada/zerada na captura inicial).
"""

# data_type -> (lista de nomes de campo, incluindo HoraData na posicao 0).
#
# [C] = ordem CONFIRMADA contra dado real do broker.
# [I] = ordem INFERIDA do resumo/estudo (vocabulario de picador florestal);
#       sujeita a ajuste. A protecao de ncols em fields_for() garante que, se a
#       contagem de colunas nao bater, caimos no fallback col_N (nunca nomeia
#       errado). O _raw preservado permite reprocessar se um nome mudar.
_SCHEMAS: dict[str, list[str]] = {
    # --- [C] Confirmados pelo dado real ------------------------------------
    "Horimetro Motor Diesel": ["HoraData", "HorimetroMotorDiesel"],
    "Horimetro Esteiras Locomoção": ["HoraData", "HorimetroEsteiras"],
    "Registro Producao Sem Reset": [
        "HoraData", "ProducaoCol1", "ProducaoCol2", "ProducaoCol3", "DescricaoProducao",
    ],

    # --- [I] Inferidos do resumo (confirmar quando a maquina operar) --------
    # Esteiras esquerda/direita: velocidades e sentidos. Contagem a confirmar.
    "Esteiras": [
        "HoraData", "VelEsteiraEsq", "VelEsteiraDir", "SentidoEsq", "SentidoDir",
    ],
    # Alimentacao: rolos avancando/revertendo, "picando", tensionador.
    "Dados Alimentacao": [
        "HoraData", "VelAlimentacao", "RoloAvancando", "RoloRevertendo",
        "Picando", "P_Tensionador",
    ],
    # Situacao de producao (1 Hz).
    "Situação Produção": [
        "HoraData", "EstadoProducao", "TorqueProducao", "ConsumoInstantaneo",
    ],
    # Dados2 do motor (1/min): temperaturas, tensao de bateria, etc.
    "Dados2 Motor Diesel": [
        "HoraData", "TempOleoMotor", "TempAgua", "TensaoBateria", "HorimetroInstantaneo",
    ],
    # Parametros Astec P1..P9 (1/15min) — ajustaveis.
    "Dados Parametros Astec": [
        "HoraData", "P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9",
    ],
    # Alarme: codigo do ultimo alarme ativo (0..250), por evento.
    "Alarmes": ["HoraData", "CodigoAlarme"],
}


def fields_for(data_type: str, ncols: int) -> list[str] | None:
    """
    Retorna os nomes de campo para o data_type SE o schema existir e o numero
    de colunas bater. Caso contrario None (usa fallback generico col_N).
    """
    names = _SCHEMAS.get(data_type)
    if names is None:
        return None
    if len(names) != ncols:
        # Layout divergente do esperado: nao arrisca nomear errado.
        return None
    return names
