-- migration_v2.sql
-- Migração para sistema de consultas gratuitas
-- Substituindo "7 dias grátis" por "5 consultas grátis"

BEGIN;

-- Adicionar novos campos à tabela usuarios
ALTER TABLE usuarios ALTER COLUMN data_expiracao DROP NOT NULL;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS consultas_gratis INTEGER DEFAULT 5;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS assinante BOOLEAN DEFAULT FALSE;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS consultas_mes INTEGER DEFAULT 0;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS limite_consultas INTEGER DEFAULT 100;
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS data_pagamento DATE;

-- Migrar usuários ATIVOS (data_expiracao > agora) → viram assinantes
UPDATE usuarios
SET assinante = TRUE,
    consultas_gratis = 0,
    consultas_mes = 0,
    limite_consultas = 100,
    data_pagamento = CURRENT_DATE
WHERE data_expiracao > CURRENT_TIMESTAMP;

-- Migrar usuários EXPIRADOS → ganham 5 consultas grátis
UPDATE usuarios
SET assinante = FALSE,
    consultas_gratis = 5,
    consultas_mes = 0,
    limite_consultas = 100,
    data_expiracao = NULL
WHERE data_expiracao <= CURRENT_TIMESTAMP OR data_expiracao IS NULL;

COMMIT;
