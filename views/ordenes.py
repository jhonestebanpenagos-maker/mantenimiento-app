# ==============================================================================
# views/ordenes.py — CON INVALIDACIÓN DE CACHÉ AUTOMÁTICA
# ==============================================================================
import streamlit as st
import pandas as pd
import time
import calendar as cal_lib
from datetime import datetime
from utils.db import supabase, run_query, run_query_paginated, render_paginacion, db_insert, db_update, db_delete, invalidate_cache
from utils.helpers import mostrar_notificaciones, agregar_notificacion, registrar_accion_critica, error_amigable
from utils.uploads import subir_archivo_generico
from utils.notifications import notificar_telegram
from utils.charts import sugerir_tecnico, render_sugerencia_tecnico
from utils.time_tracking import render_time_tracker
from utils.costos import render_costos
from utils.firmas import render_firmas_cierre
from pdf_utils import generar_pdf_orden


def render():
    st.title("GESTIÓN DE MANTENIMIENTO")
    mostrar_notificaciones()

    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")
    df_solicitudes = run_query("solicitudes")

    if not supabase:
        st.error("Sin conexión a base de datos.")
        return

    # Interceptor
    jump = st.session_state.get('jump_target')
    if jump:
        if jump in ("orden", "preventivo"):
            _render_interceptor(df_act, df_users, df_ordenes)
            return
        elif jump == "ordenes_por_activo":
            _render_ordenes_por_activo(df_act, df_users, df_ordenes)
            return
        elif jump == "crear_para_activo":
            _render_crear_para_activo(df_act, df_users, df_ordenes)
            return

    tab_mis_gestiones, tab_kanban, tab_buzon, tab_calidad, tab_gestion, tab_crear_directa, tab_preventivos = st.tabs([
        "📂 Mis Gestiones", "📋 Kanban", "📥 Buzón Solicitudes", "🧐 Control Calidad",
        "🎛️ Gestión Global", "➕ Crear Directa", "🗓️ Preventivos"
    ])

    with tab_mis_gestiones:
        _render_mis_gestiones(df_act, df_users, df_ordenes)

    with tab_kanban:
        _render_kanban(df_act, df_users, df_ordenes)

    with tab_buzon:
        _render_buzon(df_act, df_users, df_ordenes, df_solicitudes)

    with tab_calidad:
        _render_calidad(df_act, df_users)

    with tab_gestion:
        _render_gestion_global(df_act, df_users, df_ordenes)

    with tab_crear_directa:
        _render_crear_directa(df_act, df_users, df_ordenes)

    with tab_preventivos:
        _render_preventivos(df_act, df_users)


# ==============================================================================
# 🛠️ INTERCEPTOR
# ==============================================================================
def _render_interceptor(df_act, df_users, df_ordenes):
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

    if st.button("⬅️ VOLVER", use_container_width=True):
        destino = st.session_state.get('nav_origin', 'Tablero de Mando')
        st.session_state.current_page = destino
        st.session_state.jump_target = None
        st.session_state.jump_id = None
        st.session_state.nav_origin = None
        st.rerun()

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
                    time.sleep(1.2)
                    st.rerun()

            st.markdown("### 🗑️ Opciones Críticas")
            if st.button("ELIMINAR ORDEN DEFINITIVAMENTE", type="secondary", use_container_width=True):
                db_delete("ordenes", "id", target_id)
                registrar_accion_critica("ELIMINAR_ORDEN", st.session_state.get('usuario', '?'), f"Orden #{target_id} eliminada")
                st.toast("🗑️ Orden eliminada.")
                st.session_state.jump_target = None
                time.sleep(1.2)
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
                    time.sleep(1.2)
                    st.rerun()

            if st.button("🗑️ ELIMINAR PLAN DEFINITIVAMENTE", type="secondary", use_container_width=True):
                db_delete("planes_mantenimiento", "id", target_id)
                registrar_accion_critica("ELIMINAR_PLAN", st.session_state.get('usuario', '?'), f"Plan #{target_id} eliminado")
                st.session_state.jump_target = None
                st.rerun()
    except Exception as e:
        error_amigable(e, "gestión de preventivos")


# ==============================================================================
# 🔍 ÓRDENES POR ACTIVO
# ==============================================================================
def _render_ordenes_por_activo(df_act, df_users, df_ordenes):
    activo_id = st.session_state.get('jump_id')

    st.session_state.jump_target = None
    st.session_state.jump_id = None

    if not activo_id:
        st.error("No se especificó un activo.")
        if st.button("⬅️ Volver al inicio"):
            st.session_state.current_page = "Tablero de Mando"
            st.rerun()
        return

    try:
        activo_id = int(activo_id)
    except (ValueError, TypeError):
        st.error("ID de activo no válido.")
        return

    nombre_activo = "Activo"
    if not df_act.empty:
        match = df_act[df_act['id'] == int(activo_id)]
        if not match.empty:
            nombre_activo = match.iloc[0]['nombre']

    st.title(f"🛠️ Órdenes de: {nombre_activo}")
    st.caption(f"📦 Inventario > {nombre_activo} > Órdenes de Trabajo")

    if st.button("⬅️ Volver a la ficha del activo", use_container_width=True):
        st.session_state.current_page = "Inventario Activos"
        st.session_state.jump_target = "activo"
        st.session_state.jump_id = int(activo_id)
        st.rerun()

    st.markdown("---")

    if df_ordenes.empty:
        st.info("Este activo no tiene órdenes registradas.")
        if st.button("➕ Crear primera orden", type="primary"):
            st.session_state.jump_target = "crear_para_activo"
            st.session_state.jump_id = int(activo_id)
            st.rerun()
        return

    df_filtrado = df_ordenes[df_ordenes['activo_id'] == int(activo_id)].copy()

    if df_filtrado.empty:
        st.info("Este activo no tiene órdenes registradas.")
        if st.button("➕ Crear primera orden", type="primary"):
            st.session_state.jump_target = "crear_para_activo"
            st.session_state.jump_id = int(activo_id)
            st.rerun()
        return

    total = len(df_filtrado)
    abiertas = len(df_filtrado[df_filtrado['estado'] == 'Abierta'])
    por_validar = len(df_filtrado[df_filtrado['estado'] == 'Por Validar'])
    concluidas = len(df_filtrado[df_filtrado['estado'] == 'Concluida'])

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total", total)
    k2.metric("🔨 Abiertas", abiertas)
    k3.metric("🧐 Por Validar", por_validar)
    k4.metric("✅ Concluidas", concluidas)

    st.markdown("---")

    filtro = st.selectbox("Filtrar por estado", ["Todas", "Abierta", "Por Validar", "Concluida", "Cancelada"])
    if filtro != "Todas":
        df_filtrado = df_filtrado[df_filtrado['estado'] == filtro]

    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    for _, orden in df_filtrado.sort_values('fecha_creacion', ascending=False).iterrows():
        icono = "✅" if orden['estado'] == 'Concluida' else "🔨" if orden['estado'] == 'Abierta' else "🧐"
        fecha = (orden.get('fecha_creacion', '') or '')[:10]
        tecnico = map_user.get(str(orden.get('tecnico_asignado', '')), 'Sin asignar')

        col_info, col_btn = st.columns([4, 1])
        with col_info:
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border-left:3px solid {'#10B981' if orden['estado'] == 'Concluida' else '#F59E0B' if orden['estado'] == 'Abierta' else '#60A5FA'};padding:10px 14px;border-radius:0 6px 6px 0;margin-bottom:6px;">
                <div style="display:flex;justify-content:space-between;font-size:0.9rem;">
                    <span style="color:#E5E7EB;font-weight:600;">{icono} OT #{orden['id']}</span>
                    <span style="color:#9CA3AF;">{fecha}</span>
                </div>
                <div style="color:#D1D5DB;font-size:0.85rem;margin:4px 0;">{orden.get('descripcion', '')[:80]}</div>
                <div style="font-size:0.75rem;color:#6B7280;">{orden.get('estado', '?')} · {orden.get('criticidad', '?')} · 👷 {tecnico}</div>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("⚙️ Gestionar", key=f"opa_{orden['id']}", type="secondary", use_container_width=True):
                st.session_state.jump_target = "orden"
                st.session_state.jump_id = orden['id']
                st.rerun()

    st.markdown("---")
    if st.button("➕ Nueva orden para este activo", type="primary", use_container_width=True):
        st.session_state.jump_target = "crear_para_activo"
        st.session_state.jump_id = int(activo_id)
        st.rerun()


