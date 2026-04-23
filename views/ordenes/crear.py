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
from utils.uploads import subir_archivo_generico

def render_crear_directa(df_act, df_users, df_ordenes):
    st.info("Creación rápida: Los campos se limpiarán automáticamente al guardar.")
    if not df_act.empty:
        act_dict = dict(zip(df_act['nombre'], df_act['id']))
        nom_sugerido = render_sugerencia_tecnico(df_ordenes, df_users)

        # ── Paso 1: Activo + Tipo + Criticidad ──
        sel_act_dir = st.selectbox("Activo", sorted(act_dict.keys()), key="crear_dir_activo")
        c1, c2 = st.columns(2)
        tipo_d = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"], key="crear_dir_tipo")
        crit_d = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], key="crear_dir_crit")

        # ── Paso 2: Archivo/Correo (con callback para parseo en vivo) ──
        archivo_inicial, email_datos = render_archivo_unificado("crear_directa")

        # ── Inicializar descripción desde correo parseado ──
        email_desc = st.session_state.pop('_email_desc_default', '')
        if email_desc:
            st.session_state['desc_crear_directa'] = email_desc

        # ── Paso 3: Descripción + Técnico + Submit (en form) ──
        with st.form("ot_directa"):
            desc_d = st.text_area("Descripción", key="desc_crear_directa")

            tech_opts_d = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
            idx_sug = 0
            if nom_sugerido and nom_sugerido in list(tech_opts_d.keys()):
                idx_sug = list(tech_opts_d.keys()).index(nom_sugerido)
            asig_d = st.selectbox("Asignar Técnico", list(tech_opts_d.keys()), index=idx_sug,
                                   help="🤖 Preseleccionado automáticamente por menor carga")

            if st.form_submit_button("CREAR ORDEN", type="primary", use_container_width=True):
                desc_val = (desc_d or "").strip()
                if not desc_val:
                    st.error("La descripción es obligatoria.")
                else:
                    try:
                        res_orden = db_insert("ordenes", {
                            "activo_id": int(act_dict[sel_act_dir]), "descripcion": desc_val,
                            "criticidad": crit_d, "tipo_mantenimiento": tipo_d,
                            "estado": "Abierta", "tecnico_asignado": str(tech_opts_d[asig_d]),
                            "fecha_creacion": datetime.now().isoformat()
                        })
                        if res_orden.data:
                            nuevo_id_ot = res_orden.data[0]['id']
                            st.success(f"✅ Orden #{nuevo_id_ot} creada correctamente.")
                            if archivo_inicial:
                                with st.spinner("Subiendo archivo adjunto..."):
                                    url_doc = subir_archivo_generico(archivo_inicial)
                                    if url_doc:
                                        msg = "📧 Correo adjunto." if email_datos else "📎 Documento adjunto."
                                        db_insert("bitacora", {
                                            "orden_id": nuevo_id_ot,
                                            "usuario_text": st.session_state.get('usuario', ''),
                                            "mensaje": msg, "archivo_url": url_doc,
                                            "fecha": datetime.now().isoformat()
                                        })
                            # Limpiar TODOS los campos del formulario
                            for k in ['desc_crear_directa', '_parsed_email_crear_directa',
                                      '_archivo_unif_crear_directa',
                                      'crear_dir_activo', 'crear_dir_tipo', 'crear_dir_crit']:
                                st.session_state.pop(k, None)
                            agregar_notificacion('success', f'Orden #{nuevo_id_ot} creada. Puedes crear otra.')
                            time.sleep(0.3)
                            st.rerun()
                        else:
                            st.error("No se pudo obtener el ID de la nueva orden.")
                    except Exception as e:
                        error_amigable(e, "crear orden")
    else:
        st.warning("No hay activos registrados.")


# ==============================================================================
# 🗓️ PREVENTIVOS
# ==============================================================================


