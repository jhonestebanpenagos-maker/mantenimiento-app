-- ==============================================================================
-- sql/002_costos_orden.sql
-- Fase 2 (Entregable 2.1) — Tabla relacional de costos por Orden de Trabajo
-- Ejecutar una vez en el SQL Editor de Supabase (es seguro e idempotente).
-- ==============================================================================

CREATE TABLE IF NOT EXISTS public.costos_orden (
    id BIGSERIAL PRIMARY KEY,
    orden_id BIGINT NOT NULL REFERENCES public.ordenes(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('mano_obra', 'repuesto', 'servicio_externo', 'material', 'otro')),
    concepto TEXT NOT NULL,
    monto NUMERIC(14, 2) NOT NULL CHECK (monto >= 0),
    usuario TEXT NOT NULL DEFAULT 'Sistema',
    repuesto_id BIGINT NULL,
    cantidad NUMERIC(12, 3) NULL,
    bitacora_legacy_id BIGINT NULL UNIQUE,
    fecha TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_costos_orden_orden_fecha
    ON public.costos_orden (orden_id, fecha DESC);

CREATE INDEX IF NOT EXISTS idx_costos_orden_tipo
    ON public.costos_orden (tipo);

-- Vista agregada para analítica SQL, tablero de mando y reportes por OT
CREATE OR REPLACE VIEW public.v_costos_por_orden AS
SELECT
    orden_id,
    COALESCE(SUM(monto) FILTER (WHERE tipo = 'mano_obra'), 0) AS mano_obra,
    COALESCE(SUM(monto) FILTER (WHERE tipo = 'repuesto'), 0) AS repuesto,
    COALESCE(SUM(monto) FILTER (WHERE tipo = 'servicio_externo'), 0) AS servicio_externo,
    COALESCE(SUM(monto) FILTER (WHERE tipo = 'material'), 0) AS material,
    COALESCE(SUM(monto) FILTER (WHERE tipo = 'otro'), 0) AS otro,
    COALESCE(SUM(monto), 0) AS total,
    COUNT(*) AS cantidad_registros
FROM public.costos_orden
GROUP BY orden_id;

-- ==============================================================================
-- Migración idempotente de costos históricos desde public.bitacora
-- Soporta guion corto (-), semirraya (–) y raya larga (—) antes del monto.
-- ==============================================================================
INSERT INTO public.costos_orden (
    orden_id,
    tipo,
    concepto,
    monto,
    usuario,
    bitacora_legacy_id,
    fecha
)
SELECT
    b.orden_id,
    CASE
        WHEN m[1] ILIKE '%Mano de Obra%' THEN 'mano_obra'
        WHEN m[1] ILIKE '%Repuesto%' THEN 'repuesto'
        WHEN m[1] ILIKE '%Servicio%' THEN 'servicio_externo'
        WHEN m[1] ILIKE '%Material%' THEN 'material'
        ELSE 'otro'
    END AS tipo,
    TRIM(m[2]) AS concepto,
    COALESCE(NULLIF(REPLACE(m[3], ',', ''), '')::NUMERIC(14, 2), 0) AS monto,
    COALESCE(NULLIF(TRIM(b.usuario_text), ''), 'Sistema') AS usuario,
    b.id AS bitacora_legacy_id,
    COALESCE(b.fecha::TIMESTAMPTZ, NOW()) AS fecha
FROM public.bitacora b
CROSS JOIN LATERAL regexp_match(
    b.mensaje,
    '\[💰 COSTO\]\s*(.+?):\s*(.+?)\s*[-–—]\s*\$?([\d,.]+)'
) AS m
INNER JOIN public.ordenes o ON o.id = b.orden_id
WHERE b.mensaje LIKE '%[💰 COSTO]%'
  AND m IS NOT NULL
ON CONFLICT (bitacora_legacy_id) DO NOTHING;