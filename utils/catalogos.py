"""
Catálogos maestros compartidos entre módulos.
Centraliza áreas, sub-áreas, categorías y otros datos maestros.
"""

# ==============================================================================
# 🏭 ESTRUCTURA DE LA PLANTA
# ==============================================================================
AREAS_DATA = {
    "Producción": [
        "Agua Cristal", "B&B", "Calderas", "Cuarto de Lubricación", "Equipos Auxiliares",
        "Laboratorio Fisico Quimico", "Laboratorio Microbiológico", "Linea 1", "Linea 2",
        "Linea 3", "Linea 10", "Linea 8 Jugos", "Oficinas Técnicas", "Pasillo Técnico",
        "Ptap", "Ptar", "Sala de Jarabe Simple", "Sala de Jarabe Terminado",
        "Sala de Jarabes Jugos", "Sub Estación Eléctrica", "Taller de Mantenimiento"
    ],
    "Administración": ["Administración", "Auditorio", "Casino", "Portería Vehicular", "Servicios Generales"],
    "Ventas": ["Bodega Carrera 8va", "Bodega Publicidad", "Dispensadores", "Ventas"],
    "Logística": ["Almacen Materia Prima", "Almacén Producto Terminado", "Lavadero de Vehiculos",
                   "Punto de Canje", "Taller de Reparación de Estibas", "Taller Vehicular"]
}

# ==============================================================================
# 📂 CATEGORÍAS
# ==============================================================================
CATEGORIAS_ACTIVOS = sorted([
    "Aire Acondicionado", "CCTV", "Control de Acceso", "Eléctrico", "Estanterías",
    "Extraccion", "Hidrosanitario", "Infraestructura", "Mecánico", "Muelles",
    "Red Contra Incendio", "Refrigeración Industrial", "Ventilacion"
])

CATEGORIAS_REPUESTOS = sorted([
    "Eléctrico", "Mecánico", "Hidráulico", "Neumático", "Lubricantes", "Filtros",
    "Correas y Cadenas", "Rodamientos", "Electrónico", "Herramientas", "Otros"
])

# ==============================================================================
# 🎨 MAPAS DE COLOR
# ==============================================================================
COLOR_CRITICIDAD = {
    "Baja": "#10B981",
    "Media": "#F59E0B",
    "Alta": "#EA580C",
    "Crítica": "#EF4444"
}

COLOR_ESTADO_OT = {
    "Abierta": "#F59E0B",
    "Por Validar": "#60A5FA",
    "Concluida": "#10B981",
    "Cancelada": "#EF4444"
}
