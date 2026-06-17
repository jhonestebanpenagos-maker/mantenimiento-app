-- =============================================================================
-- MIGRACIÓN: Tabla de caché para escaneo rápido de Gmail
-- Fecha: 2026-06-17
-- Descripción: Cachea headers de correos escaneados para evitar
--              re-escanear toda la bandeja cada vez.
-- =============================================================================

-- Tabla principal de caché de headers
CREATE TABLE IF NOT EXISTS email_scan_cache (
    message_id TEXT PRIMARY KEY,
    asunto TEXT DEFAULT '',
    remitente TEXT DEFAULT '',
    fecha_correo TEXT DEFAULT '',
    en_procesados BOOLEAN DEFAULT FALSE,
    en_pendientes BOOLEAN DEFAULT FALSE,
    tiene_cuerpo BOOLEAN DEFAULT FALSE,
    cuerpo_corto TEXT DEFAULT '',
    n_adjuntos INTEGER DEFAULT 0,
    escaneado_en TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_email_scan_fecha
    ON email_scan_cache(fecha_correo);
CREATE INDEX IF NOT EXISTS idx_email_scan_estado
    ON email_scan_cache(en_procesados, en_pendientes);
CREATE INDEX IF NOT EXISTS idx_email_scan_remitente
    ON email_scan_cache USING gin (remitente gin_trgm_ops);

-- Si la extensión trgm no existe, crear el índice sin ella:
-- CREATE INDEX IF NOT EXISTS idx_email_scan_remitente
--     ON email_scan_cache(remitente);

-- Row Level Security
ALTER TABLE email_scan_cache ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'Allow all email_scan_cache'
    ) THEN
        CREATE POLICY "Allow all email_scan_cache" ON email_scan_cache FOR ALL USING (true);
    END IF;
END $$;

-- Comentarios
COMMENT ON TABLE email_scan_cache IS 'Caché local de headers de correos de Gmail para escaneo rápido';
COMMENT ON COLUMN email_scan_cache.message_id IS 'Message-ID del correo (clave primaria)';
COMMENT ON COLUMN email_scan_cache.en_procesados IS 'TRUE si ya existe en emails_procesados';
COMMENT ON COLUMN email_scan_cache.en_pendientes IS 'TRUE si ya existe en emails_pendientes';
COMMENT ON COLUMN email_scan_cache.tiene_cuerpo IS 'TRUE si se descargó el cuerpo completo';
