-- ==============================================================================
-- Tabla para persistir intentos de login fallidos (rate limiting server-side)
-- Ejecutar en el SQL Editor de Supabase
-- ==============================================================================
CREATE TABLE IF NOT EXISTS login_attempts (
    documento TEXT PRIMARY KEY,
    intentos INT DEFAULT 0,
    bloqueado_hasta TIMESTAMPTZ,
    ultimo_intento TIMESTAMPTZ DEFAULT NOW()
);

-- Índice para limpieza de registros antiguos (opcional)
CREATE INDEX IF NOT EXISTS idx_login_attempts_ultimo_intento
    ON login_attempts (ultimo_intento);
