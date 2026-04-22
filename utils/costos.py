"""
Utilidades de Costos para Órdenes de Trabajo.
Registra y calcula costos de mano de obra, repuestos y servicios externos.
"""
import streamlit as st
import re
from datetime import datetime
from utils.db import supabase


def registrar_costo(orden_id: int, usuario: str, tipo: str, concepto: str, monto: float) -> bool:
    """
    Registra un costo en la bitácora de la orden.
    tipos: 'mano_obra', 'repuesto', 'servicio_externo', 'material', 'otro'
    """
    try:
        tipos_labels = {
            "mano_obra": "👷 Mano de Obra",
            "repuesto": "🔩 Repuesto",
            "servicio_externo": "🏢 Servicio Externo",
            "material": "📦 Material",
            "otro": "📋 Otro"
        }
        label = tipos_labels.get(tipo, "📋 Costo")
        mensaje = f"[💰 COSTO] {label}: {concepto} — ${monto:,.0f}"

        supabase.table("bitacora").insert({
            "orden_id": int(orden_id),
            "usuario_text": usuario,
            "mensaje": mensaje,
            "fecha": datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error("No se pudo registrar el costo.")
        print(f"Error registrar_costo: {e}")
        return False


def calcular_costos(orden_id: int) -> dict:
    """
    Calcula el desglose de costos de una orden desde la bitácora.
    Retorna dict con totales por tipo y total general.
    """
    resultado = {
        "mano_obra": 0.0,
        "repuesto": 0.0,
        "servicio_externo": 0.0,
        "material": 0.0,
        "otro": 0.0,
        "total": 0.0,
        "registros": []
    }

    try:
        res = supabase.table("bitacora").select("*") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%[💰 COSTO]%") \
            .order("fecha") \
            .execute()

        if not res.data:
            return resultado

        for reg in res.data:
            msg = reg['mensaje']
            # Parsear: [💰 COSTO] Tipo: Concepto — $Monto
            match = re.search(r'\[💰 COSTO\]\s*(.+?):\s*(.+?)\s*—\s*\$?([\d,.]+)', msg)
            if match:
                tipo_label = match.group(1).strip()
                concepto = match.group(2).strip()
                monto_str = match.group(3).replace(',', '')
                try:
                    monto = float(monto_str)
                except ValueError:
                    monto = 0.0

                # Mapear label a clave
                tipo_key = "otro"
                if "Mano de Obra" in tipo_label:
                    tipo_key = "mano_obra"
                elif "Repuesto" in tipo_label:
                    tipo_key = "repuesto"
                elif "Servicio" in tipo_label:
                    tipo_key = "servicio_externo"
                elif "Material" in tipo_label:
                    tipo_key = "material"

                resultado[tipo_key] += monto
                resultado["total"] += monto
                resultado["registros"].append({
                    "tipo": tipo_key,
                    "tipo_label": tipo_label,
                    "concepto": concepto,
                    "monto": monto,
                    "fecha": reg['fecha'][:10],
                    "usuario": reg.get('usuario_text', '?'),
                    "bitacora_id": reg['id']
                })

    except Exception as e:
        print(f"Error calcular_costos: {e}")

    return resultado


def eliminar_costo(bitacora_id: int) -> bool:
    """Elimina un registro de costo de la bitácora."""
    try:
        supabase.table("bitacora").delete().eq("id", bitacora_id).execute()
        return True
    except Exception:
        return False


def render_costos(orden_id: int, usuario: str):
    """Renderiza el widget de costos para una orden."""
    st.markdown("##### 💰 Registro de Costos")

    costos = calcular_costos(orden_id)

    # Resumen visual
    c_mo, c_rep, c_ext, c_tot = st.columns(4)
    with c_mo:
        st.metric("👷 Mano de Obra", f"${costos['mano_obra']:,.0f}")
    with c_rep:
        st.metric("🔩 Repuestos", f"${costos['repuesto']:,.0f}")
    with c_ext:
        st.metric("🏢 Serv. Externos", f"${costos['servicio_externo']:,.0f}")
    with c_tot:
        st.metric("💰 TOTAL", f"${costos['total']:,.0f}")

    # Formulario para agregar costo
    with st.expander("➕ Registrar Costo"):
        with st.form(f"form_costo_{orden_id}", clear_on_submit=True):
            c_t, c_c, c_m = st.columns(3)
            tipo_costo = c_t.selectbox("Tipo", [
                "mano_obra", "repuesto", "servicio_externo", "material", "otro"
            ], format_func=lambda x: {
                "mano_obra": "👷 Mano de Obra",
                "repuesto": "🔩 Repuesto",
                "servicio_externo": "🏢 Servicio Externo",
                "material": "📦 Material",
                "otro": "📋 Otro"
            }[x])
            concepto = c_c.text_input("Concepto", placeholder="Ej: Reparación motor")
            monto = c_m.number_input("Monto ($)", min_value=0.0, value=0.0, step=1000.0)

            if st.form_submit_button("💾 REGISTRAR COSTO", type="primary"):
                if not concepto or monto <= 0:
                    st.error("Complete el concepto y un monto mayor a 0.")
                else:
                    if registrar_costo(orden_id, usuario, tipo_costo, concepto, monto):
                        st.toast("✅ Costo registrado.")
                        st.rerun()

    # Tabla de costos registrados
    if costos['registros']:
        st.markdown("---")
        st.markdown("**📜 Desglose de Costos**")
        for reg in reversed(costos['registros']):
            c_info, c_del = st.columns([5, 1])
            with c_info:
                st.markdown(f"""
                <div style="background:rgba(255,255,255,0.03);border-left:3px solid #F59E0B;padding:8px 12px;margin-bottom:4px;border-radius:0 6px 6px 0;">
                    <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                        <span style="color:#E5E7EB;">{reg['tipo_label']}</span>
                        <span style="color:#F59E0B;font-weight:700;">${reg['monto']:,.0f}</span>
                    </div>
                    <div style="color:#9CA3AF;font-size:0.8rem;">{reg['concepto']} — {reg['fecha']} por {reg['usuario']}</div>
                </div>
                """, unsafe_allow_html=True)
            with c_del:
                if st.button("🗑️", key=f"del_costo_{reg['bitacora_id']}", help="Eliminar"):
                    eliminar_costo(reg['bitacora_id'])
                    st.toast("Costo eliminado.")
                    st.rerun()
