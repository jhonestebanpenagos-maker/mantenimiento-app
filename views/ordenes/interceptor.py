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

def render_interceptor(df_act, df_users, df_ordenes):
    target_type = st.session_state.jump_target
    target_id = st.session_state.jump_id

    if 'nav_origin' not in st.session_state:
        st.session_state.nav_origin = st.session_state.get('current_page', 'Tablero de Mando')

    st.markdown(f"""
    <div style="background-color:#1F2937;padding:15px;border-radius:8px;border-left:5px solid #3B82F6;margin-bottom:20px;">
        <h3 style="color:#60A5FA;margin:0;">🛠️ Gestión de Dependencia #{target_id}</h3>
        <p style="margin:0;color:#9CA3AF;font-size:0.9em;">Edita o reasigna este registro para liberar el activo original.</p>
    </div>
    """, unsafe_allow_html=True)

    render_back_button()

    st.markdown("---")

    if target_type == "orden":
        _interceptor_orden(target_id, df_act, df_users)
    elif target_type == "preventivo":
        _interceptor_preventivo(target_id, df_act, df_users)




def _interceptor_orden(target_id, df_act, df_users):
    try:
        res = supabase.table("ordenes").select("*").eq("id", target_id).execute()
        if res.data:
            orden_actual = res.data[0]
            with st.form(key=f"form_focus_orden_{target_id}"):
                c_edit1, c_edit2, c_edit3 = st.columns(3)
                est_opts = ["Abierta", "Por Validar", "Concluida", "Cancelada"]
                idx_est = est_opts.index(orden_actual['estado']) if orden_actual['estado'] in est_opts else 0
                nuevo_estado = c_edit1.selectbox("Estado", est_opts, index=idx_est)

                lista_tecnicos = df_users[df_users['rol'].isin(['Tecnico', 'Admin', 'Programador'])]
                tech_dict = dict(zip(lista_tecnicos['nombre'], lista_tecnicos['id']))
                tech_actual_id = str(orden_actual['tecnico_asignado'])
                nombre_tech = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), "Seleccionar...")

                act_dict = dict(zip(df_act['nombre'], df_act['id']))
                act_actual_id = orden_actual['activo_id']
                nombre_act = next((k for k, v in act_dict.items() if v == act_actual_id), list(act_dict.keys())[0])

                nuevo_act_nom = c_edit2.selectbox("Reasignar Activo", list(act_dict.keys()),
                                                   index=list(act_dict.keys()).index(nombre_act))
                nuevo_tec_nom = c_edit3.selectbox("Técnico", list(tech_dict.keys()),
                                                   index=list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0)
                nueva_desc = st.text_area("Descripción / Reporte", value=orden_actual['descripcion'])
                nueva_crit = st.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], value=orden_actual['criticidad'])

                if st.form_submit_button("💾 GUARDAR CAMBIOS Y REASIGNAR", type="primary", use_container_width=True):
                    db_update("ordenes", {
                        "estado": nuevo_estado, "tecnico_asignado": str(tech_dict[nuevo_tec_nom]),
                        "activo_id": int(act_dict[nuevo_act_nom]), "criticidad": nueva_crit, "descripcion": nueva_desc
                    }, "id", target_id)
                    st.toast("✅ Orden actualizada correctamente.")
                    time.sleep(0.3)
                    st.rerun()

            st.markdown("### 🗑️ Opciones Críticas")
            confirm_del_ord = st.text_input("Escriba ELIMINAR para confirmar", key=f"confirm_del_ord_{target_id}", placeholder="ELIMINAR")
            if st.button("ELIMINAR ORDEN DEFINITIVAMENTE", type="secondary", use_container_width=True, disabled=(confirm_del_ord.strip().upper() != "ELIMINAR")):
                db_delete("ordenes", "id", target_id)
                registrar_accion_critica("ELIMINAR_ORDEN", st.session_state.get('usuario', '?'), f"Orden #{target_id} eliminada")
                st.toast("🗑️ Orden eliminada.")
                st.session_state.jump_target = None
                time.sleep(0.3)
                st.rerun()
        else:
            st.error("Orden no encontrada.")
    except Exception as e:
        error_amigable(e)




def _interceptor_preventivo(target_id, df_act, df_users):
    try:
        res = supabase.table("planes_mantenimiento").select("*").eq("id", target_id).execute()
        if res.data:
            plan_focus = res.data[0]
            with st.form("form_focus_prev"):
                c1, c2 = st.columns(2)
                act_dict = dict(zip(df_act['nombre'], df_act['id']))
                nombre_act_actual = next((k for k, v in act_dict.items() if v == plan_focus['activo_id']), list(act_dict.keys())[0])
                nuevo_act_nom = c1.selectbox("Reasignar a Activo", list(act_dict.keys()),
                                              index=list(act_dict.keys()).index(nombre_act_actual))
                tech_dict = dict(zip(df_users['nombre'], df_users['id']))
                nombre_tech = next((k for k, v in tech_dict.items() if str(v) == str(plan_focus['tecnico_default'])), list(tech_dict.keys())[0])
                nuevo_tec_nom = c2.selectbox("Técnico Encargado", list(tech_dict.keys()),
                                              index=list(tech_dict.keys()).index(nombre_tech))
                desc_p = st.text_input("Tarea", value=plan_focus['descripcion'])
                dias_p = st.number_input("Frecuencia (Días)", value=plan_focus['frecuencia_dias'])

                if st.form_submit_button("💾 GUARDAR Y REASIGNAR", type="primary", use_container_width=True):
                    db_update("planes_mantenimiento", {
                        "activo_id": int(act_dict[nuevo_act_nom]),
                        "tecnico_default": str(tech_dict[nuevo_tec_nom]),
                        "descripcion": desc_p, "frecuencia_dias": dias_p
                    }, "id", target_id)
                    st.toast("✅ Plan actualizado.")
                    time.sleep(0.3)
                    st.rerun()

            confirm_del_plan = st.text_input("Escriba ELIMINAR para confirmar", key=f"confirm_del_plan_{target_id}", placeholder="ELIMINAR")
            if st.button("🗑️ ELIMINAR PLAN DEFINITIVAMENTE", type="secondary", use_container_width=True, disabled=(confirm_del_plan.strip().upper() != "ELIMINAR")):
                db_delete("planes_mantenimiento", "id", target_id)
                registrar_accion_critica("ELIMINAR_PLAN", st.session_state.get('usuario', '?'), f"Plan #{target_id} eliminado")
                st.session_state.jump_target = None
                st.rerun()
    except Exception as e:
        error_amigable(e, "gestión de preventivos")


# ==============================================================================
# 🔍 ÓRDENES POR ACTIVO
# ==============================================================================


