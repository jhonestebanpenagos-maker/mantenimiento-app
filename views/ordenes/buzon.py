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

def render_buzon(df_act, df_users, df_ordenes, df_solicitudes):
    if df_solicitudes.empty:
        st.markdown("<div style='text-align:center;padding:40px;color:#6B7280;'><h3>✨ Todo limpio</h3><p>No hay solicitudes pendientes.</p></div>", unsafe_allow_html=True)
        return

    st.markdown(f"### 📥 Solicitudes Pendientes ({len(df_solicitudes)})")
    if not df_act.empty:
        act_map_nombre_id = dict(zip(df_act['nombre'], df_act['id']))
        lista_nombres_activos = sorted(list(act_map_nombre_id.keys()))

        for idx, sol in df_solicitudes.iterrows():
            with st.form(key=f"form_sol_{sol['id']}"):
                st.markdown(f"""
                <div style="border:1px solid #374151;border-radius:8px;padding:15px;margin-bottom:15px;background-color:#1F2937;">
                    <div style="display:flex;justify-content:space-between;">
                        <h4 style="color:#F59E0B;margin:0;">Solicitud #{sol['id']}</h4>
                        <span style="color:#6B7280;font-size:0.8em;">📅 {sol['fecha_solicitud'][:10]}</span>
                    </div>
                    <p style="margin:5px 0;color:#D1D5DB;">👤 <b>Solicita:</b> {sol['solicitante_id']}</p>
                    <p style="margin:5px 0;color:#E5E7EB;background:rgba(255,255,255,0.05);padding:8px;border-radius:4px;">📝 <i>"{sol['descripcion']}"</i></p>
                </div>
                """, unsafe_allow_html=True)

                cols_val = st.columns([1, 2, 2, 1])
                with cols_val[0]:
                    if sol['foto_url']:
                        st.image(sol['foto_url'], width=80)
                    else:
                        st.caption("Sin foto")
                with cols_val[1]:
                    activo_final_nombre = st.selectbox("Vincular Activo", lista_nombres_activos,
                                                        index=None, placeholder="🔍 Buscar activo...")
                    tipo_ot = st.selectbox("Tipo Mant.", ["Correctivo", "Preventivo", "Predictivo", "Mejora"],
                                            index=None, placeholder="Seleccionar tipo...")
                with cols_val[2]:
                    tech_options = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
                    _, nom_sug_b, _ = sugerir_tecnico(df_ordenes, df_users)
                    tech_keys_b = list(tech_options.keys())
                    idx_sug_b = tech_keys_b.index(nom_sug_b) if nom_sug_b and nom_sug_b in tech_keys_b else 0
                    asignar_a = st.selectbox("Asignar a", tech_keys_b, index=idx_sug_b)
                    sug = sol['prioridad_sugerida']
                    val_defecto = sug if sug in ["Baja", "Media", "Alta", "Crítica"] else "Media"
                    criticidad_final = st.select_slider("Definir Criticidad",
                                                          options=["Baja", "Media", "Alta", "Crítica"],
                                                          value=val_defecto)
                with cols_val[3]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_crear = st.form_submit_button("✅ CREAR", type="primary", use_container_width=True)
                    btn_rechazar = st.form_submit_button("❌ RECHAZAR", type="secondary", use_container_width=True)

                if btn_crear:
                    if not activo_final_nombre or not tipo_ot or not asignar_a:
                        st.error("⚠️ Falta seleccionar: Activo, Tipo o Técnico.")
                    else:
                        try:
                            res_orden = db_insert("ordenes", {
                                "activo_id": int(act_map_nombre_id[activo_final_nombre]),
                                "chat_id": sol.get('chat_id'),
                                "descripcion": f"[Solicitud #{sol['id']}] {sol['descripcion']}",
                                "criticidad": criticidad_final, "tipo_mantenimiento": tipo_ot,
                                "estado": "Abierta", "tecnico_asignado": str(tech_options[asignar_a]),
                                "fecha_creacion": datetime.now().isoformat(),
                            })
                            if res_orden.data:
                                nuevo_id = res_orden.data[0]['id']
                                if sol.get('foto_url'):
                                    es_imagen = sol['foto_url'].lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))
                                    icono_msg = "📸" if es_imagen else "📎"
                                    db_insert("bitacora", {
                                        "orden_id": nuevo_id, "usuario_text": f"Solicitante: {sol['solicitante_id']}",
                                        "mensaje": f"{icono_msg} Evidencia original del reporte.",
                                        "archivo_url": sol['foto_url'], "fecha": datetime.now().isoformat()
                                    })
                                msj_ok = f"✅ **¡Solicitud Aprobada!**\n\nOrden **#{nuevo_id}** ({tipo_ot}). Prioridad: {criticidad_final}."
                                notificar_telegram(sol.get('chat_id'), msj_ok)
                                db_update("solicitudes", {"estado": "Aprobada"}, "id", sol['id'])
                                st.toast(f"✅ Orden #{nuevo_id} creada.")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error("Error: No se generó el ID de la orden.")
                        except Exception as e:
                            error_amigable(e)

                if btn_rechazar:
                    db_update("solicitudes", {"estado": "Rechazada"}, "id", sol['id'])
                    notificar_telegram(sol.get('chat_id'), "🚫 Solicitud Rechazada.")
                    st.warning("Rechazada.")
                    st.rerun()


# ==============================================================================
# 🧐 CONTROL DE CALIDAD
# ==============================================================================