# ==============================================================================
# ➕ CREAR ORDEN PARA ACTIVO ESPECÍFICO
# ==============================================================================
def _render_crear_para_activo(df_act, df_users, df_ordenes):
    activo_id = st.session_state.get('jump_id')

    st.session_state.jump_target = None
    st.session_state.jump_id = None

    if not activo_id:
        st.error("No se especificó un activo.")
        if st.button("⬅️ Volver al inicio"):
            st.session_state.current_page = "Tablero de Mando"
            st.rerun()
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
        st.session_state.current_page = "Inventario Activos"
        st.session_state.jump_target = "activo"
        st.session_state.jump_id = int(activo_id)
        st.rerun()

    st.markdown("---")

    nom_sugerido = render_sugerencia_tecnico(df_ordenes, df_users)

    with st.form("ot_para_activo", clear_on_submit=True):
        st.info(f"📍 **Activo:** {nombre_activo} (ID: {activo_id})")

        c1, c2 = st.columns(2)
        tipo_d = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"])
        crit_d = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        desc_d = st.text_area("Descripción del problema o tarea")

        tech_opts_d = {u['nombre']: u['id'] for _, u in df_users.iterrows()} if not df_users.empty else {}
        idx_sug = 0
        if nom_sugerido and nom_sugerido in list(tech_opts_d.keys()):
            idx_sug = list(tech_opts_d.keys()).index(nom_sugerido)
        asig_d = st.selectbox("Asignar Técnico", list(tech_opts_d.keys()), index=idx_sug if tech_opts_d else 0) if tech_opts_d else None

        if st.form_submit_button("✅ CREAR ORDEN", type="primary", use_container_width=True):
            if not desc_d:
                st.error("La descripción es obligatoria.")
            elif not asig_d:
                st.error("Debe asignar un técnico.")
            else:
                try:
                    res = db_insert("ordenes", {
                        "activo_id": int(activo_id), "descripcion": desc_d,
                        "criticidad": crit_d, "tipo_mantenimiento": tipo_d,
                        "estado": "Abierta", "tecnico_asignado": str(tech_opts_d[asig_d]),
                        "fecha_creacion": datetime.now().isoformat()
                    })
                    if res.data:
                        nuevo_id = res.data[0]['id']
                        st.toast(f"✅ Orden #{nuevo_id} creada para {nombre_activo}.")
                        time.sleep(1)
                        st.session_state.current_page = "Ordenes de Trabajo"
                        st.session_state.jump_target = "orden"
                        st.session_state.jump_id = nuevo_id
                        st.rerun()
                except Exception as e:
                    error_amigable(e, "crear orden")


