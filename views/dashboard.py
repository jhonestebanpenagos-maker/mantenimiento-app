# ==============================================================================
# views/dashboard.py — OPTIMIZADO (carga lazy + caché agresivo)
# ==============================================================================
import streamlit as st
import pandas as pd
from datetime import datetime
from utils.db import run_query
from utils.helpers import mostrar_notificaciones
from utils.notifications import verificar_sla_y_alertar
from utils.charts import (
    mostrar_metricas_inteligentes, graficar_alternativas_visuales,
    mostrar_tops_ordenes, mostrar_kpis_industriales, graficar_estado_barras,
    graficar_criticidad, graficar_torta_tipo, graficar_ordenes_por_tecnico,
    semaforo_tecnicos
)
from utils.excel_gen import generar_excel_historial


# ==============================================================================
# 🚀 CARGA UNIFICADA DE DATOS (1 sola llamada cacheada)
# ==============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def _cargar_datos_dashboard():
    """Carga todas las tablas necesarias en una sola función cacheada.
    TTL de 5 min — evita re-consultas innecesarias en reruns."""
    df_ordenes = run_query("ordenes")
    df_users = run_query("usuarios")
    df_solicitudes = run_query("solicitudes")
    df_activos = run_query("activos")
    df_planes = run_query("planes_mantenimiento")
    return df_ordenes, df_users, df_solicitudes, df_activos, df_planes


@st.cache_data(ttl=600, show_spinner="Generando Excel...")
def generar_excel_cached(df_len, df_ordenes, df_activos, df_usuarios):
    """Excel cacheado 10 min — solo regenera si cambian los datos."""
    return generar_excel_historial(df_ordenes, df_activos, df_usuarios)


# ==============================================================================
# 📄 RENDERIZAR SECCIONES PESADAS (lazy)
# ==============================================================================
def _render_seccion_graficos(df, df_users):
    """Sección de gráficos — se renderiza solo cuando es visible."""
    graficar_alternativas_visuales(df, df_users)
    st.markdown("---")
    mostrar_tops_ordenes(df)


def _render_seccion_kpis(df, df_act_sla, df_planes):
    """KPIs industriales — cálculo pesado, se renderiza lazy."""
    mostrar_kpis_industriales(df, df_act_sla, df_planes)


def _render_seccion_analisis(df):
    """Análisis global con 3 gráficos."""
    st.markdown("### 📊 Análisis Global")
    c_left, c_mid, c_right = st.columns(3)
    with c_left:
        st.markdown("<div class='card-style'><span class='chart-header'>Progreso Global</span>", unsafe_allow_html=True)
        graficar_estado_barras(df)
        st.markdown("</div>", unsafe_allow_html=True)
    with c_mid:
        st.markdown("<div class='card-style'><span class='chart-header'>Nivel de Riesgo</span>", unsafe_allow_html=True)
        graficar_criticidad(df)
        st.markdown("</div>", unsafe_allow_html=True)
    with c_right:
        st.markdown("<div class='card-style'><span class='chart-header'>Por Categoría</span>", unsafe_allow_html=True)
        graficar_torta_tipo(df)
        st.markdown("</div>", unsafe_allow_html=True)


def _render_seccion_tecnicos(df, df_users):
    """Carga por técnico + semáforo."""
    st.markdown("### 👥 Carga por Técnico")
    with st.container():
        graficar_ordenes_por_tecnico(df, df_users)
    st.markdown("---")
    semaforo_tecnicos(df, df_users)


# ==============================================================================
# 🏠 RENDER PRINCIPAL
# ==============================================================================
def render():
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()

    # ── Carga unificada (cacheada 5 min) ──
    with st.spinner("Cargando datos del tablero..."):
        df, df_users, df_solicitudes, df_act_sla, df_planes = _cargar_datos_dashboard()

    # ── SLA — la función ya tiene guard interno, no re-ejecuta si ya verificó ──
    verificar_sla_y_alertar(df, df_users, df_act_sla)

    if st.session_state.get('sla_alertas_count', 0) > 0:
        n = st.session_state['sla_alertas_count']
        st.toast(f"🚨 {n} órdenes superaron su límite de tiempo", icon="⚠️")
        st.session_state['sla_alertas_count'] = 0

    # ── Métricas (rápidas, se renderizan de inmediato) ──
    mostrar_metricas_inteligentes(df, df_users, df_solicitudes)

    if df.empty:
        st.info("No hay órdenes registradas. El tablero se activará con datos.")
        return

    # ── Acciones rápidas ──
    st.markdown("#### ⚡ Acciones Rápidas")
    qa1, qa2, qa3 = st.columns(3)

    with qa1:
        n_abiertas = len(df[df['estado'] == 'Abierta'])
        if st.button(f"🔨 OT Abiertas ({n_abiertas})", use_container_width=True, key="dash_qa_abiertas"):
            st.session_state.current_page = "Ordenes de Trabajo"
            st.rerun()
    with qa2:
        n_solic = len(df_solicitudes[df_solicitudes['estado'] == 'Pendiente']) if not df_solicitudes.empty else 0
        if st.button(f"📬 Buzón ({n_solic})", use_container_width=True, key="dash_qa_buzon"):
            st.session_state.current_page = "Ordenes de Trabajo"
            st.rerun()
    with qa3:
        if st.button("➕ Nueva Orden", use_container_width=True, key="dash_qa_nueva", type="primary"):
            st.session_state.current_page = "Ordenes de Trabajo"
            st.rerun()

    st.markdown("---")

    # ── Exportar Excel (solo genera al hacer clic, no automáticamente) ──
    col_exp1, col_exp2, col_exp3 = st.columns([3, 1, 1])
    with col_exp3:
        try:
            buffer_excel = generar_excel_cached(len(df), df, df_act_sla, df_users)
            st.download_button(
                label="📊 Exportar Excel",
                data=buffer_excel,
                file_name=f"Historial_OTs_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        except Exception as e:
            st.caption(f"Excel no disponible: {e}")

    st.write("")
    st.markdown("---")

    # ── Secciones con tabs para carga lazy ──
    # En vez de renderizar todo de golpe, el usuario ve primero lo importante
    # y elige qué sección pesada cargar
    tab_graficos, tab_kpis, tab_analisis, tab_tecnicos = st.tabs([
        "📊 Flujo y Tendencias",
        "🏭 KPIs Industriales",
        "📈 Análisis Global",
        "👥 Técnicos"
    ])

    with tab_graficos:
        _render_seccion_graficos(df, df_users)

    with tab_kpis:
        _render_seccion_kpis(df, df_act_sla, df_planes)

    with tab_analisis:
        _render_seccion_analisis(df)

    with tab_tecnicos:
        _render_seccion_tecnicos(df, df_users)
