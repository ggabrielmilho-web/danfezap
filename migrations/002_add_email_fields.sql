-- Migration 002: Adicionar campos de email e estado de conversa
-- Adiciona funcionalidade de envio de DANFE por email

-- Adicionar campos de email na tabela usuarios
ALTER TABLE usuarios
ADD COLUMN IF NOT EXISTS email VARCHAR(255),
ADD COLUMN IF NOT EXISTS email_secundario VARCHAR(255),
ADD COLUMN IF NOT EXISTS aguardando_email_principal BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS aguardando_email_secundario BOOLEAN DEFAULT FALSE;

-- Criar índice para busca por email
CREATE INDEX IF NOT EXISTS idx_usuarios_email ON usuarios(email);

-- Comentários nas colunas para documentação
COMMENT ON COLUMN usuarios.email IS 'Email principal do usuário para receber DANFE';
COMMENT ON COLUMN usuarios.email_secundario IS 'Email secundário (contador, transportadora, etc.)';
COMMENT ON COLUMN usuarios.aguardando_email_principal IS 'Estado de conversa: aguardando cadastro de email principal';
COMMENT ON COLUMN usuarios.aguardando_email_secundario IS 'Estado de conversa: aguardando cadastro de email secundário';
