"""
Tests — utils/catalogos.py (integridad de los catálogos maestros).
"""
from utils.catalogos import (
    AREAS_DATA,
    CATEGORIAS_ACTIVOS,
    CATEGORIAS_REPUESTOS,
    COLOR_CRITICIDAD,
    COLOR_ESTADO_OT,
)


class TestAreasData:
    def test_subarea_sala_de_cip_existe(self):
        # Regresión: sub-área agregada el 2026-11-09 a petición del usuario
        assert "Sala de CIP" in AREAS_DATA["Producción"]

    def test_produccion_es_area_valida(self):
        assert "Producción" in AREAS_DATA

    def test_todas_las_areas_tienen_subareas(self):
        for area, subs in AREAS_DATA.items():
            assert len(subs) > 0, f"El área '{area}' no tiene sub-áreas"

    def test_sin_subareas_duplicadas_por_area(self):
        for area, subs in AREAS_DATA.items():
            vistos = [s.strip().lower() for s in subs]
            assert len(vistos) == len(set(vistos)), f"Sub-áreas duplicadas en '{area}'"

    def test_subareas_sin_blancos_extremos(self):
        for area, subs in AREAS_DATA.items():
            for s in subs:
                assert s == s.strip() and s, f"Sub-área inválida en '{area}': {s!r}"


class TestCategorias:
    def test_categorias_activos_unicas(self):
        assert len(CATEGORIAS_ACTIVOS) == len(set(CATEGORIAS_ACTIVOS))

    def test_categorias_activos_ordenadas(self):
        assert CATEGORIAS_ACTIVOS == sorted(CATEGORIAS_ACTIVOS)

    def test_categorias_repuestos_unicas(self):
        assert len(CATEGORIAS_REPUESTOS) == len(set(CATEGORIAS_REPUESTOS))


class TestColores:
    def test_criticidades_cubiertas(self):
        assert set(COLOR_CRITICIDAD) == {"Baja", "Media", "Alta", "Crítica"}

    def test_estados_ot_cubiertos(self):
        assert set(COLOR_ESTADO_OT) == {"Abierta", "Por Validar", "Concluida", "Cancelada"}
