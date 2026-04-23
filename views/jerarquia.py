"""
Vista de Jerarquía de Activos - Navegación tipo árbol.
Estructura: Planta → Área → Sub-área → Activo
"""
import streamlit as st
import pandas as pd
from utils.db import supabase, run_query
from utils.catalogos import AREAS_DATA
from utils.helpers import navegar_a


def render():
    st.title("🏗️ JERARQUÍA DE ACTIVOS")
    st.caption("Navega la estructura de tu planta: Planta → Área → Sub-área → Equipo.")

    df_act = run_query("activos")
    df_ordenes = run_query("ordenes")

    if df_act.empty:
        st.info("No hay activos registrados. Ve a Inventario de Activos para crear el primero.")
        return

    # Calcular métricas por ubicación
    mapa_ordenes_abiertas = {}
    if not df_ordenes.empty:
        abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta']
        conteo = abiertas.groupby('activo_id').size().to_dict()
        mapa_ordenes_abiertas = conteo

    # KPIs generales
    total_activos = len(df_act)
    total_areas = len(AREAS_DATA)
    total_subs = sum(len(v) for v in AREAS_DATA.values())
    con_ordenes = len([a for a in df_act['id'] if a in mapa_ordenes_abiertas])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("🏢 Áreas", total_areas)
    k2.metric("📍 Sub-áreas", total_subs)
    k3.metric("🔧 Activos", total_activos)
    k4.metric("⚠️ Con OTs Abiertas", con_ordenes)

    st.markdown("---")

    # ── NAVEGACIÓN POR ÁREA ──
    for area_nombre, sub_areas in sorted(AREAS_DATA.items()):
        # Contar activos en esta area
        activos_area = df_act[df_act['area'] == area_nombre]
        n_activos = len(activos_area)
        ots_area = sum(1 for _, a in activos_area.iterrows() if a['id'] in mapa_ordenes_abiertas)

        area_color = "#3B82F6" if ots_area == 0 else "#F59E0B"
        area_icon = "🏭" if area_nombre == "Producción" else "🏢" if area_nombre == "Administración" else "📦" if area_nombre == "Ventas" else "🚚"

        with st.expander(f"{area_icon} {area_nombre}  —  {n_activos} activos  {'⚠️ ' + str(ots_area) + ' OTs' if ots_area > 0 else '✅'}", expanded=False):
            for sub_area in sorted(sub_areas):
                # Filtrar activos de esta sub-área
                activos_sub = activos_area[
                    activos_area['ubicacion'].str.contains(
                        rf"\[{re_escape(sub_area)}\]", regex=False, na=False
                    )
                ]

                if activos_sub.empty:
                    # Sub-área sin activos
                    st.markdown(f"""
                    <div style="padding:6px 12px;margin:2px 0;color:#6B7280;font-size:0.85rem;">
                        📍 {sub_area} <span style="font-size:0.75rem;">(vacía)</span>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    n_sub = len(activos_sub)
                    ots_sub = sum(1 for _, a in activos_sub.iterrows() if a['id'] in mapa_ordenes_abiertas)
                    badge = f"🔴 {ots_sub} OTs" if ots_sub > 0 else f"🟢 {n_sub} activos"

                    with st.expander(f"📍 {sub_area}  —  {badge}", expanded=False):
                        for _, activo in activos_sub.iterrows():
                            oid = activo['id']
                            tiene_ots = oid in mapa_ordenes_abiertas
                            n_ots = mapa_ordenes_abiertas.get(oid, 0)

                            icono_estado = "🔴" if tiene_ots else "🟢"
                            foto = activo.get('foto_url', '')

                            col_foto, col_info = st.columns([1, 4])
                            with col_foto:
                                if foto and isinstance(foto, str) and len(foto) > 10:
                                    try:
                                        st.image(foto, use_container_width=True)
                                    except Exception as e:
                                        st.caption("📷")
                                        print(f"Error cargando foto jerarquía: {e}")
                                else:
                                    st.markdown("<div style='text-align:center;font-size:2rem;padding:20px;'>🔧</div>", unsafe_allow_html=True)

                            with col_info:
                                st.markdown(f"""
                                <div style="background:rgba(30,41,59,0.5);border-radius:8px;padding:12px;margin-bottom:8px;">
                                    <div style="display:flex;justify-content:space-between;align-items:center;">
                                        <span style="color:#E5E7EB;font-weight:700;font-size:1rem;">{icono_estado} {activo['nombre']}</span>
                                        <span style="font-size:0.75rem;color:#9CA3AF;">ID: {oid}</span>
                                    </div>
                                    <div style="display:flex;gap:15px;margin-top:6px;font-size:0.8rem;color:#9CA3AF;">
                                        <span>🔧 {activo.get('categoria', 'N/A')}</span>
                                        <span>📍 {activo.get('ubicacion', 'N/A')}</span>
                                    </div>
                                </div>
                                """, unsafe_allow_html=True)

                                # Detalles técnicos
                                detalles = activo.get('detalles')
                                if detalles and isinstance(detalles, dict) and len(detalles) > 0:
                                    with st.expander("⚙️ Especificaciones"):
                                        for k, v in detalles.items():
                                            st.markdown(f"**{k}:** {v}")

                                # Botón para ir al activo
                                if st.button(f"📋 Ver ficha completa", key=f"jer_act_{oid}", type="primary"):
                                    navegar_a("Inventario Activos", jump_target="activo", jump_id=oid)
                                if st.button(f"🛠️ Ver sus órdenes", key=f"jer_ot_{oid}", type="secondary"):
                                    navegar_a("Ordenes de Trabajo", jump_target="ordenes_por_activo", jump_id=oid)

    # ── SUB-ÁREAS SIN ÁREA ASIGNADA ──
    activos_sin_area = df_act[~df_act['area'].isin(AREAS_DATA.keys())]
    if not activos_sin_area.empty:
        with st.expander(f"⚠️ Activos sin área asignada  —  {len(activos_sin_area)}", expanded=False):
            for _, act in activos_sin_area.iterrows():
                st.markdown(f"- **{act['nombre']}** (ID: {act['id']}) — Área: {act.get('area', 'N/A')}")


def re_escape(s):
    """Escapa caracteres especiales para regex literal."""
    import re
    return re.escape(s)
