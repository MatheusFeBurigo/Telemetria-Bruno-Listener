-- ============================================================================
-- Migration 0001: esquema inicial de telemetria multi-tenant.
--
-- Modelo:
--   tenants   (clientes)
--   machines  (maquinas; podem existir SEM tenant ate serem atribuidas)
--   telemetry (mensagens MQTT, ligadas a tenant + machine)
--
-- Identificacao via topico: {machine_code}/{data_type}
-- Maquinas sao PRE-CADASTRADAS. O Listener so grava telemetria de machine_code
-- ja existente; o vinculo maquina<->cliente (tenant_id) e feito depois.
-- ============================================================================

-- Extensao para UUID (Supabase ja costuma ter habilitada).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ---------------------------------------------------------------------------
-- TENANTS (clientes)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tenants (
    id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    -- slug curto e estavel usado na hierarquia do topico MQTT (ex: "acme").
    slug        TEXT        NOT NULL UNIQUE,
    name        TEXT        NOT NULL,
    status      TEXT        NOT NULL DEFAULT 'active'
                            CHECK (status IN ('active', 'suspended')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- MACHINES (maquinas)
--   - machine_code: identificador usado no topico (ex: "maq01"). Unico global.
--   - tenant_id: NULL enquanto a maquina nao foi atribuida a um cliente.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS machines (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    machine_code  TEXT        NOT NULL UNIQUE,
    tenant_id     UUID        REFERENCES tenants (id) ON DELETE SET NULL,
    name          TEXT,
    model         TEXT,
    -- ciclo de vida do provisionamento / atribuicao.
    status        TEXT        NOT NULL DEFAULT 'unassigned'
                              CHECK (status IN ('unassigned', 'assigned', 'inactive')),
    assigned_at   TIMESTAMPTZ,
    metadata      JSONB       NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_machines_tenant ON machines (tenant_id);
CREATE INDEX IF NOT EXISTS idx_machines_code   ON machines (machine_code);

-- ---------------------------------------------------------------------------
-- TELEMETRY (mensagens MQTT)
--   - tenant_id denormalizado: copiado da maquina no momento da gravacao,
--     para o RLS e os filtros do painel serem rapidos sem JOIN.
--   - category: tipo de dado vindo do topico (ex: "Dados Motor Diesel").
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS telemetry (
    id           BIGSERIAL   PRIMARY KEY,
    tenant_id    UUID        REFERENCES tenants (id)  ON DELETE SET NULL,
    machine_id   UUID        NOT NULL REFERENCES machines (id) ON DELETE CASCADE,
    category     TEXT,
    topic        TEXT        NOT NULL,
    qos          SMALLINT    NOT NULL,
    retain       BOOLEAN     NOT NULL DEFAULT FALSE,
    received_at  TIMESTAMPTZ NOT NULL,
    payload      JSONB       NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indices alinhados aos filtros do painel (cliente, maquina, tempo, categoria).
CREATE INDEX IF NOT EXISTS idx_telemetry_tenant      ON telemetry (tenant_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_machine     ON telemetry (machine_id);
CREATE INDEX IF NOT EXISTS idx_telemetry_received_at ON telemetry (received_at DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_category    ON telemetry (category);
-- Consulta tipica: dados de uma maquina numa janela de tempo.
CREATE INDEX IF NOT EXISTS idx_telemetry_machine_time
    ON telemetry (machine_id, received_at DESC);
CREATE INDEX IF NOT EXISTS idx_telemetry_payload     ON telemetry USING GIN (payload);

-- ---------------------------------------------------------------------------
-- ROW LEVEL SECURITY
--   A secret key (service_role) que o Listener usa IGNORA o RLS, entao a
--   gravacao continua funcionando. As policies abaixo isolam o acesso quando
--   o painel/backend usar chaves de usuario (anon/authenticated) no futuro.
-- ---------------------------------------------------------------------------
ALTER TABLE tenants   ENABLE ROW LEVEL SECURITY;
ALTER TABLE machines  ENABLE ROW LEVEL SECURITY;
ALTER TABLE telemetry ENABLE ROW LEVEL SECURITY;

-- Sem policies, ninguem com chave de usuario acessa (default deny).
-- Quando definirmos como o usuario do painel se vincula a um tenant
-- (ex: tabela tenant_users + auth.uid()), criamos as policies de SELECT aqui.
