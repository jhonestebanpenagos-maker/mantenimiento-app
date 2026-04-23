# ==============================================================================
# views/dashboard.py — TABLERO COMPLETO EN UNA SOLA HOJA
# ==============================================================================
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.db import run_query
from utils.helpers import mostrar_notificaciones, navegar_a
from utils.nav_button import render_back_button
from utils.notifications import verificar_sla_y_alertar
from utils.charts import (
    mostrar_metricas_inteligentes, graficar_tendencia_semanal,
    mostrar_tops_ordenes, mostrar_kpis_industriales, graficar_estado_barras,
    graficar_criticidad, graficar_torta_tipo, graficar_ordenes_por_tecnico,
    semaforo_tecnicos
)
from utils.excel_gen import generar_excel_historial


# ==============================================================================
# 🎨 SEPARADORES VISUALES
# ==============================================================================
def _seccion(titulo, icono="📊"):
    """Renderiza un encabezado de sección con estilo consistente."""
    st.markdown(f"""
    <div style="margin: 30px 0 15px 0; padding-bottom: 8px; border-bottom: 2px solid rgba(245,158,11,0.3);">
        <span style="font-size: 1.3rem; font-weight: 700; color: #F59E0B;">{icono} {titulo}</span>
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 🚀 CARGA UNIFICADA
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def _cargar_datos_dashboard():
    df_ordenes = run_query("ordenes")
    df_users = run_query("usuarios")
    df_solicitudes = run_query("solicitudes")
    df_activos = run_query("activos")
    df_planes = run_query("planes_mantenimiento")
    return df_ordenes, df_users, df_solicitudes, df_activos, df_planes


@st.cache_data(ttl=600, show_spinner=False)
def generar_excel_cached(df_len, df_ordenes, df_activos, df_usuarios):
    return generar_excel_historial(df_ordenes, df_activos, df_usuarios)


# ==============================================================================
# 🏠 RENDER PRINCIPAL — TODO EN UNA HOJA
# ==============================================================================
def render():
    st.title("📊 TABLERO DE MANDO")
    render_back_button()
    mostrar_notificaciones()

    # ── Carga de datos ──
    with st.spinner("Cargando tablero..."):
        df, df_users, df_solicitudes, df_act_sla, df_planes = _cargar_datos_dashboard()

    # ── SLA ──
    verificar_sla_y_alertar(df, df_users, df_act_sla)
    if st.session_state.get('sla_alertas_count', 0) > 0:
        st.toast(f"🚨 {st.session_state['sla_alertas_count']} órdenes superaron su SLA", icon="⚠️")
        st.session_state['sla_alertas_count'] = 0

    if df.empty:
        mostrar_metricas_inteligentes(df, df_users, df_solicitudes)
        st.info("No hay órdenes registradas. El tablero se activará con datos.")
        return

    # ════════════════════════════════════════════════════════════════════════
    # 1️⃣ MÉTRICAS PRINCIPALES
    # ════════════════════════════════════════════════════════════════════════
    mostrar_metricas_inteligentes(df, df_users, df_solicitudes)

    # ── Acciones rápidas + Excel ──
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        n_abiertas = len(df[df['estado'] == 'Abierta'])
        if st.button(f"🔨 OT Abiertas ({n_abiertas})", use_container_width=True, key="dash_qa1"):
            navegar_a("Ordenes de Trabajo")
    with c2:
        n_solic = len(df_solicitudes[df_solicitudes['estado'] == 'Pendiente']) if not df_solicitudes.empty else 0
        if st.button(f"📬 Buzón ({n_solic})", use_container_width=True, key="dash_qa2"):
            navegar_a("Ordenes de Trabajo")
    with c3:
        if st.button("➕ Nueva Orden", use_container_width=True, key="dash_qa3", type="primary"):
            navegar_a("Ordenes de Trabajo")
    with c4:
        try:
            buf = generar_excel_cached(len(df), df, df_act_sla, df_users)
            st.download_button("📥 Exportar Excel", data=buf,
                               file_name=f"OTs_{datetime.now().strftime('%Y%m%d')}.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                               use_container_width=True)
        except Exception:
            st.caption("Excel no disponible")

    # ════════════════════════════════════════════════════════════════════════
    # 2️⃣ TENDENCIA SEMANAL
    # ════════════════════════════════════════════════════════════════════════
    _seccion("Tendencia Semanal", "📈")
    graficar_tendencia_semanal(df)

    # ════════════════════════════════════════════════════════════════════════
    # 3️⃣ ANÁLISIS GLOBAL (3 gráficos en fila)
    # ════════════════════════════════════════════════════════════════════════
    _seccion("Distribución Global", "📊")
    g1, g2, g3 = st.columns(3)
    with g1:
        st.caption("Estado de OTs")
        graficar_estado_barras(df)
    with g2:
        st.caption("Por Criticidad")
        graficar_criticidad(df)
    with g3:
        st.caption("Por Tipo")
        graficar_torta_tipo(df)

    # ════════════════════════════════════════════════════════════════════════
    # 4️⃣ KPIs INDUSTRIALES
    # ════════════════════════════════════════════════════════════════════════
    _seccion("KPIs Industriales", "🏭")
    mostrar_kpis_industriales(df, df_act_sla, df_planes)

    # ════════════════════════════════════════════════════════════════════════
    # 5️⃣ EQUIPO TÉCNICO
    # ════════════════════════════════════════════════════════════════════════
    _seccion("Equipo Técnico", "👥")
    graficar_ordenes_por_tecnico(df, df_users)
    semaforo_tecnicos(df, df_users)

    # ════════════════════════════════════════════════════════════════════════
    # 6️⃣ ATENCIÓN REQUERIDA
    # ════════════════════════════════════════════════════════════════════════
    _seccion("Atención Requerida", "🚨")
    mostrar_tops_ordenes(df)
