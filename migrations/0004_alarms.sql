-- ============================================================================
-- Migration 0004: tabela dedicada de ALARMES.
--
-- Por que separar de telemetry: alarme e evento RARO, mas a telemetry e
-- dominada (~99%) pelos dados densos (motor/maquina a ~2s). Varrer a telemetry
-- para achar as poucas ativacoes fica caro conforme ela cresce. Uma tabela
-- propria torna a leitura do historico de alarmes instantanea e isolada.
--
-- Fonte: cada linha de telemetry com category='Alarmes Ativos' que carrega
-- CodigoAlarme/Descricao e uma ATIVACAO. O Listener passa a gravar aqui tambem
-- (em paralelo a telemetry); esta migration faz o BACKFILL do que ja existe.
-- ============================================================================

-- ---------------------------------------------------------------------------
-- ALARMS (ativacoes de alarme por maquina)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS alarms (
    id           BIGSERIAL   PRIMARY KEY,
    tenant_id    UUID        REFERENCES tenants (id)  ON DELETE SET NULL,
    machine_id   UUID        NOT NULL REFERENCES machines (id) ON DELETE CASCADE,
    code         TEXT,
    description  TEXT,
    -- instante da ativacao (hora da maquina quando conhecida; senao a de chegada)
    activated_at TIMESTAMPTZ NOT NULL,
    -- rastro de origem: id da linha telemetry que originou a ativacao (dedup do
    -- backfill). UNIQUE na tabela para servir de alvo do ON CONFLICT abaixo —
    -- multiplos NULL sao permitidos (insercoes do Listener nao preenchem source_id).
    source_id    BIGINT      UNIQUE,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Garante a UNIQUE de source_id mesmo se a tabela ja existir de uma tentativa
-- anterior (o CREATE TABLE IF NOT EXISTS teria pulado a coluna). Idempotente:
-- so cria a constraint se ainda nao houver. Sem isso, o ON CONFLICT abaixo
-- falharia (42P10) num banco onde a tabela nasceu sem a constraint.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'alarms_source_id_key'
    ) THEN
        ALTER TABLE alarms ADD CONSTRAINT alarms_source_id_key UNIQUE (source_id);
    END IF;
END $$;

-- Consulta tipica do painel: alarmes de UMA maquina, mais recentes primeiro.
CREATE INDEX IF NOT EXISTS idx_alarms_machine_time
    ON alarms (machine_id, activated_at DESC);
CREATE INDEX IF NOT EXISTS idx_alarms_tenant ON alarms (tenant_id);

-- ---------------------------------------------------------------------------
-- BACKFILL: importa as ativacoes ja gravadas em telemetry.
--   - so linhas 'Alarmes Ativos' que tenham codigo OU descricao (payload
--     vazio = "sem alarme" -> ignorado);
--   - activated_at prefere o _ts (hora da maquina), cai para received_at;
--   - ON CONFLICT (source_id) faz a operacao ser idempotente (re-executavel).
-- ---------------------------------------------------------------------------
INSERT INTO alarms (tenant_id, machine_id, code, description, activated_at, source_id)
SELECT
    t.tenant_id,
    t.machine_id,
    NULLIF(t.payload ->> 'CodigoAlarme', '') AS code,
    NULLIF(t.payload ->> 'Descricao',    '') AS description,
    COALESCE(
        -- _ts vem em ISO-8601 quando reconhecido pelo Listener
        (NULLIF(t.payload ->> '_ts', ''))::timestamptz,
        t.received_at
    ) AS activated_at,
    t.id AS source_id
FROM telemetry t
WHERE t.category = 'Alarmes Ativos'
  AND (
        NULLIF(t.payload ->> 'CodigoAlarme', '') IS NOT NULL
     OR NULLIF(t.payload ->> 'Descricao',    '') IS NOT NULL
  )
ON CONFLICT (source_id) DO NOTHING;
