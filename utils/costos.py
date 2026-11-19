"""
Utilidades de Costos para Órdenes de Trabajo.
Registra y calcula costos de mano de obra, repuestos, materiales y servicios externos
usando la tabla relacional `costos_orden`, con respaldo compatible para registros
históricos en `bitacora`.
"""
import html
import re
from datetime import datetime
import streamlit as st
from utils.db import supabase

TIPOS_COSTO_LABELS = {
    "mano_obra": "👷 Mano de Obra",
    "repuesto": "🔩 Repuesto",
    "servicio_externo": "🏢 Servicio Externo",
    "material": "📦 Material",
    "otro": "📋 Otro",
}

TIPOS_COSTO_VALIDOS = set(TIPOS_COSTO_LABELS.keys())


def _normalizar_tipo(tipo_o_label: str) -> str:
    """Normaliza una clave o etiqueta textual de tipo de costo."""
    valor = (tipo_o_label or "").strip()
    if valor in TIPOS_COSTO_VALIDOS:
        return valor
    if "Mano de Obra" in valor:
        return "mano_obra"
    if "Repuesto" in valor:
        return "repuesto"
    if "Servicio" in valor:
        return "servicio_externo"
    if "Material" in valor:
        return "material"
    return "otro"


def registrar_costo(
    orden_id: int,
    usuario: str,
    tipo: str,
    concepto: str,
    monto: float,
    repuesto_id: int = None,
    cantidad: float = None,
) -> bool:
    """Registra un costo en `costos_orden` (con fallback a `bitacora` si la tabla no existe)."""
    tipo_norm = _normalizar_tipo(tipo)
    concepto_limpio = (concepto or "").strip()
    monto_val = float(monto)
    ahora = datetime.now().isoformat()

    payload = {
        "orden_id": int(orden_id),
        "tipo": tipo_norm,
        "concepto": concepto_limpio,
        "monto": monto_val,
        "usuario": usuario or "Sistema",
        "fecha": ahora,
    }
    if repuesto_id is not None:
        payload["repuesto_id"] = int(repuesto_id)
    if cantidad is not None:
        payload["cantidad"] = float(cantidad)

    try:
        supabase.table("costos_orden").insert(payload).execute()
        return True
    except Exception as e_rel:
        print(f"Aviso registrar_costo (fallback a bitacora): {e_rel}")
        try:
            label = TIPOS_COSTO_LABELS.get(tipo_norm, "📋 Costo")
            mensaje = f"[💰 COSTO] {label}: {concepto_limpio} - ${monto_val:,.0f}"
            supabase.table("bitacora").insert({
                "orden_id": int(orden_id),
                "usuario_text": usuario,
                "mensaje": mensaje,
                "fecha": ahora,
            }).execute()
            return True
        except Exception as e_leg:
            st.error("No se pudo registrar el costo.")
            print(f"Error registrar_costo: {e_leg}")
            return False


def _procesar_fila_relacional(reg: dict) -> dict | None:
    """Convierte una fila de `costos_orden` al formato estándar de desglose."""
    if "monto" not in reg or reg.get("monto") is None:
        return None
    try:
        monto = float(reg["monto"])
    except (TypeError, ValueError):
        monto = 0.0

    tipo_key = _normalizar_tipo(reg.get("tipo", "otro"))
    fecha_raw = str(reg.get("fecha") or "")
    reg_id = reg.get("id")

    return {
        "id": reg_id,
        "origen": "costos_orden",
        "tipo": tipo_key,
        "tipo_label": TIPOS_COSTO_LABELS.get(tipo_key, "📋 Otro"),
        "concepto": (reg.get("concepto") or "").strip(),
        "monto": monto,
        "fecha": fecha_raw[:10],
        "usuario": reg.get("usuario") or reg.get("usuario_text") or "?",
        "bitacora_id": reg_id,
        "repuesto_id": reg.get("repuesto_id"),
        "cantidad": reg.get("cantidad"),
    }


def _procesar_fila_bitacora(reg: dict) -> dict | None:
    """Parsea un mensaje `[💰 COSTO]` heredado desde `bitacora`."""
    msg = reg.get("mensaje") or ""
    if "[💰 COSTO]" not in msg:
        return None

    match = re.search(r"\[💰 COSTO\]\s*(.+?):\s*(.+?)\s*[-–—]\s*\$?([\d,.]+)", msg)
    if not match:
        return None

    tipo_label = match.group(1).strip()
    concepto = match.group(2).strip()
    monto_str = match.group(3).replace(",", "")
    try:
        monto = float(monto_str)
    except ValueError:
        monto = 0.0

    tipo_key = _normalizar_tipo(tipo_label)
    fecha_raw = str(reg.get("fecha") or "")
    reg_id = reg.get("id")

    return {
        "id": reg_id,
        "origen": "bitacora",
        "tipo": tipo_key,
        "tipo_label": tipo_label,
        "concepto": concepto,
        "monto": monto,
        "fecha": fecha_raw[:10],
        "usuario": reg.get("usuario_text", "?"),
        "bitacora_id": reg_id,
    }


