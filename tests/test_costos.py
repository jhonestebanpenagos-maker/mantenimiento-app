"""
Tests — utils/costos.py (cálculo de costos desde bitácora, modo memoria).
"""
from utils.costos import calcular_costos


def _reg(id_, mensaje, fecha="2026-11-09T10:00:00", usuario="jperez"):
    return {"id": id_, "mensaje": mensaje, "fecha": fecha, "usuario_text": usuario}


class TestCalcularCostos:
    def test_desglose_por_tipo_y_total(self):
        registros = [
            _reg(1, "[💰 COSTO] 👷 Mano de Obra: Cambio de correa — $150,000"),
            _reg(2, "[💰 COSTO] 🔩 Repuesto: Rodamiento 6204 — $80,500"),
            _reg(3, "[💰 COSTO] 🏢 Servicio Externo: Soldadura — $200,000"),
            _reg(4, "[💰 COSTO] 📦 Material: Tornillos — $10,000"),
            _reg(5, "[💰 COSTO] 📋 Costo: Reparación menor — $5,000"),
        ]
        r = calcular_costos(1, registros=registros)

        assert r["mano_obra"] == 150000.0
        assert r["repuesto"] == 80500.0
        assert r["servicio_externo"] == 200000.0
        assert r["material"] == 10000.0
        assert r["otro"] == 5000.0
        assert r["total"] == 445500.0
        assert len(r["registros"]) == 5

    def test_monto_con_comas(self):
        registros = [_reg(1, "[💰 COSTO] 🔩 Repuesto: Motor — $1,250,000")]
        r = calcular_costos(1, registros=registros)
        assert r["repuesto"] == 1250000.0
        assert r["total"] == 1250000.0

    def test_ignora_mensajes_que_no_son_costos(self):
        registros = [
            _reg(1, "[⏱️ INICIO] Sesión de trabajo iniciada."),
            _reg(2, "[💰 COSTO] 🔩 Repuesto: Filtro — $30,000"),
            _reg(3, "Avance general sin costo."),
        ]
        r = calcular_costos(1, registros=registros)
        assert len(r["registros"]) == 1
        assert r["total"] == 30000.0

    def test_mensaje_none_no_revienta(self):
        registros = [{"id": 1, "mensaje": None, "fecha": "2026-11-09", "usuario_text": "x"}]
        r = calcular_costos(1, registros=registros)
        assert r["total"] == 0.0
        assert r["registros"] == []

    def test_registro_vacio(self):
        r = calcular_costos(1, registros=[])
        assert r["total"] == 0.0
        assert r["registros"] == []
        assert r["mano_obra"] == 0.0

    def test_campos_del_registro_desglosado(self):
        registros = [
            _reg(42, "[💰 COSTO] 👷 Mano de Obra: Ajuste — $25,000",
                 fecha="2026-11-09T14:30:00", usuario="mlopez"),
        ]
        r = calcular_costos(1, registros=registros)
        reg = r["registros"][0]
        assert reg["tipo"] == "mano_obra"
        assert reg["tipo_label"] == "👷 Mano de Obra"
        assert reg["concepto"] == "Ajuste"
        assert reg["monto"] == 25000.0
        assert reg["fecha"] == "2026-11-09"   # solo la fecha, sin hora
        assert reg["usuario"] == "mlopez"
        assert reg["bitacora_id"] == 42

    def test_tipo_desconocido_cae_en_otro(self):
        registros = [_reg(1, "[💰 COSTO] 🚚 Flete: Transporte — $60,000")]
        r = calcular_costos(1, registros=registros)
        assert r["otro"] == 60000.0