# ==============================================================================
# 📋 VISTA KANBAN
# ==============================================================================
def _render_kanban(df_act, df_users, df_ordenes):
    st.markdown("### 📋 Tablero Kanban")
    st.caption("Vista visual de todas las órdenes. Haz clic en una tarjeta para gestionarla.")

    if df_ordenes.empty:
        st.info("No hay órdenes para mostrar.")
        return

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy()
    df_validar = df_ordenes[df_ordenes['estado'] == 'Por Validar'].copy()
    df_concluidas = df_ordenes[df_ordenes['estado'] == 'Concluida'].copy()

    c_f1, c_f2 = st.columns(2)
    with c_f1:
        filtro_activo_k = st.selectbox(
            "Filtrar por activo",
            ["Todos"] + sorted([v for v in map_act.values() if v]),
            key="kanban_filtro_activo"
        )
    with c_f2:
        filtro_crit_k = st.selectbox(
            "Filtrar criticidad",
            ["Todas", "Crítica", "Alta", "Media", "Baja"],
            key="kanban_filtro_crit"
        )

    def _aplicar_filtros(df):
        if filtro_activo_k != "Todos":
            act_ids = [k for k, v in map_act.items() if v == filtro_activo_k]
            df = df[df['activo_id'].isin(act_ids)]
        if filtro_crit_k != "Todas":
            df = df[df['criticidad'] == filtro_crit_k]
        return df

    df_abiertas = _aplicar_filtros(df_abiertas)
    df_validar = _aplicar_filtros(df_validar)
    df_concluidas = _aplicar_filtros(df_concluidas)

    def _tarjeta_orden(row, color_borde):
        nombre_activo = map_act.get(row.get('activo_id'), 'Activo')
        tecnico = map_user.get(str(row.get('tecnico_asignado', '')), 'Sin asignar')
        desc_corta = (row.get('descripcion', '') or '')[:60]
        criticidad = row.get('criticidad', 'Media')
        tipo = row.get('tipo_mantenimiento', '')
        fecha = (row.get('fecha_creacion', '') or '')[:10]

        crit_color = {"Crítica": "#EF4444", "Alta": "#F59E0B", "Media": "#60A5FA", "Baja": "#10B981"}.get(criticidad, "#6B7280")
        tipo_icon = {"Correctivo": "🔧", "Preventivo": "🛡️", "Predictivo": "📡", "Mejora": "⬆️"}.get(tipo, "📋")

        return f"""
        <div style="
            background: rgba(30,41,59,0.6);
            border-left: 4px solid {color_borde};
            border-radius: 8px;
            padding: 12px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: all 0.2s;
        " onmouseover="this.style.background='rgba(30,41,59,0.9)'" onmouseout="this.style.background='rgba(30,41,59,0.6)'">
            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="color:#E5E7EB;font-weight:700;font-size:0.9rem;">OT #{row['id']}</span>
                <span style="background:{crit_color};color:white;padding:2px 8px;border-radius:10px;font-size:0.65rem;font-weight:700;">{criticidad}</span>
            </div>
            <div style="color:#D1D5DB;font-size:0.8rem;margin-bottom:6px;">{desc_corta}{'...' if len(row.get('descripcion', '') or '') > 60 else ''}</div>
            <div style="display:flex;justify-content:space-between;font-size:0.7rem;color:#9CA3AF;">
                <span>{tipo_icon} {tipo}</span>
                <span>👷 {tecnico.split()[0] if tecnico else '?'}</span>
            </div>
            <div style="font-size:0.7rem;color:#6B7280;margin-top:4px;">
                📍 {nombre_activo[:25]} | 📅 {fecha}
            </div>
        </div>
        """

    def _render_columna(titulo, color, icono, df_col, key_prefix):
        count = len(df_col)
        st.markdown(f"""
        <div style="text-align:center;margin-bottom:10px;">
            <span style="font-size:1.5rem;">{icono}</span>
            <span style="color:{color};font-weight:800;font-size:1.1rem;margin-left:8px;">{titulo}</span>
            <span style="background:{color};color:white;border-radius:12px;padding:2px 10px;font-size:0.8rem;font-weight:700;margin-left:8px;">{count}</span>
        </div>
        """, unsafe_allow_html=True)

        if df_col.empty:
            st.caption("Sin órdenes")
            return

        max_default = 10
        state_key = f"kanban_show_all_{key_prefix}"
        mostrar_todas = st.session_state.get(state_key, False)

        if mostrar_todas:
            items = df_col
        else:
            items = df_col.head(max_default)

        for _, row in items.iterrows():
            html_tarjeta = _tarjeta_orden(row, color)
            st.markdown(html_tarjeta, unsafe_allow_html=True)

            oid = row['id']
            if st.button(f"⚙️ Gestionar #{oid}", key=f"{key_prefix}_kanban_{oid}", use_container_width=True, type="secondary"):
                st.session_state.current_page = "Ordenes de Trabajo"
                st.session_state.jump_target = "orden"
                st.session_state.jump_id = oid
                st.rerun()

        if len(df_col) > max_default:
            if not mostrar_todas:
                if st.button(f"▼ Ver todas ({count})", key=f"{key_prefix}_kanban_more", use_container_width=True):
                    st.session_state[state_key] = True
                    st.rerun()
            else:
                if st.button(f"▲ Mostrar menos", key=f"{key_prefix}_kanban_less", use_container_width=True):
                    st.session_state[state_key] = False
                    st.rerun()

    col1, col2, col3 = st.columns(3)

    with col1:
        _render_columna("ABIERTAS", "#F59E0B", "🔨", df_abiertas, "abierta")

    with col2:
        _render_columna("POR VALIDAR", "#60A5FA", "🧐", df_validar, "validar")

    with col3:
        _render_columna("CONCLUIDAS", "#10B981", "✅", df_concluidas, "concluida")

    st.markdown("---")
    total = len(df_abiertas) + len(df_validar) + len(df_concluidas)
    if total > 0:
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("🔨 Abiertas", len(df_abiertas))
        r2.metric("🧐 Por Validar", len(df_validar))
        r3.metric("✅ Concluidas", len(df_concluidas))
        pct = (len(df_concluidas) / total * 100) if total > 0 else 0
        r4.metric("📊 Progreso", f"{pct:.0f}%")


# ==============================================================================
# 📂 MIS GESTIONES
# ==============================================================================
def _render_mis_gestiones(df_act, df_users, df_ordenes):
    st.info("Aquí administras las órdenes asignadas a ti (Cotizaciones, Compras, Trámites).")

    @st.dialog("✏️ Editar Avance")
    def editar_avance_dialog(item_id, texto_actual, url_actual):
        st.write(f"Editando registro #{item_id}")
        nuevo_texto = st.text_area("Corrección", value=texto_actual, height=100)
        st.markdown("---")
        st.caption("📎 Gestión de Archivos")
        borrar_archivo = False
        if url_actual:
            st.markdown(f"**Archivo actual:** [Ver documento]({url_actual})")
            borrar_archivo = st.checkbox("🗑️ Borrar archivo actual", value=False)
        archivo_nuevo = st.file_uploader("Cambiar archivo (Opcional)", type=["pdf", "docx", "xlsx", "jpg", "png", "msg"])
        if st.button("💾 GUARDAR CAMBIOS", type="primary"):
            with st.spinner("Procesando..."):
                try:
                    datos_update = {"mensaje": nuevo_texto}
                    if borrar_archivo:
                        datos_update["archivo_url"] = None
                    if archivo_nuevo:
                        url_subida = subir_archivo_generico(archivo_nuevo)
                        if url_subida:
                            datos_update["archivo_url"] = url_subida
                    db_update("bitacora", datos_update, "id", item_id)
                    st.toast("Registro actualizado.")
                    st.rerun()
                except Exception as e:
                    error_amigable(e, "guardar avance")

    usuario = st.session_state.get('usuario', '')
    mi_id_admin = None
    if not df_users.empty:
        user_match = df_users[df_users['nombre'] == usuario]
        if not user_match.empty:
            mi_id_admin = user_match.iloc[0]['id']

    if mi_id_admin:
        mis_gestiones = df_ordenes[
            (df_ordenes['tecnico_asignado'] == str(mi_id_admin)) &
            (df_ordenes['estado'] != 'Concluida')
        ]
        if mis_gestiones.empty:
            st.toast("🎉 No tienes gestiones administrativas pendientes.")
        else:
            for idx, row in mis_gestiones.iterrows():
                nombre_activo = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "Activo"
                _render_orden_gestion(row, nombre_activo, df_users, usuario)