def _consultar_costos_db(orden_id: int) -> list:
    """Consulta `costos_orden` en Supabase con fallback automático a `bitacora`."""
    try:
        res = (
            supabase.table("costos_orden")
            .select("*")
            .eq("orden_id", int(orden_id))
            .order("fecha")
            .execute()
        )
        return res.data if res.data else []
    except Exception as e_rel:
        print(f"Aviso calcular_costos (fallback a bitacora): {e_rel}")
        res = (
            supabase.table("bitacora")
            .select("*")
            .eq("orden_id", int(orden_id))
            .like("mensaje", "%[💰 COSTO]%")
            .order("fecha")
            .execute()
        )
        return res.data if res.data else []


def calcular_costos(orden_id: int, registros: list = None) -> dict:
    """Calcula el desglose de costos de una orden.

    Acepta `registros` en memoria tanto en formato relacional (`costos_orden`)
    como en formato heredado (`bitacora`). Si `registros` es `None`, consulta
    primero `costos_orden` en Supabase con fallback a `bitacora`.
    """
    resultado = {
        "mano_obra": 0.0,
        "repuesto": 0.0,
        "servicio_externo": 0.0,
        "material": 0.0,
        "otro": 0.0,
        "total": 0.0,
        "registros": [],
    }
    try:
        fuente = registros if registros is not None else _consultar_costos_db(orden_id)
        for reg in fuente:
            if not isinstance(reg, dict):
                continue
            if "monto" in reg and "tipo" in reg:
                item = _procesar_fila_relacional(reg)
            else:
                item = _procesar_fila_bitacora(reg)

            if not item:
                continue

            resultado[item["tipo"]] += item["monto"]
            resultado["total"] += item["monto"]
            resultado["registros"].append(item)
    except Exception as e:
        print(f"Error calcular_costos: {e}")
    return resultado


def eliminar_costo(registro_id: int, origen: str = "costos_orden") -> bool:
    """Elimina un registro de costo de `costos_orden` (o `bitacora` si es legacy)."""
    tabla = "bitacora" if origen == "bitacora" else "costos_orden"
    try:
        supabase.table(tabla).delete().eq("id", int(registro_id)).execute()
        return True
    except Exception as e:
        print(f"Error eliminar_costo ({tabla}): {e}")
        return False


def render_costos(orden_id: int, usuario: str, registros: list = None):
    """Renderiza el widget de costos para una orden."""
    st.markdown("##### 💰 Registro de Costos")

    costos = calcular_costos(orden_id, registros=None) if supabase is not None else calcular_costos(orden_id, registros)
    if not costos["registros"] and registros:
        costos = calcular_costos(orden_id, registros)

    c_mo, c_rep, c_ext, c_tot = st.columns(4)
    with c_mo:
        st.metric("👷 Mano de Obra", f"${costos['mano_obra']:,.0f}")
    with c_rep:
        st.metric("🔩 Repuestos", f"${costos['repuesto']:,.0f}")
    with c_ext:
        st.metric("🏢 Serv. Externos", f"${costos['servicio_externo']:,.0f}")
    with c_tot:
        st.metric("💰 TOTAL", f"${costos['total']:,.0f}")

    if st.toggle("➕ Registrar Costo", key=f"toggle_costo_{orden_id}"):
        with st.form(f"form_costo_{orden_id}", clear_on_submit=True):
            c_t, c_c, c_m = st.columns(3)
            tipo_costo = c_t.selectbox(
                "Tipo",
                ["mano_obra", "repuesto", "servicio_externo", "material", "otro"],
                format_func=lambda x: TIPOS_COSTO_LABELS[x],
            )
            concepto = c_c.text_input("Concepto", placeholder="Ej: Reparación motor")
            monto = c_m.number_input("Monto ($)", min_value=0.0, value=0.0, step=1000.0)

            if st.form_submit_button("💾 REGISTRAR COSTO", type="primary"):
                if not concepto or monto <= 0:
                    st.error("Complete el concepto y un monto mayor a 0.")
                else:
                    if registrar_costo(orden_id, usuario, tipo_costo, concepto, monto):
                        st.toast("✅ Costo registrado.")
                        st.rerun()

    if costos["registros"]:
        st.markdown("---")
        st.markdown("**📜 Desglose de Costos**")
        for reg in reversed(costos["registros"]):
            c_info, c_del = st.columns([5, 1])
            tipo_safe = html.escape(str(reg["tipo_label"]))
            concepto_safe = html.escape(str(reg["concepto"]))
            fecha_safe = html.escape(str(reg["fecha"]))
            usuario_safe = html.escape(str(reg["usuario"]))
            with c_info:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border-left:3px solid #F59E0B;padding:8px 12px;margin-bottom:4px;border-radius:0 6px 6px 0;">
                    <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                        <span style="color:#E5E7EB;">{tipo_safe}</span>
                        <span style="color:#F59E0B;font-weight:700;">${reg['monto']:,.0f}</span>
                    </div>
                    <div style="color:#9CA3AF;font-size:0.8rem;">{concepto_safe} - {fecha_safe} por {usuario_safe}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_del:
                origen = reg.get("origen", "costos_orden")
                reg_id = reg.get("id", reg.get("bitacora_id"))
                if st.button("🗑️", key=f"del_costo_{origen}_{reg_id}", help="Eliminar"):
                    eliminar_costo(reg_id, origen=origen)
                    st.toast("Costo eliminado.")
                    st.rerun()