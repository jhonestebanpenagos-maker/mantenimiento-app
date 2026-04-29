-- ==============================================================================
-- MIGRACIÓN: Tablas de persistencia de correos
-- Ejecutar en el SQL Editor de Supabase
-- ==============================================================================

-- Tabla de correos pendientes (descargados pero aún no gestionados)
CREATE TABLE IF NOT EXISTS emails_pendientes (
    message_id TEXT PRIMARY KEY,
    remitente TEXT,
    remitente_nombre TEXT,
    asunto TEXT,
    fecha_correo TEXT,
    cuerpo_corto TEXT,
    n_adjuntos INTEGER DEFAULT 0,
    leido BOOLEAN DEFAULT FALSE,
    descargado_en TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para emails_pendientes
CREATE INDEX IF NOT EXISTS idx_emails_pendientes_descargado ON emails_pendientes(descargado_en DESC);

-- Tabla de correos procesados (si no existe ya)
CREATE TABLE IF NOT EXISTS emails_procesados (
    message_id TEXT PRIMARY KEY,
    orden_id INTEGER,
    accion TEXT DEFAULT 'orden',
    fecha_procesado TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para emails_procesados
CREATE INDEX IF NOT EXISTS idx_emails_procesados_accion ON emails_procesados(accion);
CREATE INDEX IF NOT EXISTS idx_emails_procesados_orden ON emails_procesados(orden_id);

-- RLS (Row Level Security) — Deshabilitar para uso interno de la app
ALTER TABLE emails_pendientes ENABLE ROW LEVEL SECURITY;
ALTER TABLE emails_procesados ENABLE ROW LEVEL SECURITY;

-- Políticas permisivas (la app se autentica con service key)
CREATE POLICY "Allow all on emails_pendientes" ON emails_pendientes FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on emails_procesados" ON emails_procesados FOR ALL USING (true) WITH CHECK (true);

-- Comentarios
COMMENT ON TABLE emails_pendientes IS 'Correos descargados de Gmail pendientes de gestión (Crear OT, Vincular, Descartar)';
COMMENT ON TABLE emails_procesados IS 'Correos que ya fueron gestionados (convertidos en OT, vinculados, o descartados)';