def render_crear_para_activo(df_act, df_users, df_ordenes):
    activo_id = st.session_state.get('jump_id')

    st.session_state.jump_target = None
    st.session_state.jump_id = None

    if not activo_id:
        st.error("No se especificó un activo.")
        if st.button("⬅️ Volver al inicio"):
            navegar_a("Tablero de Mando")
        return

    try:
        activo_id = int(activo_id)
    except (ValueError, TypeError):
        st.error("ID de activo no válido.")
        return

    nombre_activo = "Activo"
    if not df_act.empty:
        match = df_act[df_act['id'] == activo_id]
        if not match.empty:
            nombre_activo = match.iloc[0]['nombre']

    st.title(f"➕ Nueva Orden para: {nombre_activo}")
    st.caption(f"📦 Inventario > {nombre_activo} > Crear Orden")

    if st.button("⬅️ Volver a la ficha del activo", use_container_width=True):
        navegar_a("Inventario Activos", jump_target="activo", jump_id=int(activo_id))

    st.markdown("---")

    # ── Paso 1: Info del activo + Tipo + Criticidad ──
    st.info(f"📍 **Activo:** {nombre_activo} (ID: {activo_id})")

    c1, c2 = st.columns(2)
    tipo_d = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"], key=f"crear_pa_tipo_{activo_id}")
    crit_d = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], key=f"crear_pa_crit_{activo_id}")

    # ── Paso 2: Archivo/Correo (con callback para parseo en vivo) ──
    archivo_inicial, email_datos = render_archivo_unificado(f"crear_para_activo_{activo_id}")

    # ── Inicializar descripción desde correo parseado ──
    desc_key = f'desc_para_activo_{activo_id}'
    email_desc = st.session_state.pop('_email_desc_default', '')
    if email_desc:
        st.session_state[desc_key] = email_desc

    nom_sugerido = render_sugerencia_tecnico(df_ordenes, df_users)

    # ── Paso 3: Descripción + Técnico + Submit (en form) ──
    with st.form("ot_para_activo"):
        desc_d = st.text_area("Descripción del problema o tarea", key=desc_key)

        tech_opts_d = {u['nombre']: u['id'] for _, u in df_users.iterrows()} if not df_users.empty else {}
        idx_sug = 0
        if nom_sugerido and nom_sugerido in list(tech_opts_d.keys()):
            idx_sug = list(tech_opts_d.keys()).index(nom_sugerido)
        asig_d = st.selectbox("Asignar Técnico", list(tech_opts_d.keys()), index=idx_sug if tech_opts_d else 0) if tech_opts_d else None

        if st.form_submit_button("✅ CREAR ORDEN", type="primary", use_container_width=True):
            desc_val = (desc_d or "").strip()
            if not desc_val:
                st.error("La descripción es obligatoria.")
            elif not asig_d:
                st.error("Debe asignar un técnico.")
            else:
                try:
                    res = db_insert("ordenes", {
                        "activo_id": int(activo_id), "descripcion": desc_val,
                        "criticidad": crit_d, "tipo_mantenimiento": tipo_d,
                        "estado": "Abierta", "tecnico_asignado": str(tech_opts_d[asig_d]),
                        "fecha_creacion": datetime.now().isoformat()
                    })
                    if res.data:
                        nuevo_id = res.data[0]['id']
                        st.success(f"✅ Orden #{nuevo_id} creada para {nombre_activo}.")
                        if archivo_inicial:
                            with st.spinner("Subiendo archivo adjunto..."):
                                url_doc = subir_archivo_generico(archivo_inicial)
                                if url_doc:
                                    msg = "📧 Correo adjunto." if email_datos else "📎 Documento adjunto."
                                    db_insert("bitacora", {
                                        "orden_id": nuevo_id,
                                        "usuario_text": st.session_state.get('usuario', ''),
                                        "mensaje": msg, "archivo_url": url_doc,
                                        "fecha": datetime.now().isoformat()
                                    })
                        for k in [desc_key, f'_parsed_email_crear_para_activo_{activo_id}',
                                  f'_archivo_unif_crear_para_activo_{activo_id}',
                                  f'crear_pa_tipo_{activo_id}', f'crear_pa_crit_{activo_id}']:
                            st.session_state.pop(k, None)
                        agregar_notificacion('success', f'Orden #{nuevo_id} creada para {nombre_activo}.')
                        time.sleep(0.3)
                        navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=nuevo_id)
                except Exception as e:
                    error_amigable(e, "crear orden")


# ==============================================================================
# 📋 VISTA KANBAN
# ==============================================================================


