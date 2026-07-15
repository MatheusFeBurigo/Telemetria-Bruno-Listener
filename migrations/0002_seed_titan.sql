-- ============================================================================
-- Migration 0002: dados iniciais (seed) para o fluxo multi-tenant TITAN.
--
-- IMPORTANTE: machine_code deve ser EXATAMENTE a string que o dispositivo
-- publica no 1o nivel do topico. Observado no EMQX:
--   "TITAN-Maquina Não Identificad/Dados Motor Diesel"
--                ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ este e o machine_code
--
-- A maquina abaixo esta PRE-CADASTRADA porem SEM cliente (unassigned).
-- O vinculo a um tenant e feito depois (fluxo de atribuicao).
-- Idempotente: ON CONFLICT DO NOTHING.
-- ============================================================================

-- Cliente de exemplo (para quando a maquina for atribuida).
INSERT INTO tenants (slug, name)
VALUES ('acme', 'ACME Mineracao')
ON CONFLICT (slug) DO NOTHING;

-- Maquina TITAN real, pre-cadastrada e ainda SEM dono.
-- Assim o Listener aceita a telemetria (machine cadastrada) gravando com
-- tenant_id NULL ate a atribuicao.
INSERT INTO machines (machine_code, name, model, status)
VALUES ('TITAN-Maquina Não Identificad', 'TITAN (não identificada)', 'TITAN', 'unassigned')
ON CONFLICT (machine_code) DO NOTHING;
