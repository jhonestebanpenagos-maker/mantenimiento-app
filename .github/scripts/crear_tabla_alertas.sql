-- Tabla para rastrear alertas ya enviadas (evita duplicados)
-- Ejecutar en el SQL Editor de Supabase

CREATE TABLE IF NOT EXISTS alertas_enviadas (
    id BIGSERIAL PRIMARY KEY,
    tipo TEXT NOT NULL,           -- 'solicitud' o 'correo'
    item_id TEXT NOT NULL,        -- id de solicitud o message_id de correo
    alertado_en TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(tipo, item_id)
);

-- Índice para búsquedas rápidas
CREATE INDEX IF NOT EXISTS idx_alertas_enviadas_tipo_item
    ON alertas_enviadas(tipo, item_id);

-- Habilitar RLS (ajustar según tus políticas)
ALTER TABLE alertas_enviadas ENABLE ROW LEVEL SECURITY;

-- Política permisiva (mismo patrón que tus otras tablas)
CREATE POLICY "Allow all" ON alertas_enviadas FOR ALL USING (true);
