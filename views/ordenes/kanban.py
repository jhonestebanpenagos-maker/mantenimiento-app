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

def render_kanban(df_act, df_users, df_ordenes, df_solicitudes=None):
    st.markdown("### 📋 Tablero Kanban")
    st.caption("Vista visual de todas las órdenes. Haz clic en una tarjeta para gestionarla.")

    # ── Solicitudes pendientes (viene del tablero) ──
    mostrar_solicitudes = st.session_state.get('kanban_filtro_solicitudes', False)
    if mostrar_solicitudes:
        st.session_state.pop('kanban_filtro_solicitudes', None)
    if mostrar_solicitudes and df_solicitudes is not None and not df_solicitudes.empty:
        solicitudes_pend = df_solicitudes[df_solicitudes['estado'] == 'Pendiente']
        if not solicitudes_pend.empty:
            st.markdown(
                '<div style="background:linear-gradient(135deg,rgba(245,158,11,0.12),rgba(239,68,68,0.08));'
                'border:1px solid #F59E0B;border-radius:12px;padding:20px;margin-bottom:20px;">'
                '<div style="display:flex;align-items:center;gap:12px;margin-bottom:15px;">'
                '<span style="font-size:1.5rem;">📬</span>'
                '<div>'
                '<div style="color:#F59E0B;font-weight:800;font-size:1.1rem;">SOLICITUDES PENDIENTES — '
                + str(len(solicitudes_pend)) + '</div>'
                '<div style="color:#9CA3AF;font-size:0.8rem;">Reportes desde Telegram esperando aprobación</div>'
                '</div></div>',
                unsafe_allow_html=True
            )
            for _, sol in solicitudes_pend.iterrows():
                fecha = (sol.get('fecha_solicitud', '') or '')[:10]
                desc = (sol.get('descripcion', '') or '')[:80]
                prioridad = sol.get('prioridad_sugerida', 'Media')
                prio_color = {"Crítica": "#EF4444", "Alta": "#F59E0B", "Media": "#60A5FA", "Baja": "#10B981"}.get(prioridad, "#6B7280")
                st.markdown(
                    '<div style="background:rgba(30,41,59,0.6);border-left:3px solid ' + prio_color
                    + ';border-radius:6px;padding:10px 14px;margin-bottom:6px;">'
                    '<div style="display:flex;justify-content:space-between;align-items:center;">'
                    '<span style="color:#E5E7EB;font-weight:600;font-size:0.9rem;">Solicitud #' + str(sol['id']) + '</span>'
                    '<span style="background:' + prio_color + ';color:white;padding:2px 8px;border-radius:8px;font-size:0.65rem;font-weight:700;">'
                    + prioridad + '</span></div>'
                    '<div style="color:#D1D5DB;font-size:0.8rem;margin-top:4px;">' + desc + '</div>'
                    '<div style="color:#9CA3AF;font-size:0.7rem;margin-top:4px;">📅 ' + fecha
                    + ' · 👤 ' + str(sol.get('solicitante_id', 'N/A')) + '</div>'
                    '</div>',
                    unsafe_allow_html=True
                )
            st.markdown(
                '<div style="text-align:center;margin-top:10px;">'
                '<span style="color:#F59E0B;font-size:0.8rem;">👇 Gestiona estas solicitudes en la pestaña '
                '<b>📥 Buzón Solicitudes</b></span></div></div>',
                unsafe_allow_html=True
            )
            st.markdown("---")
        else:
            st.toast("✨ No hay solicitudes pendientes", icon="✅")

    if df_ordenes.empty:
        st.info("No hay órdenes para mostrar.")
        return

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy()
    df_validar = df_ordenes[df_ordenes['estado'] == 'Por Validar'].copy()
    df_concluidas = df_ordenes[df_ordenes['estado'] == 'Concluida'].copy()
    df_canceladas = df_ordenes[df_ordenes['estado'] == 'Cancelada'].copy()

    c_f1, c_f2, c_f3 = st.columns(3)
    with c_f1:
        filtro_estado_k = st.selectbox(
            "Filtrar por estado",
            ["Todas", "Abierta", "Por Validar", "Concluida", "Cancelada"],
            key="kanban_filtro_estado"
        )
    with c_f2:
        filtro_crit_k = st.selectbox(
            "Filtrar criticidad",
            ["Todas", "Crítica", "Alta", "Media", "Baja"],
            key="kanban_filtro_crit"
        )
    with c_f3:
        filtro_tipo_k = st.selectbox(
            "Filtrar por tipo",
            ["Todos", "Correctivo", "Preventivo", "Predictivo", "Mejora"],
            key="kanban_filtro_tipo"
        )

    def _aplicar_filtros(df):
        if filtro_estado_k != "Todas":
            df = df[df['estado'] == filtro_estado_k]
        if filtro_crit_k != "Todas":
            df = df[df['criticidad'] == filtro_crit_k]
        if filtro_tipo_k != "Todos":
            df = df[df['tipo_mantenimiento'] == filtro_tipo_k]
        return df

    df_abiertas = _aplicar_filtros(df_abiertas)
    df_validar = _aplicar_filtros(df_validar)
    df_concluidas = _aplicar_filtros(df_concluidas)
    df_canceladas = _aplicar_filtros(df_canceladas)

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
                navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=oid)

        if len(df_col) > max_default:
            if not mostrar_todas:
                if st.button(f"▼ Ver todas ({count})", key=f"{key_prefix}_kanban_more", use_container_width=True):
                    st.session_state[state_key] = True
                    st.rerun()
            else:
                if st.button(f"▲ Mostrar menos", key=f"{key_prefix}_kanban_less", use_container_width=True):
                    st.session_state[state_key] = False
                    st.rerun()

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        _render_columna("ABIERTAS", "#F59E0B", "🔨", df_abiertas, "abierta")

    with col2:
        _render_columna("POR VALIDAR", "#60A5FA", "🧐", df_validar, "validar")

    with col3:
        _render_columna("CONCLUIDAS", "#10B981", "✅", df_concluidas, "concluida")

    with col4:
        _render_columna("CANCELADAS", "#EF4444", "❌", df_canceladas, "cancelada")

    st.markdown("---")
    total = len(df_abiertas) + len(df_validar) + len(df_concluidas) + len(df_canceladas)
    if total > 0:
        r1, r2, r3, r4, r5 = st.columns(5)
        r1.metric("🔨 Abiertas", len(df_abiertas))
        r2.metric("🧐 Por Validar", len(df_validar))
        r3.metric("✅ Concluidas", len(df_concluidas))
        r4.metric("❌ Canceladas", len(df_canceladas))
        pct = (len(df_concluidas) / total * 100) if total > 0 else 0
        r5.metric("📊 Progreso", f"{pct:.0f}%")


# ==============================================================================
# 📂 MIS GESTIONES
# ==============================================================================


