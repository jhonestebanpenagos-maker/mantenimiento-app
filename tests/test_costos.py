"""
Tests — utils/costos.py (cálculo de costos en modo relacional `costos_orden`
y modo heredado `bitacora`).
"""
from utils.costos import calcular_costos


def _reg(id_, mensaje, fecha="2026-11-09T10:00:00", usuario="jperez"):
    return {"id": id_, "mensaje": mensaje, "fecha": fecha, "usuario_text": usuario}


def _reg_rel(id_, tipo, concepto, monto, fecha="2026-11-19T10:00:00+00:00", usuario="jperez"):
    return {
        "id": id_,
        "orden_id": 1,
        "tipo": tipo,
        "concepto": concepto,
        "monto": monto,
        "fecha": fecha,
        "usuario": usuario,
    }


class TestCalcularCostosLegacyBitacora:
    def test_desglose_por_tipo_y_total(self):
        registros = [
            _reg(1, "[💰 COSTO] 👷 Mano de Obra: Cambio de correa - $150,000"),
            _reg(2, "[💰 COSTO] 🔩 Repuesto: Rodamiento 6204 - $80,500"),
            _reg(3, "[💰 COSTO] 🏢 Servicio Externo: Soldadura - $200,000"),
            _reg(4, "[💰 COSTO] 📦 Material: Tornillos - $10,000"),
            _reg(5, "[💰 COSTO] 📋 Costo: Reparación menor - $5,000"),
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
        registros = [_reg(1, "[💰 COSTO] 🔩 Repuesto: Motor - $1,250,000")]
        r = calcular_costos(1, registros=registros)
        assert r["repuesto"] == 1250000.0
        assert r["total"] == 1250000.0

    def test_soporta_raya_larga_em_dash(self):
        registros = [
            _reg(1, "[💰 COSTO] 🏢 Servicio Externo: Pago contratista Serboomerang — $13,525,000"),
            _reg(2, "[💰 COSTO] 🏢 Servicio Externo: contratista muñoz reparacion  — $1,800,000"),
        ]
        r = calcular_costos(1, registros=registros)
        assert r["servicio_externo"] == 15325000.0
        assert r["total"] == 15325000.0
        assert len(r["registros"]) == 2

    def test_ignora_mensajes_que_no_son_costos(self):
        registros = [
            _reg(1, "[⏱️ INICIO] Sesión de trabajo iniciada."),
            _reg(2, "[💰 COSTO] 🔩 Repuesto: Filtro - $30,000"),
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
            _reg(42, "[💰 COSTO] 👷 Mano de Obra: Ajuste - $25,000",
                 fecha="2026-11-09T14:30:00", usuario="mlopez"),
        ]
        r = calcular_costos(1, registros=registros)
        reg = r["registros"][0]
        assert reg["tipo"] == "mano_obra"
        assert reg["tipo_label"] == "👷 Mano de Obra"
        assert reg["concepto"] == "Ajuste"
        assert reg["monto"] == 25000.0
        assert reg["fecha"] == "2026-11-09"
        assert reg["usuario"] == "mlopez"
        assert reg["bitacora_id"] == 42
        assert reg["origen"] == "bitacora"

    def test_tipo_desconocido_cae_en_otro(self):
        registros = [_reg(1, "[💰 COSTO] 🚚 Flete: Transporte - $60,000")]
        r = calcular_costos(1, registros=registros)
        assert r["otro"] == 60000.0


class TestCalcularCostosRelacional:
    def test_desglose_relacional_completo(self):
        registros = [
            _reg_rel(10, "mano_obra", "Técnico 2h", 120000),
            _reg_rel(11, "repuesto", "Sello mecánico", 95500.5),
            _reg_rel(12, "servicio_externo", "Bobinado", 310000),
            _reg_rel(13, "material", "Grasa alta temp", 18000),
            _reg_rel(14, "otro", "Viáticos", 25000),
        ]
        r = calcular_costos(1, registros=registros)
        assert r["mano_obra"] == 120000.0
        assert r["repuesto"] == 95500.5
        assert r["servicio_externo"] == 310000.0
        assert r["material"] == 18000.0
        assert r["otro"] == 25000.0
        assert r["total"] == 568500.5
        assert len(r["registros"]) == 5

    def test_campos_relacionales_y_origen(self):
        registros = [_reg_rel(77, "repuesto", "Valvula 2in", "45000.00", usuario="agomez")]
        r = calcular_costos(1, registros=registros)
        reg = r["registros"][0]
        assert reg["id"] == 77
        assert reg["origen"] == "costos_orden"
        assert reg["tipo"] == "repuesto"
        assert reg["tipo_label"] == "🔩 Repuesto"
        assert reg["concepto"] == "Valvula 2in"
        assert reg["monto"] == 45000.0
        assert reg["fecha"] == "2026-11-19"
        assert reg["usuario"] == "agomez"

    def test_monto_none_se_ignora_y_tipo_invalido_va_a_otro(self):
        registros = [
            _reg_rel(1, "mano_obra", "Inválido", None),
            _reg_rel(2, "desconocido", "Flete", 15000),
        ]
        r = calcular_costos(1, registros=registros)
        assert len(r["registros"]) == 1
        assert r["otro"] == 15000.0
        assert r["total"] == 15000.0