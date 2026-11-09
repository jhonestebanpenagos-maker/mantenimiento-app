"""
Tests — utils/time_tracking.py (sesiones de trabajo, modo memoria).
"""
from datetime import datetime

from utils.time_tracking import (
    sesion_activa,
    obtener_tiempo_inicio,
    calcular_total_horas,
    obtener_resumen_sesiones,
)


def _reg(id_, mensaje, fecha, usuario="jperez"):
    return {"id": id_, "mensaje": mensaje, "fecha": fecha, "usuario_text": usuario}


INICIO = "[⏱️ INICIO] Sesión de trabajo iniciada."


class TestSesionActiva:
    def test_sin_registros(self):
        assert sesion_activa(1, registros=[]) is False

    def test_inicio_sin_fin_es_activa(self):
        regs = [_reg(1, INICIO, "2026-11-09T08:00:00")]
        assert sesion_activa(1, registros=regs) is True

    def test_fin_despues_de_inicio_no_es_activa(self):
        regs = [
            _reg(1, INICIO, "2026-11-09T08:00:00"),
            _reg(2, "[⏱️ FIN] Sesión cerrada. Duración: 1h 0m", "2026-11-09T09:00:00"),
        ]
        assert sesion_activa(1, registros=regs) is False

    def test_nuevo_inicio_despues_de_fin_es_activa(self):
        regs = [
            _reg(1, INICIO, "2026-11-09T08:00:00"),
            _reg(2, "[⏱️ FIN] Sesión cerrada. Duración: 1h 0m", "2026-11-09T09:00:00"),
            _reg(3, INICIO, "2026-11-09T10:00:00"),
        ]
        assert sesion_activa(1, registros=regs) is True


class TestTiempoInicio:
    def test_sin_inicios_retorna_none(self):
        assert obtener_tiempo_inicio(1, registros=[]) is None

    def test_retorna_ultimo_inicio(self):
        regs = [
            _reg(1, INICIO, "2026-11-09T08:00:00"),
            _reg(2, INICIO, "2026-11-09T10:30:00"),
        ]
        ts = obtener_tiempo_inicio(1, registros=regs)
        assert ts == datetime(2026, 11, 9, 10, 30, 0)


class TestCalcularTotalHoras:
    def test_suma_duraciones(self):
        regs = [
            _reg(1, "[⏱️ FIN] Sesión cerrada. Duración: 2h 30m", "2026-11-09T10:30:00"),
            _reg(2, "[⏱️ FIN] Sesión cerrada. Duración: 1h 15m", "2026-11-09T17:00:00"),
        ]
        assert calcular_total_horas(1, registros=regs) == 3.75

    def test_redondea_a_2_decimales(self):
        regs = [_reg(1, "[⏱️ FIN] Duración: 0h 20m", "2026-11-09T08:20:00")]
        assert calcular_total_horas(1, registros=regs) == 0.33

    def test_ignora_mensajes_sin_duracion(self):
        regs = [
            _reg(1, "[⏱️ FIN] Sesión cerrada.", "2026-11-09T09:00:00"),
            _reg(2, INICIO, "2026-11-09T08:00:00"),
        ]
        assert calcular_total_horas(1, registros=regs) == 0.0

    def test_sin_registros(self):
        assert calcular_total_horas(1, registros=[]) == 0.0


class TestResumenSesiones:
    def test_sesion_completa(self):
        regs = [
            _reg(1, INICIO, "2026-11-09T08:00:00", usuario="mlopez"),
            _reg(2, "[⏱️ FIN] Sesión cerrada. Duración: 2h 30m Nota: Probado OK",
                 "2026-11-09T10:30:00"),
        ]
        sesiones = obtener_resumen_sesiones(1, registros=regs)
        assert len(sesiones) == 1
        s = sesiones[0]
        assert s["inicio"] == "2026-11-09T08:00:00"
        assert s["fin"] == "2026-11-09T10:30:00"
        assert s["duracion"] == "2h 30m"
        assert s["nota"] == "Probado OK"
        assert s["usuario"] == "mlopez"
        assert s["bitacora_inicio_id"] == 1
        assert s["bitacora_fin_id"] == 2

    def test_sesion_abierta_queda_en_curso(self):
        regs = [_reg(1, INICIO, "2026-11-09T08:00:00")]
        sesiones = obtener_resumen_sesiones(1, registros=regs)
        assert len(sesiones) == 1
        assert sesiones[0]["fin"] is None
        assert "curso" in sesiones[0]["duracion"]

    def test_orden_cronologico(self):
        regs = [
            _reg(3, "[⏱️ FIN] Duración: 1h 0m", "2026-11-09T09:00:00"),
            _reg(2, INICIO, "2026-11-09T08:00:00"),
            _reg(5, "[⏱️ FIN] Duración: 2h 0m", "2026-11-09T13:00:00"),
            _reg(4, INICIO, "2026-11-09T11:00:00"),
        ]
        sesiones = obtener_resumen_sesiones(1, registros=regs)
        assert len(sesiones) == 2
        assert sesiones[0]["inicio"] == "2026-11-09T08:00:00"
        assert sesiones[1]["inicio"] == "2026-11-09T11:00:00"

    def test_sin_registros(self):
        assert obtener_resumen_sesiones(1, registros=[]) == []
