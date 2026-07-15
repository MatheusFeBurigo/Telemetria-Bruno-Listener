-- ============================================================================
-- Migration 0003: registra a maquina de teste "Bancada".
--
-- A maquina que publica os dados de teste ainda nao existe fisicamente:
-- e uma bancada TITAN. O dispositivo publica com o 1o nivel do topico
-- 'TITAN-Maquina Não Identificad' — esse valor E o machine_code e precisa
-- ser mantido exatamente assim para o Listener aceitar as mensagens.
--
-- Aqui registramos (ou renomeamos, se a 0002 ja inseriu) essa maquina como
-- "Bancada", marcando no metadata que e ambiente de teste.
-- ============================================================================

INSERT INTO machines (machine_code, name, model, status, metadata)
VALUES (
    'TITAN-Maquina Não Identificad',
    'Bancada',
    'TITAN',
    'unassigned',
    '{"ambiente": "bancada_teste", "fisica": false}'::jsonb
)
ON CONFLICT (machine_code) DO UPDATE
SET name     = EXCLUDED.name,
    model    = EXCLUDED.model,
    metadata = machines.metadata || EXCLUDED.metadata;
