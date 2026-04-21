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


def render():
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()

    df = run_query("ordenes")
    df_users = run_query("usuarios")
    df_solicitudes = run_query("solicitudes")
    df_act_sla = run_query("activos")

    verificar_sla_y_alertar(pd.DataFrame(df), df_users, df_act_sla)

    if st.session_state.get('sla_alertas_count', 0) > 0:
        n = st.session_state['sla_alertas_count']
        st.toast(f"🚨 {n} órdenes superaron su límite de tiempo", icon="⚠️")
        st.session_state['sla_alertas_count'] = 0

    mostrar_metricas_inteligentes(df, df_users, df_solicitudes)

    if not df.empty:
        col_exp1, col_exp2, col_exp3 = st.columns([3, 1, 1])
        with col_exp3:
            try:
                buffer_excel = generar_excel_historial(df, df_act_sla, df_users)
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
        graficar_alternativas_visuales(df, df_users)
        st.markdown("---")
        mostrar_tops_ordenes(df)
        st.markdown("---")
        mostrar_kpis_industriales(df, df_act_sla)
        st.markdown("---")
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

        st.markdown("### 👥 Carga por Técnico")
        with st.container():
            graficar_ordenes_por_tecnico(df, df_users)
        st.markdown("---")
        semaforo_tecnicos(df, df_users)
    else:
        st.info("No hay órdenes registradas. El tablero se activará con datos.")
