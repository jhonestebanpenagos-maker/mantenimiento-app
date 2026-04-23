import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.db import supabase, run_query, run_query_paginated, render_paginacion, db_insert, db_update, db_delete, invalidate_cache
from utils.helpers import mostrar_notificaciones, agregar_notificacion, registrar_accion_critica, error_amigable, navegar_a
from utils.nav_button import render_back_button
from utils.notifications import notificar_telegram
from utils.charts import sugerir_tecnico, render_sugerencia_tecnico
from .helpers import generar_adjunto_html, render_archivo_unificado

def render_calidad(df_act, df_users):
    df_revision = run_query("ordenes", {"estado": "Por Validar"})
    if df_revision.empty:
        st.markdown("<div style='text-align:center;padding:40px;color:#10B981;'><h3>✨ Todo revisado</h3><p>No hay trabajos pendientes.</p></div>", unsafe_allow_html=True)
        return

    st.markdown(f"### 🧐 Auditoría de Trabajos ({len(df_revision)})")
    for idx, row in df_revision.iterrows():
        nombre_activo = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "N/A"
        tecnico_nombre = "Desconocido"
        if not df_users.empty:
            t_data = df_users[df_users['id'].astype(str) == row['tecnico_asignado']]
            if not t_data.empty:
                tecnico_nombre = t_data.iloc[0]['nombre']

        with st.container():
            st.markdown(f"""
            <div style="border:1px solid #4B5563;border-radius:8px;padding:20px;margin-bottom:20px;background-color:#1F2937;">
                <h3 style="color:#60A5FA;margin:0;">OT #{row['id']} | {nombre_activo}</h3>
                <p style="color:#9CA3AF;">👷 Realizado por: <b>{tecnico_nombre}</b></p>
                <hr style="border-color:#374151;">
            """, unsafe_allow_html=True)

            col_rev1, col_rev2 = st.columns([1, 1])
            with col_rev1:
                st.markdown("**📸 EVIDENCIA:**")
                if row.get('foto_cierre_url'):
                    st.image(row['foto_cierre_url'], use_container_width=True)
                else:
                    st.warning("Sin foto.")
            with col_rev2:
                st.markdown("**📝 REPORTE:**")
                st.info(f"{row.get('comentarios_cierre', 'Sin reporte')}")
                st.markdown("---")
                if st.button("✅ APROBAR Y CERRAR", key=f"apr_fin_{row['id']}", type="primary", use_container_width=True):
                    db_update("ordenes", {"estado": "Concluida"}, "id", row['id'])
                    if row.get('chat_id'):
                        notificar_telegram(row.get('chat_id'),
                            f"🎉 **¡Solucionado!**\n\nOrden **#{row['id']}** cerrada.",
                            row.get('foto_cierre_url'))
                    st.toast("Orden cerrada.")
                    st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)
                with st.expander("↩️ Devolver (Rechazar)"):
                    motivo = st.text_input("Motivo", key=f"mot_{row['id']}")
                    if st.button("CONFIRMAR DEVOLUCIÓN", key=f"dev_{row['id']}", type="secondary", use_container_width=True):
                        if motivo:
                            db_update("ordenes", {
                                "estado": "Abierta", "comentarios_validacion": f"DEVUELTA: {motivo}"
                            }, "id", row['id'])
                            st.warning("Devuelta.")
                            st.rerun()
                        else:
                            st.error("Falta motivo.")
            st.markdown("</div>", unsafe_allow_html=True)


# ==============================================================================
# 🎛️ GESTIÓN GLOBAL
# ==============================================================================