def _render_orden_gestion(row, nombre_activo, df_users, usuario):
    with st.expander(f"📂 {nombre_activo} | {row['descripcion'][:50]}... (ID: {row['id']})", expanded=False):
        color_borde = "#3B82F6"
        if row['criticidad'] == 'Alta': color_borde = "#F59E0B"
        if row['criticidad'] == 'Crítica': color_borde = "#EF4444"

        st.markdown(f"""
        <div style="background-color:#1F2937;border-left:4px solid {color_borde};padding:15px;border-radius:4px;margin-bottom:20px;">
            <h5 style="color:#9CA3AF;margin:0;font-size:0.9em;">📋 Detalle del Requerimiento</h5>
            <p style="color:#F3F4F6;font-size:1.1em;margin:8px 0;font-weight:500;">"{row['descripcion']}"</p>
            <div style="display:flex;gap:20px;font-size:0.85em;color:#9CA3AF;border-top:1px solid #374151;padding-top:8px;margin-top:10px;">
                <span>📅 <b>Creada:</b> {row['fecha_creacion'][:10]}</span>
                <span>🚨 <b>Criticidad:</b> {row['criticidad']}</span>
                <span>🔧 <b>Tipo:</b> {row['tipo_mantenimiento']}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if row['estado'] != 'Concluida':
            render_time_tracker(row['id'], usuario)
            render_costos(row['id'], usuario)
            render_firmas_cierre(row['id'], usuario, st.session_state.get('rol', ''), row['estado'])
            st.markdown("---")

        st.markdown("##### 📜 Historial de Gestión")
        try:
            bitacora = supabase.table("bitacora").select("*") \
                .eq("orden_id", row['id']).order("fecha", desc=True).execute()
            if bitacora.data:
                for b in bitacora.data:
                    c_info, c_actions = st.columns([5, 1])
                    with c_info:
                        fecha_fmt = b['fecha'][:10] + " " + b['fecha'][11:16]
                        usuario_log = b.get('usuario_text', 'Usuario')
                        url = b['archivo_url']
                        adjunto_html = _generar_adjunto_html(url)
                        st.markdown(f"""
                        <div style="background-color:rgba(255,255,255,0.05);border-left:3px solid #F59E0B;padding:10px;border-radius:0 5px 5px 0;margin-bottom:5px;">
                            <div style="display:flex;justify-content:space-between;color:#9CA3AF;font-size:0.85em;">
                                <span>📅 {fecha_fmt}</span><span>👤 <b>{usuario_log}</b></span>
                            </div>
                            <div style="margin-top:5px;color:#E5E7EB;white-space:pre-wrap;">{b['mensaje']}</div>
                            {adjunto_html}
                        </div>
                        """, unsafe_allow_html=True)
                    with c_actions:
                        if st.button("✏️", key=f"btn_edit_{b['id']}", help="Editar"):
                            editar_avance_dialog(b['id'], b['mensaje'], b['archivo_url'])
                        if st.button("🗑️", key=f"btn_del_{b['id']}", help="Eliminar"):
                            db_delete("bitacora", "id", b['id'])
                            st.toast("Eliminado")
                            time.sleep(0.5)
                            st.rerun()
            else:
                st.caption("No hay avances registrados aún.")
        except Exception as e:
            error_amigable(e, "cargar historial")

        st.divider()
        st.markdown("##### ➕ Registrar Nuevo Avance")
        with st.form(key=f"form_bitacora_{row['id']}", clear_on_submit=True):
            c_msg, c_file = st.columns([2, 1])
            nuevo_mensaje = c_msg.text_area("Detalle del avance", height=100)
            archivo_gestion = c_file.file_uploader("Adjuntar archivo",
                                                    type=["pdf", "docx", "xlsx", "jpg", "png", "msg"],
                                                    key=f"file_{row['id']}")
            if st.form_submit_button("💾 GUARDAR AVANCE", type="primary", use_container_width=True):
                if not nuevo_mensaje:
                    st.error("⚠️ El mensaje no puede estar vacío.")
                else:
                    url_doc = None
                    if archivo_gestion:
                        with st.spinner("Subiendo archivo..."):
                            url_doc = subir_archivo_generico(archivo_gestion)
                    db_insert("bitacora", {
                        "orden_id": row['id'], "usuario_text": usuario,
                        "mensaje": nuevo_mensaje, "archivo_url": url_doc,
                        "fecha": datetime.now().isoformat()
                    })
                    st.toast("✅ Avance registrado correctamente.")
                    time.sleep(1)
                    st.rerun()

        st.markdown("---")
        activar_cierre = st.checkbox("✅ Habilitar opciones de Finalizar / Cerrar", key=f"check_fin_{row['id']}")
        if activar_cierre:
            st.markdown("""
            <div style="background-color:rgba(16,185,129,0.1);padding:10px;border-radius:5px;border-left:3px solid #10B981;margin:10px 0;">
                <small>Al finalizar, la orden pasará a estado <b>Concluida</b>.</small>
            </div>
            """, unsafe_allow_html=True)
            motivo_cierre = st.text_input("Comentario final de cierre (Opcional)", key=f"cierre_text_{row['id']}")
            if st.button("CONFIRMAR Y FINALIZAR ORDEN", key=f"btn_fin_seguro_{row['id']}", type="primary", use_container_width=True):
                msg_final = f"[CIERRE ADMIN] {motivo_cierre}" if motivo_cierre else "[CIERRE ADMIN] Gestión finalizada."
                db_update("ordenes", {
                    "estado": "Concluida", "comentarios_cierre": msg_final,
                    "fecha_cierre": datetime.now().isoformat()
                }, "id", row['id'])
                db_insert("bitacora", {
                    "orden_id": row['id'], "usuario_text": usuario,
                    "mensaje": "🏁 Orden finalizada administrativamente.",
                    "fecha": datetime.now().isoformat()
                })
                st.balloons()
                st.toast("🏆 Orden finalizada correctamente.")
                time.sleep(1.5)
                st.rerun()


# ==============================================================================
# 📥 BUZÓN DE SOLICITUDES
# ==============================================================================
def _render_buzon(df_act, df_users, df_ordenes, df_solicitudes):
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
def _render_calidad(df_act, df_users):
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
def _render_gestion_global(df_act, df_users, df_ordenes):
    st.markdown("### 🎛️ Control Central de Órdenes")

    filtro_ot_externo = None
    if st.session_state.get('jump_target') == 'orden' and st.session_state.get('jump_id'):
        filtro_ot_externo = st.session_state.jump_id
        st.toast(f"📍 Filtrando Orden #{filtro_ot_externo}", icon="🔍")
        st.session_state.jump_target = None
        st.session_state.jump_id = None

    col_filtros = st.columns(3)

    # Leer filtro desde dashboard si fue seteado
    _filtro_estado = st.session_state.pop('_filtro_estado_ots', None)
    if _filtro_estado and _filtro_estado != "Todas":
        opciones = ["Todas", "Abierta", "Por Validar", "Concluida", "Cancelada"]
        idx_default = opciones.index(_filtro_estado) if _filtro_estado in opciones else 0
        filtro_estado = col_filtros[0].selectbox("Filtrar Estado", opciones, index=idx_default)
    else:
        filtro_estado = col_filtros[0].selectbox("Filtrar Estado", ["Todas", "Abierta", "Por Validar", "Concluida", "Cancelada"], index=0)

    if 'gestion_pagina' not in st.session_state:
        st.session_state.gestion_pagina = 1

    query_filters = {}
    if filtro_estado != "Todas":
        query_filters['estado'] = filtro_estado

    PER_PAGE = 20

    if filtro_ot_externo:
        try:
            oid_filtro = int(filtro_ot_externo)
            res = supabase.table("ordenes").select("*").eq("id", oid_filtro).execute()
            if res.data:
                df_display = pd.DataFrame(res.data)
                total = 1
                total_pag = 1
            else:
                df_display = pd.DataFrame()
                total = 0
                total_pag = 1
        except Exception:
            df_display = pd.DataFrame()
            total = 0
            total_pag = 1
    else:
        df_display, total, total_pag = run_query_paginated(
            "ordenes",
            page=st.session_state.gestion_pagina,
            per_page=PER_PAGE,
            filters=query_filters if query_filters else None,
            order_by="id",
            desc=True
        )

    if not df_display.empty:
        map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
        map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
        df_display['Activo Nombre'] = df_display['activo_id'].map(map_act).fillna("Desconocido")
        df_display['Técnico Nombre'] = df_display['tecnico_asignado'].map(map_user).fillna("Sin Asignar")

        nueva_pag = render_paginacion("gestion_ordenes", st.session_state.gestion_pagina, total_pag, total)
        if nueva_pag != st.session_state.gestion_pagina:
            st.session_state.gestion_pagina = nueva_pag
            st.rerun()

        event = st.dataframe(
            df_display[['id', 'estado', 'Activo Nombre', 'descripcion', 'Técnico Nombre', 'criticidad', 'fecha_creacion']],
            use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", height=250
        )

        if len(event.selection.rows) > 0:
            idx_tabla = event.selection.rows[0]
            id_orden_selec = df_display.iloc[idx_tabla]['id']
            try:
                res_sel = supabase.table("ordenes").select("*").eq("id", int(id_orden_selec)).execute()
                if res_sel.data:
                    orden_actual = pd.Series(res_sel.data[0])
                else:
                    orden_actual = df_display.iloc[idx_tabla]
            except Exception:
                orden_actual = df_display.iloc[idx_tabla]
            _render_orden_detalle(id_orden_selec, orden_actual, df_display, idx_tabla, df_users)

        render_paginacion("gestion_ordenes_bottom", st.session_state.gestion_pagina, total_pag, total)
    else:
        st.info("No hay órdenes registradas con los filtros actuales.")


def _render_orden_detalle(id_orden_selec, orden_actual, df_display, idx_tabla, df_users):
    st.divider()
    col_izq, col_der = st.columns([1.5, 1])

    with col_izq:
        st.markdown(f"#### ✏️ Gestionar Orden #{id_orden_selec}")
        if orden_actual['estado'] in ['Concluida', 'Por Validar']:
            try:
                pdf_data = generar_pdf_orden(orden_actual,
                                              df_display.iloc[idx_tabla]['Activo Nombre'],
                                              df_display.iloc[idx_tabla]['Técnico Nombre'])
                st.download_button("📄 Descargar PDF Reporte", data=pdf_data,
                                   file_name=f"Reporte_OT_{id_orden_selec}.pdf",
                                   mime="application/pdf", key=f"btn_pdf_g_{id_orden_selec}")
            except Exception as e:
                print(f"Error generando PDF: {e}")
                pass

        with st.form(key=f"form_edit_orden_g_{id_orden_selec}"):
            c_edit1, c_edit2, c_edit3 = st.columns(3)
            est_opts = ["Abierta", "Por Validar", "Concluida", "Cancelada"]
            idx_est = est_opts.index(orden_actual['estado']) if orden_actual['estado'] in est_opts else 0
            nuevo_estado = c_edit1.selectbox("Estado", est_opts, index=idx_est)

            lista_tecnicos = df_users[df_users['rol'].isin(['Tecnico', 'Admin', 'Programador'])]
            tech_dict = dict(zip(lista_tecnicos['nombre'], lista_tecnicos['id']))
            tech_actual_id = str(orden_actual['tecnico_asignado'])
            nombre_tech = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), "Seleccionar...")
            idx_tech = list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0
            nuevo_tec_nom = c_edit2.selectbox("Reasignar Técnico", list(tech_dict.keys()), index=idx_tech)
            nueva_crit = c_edit3.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"],
                                                value=orden_actual['criticidad'])
            st.markdown("**Descripción / Falla:**")
            nueva_desc = st.text_area("Descripción", value=orden_actual['descripcion'], height=100)
            st.markdown("<br>", unsafe_allow_html=True)

            if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                try:
                    db_update("ordenes", {
                        "estado": nuevo_estado, "tecnico_asignado": str(tech_dict[nuevo_tec_nom]),
                        "criticidad": nueva_crit, "descripcion": nueva_desc
                    }, "id", int(id_orden_selec))
                    st.toast("Orden actualizada correctamente.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    error_amigable(e, "actualizar orden")

        if orden_actual['estado'] in ['Concluida', 'Cancelada']:
            st.markdown("---")
            st.markdown("#### 🔓 Reactivar Orden")
            if st.button("🔄 RE-ABRIR ORDEN", key=f"reopen_{id_orden_selec}", type="secondary", use_container_width=True):
                try:
                    id_limpio = int(id_orden_selec)
                    db_update("ordenes", {
                        "estado": "Abierta", "fecha_cierre": None
                    }, "id", id_limpio)
                    db_insert("bitacora", {
                        "orden_id": id_limpio, "usuario_text": str(st.session_state.get('usuario', '')),
                        "mensaje": "🔄 Orden RE-ABIERTA administrativamente.",
                        "fecha": datetime.now().isoformat()
                    })
                    st.toast("✅ Orden reactivada.")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    error_amigable(e, "reabrir orden")

        with st.expander("🗑️ Zona de Peligro (Eliminar)"):
            if st.button("ELIMINAR DEFINITIVAMENTE", key=f"del_g_{id_orden_selec}", type="secondary", use_container_width=True):
                db_delete("ordenes", "id", int(id_orden_selec))
                registrar_accion_critica("ELIMINAR_ORDEN", st.session_state.get('usuario', '?'), f"Orden #{id_orden_selec} eliminada (Gestión Global)")
                st.toast("Eliminado.")
                time.sleep(1)
                st.rerun()

    with col_der:
        _render_bitacora(id_orden_selec)


def _render_bitacora(id_orden_selec):
    st.markdown("#### 📜 Bitácora y Adjuntos")

    try:
        oid = int(id_orden_selec)
    except (ValueError, TypeError):
        st.error("ID de orden no válido.")
        return

    usuario = st.session_state.get('usuario', '')
    rol = st.session_state.get('rol', '')

    estado_orden = "Abierta"
    try:
        res_estado = supabase.table("ordenes").select("estado").eq("id", oid).execute()
        if res_estado.data:
            estado_orden = res_estado.data[0].get('estado', 'Abierta')
    except Exception:
        pass

    render_time_tracker(id_orden_selec, usuario)
    render_costos(id_orden_selec, usuario)
    render_firmas_cierre(id_orden_selec, usuario, rol, estado_orden)

    st.markdown("---")
    st.caption("Historial de avances y archivos cargados.")
    with st.container(border=True):
        try:
            bitacora_res = supabase.table("bitacora").select("*") \
                .eq("orden_id", id_orden_selec).order("fecha", desc=True).execute()
            if bitacora_res.data:
                for b in bitacora_res.data:
                    fecha_fmt = b['fecha'][:10] + " " + b['fecha'][11:16]
                    usuario_log = b.get('usuario_text', 'Sistema')
                    url = b.get('archivo_url')
                    adjunto_html = _generar_adjunto_html(url, icon_mode=True)
                    st.markdown(f"""
                    <div style="background-color:rgba(255,255,255,0.05);padding:10px;border-radius:6px;margin-bottom:8px;border-left:3px solid #60A5FA;">
                        <div style="font-size:0.8em;color:#9CA3AF;display:flex;justify-content:space-between;">
                            <span>{usuario_log}</span><span>{fecha_fmt}</span>
                        </div>
                        <div style="color:#E5E7EB;margin-top:4px;font-size:0.95em;">{b['mensaje']}</div>
                        {adjunto_html}
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("No hay registros en la bitácora para esta orden.")
        except Exception as e:
            st.error("⚠️ No se pudo cargar la bitácora de esta orden.")


# ==============================================================================
# ➕ CREAR DIRECTA
# ==============================================================================
def _render_crear_directa(df_act, df_users, df_ordenes):
    st.info("Creación rápida: Los campos se limpiarán automáticamente al guardar.")
    if not df_act.empty:
        act_dict = dict(zip(df_act['nombre'], df_act['id']))
        nom_sugerido = render_sugerencia_tecnico(df_ordenes, df_users)

        with st.form("ot_directa", clear_on_submit=True):
            sel_act_dir = st.selectbox("Activo", sorted(act_dict.keys()))
            c1, c2 = st.columns(2)
            tipo_d = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"])
            crit_d = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
            desc_d = st.text_area("Descripción")

            tech_opts_d = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
            idx_sug = 0
            if nom_sugerido and nom_sugerido in list(tech_opts_d.keys()):
                idx_sug = list(tech_opts_d.keys()).index(nom_sugerido)
            asig_d = st.selectbox("Asignar Técnico", list(tech_opts_d.keys()), index=idx_sug,
                                   help="🤖 Preseleccionado automáticamente por menor carga")

            st.markdown("---")
            st.markdown("##### 📎 Adjuntos Iniciales")
            archivo_inicial = st.file_uploader("Soporte (PDF, Excel, Foto, Correo)",
                                                type=["pdf", "docx", "xlsx", "jpg", "png", "msg"])
            st.markdown("<br>", unsafe_allow_html=True)

            if st.form_submit_button("CREAR ORDEN", type="primary", use_container_width=True):
                if not desc_d:
                    st.error("La descripción es obligatoria.")
                else:
                    try:
                        res_orden = db_insert("ordenes", {
                            "activo_id": int(act_dict[sel_act_dir]), "descripcion": desc_d,
                            "criticidad": crit_d, "tipo_mantenimiento": tipo_d,
                            "estado": "Abierta", "tecnico_asignado": str(tech_opts_d[asig_d]),
                            "fecha_creacion": datetime.now().isoformat()
                        })
                        if res_orden.data:
                            nuevo_id_ot = res_orden.data[0]['id']
                            st.toast(f"✅ Orden #{nuevo_id_ot} creada correctamente.")
                            if archivo_inicial:
                                with st.spinner("Subiendo archivo adjunto..."):
                                    url_doc = subir_archivo_generico(archivo_inicial)
                                    if url_doc:
                                        db_insert("bitacora", {
                                            "orden_id": nuevo_id_ot, "usuario_text": st.session_state.get('usuario', ''),
                                            "mensaje": "📎 Documento inicial adjunto al crear la orden.",
                                            "archivo_url": url_doc, "fecha": datetime.now().isoformat()
                                        })
                                        st.toast("Documento vinculado a la bitácora")
                                    else:
                                        st.error("La orden se creó, pero falló la subida del archivo.")
                            time.sleep(1.5)
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
def _render_preventivos(df_act, df_users):
    st.markdown("### 🗓️ Planes de Mantenimiento Recurrente")

    filtro_id_externo = None
    if st.session_state.get('jump_target') == 'preventivo' and st.session_state.get('jump_id'):
        filtro_id_externo = st.session_state.jump_id
        st.info(f"📍 Has sido redirigido al Plan #{filtro_id_externo}.")
        st.session_state.jump_target = None
        st.session_state.jump_id = None

    st.info("Aquí configuras las tareas que se repiten (ej: Limpieza mensual).")

    with st.expander("➕ Crear Nuevo Plan Preventivo"):
        st.markdown("#### ✅ Checklist de Verificación")
        st.caption("Agrega los pasos que el técnico debe verificar en cada ejecución.")

        if 'checklist_items' not in st.session_state:
            st.session_state.checklist_items = ["", ""]

        for i in range(len(st.session_state.checklist_items)):
            c_item, c_del = st.columns([5, 1])
            nuevo_val = c_item.text_input(
                f"Paso {i+1}",
                value=st.session_state.checklist_items[i],
                key=f"prev_ci_{i}",
                placeholder=f"Ej: Verificar temperatura del motor",
                label_visibility="collapsed"
            )
            st.session_state.checklist_items[i] = nuevo_val
            if len(st.session_state.checklist_items) > 1:
                if c_del.button("🗑️", key=f"prev_dc_{i}", help="Eliminar paso"):
                    st.session_state.checklist_items.pop(i)
                    st.rerun()

        if st.button("➕ Agregar paso", key="prev_add_step"):
            st.session_state.checklist_items.append("")
            st.rerun()

        st.markdown("---")

        with st.form("form_plan_prev"):
            c1, c2 = st.columns(2)
            act_nombres = df_act['nombre'].values if not df_act.empty else []
            act_sel = c1.selectbox("Activo", act_nombres)
            users_dict = dict(zip(df_users['nombre'], df_users['id'])) if not df_users.empty else {}
            tec_sel = c2.selectbox("Técnico Sugerido", list(users_dict.keys()))
            desc = st.text_input("Título del plan (Ej: Limpieza mensual de filtros)")
            c3, c4 = st.columns(2)
            dias = c3.number_input("Frecuencia (Días)", min_value=1, value=30)
            fecha_base = c4.date_input("Fecha de Inicio / Última vez hecho")

            enviado = st.form_submit_button("GUARDAR PLAN")

            if enviado:
                id_act = df_act[df_act['nombre'] == act_sel].iloc[0]['id']
                id_tec = users_dict[tec_sel]
                checklist_limpio = [item.strip() for item in st.session_state.checklist_items if item.strip()]
                checklist_json = checklist_limpio if checklist_limpio else None
                try:
                    db_insert("planes_mantenimiento", {
                        "activo_id": int(id_act), "descripcion": desc,
                        "frecuencia_dias": int(dias), "ultima_ejecucion": fecha_base.isoformat(),
                        "tecnico_default": str(id_tec),
                        "checklist": checklist_json
                    })
                    st.session_state.checklist_items = ["", ""]
                    st.toast(f"✅ Plan guardado con {len(checklist_limpio)} pasos de verificación.")
                    st.rerun()
                except Exception as e:
                    error_amigable(e)

    st.divider()

    df_planes = run_query("planes_mantenimiento")
    if filtro_id_externo:
        df_planes = df_planes[df_planes['id'].astype(str) == str(filtro_id_externo)]

    if df_planes.empty:
        st.warning("No hay planes configurados.")
        return

    df_planes['ultima_ejecucion'] = pd.to_datetime(df_planes['ultima_ejecucion'])
    df_planes['proxima_fecha'] = df_planes['ultima_ejecucion'] + pd.to_timedelta(df_planes['frecuencia_dias'], unit='D')
    df_planes['dias_restantes'] = (df_planes['proxima_fecha'] - datetime.now()).dt.days

    def color_estado(dias):
        if dias < 0: return "🔴 Vencido"
        elif dias <= 5: return "🟡 Próximo"
        else: return "🟢 A tiempo"

    df_planes['Estado'] = df_planes['dias_restantes'].apply(color_estado)
    map_act = dict(zip(df_act['id'], df_act['nombre']))
    df_planes['Activo'] = df_planes['activo_id'].map(map_act)

    tab_cal, tab_lista = st.tabs(["📅 Calendario Visual", "📋 Lista de Planes"])

    with tab_cal:
        _render_calendario_preventivo(df_planes, map_act)

    with tab_lista:
        st.dataframe(
            df_planes[['id', 'Activo', 'descripcion', 'frecuencia_dias', 'ultima_ejecucion', 'proxima_fecha', 'Estado']],
            column_config={
                "ultima_ejecucion": st.column_config.DateColumn("Última vez"),
                "proxima_fecha": st.column_config.DateColumn("Próxima"),
                "frecuencia_dias": st.column_config.NumberColumn("Cada (días)"),
                "descripcion": "Tarea"
            },
            use_container_width=True, hide_index=True
        )

        st.markdown("#### ✅ Checklists por Plan")
        if "checklist" in df_planes.columns:
            planes_con_checklist = df_planes[df_planes["checklist"].apply(lambda x: isinstance(x, list) and len(x) > 0 if x is not None else False)]
        else:
            planes_con_checklist = pd.DataFrame()
        if not planes_con_checklist.empty:
            for _, plan in planes_con_checklist.iterrows():
                nombre_act = map_act.get(plan.get('activo_id'), 'Activo')
                with st.expander(f"📋 {plan['descripcion']} — {nombre_act}"):
                    for i, item in enumerate(plan['checklist'], 1):
                        st.markdown(f"  **{i}.** {item}")
        else:
            st.caption("Ningún plan tiene checklist configurado.")

    st.markdown("---")

    # =====================================================================
    # 🤖 GENERADOR AUTOMÁTICO
    # =====================================================================
    st.markdown("### 🤖 Generador Automático")
    c_gen1, c_gen2 = st.columns([3, 1])
    c_gen1.caption("Buscará todos los planes 'Vencidos' o 'Próximos' y creará Órdenes de Trabajo automáticamente.")

    if c_gen2.button("🚀 EJECUTAR RUTINA", type="primary"):
        contador = 0
        now = datetime.now()
        progress_bar = st.progress(0)

        for idx, plan in df_planes.iterrows():
            if plan['proxima_fecha'] <= now:
                try:
                    desc_orden = f"[PREVENTIVO] {plan['descripcion']}"
                    checklist = plan.get('checklist')
                    if checklist and isinstance(checklist, list) and len(checklist) > 0:
                        checklist_texto = "\n".join([f"☐ {item}" for item in checklist])
                        desc_orden = f"{desc_orden}\n\n✅ CHECKLIST:\n{checklist_texto}"

                    res_orden = db_insert("ordenes", {
                        "activo_id": int(plan['activo_id']),
                        "descripcion": desc_orden,
                        "criticidad": "Media", "tipo_mantenimiento": "Preventivo",
                        "estado": "Abierta", "tecnico_asignado": str(plan['tecnico_default']),
                        "fecha_creacion": now.isoformat()
                    })

                    if checklist and isinstance(checklist, list) and len(checklist) > 0 and res_orden.data:
                        nuevo_id = res_orden.data[0]['id']
                        checklist_log = "📋 CHECKLIST DEL PREVENTIVO:\n" + "\n".join(
                            [f"{i+1}. {item}" for i, item in enumerate(checklist)]
                        )
                        db_insert("bitacora", {
                            "orden_id": nuevo_id, "usuario_text": "SISTEMA",
                            "mensaje": checklist_log,
                            "fecha": now.isoformat()
                        })

                    db_update("planes_mantenimiento", {
                        "ultima_ejecucion": now.isoformat()
                    }, "id", plan['id'])
                    contador += 1
                except Exception as e:
                    error_amigable(e, f"generar preventivo del plan #{plan['id']}")
            progress_bar.progress((idx + 1) / len(df_planes))

        if contador > 0:
            st.toast(f"✅ Se generaron {contador} órdenes de mantenimiento preventivo.")
            time.sleep(2)
            st.rerun()
        else:
            st.info("👍 Todo al día. No hay mantenimientos pendientes para hoy.")


def _render_calendario_preventivo(df_planes, map_act):
    now = datetime.now()

    c_mes, c_ano, c_nav = st.columns([2, 1, 2])
    with c_mes:
        meses_nombres = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                         "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
        mes_sel = st.selectbox("Mes", meses_nombres, index=now.month - 1, label_visibility="collapsed")
        mes_num = meses_nombres.index(mes_sel) + 1
    with c_ano:
        ano_sel = st.selectbox("Año", [now.year - 1, now.year, now.year + 1],
                               index=1, label_visibility="collapsed")

    tareas_por_fecha = {}
    for _, plan in df_planes.iterrows():
        prox = plan['proxima_fecha']
        if pd.isna(prox):
            continue
        fecha_base = prox
        dias_freq = plan['frecuencia_dias']
        inicio_mes = datetime(ano_sel, mes_num, 1)
        fin_mes = datetime(ano_sel, mes_num, cal_lib.monthrange(ano_sel, mes_num)[1], 23, 59, 59)
        fecha_calc = fecha_base
        fechas_instancias = []
        while fecha_calc <= fin_mes:
            if fecha_calc >= inicio_mes:
                fechas_instancias.append(fecha_calc)
            fecha_calc = fecha_calc + pd.Timedelta(days=dias_freq)
        fecha_calc = fecha_base - pd.Timedelta(days=dias_freq)
        while fecha_calc >= inicio_mes:
            fechas_instancias.append(fecha_calc)
            fecha_calc = fecha_calc - pd.Timedelta(days=dias_freq)

        for fecha_inst in fechas_instancias:
            clave = fecha_inst.day
            if clave not in tareas_por_fecha:
                tareas_por_fecha[clave] = []
            dias_restantes = (fecha_inst - now).days
            if dias_restantes < 0:
                estado = "vencido"
                color = "#EF4444"
                icono = "🔴"
            elif dias_restantes <= 5:
                estado = "proximo"
                color = "#F59E0B"
                icono = "🟡"
            else:
                estado = "ok"
                color = "#10B981"
                icono = "🟢"
            nombre_activo = map_act.get(plan.get('activo_id'), 'Activo')
            tareas_por_fecha[clave].append({
                'desc': plan['descripcion'],
                'activo': nombre_activo,
                'estado': estado,
                'color': color,
                'icono': icono,
                'dias': dias_restantes
            })

    cal = cal_lib.Calendar(firstweekday=6)
    semanas = cal.monthdayscalendar(ano_sel, mes_num)
    dias_semana = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"]

    total_venc = sum(1 for tareas in tareas_por_fecha.values() for t in tareas if t['estado'] == 'vencido')
    total_prox = sum(1 for tareas in tareas_por_fecha.values() for t in tareas if t['estado'] == 'proximo')
    total_ok = sum(1 for tareas in tareas_por_fecha.values() for t in tareas if t['estado'] == 'ok')

    st.markdown(f"""
    <div style="display:flex;gap:15px;margin-bottom:20px;justify-content:center;">
        <div style="background:rgba(239,68,68,0.15);border:1px solid #EF4444;border-radius:8px;padding:10px 20px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:800;color:#EF4444;">{total_venc}</div>
            <div style="font-size:0.75rem;color:#FCA5A5;">Vencidos</div>
        </div>
        <div style="background:rgba(245,158,11,0.15);border:1px solid #F59E0B;border-radius:8px;padding:10px 20px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:800;color:#F59E0B;">{total_prox}</div>
            <div style="font-size:0.75rem;color:#FDE68A;">Próximos (5 días)</div>
        </div>
        <div style="background:rgba(16,185,129,0.15);border:1px solid #10B981;border-radius:8px;padding:10px 20px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:800;color:#10B981;">{total_ok}</div>
            <div style="font-size:0.75rem;color:#A7F3D0;">A tiempo</div>
        </div>
        <div style="background:rgba(96,165,250,0.15);border:1px solid #60A5FA;border-radius:8px;padding:10px 20px;text-align:center;">
            <div style="font-size:1.5rem;font-weight:800;color:#60A5FA;">{len(df_planes)}</div>
            <div style="font-size:0.75rem;color:#BFDBFE;">Planes activos</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    html_cal = """
    <style>
        .cal-container { background: rgba(30, 41, 59, 0.7); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.08); }
        .cal-header { text-align: center; font-size: 1.3rem; font-weight: 800; color: #F59E0B; margin-bottom: 15px; text-transform: uppercase; letter-spacing: 2px; }
        .cal-grid { display: grid; grid-template-columns: repeat(7, 1fr); gap: 4px; }
        .cal-day-name { text-align: center; font-size: 0.75rem; font-weight: 700; color: #9CA3AF; padding: 8px 0; text-transform: uppercase; }
        .cal-day { background: rgba(255,255,255,0.03); border-radius: 8px; min-height: 90px; padding: 6px; position: relative; border: 1px solid rgba(255,255,255,0.05); transition: all 0.2s; }
        .cal-day:hover { background: rgba(255,255,255,0.06); border-color: rgba(255,255,255,0.15); }
        .cal-day.empty { background: transparent; border: none; }
        .cal-day.today { border: 2px solid #60A5FA; box-shadow: 0 0 10px rgba(96,165,250,0.3); }
        .cal-day-num { font-size: 0.85rem; font-weight: 700; color: #E5E7EB; margin-bottom: 4px; }
        .cal-day.today .cal-day-num { color: #60A5FA; }
        .cal-task { font-size: 0.6rem; padding: 2px 4px; border-radius: 3px; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: default; }
        .cal-task.vencido { background: rgba(239,68,68,0.2); color: #FCA5A5; border-left: 2px solid #EF4444; }
        .cal-task.proximo { background: rgba(245,158,11,0.2); color: #FDE68A; border-left: 2px solid #F59E0B; }
        .cal-task.ok { background: rgba(16,185,129,0.15); color: #A7F3D0; border-left: 2px solid #10B981; }
        .cal-more { font-size: 0.6rem; color: #9CA3AF; padding: 1px 4px; font-style: italic; }
    </style>
    """

    html_cal += f"""
    <div class="cal-container">
        <div class="cal-header">{mes_sel} {ano_sel}</div>
        <div class="cal-grid">
    """

    for dia_nombre in dias_semana:
        html_cal += f'<div class="cal-day-name">{dia_nombre}</div>'

    for semana in semanas:
        for dia in semana:
            if dia == 0:
                html_cal += '<div class="cal-day empty"></div>'
            else:
                clase_hoy = "today" if (dia == now.day and mes_num == now.month and ano_sel == now.year) else ""
                html_cal += f'<div class="cal-day {clase_hoy}">'
                html_cal += f'<div class="cal-day-num">{dia}</div>'
                if dia in tareas_por_fecha:
                    tareas = tareas_por_fecha[dia]
                    for tarea in tareas[:3]:
                        tooltip = f"{tarea['icono']} {tarea['activo']}: {tarea['desc']} ({tarea['dias']}d)"
                        html_cal += f'<div class="cal-task {tarea["estado"]}" title="{tooltip}">{tarea["icono"]} {tarea["desc"][:15]}</div>'
                    if len(tareas) > 3:
                        html_cal += f'<div class="cal-more">+{len(tareas) - 3} más</div>'
                html_cal += '</div>'

    html_cal += """
        </div>
    </div>
    """

    st.markdown(html_cal, unsafe_allow_html=True)
    st.caption("🔴 Vencido | 🟡 Próximo (≤5 días) | 🟢 A tiempo | Los tooltips muestran detalles al pasar el mouse")

    st.markdown("---")
    st.markdown("#### 🔍 Explorar Día")
    dia_explorar = st.number_input("Seleccionar día del mes",
                                    min_value=1,
                                    max_value=cal_lib.monthrange(ano_sel, mes_num)[1],
                                    value=min(now.day, cal_lib.monthrange(ano_sel, mes_num)[1]),
                                    key="explorar_dia_cal")

    if dia_explorar in tareas_por_fecha:
        st.markdown(f"**📅 Tareas programadas para el día {dia_explorar} de {mes_sel}:**")
        for tarea in tareas_por_fecha[dia_explorar]:
            st.markdown(f"""
            <div style="background:rgba(30,41,59,0.5);border-left:3px solid {tarea['color']};padding:10px 15px;border-radius:0 8px 8px 0;margin-bottom:8px;">
                <div style="color:#E5E7EB;font-weight:600;">{tarea['icono']} {tarea['activo']}</div>
                <div style="color:#9CA3AF;font-size:0.85rem;">{tarea['desc']}</div>
                <div style="color:{tarea['color']};font-size:0.75rem;margin-top:4px;">
                    {'Vencido hace' if tarea['dias'] < 0 else 'En'} {abs(tarea['dias'])} día(s)
                </div>
            </div>
            """, unsafe_allow_html=True)
    else:
        st.info(f"No hay tareas programadas para el día {dia_explorar} de {mes_sel}.")


# ==============================================================================
# 🛠️ HELPERS
# ==============================================================================
def _generar_adjunto_html(url, icon_mode=False):
    if not url:
        return ""
    ul = url.lower()
    if ul.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return f"""<br><a href="{url}" target="_blank" style="color:#10B981;font-weight:bold;">🖼️ Ver Imagen</a>"""
    elif ul.endswith('.pdf'):
        return f"""<br><a href="{url}" target="_blank" style="color:#EF4444;font-weight:bold;">📄 Ver PDF</a>"""
    elif ul.endswith(('.xls', '.xlsx')):
        return f"""<br><a href="{url}" target="_blank" style="color:#16A34A;font-weight:bold;">📊 Ver Excel</a>"""
    elif ul.endswith('.msg'):
        return f"""<br><a href="{url}" target="_blank" style="color:#3B82F6;font-weight:bold;">📧 Ver Correo</a>"""
    else:
        return f"""<br><a href="{url}" target="_blank" style="color:#F59E0B;font-weight:bold;">📎 Ver Archivo</a>"""
