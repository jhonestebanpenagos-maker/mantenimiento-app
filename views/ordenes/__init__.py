# views/ordenes/__init__.py — Módulo principal de gestión de órdenes
# Re-exporta render() para mantener compatibilidad con app.py
import streamlit as st
import pandas as pd
import time
from datetime import datetime
from utils.db import supabase, run_query, db_insert, db_update, db_delete
from utils.helpers import mostrar_notificaciones, agregar_notificacion, error_amigable, navegar_a
from utils.nav_button import render_back_button
from utils.notifications import notificar_telegram
from utils.charts import sugerir_tecnico, render_sugerencia_tecnico

from .helpers import generar_adjunto_html, render_archivo_unificado
from .kanban import render_kanban
from .calidad import render_calidad
from .gestion import render_gestion_global
from .crear import render_crear_directa, render_crear_para_activo
from .preventivos import render_preventivos
from .buzon import render_buzon
from .mis_gestiones import render_mis_gestiones
from .interceptor import render_interceptor
from utils.email_monitor import render_buzon_correo, render_auditoria_correos


def render():
    st.title("GESTIÓN DE MANTENIMIENTO")
    mostrar_notificaciones()

    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")
    df_solicitudes_all = run_query("solicitudes")
    df_solicitudes = df_solicitudes_all[df_solicitudes_all['estado'] == 'Pendiente'] if not df_solicitudes_all.empty else df_solicitudes_all

    if not supabase:
        st.error("Sin conexión a base de datos.")
        return

    # Interceptor
    jump = st.session_state.get('jump_target')
    if jump:
        if jump in ("orden", "preventivo"):
            render_interceptor(df_act, df_users, df_ordenes)
            return
        elif jump == "ordenes_por_activo":
            _render_ordenes_por_activo(df_act, df_users, df_ordenes)
            return
        elif jump == "crear_para_activo":
            render_crear_para_activo(df_act, df_users, df_ordenes)
            return

    # ── Botón volver (solo en vista normal de tabs) ──
    render_back_button()

    # ── Determinar tab activo ──
    tab_activa = st.session_state.get('ordenes_tab', None)
    if tab_activa is None:
        if st.session_state.pop('kanban_filtro_solicitudes', False):
            tab_activa = 'kanban'
        else:
            tab_activa = st.session_state.get('_ordenes_tab_activa', 'mis_gestiones')
    if 'ordenes_tab' in st.session_state:
        del st.session_state['ordenes_tab']

    # ── Navegación en 2 grupos para mejor legibilidad ──
    GRUPO_TRABAJO = [
        ("mis_gestiones", "📂", "Mis Gestiones"),
        ("kanban",        "📋", "Kanban"),
        ("crear",         "➕", "Crear"),
        ("preventivos",   "🗓️", "Preventivos"),
    ]
    GRUPO_SUPERVISION = [
        ("buzon",   "📥", "Buzón"),
        ("calidad", "🧐", "Calidad"),
        ("correo",  "📧", "Correo"),
        ("auditoria", "🔍", "Auditoría"),
        ("gestion", "🎛️", "Global"),
    ]

    st.caption("🔨 Mi Trabajo")
    nav1_cols = st.columns(len(GRUPO_TRABAJO))
    for i, (key, icon, label) in enumerate(GRUPO_TRABAJO):
        with nav1_cols[i]:
            is_active = key == tab_activa
            if st.button(f"{icon} {label}", key=f"_nav_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state['_ordenes_tab_activa'] = key
                st.rerun()

    st.caption("👁️ Supervisión")
    nav2_cols = st.columns(len(GRUPO_SUPERVISION))
    for i, (key, icon, label) in enumerate(GRUPO_SUPERVISION):
        with nav2_cols[i]:
            is_active = key == tab_activa
            if st.button(f"{icon} {label}", key=f"_nav_{key}", use_container_width=True,
                         type="primary" if is_active else "secondary"):
                st.session_state['_ordenes_tab_activa'] = key
                st.rerun()

    st.markdown("<div style='margin-top:8px;'></div>", unsafe_allow_html=True)

    # ── Renderizar contenido según tab activo ──
    if tab_activa == 'mis_gestiones':
        render_mis_gestiones(df_act, df_users, df_ordenes)
    elif tab_activa == 'kanban':
        render_kanban(df_act, df_users, df_ordenes, df_solicitudes)
    elif tab_activa == 'buzon':
        render_buzon(df_act, df_users, df_ordenes, df_solicitudes)
    elif tab_activa == 'calidad':
        render_calidad(df_act, df_users)
    elif tab_activa == 'gestion':
        render_gestion_global(df_act, df_users, df_ordenes)
    elif tab_activa == 'crear':
        render_crear_directa(df_act, df_users, df_ordenes)
    elif tab_activa == 'preventivos':
        render_preventivos(df_act, df_users)
    elif tab_activa == 'correo':
        render_buzon_correo()
    elif tab_activa == 'auditoria':
        render_auditoria_correos()


# ==============================================================================
# 🔍 ÓRDENES POR ACTIVO (se queda aquí por simplicidad)
# ==============================================================================
def _render_ordenes_por_activo(df_act, df_users, df_ordenes):
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
        match = df_act[df_act['id'] == int(activo_id)]
        if not match.empty:
            nombre_activo = match.iloc[0]['nombre']

    st.title(f"🛠️ Órdenes de: {nombre_activo}")
    st.caption(f"📦 Inventario > {nombre_activo} > Órdenes de Trabajo")

    if st.button("⬅️ Volver a la ficha del activo", use_container_width=True):
        navegar_a("Inventario Activos", jump_target="activo", jump_id=int(activo_id))

    st.markdown("---")

    if df_ordenes.empty:
        st.info("Este activo no tiene órdenes registradas.")
        if st.button("➕ Crear primera orden", type="primary"):
            navegar_a("Ordenes de Trabajo", jump_target="crear_para_activo", jump_id=int(activo_id))
        return

    df_filtrado = df_ordenes[df_ordenes['activo_id'] == int(activo_id)].copy()

    if df_filtrado.empty:
        st.info("Este activo no tiene órdenes registradas.")
        if st.button("➕ Crear primera orden", type="primary"):
            navegar_a("Ordenes de Trabajo", jump_target="crear_para_activo", jump_id=int(activo_id))
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
                navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=orden['id'])

    st.markdown("---")
    if st.button("➕ Nueva orden para este activo", type="primary", use_container_width=True):
        navegar_a("Ordenes de Trabajo", jump_target="crear_para_activo", jump_id=int(activo_id))
