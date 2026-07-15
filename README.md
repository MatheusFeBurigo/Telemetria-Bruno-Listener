# Telemetria — Listener MQTT (EMQX → PostgreSQL)

Serviço **listener** dedicado que se inscreve nos tópicos do broker EMQX
(TLS/8883), recebe as mensagens publicadas por outra aplicação e grava cada
uma no **PostgreSQL**. Um backend separado (a ser desenvolvido) lê desse mesmo
banco para filtrar e servir o painel.

## Arquitetura

```
[App publica] → MQTT(TLS) → [Listener] → [PostgreSQL] ← [Backend/API] → [Painel]
                                              ↑
                                  fonte única da verdade
```

- O **listener** só escreve no banco. Roda como processo único, sempre ligado.
- O **backend** só lê do banco. São desacoplados — reiniciar um não afeta o outro.

## Conexão MQTT

- **Host:** `t0ceb6f9.ala.us-east-1.emqxsl.com`
- **Porta (TLS):** `8883`

## Clean Architecture (estrutura do código)

O código segue Clean Architecture: as dependências apontam sempre **para
dentro** (infraestrutura → aplicação → domínio; nunca o contrário).

```
main.py                          ← raiz de composição: monta e injeta tudo
app/
  domain/                        ← centro: puro, sem dependências externas
    entities.py                  Machine, TelemetryEvent
    topic.py                     regra de parse do tópico ({machine_code}/{data_type})
    payload.py                   regra de decodificação do payload (json/texto/binário)
  application/                   ← casos de uso: orquestram o domínio via portas
    ports.py                     MachineRepository, TelemetryRepository, FallbackWriter
    ingest_telemetry.py          IngestTelemetry: parse → resolve máquina → grava
  infrastructure/                ← borda: implementa as portas com tecnologia real
    config.py                    Settings (único lugar que lê o .env)
    supabase.py                  repositórios via API REST do Supabase
    machine_cache.py             cache TTL (decorator sobre MachineRepository)
    json_file_writer.py          fallback opcional em arquivo .json
    mqtt_subscriber.py           adaptador paho-mqtt (entrada)
tests/
  test_ingest_telemetry.py       caso de uso testado com fakes, sem rede
```

Regras ao criar cada parte nova da aplicação:

- **Regra de negócio nova** → `domain/` (função/entidade pura) ou um caso de
  uso em `application/`, falando só com portas.
- **Tecnologia nova** (outro banco, outra fila, API) → adaptador em
  `infrastructure/` implementando uma porta de `application/ports.py`.
- **Nada em `domain/` ou `application/` importa de `infrastructure/`.**
  Só o `main.py` conhece as implementações concretas.
- Todo caso de uso nasce com teste em `tests/` usando fakes (rode
  `python -m unittest`).

## Arquivos

| Arquivo | Função |
|---|---|
| `main.py` | Ponto de entrada: injeta dependências e sobe o listener |
| `app/` | Código da aplicação em camadas (domain / application / infrastructure) |
| `migrations/` | Evolução versionada do banco (`0001_...sql`, `0002_...sql`, ...), aplicadas manualmente |
| `tests/` | Testes unitários dos casos de uso (`python -m unittest`) |
| `.env` | Configuração (NÃO commitar — está no .gitignore) |

## Migrations (evolução do banco)

Toda mudança no banco (tabela nova, coluna, índice, seed) entra como um
arquivo SQL numerado em `migrations/`. As migrations são **aplicadas
manualmente** — copie o conteúdo do arquivo e rode no SQL Editor do Supabase
(ou via `psql` com a `DATABASE_URL` de conexão direta), na ordem numérica.

```
migrations/
  0001_initial_schema.sql    schema base (tenants, machines, telemetry)
  0002_seed_titan.sql        seed do fluxo TITAN
  0003_maquina_bancada.sql   máquina de bancada
  0004_alarms.sql            tabela dedicada de alarmes + backfill
```

Regras do fluxo:

- **Uma mudança = uma migration.** Cada nova parte da aplicação que precisar
  de banco (alertas, usuários do painel, policies de RLS...) nasce como uma
  migration nova, com o próximo número.
- **Aplique na ordem** e apenas as que ainda não rodou naquele banco.
- **Escreva SQL idempotente** (`IF NOT EXISTS`, `ON CONFLICT DO NOTHING`,
  guardas `DO $$ ... $$`) — assim reaplicar uma migration é seguro. Todas as
  migrations do projeto seguem isso.

## Deploy recomendado: Docker Compose

Pré-requisito: Docker instalado (Docker Desktop no Windows/Mac, ou Docker Engine no Linux).

```bash
# 1. Configure o .env (copie de .env.example se necessário)
copy .env.example .env   # e preencha credenciais

# 2. Suba listener + banco em segundo plano
docker compose up -d --build

# 3. Acompanhe os logs do listener
docker compose logs -f listener
```

Pronto. O listener conecta no EMQX e grava cada mensagem na tabela
`mqtt_messages`. O `restart: unless-stopped` garante que ele volta sozinho se
cair ou se o servidor reiniciar.

### Comandos úteis

```bash
docker compose ps                 # status dos serviços
docker compose logs -f listener   # logs ao vivo
docker compose restart listener   # reinicia só o listener
docker compose down               # para tudo (mantém os dados no volume)
docker compose down -v            # para tudo E apaga o banco (cuidado)
```

### Acessar o banco

O PostgreSQL fica exposto em `localhost:5432` (user/senha/db conforme `.env`).
Use DBeaver, `psql` ou o futuro backend para consultar:

```sql
SELECT topic, received_at, payload
FROM mqtt_messages
ORDER BY received_at DESC
LIMIT 20;
```

## Rodar SEM Docker (desenvolvimento local)

Precisa de um PostgreSQL acessível e da `DATABASE_URL` no `.env`.

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
# aplique as migrations pendentes de migrations/ no banco (SQL Editor / psql)
python main.py
```

## Estrutura de cada registro (tabela mqtt_messages)

| coluna | tipo | descrição |
|---|---|---|
| `id` | bigint | PK auto-incremento |
| `topic` | text | tópico MQTT |
| `qos` | smallint | 0, 1 ou 2 |
| `retain` | boolean | mensagem retida? |
| `received_at` | timestamptz | quando o listener recebeu (UTC) |
| `payload` | jsonb | `{"json": {...}}`, `{"text": "..."}` ou `{"raw_hex": "..."}` |
| `created_at` | timestamptz | quando foi inserido no banco |

O `payload` é JSONB: se a mensagem for JSON válido, fica consultável com
operadores JSON do PostgreSQL (ex: `payload->'json'->>'valor'`).

## Migrar para um servidor depois

Como tudo está em Docker, mover para produção é copiar o projeto + `.env` para
o servidor (VPS Linux, AWS, etc.) e rodar o mesmo `docker compose up -d`.
Nada no código muda.

## Próximos passos

- Restringir `MQTT_TOPICS` no `.env` aos tópicos reais (após descobri-los com `#`).
- Desenvolver o **backend/API** que lê de `mqtt_messages` e serve o painel.
- (Se o volume crescer muito) considerar TimescaleDB e/ou uma fila intermediária.
