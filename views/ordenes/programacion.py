import streamlit as st
import pandas as pd
import datetime
import calendar
from utils.db import db_update
from utils.helpers import navegar_a

def render_programacion(df_ordenes, df_users, df_activos):
    st.markdown("### 📅 Torre de Control: Planificador de Mantenimiento")
    st.caption("Modo Administrador: Asigna fechas, gestiona contratistas y visualiza el calendario de ejecución.")

    # ── 1. Protecciones y Preparación de Datos ──
    if 'fecha_programada' not in df_ordenes.columns:
        st.warning("⚠️ Falta la columna 'fecha_programada' en BD. Ejecuta el script SQL.")
        return

    # Si las columnas nuevas aún no están en el DataFrame, las simulamos para evitar errores
    if 'estado_disponibilidad' not in df_users.columns:
        df_users['estado_disponibilidad'] = 'Activo'
    if 'tipo_personal' not in df_users.columns:
        df_users['tipo_personal'] = 'Técnico Interno'

    df_ordenes['fecha_programada'] = df_ordenes['fecha_programada'].fillna("")
    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy()
    mapa_activos = dict(zip(df_activos['id'], df_activos['nombre'])) if not df_activos.empty else {}

    # Separar usuarios por disponibilidad
    usuarios_activos = df_users[df_users['estado_disponibilidad'] == 'Activo']
    usuarios_inactivos = df_users[df_users['estado_disponibilidad'] != 'Activo']

    tab_asignacion, tab_calendario = st.tabs(["🎛️ Asignación Diaria", "📆 Calendario Mensual"])

    # =========================================================================
    # 🎛️ PESTAÑA 1: ASIGNACIÓN Y AGENDA
    # =========================================================================
    with tab_asignacion:
        st.markdown("#### 📥 Órdenes en Espera (Sin fecha asignada)")
        sin_fecha = df_abiertas[df_abiertas['fecha_programada'] == ""]

        if not sin_fecha.empty:
            with st.container(border=True):
                opciones_ot = [f"OT #{row['id']} - {str(row['descripcion'])[:50]}..." for _, row in sin_fecha.iterrows()]
                sel_ot_str = st.selectbox("Selecciona la OT a programar:", opciones_ot)
                sel_ot_id = int(sel_ot_str.split(" ")[1].replace("#", ""))
                
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    fecha_prog = st.date_input("📅 Fecha de Ejecución", value=datetime.date.today())
                    
                with c2:
                    # Solo mostramos personal ACTIVO en el selector
                    if not usuarios_activos.empty:
                        tech_opts = {f"{u['nombre']} ({u['tipo_personal']})": u['id'] for _, u in usuarios_activos.iterrows()}
                        nuevo_tech_name = st.selectbox("👷‍♂️ Asignar a (Solo Activos)", list(tech_opts.keys()))
                    else:
                        st.error("No hay personal activo.")
                        nuevo_tech_name = None
                    
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 PROGRAMAR ORDEN", type="primary", use_container_width=True, disabled=(nuevo_tech_name is None)):
                        id_tecnico_nuevo = tech_opts[nuevo_tech_name]
                        db_update("ordenes", {
                            "fecha_programada": str(fecha_prog), 
                            "tecnico_asignado": str(id_tecnico_nuevo)
                        }, "id", sel_ot_id)
                        st.toast(f"✅ OT #{sel_ot_id} programada exitosamente.")
                        st.rerun()
        else:
            st.success("✨ Todas las órdenes abiertas ya tienen una fecha asignada.")

        st.markdown("---")
        st.markdown("#### 📆 Agenda Diaria por Equipos")
        
        col_fecha, _ = st.columns([1, 3])
        with col_fecha:
            dia_seleccionado = st.date_input("🔍 Ver agenda del día:", value=datetime.date.today(), key="agenda_date")
        
        con_fecha = df_abiertas[df_abiertas['fecha_programada'] == str(dia_seleccionado)]
        
        def render_grupo_personal(titulo, df_grupo, icono):
            if not df_grupo.empty:
                st.markdown(f"##### {icono} {titulo}")
                cols = st.columns(max(len(df_grupo), 1))
                for idx, (_, tech) in enumerate(df_grupo.iterrows()):
                    with cols[idx]:
                        st.markdown(f"<div style='text-align:center; background:#1F2937; color:#F9FAFB; padding:8px; border-radius:6px; border:1px solid #374151; margin-bottom:10px;'><b>{tech['nombre']}</b></div>", unsafe_allow_html=True)
                        ots_del_tecnico = con_fecha[con_fecha['tecnico_asignado'] == str(tech['id'])]
                        
                        if ots_del_tecnico.empty:
                            st.markdown("<div style='text-align:center; color:#6B7280; font-size:0.8rem; padding:15px; border: 1px dashed #374151; border-radius:6px;'>Libre</div>", unsafe_allow_html=True)
                        else:
                            for _, ot in ots_del_tecnico.iterrows():
                                color_crit = "#EF4444" if ot['criticidad'] == 'Crítica' else "#F59E0B" if ot['criticidad'] == 'Alta' else "#3B82F6"
                                st.markdown(f"""
                                <div style='border:1px solid #374151; border-radius:6px; padding:10px; margin-bottom:8px; background:rgba(255,255,255,0.02);'>
                                    <strong style='color:#E5E7EB;'>OT #{ot['id']}</strong><br>
                                    <span style='font-size:0.75rem; color:#9CA3AF;'>🔧 {mapa_activos.get(ot.get('activo_id'), 'Desconocido')}</span><br>
                                    <span style='color:{color_crit}; font-size:0.75rem;'>● {ot['criticidad']}</span>
                                </div>
                                """, unsafe_allow_html=True)

        # Renderizamos los grupos ordenadamente
        render_grupo_personal("Técnicos Internos", usuarios_activos[usuarios_activos['tipo_personal'] == 'Técnico Interno'], "👷‍♂️")
        render_grupo_personal("Contratistas / Terceros", usuarios_activos[usuarios_activos['tipo_personal'] == 'Contratista Externo'], "🤝")
        render_grupo_personal("Administrativos", usuarios_activos[usuarios_activos['tipo_personal'] == 'Administrador'], "🏢")

        # Mostrar bloqueados
        if not usuarios_inactivos.empty:
            st.markdown("---")
            st.markdown("##### 🏖️ Personal No Disponible (Vacaciones / Incapacitados)")
            bloqueados = [f"{u['nombre']} ({u['estado_disponibilidad']})" for _, u in usuarios_inactivos.iterrows()]
            st.warning(" | ".join(bloqueados))

    # =========================================================================
    # 📆 PESTAÑA 2: CALENDARIO VISUAL
    # =========================================================================
    with tab_calendario:
        st.markdown("#### 📅 Visión General del Mes")
        
        c_mes, c_anio, _ = st.columns([1, 1, 3])
        mes_actual = c_mes.selectbox("Mes", range(1, 13), index=datetime.date.today().month - 1)
        anio_actual = c_anio.selectbox("Año", [datetime.date.today().year, datetime.date.today().year + 1])

        cal = calendar.Calendar(firstweekday=0) # Inicia en Lunes
        semanas = cal.monthdatescalendar(anio_actual, mes_actual)

        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        # Encabezado de días
        cols_dias = st.columns(7)
        for i, d in enumerate(dias):
            cols_dias[i].markdown(f"<div style='text-align:center; font-weight:bold; color:#9CA3AF; margin-bottom:10px;'>{d}</div>", unsafe_allow_html=True)

        # Dibujar la cuadrícula
        for semana in semanas:
            cols = st.columns(7)
            for i, dia in enumerate(semana):
                with cols[i]:
                    es_otro_mes = dia.month != mes_actual
                    es_hoy = dia == datetime.date.today()
                    
                    bg_color = "rgba(55, 65, 81, 0.2)" if es_otro_mes else ("rgba(16, 185, 129, 0.15)" if es_hoy else "#1F2937")
                    border = "1px solid #10B981" if es_hoy else "1px solid #374151"

                    # Marco del día
                    html_dia = f"<div style='background:{bg_color}; border:{border}; border-radius:6px; padding:6px; min-height:100px; margin-bottom:10px;'>"
                    html_dia += f"<div style='text-align:right; font-size:0.8rem; color:#D1D5DB; margin-bottom:5px;'><b>{dia.day}</b></div>"

                    # Buscar OTs para este dia
                    ots_dia = df_abiertas[df_abiertas['fecha_programada'] == str(dia)]
                    if not ots_dia.empty:
                        for _, ot in ots_dia.iterrows():
                            # Colores según criticidad
                            color_badge = "#EF4444" if ot['criticidad'] == 'Crítica' else "#F59E0B" if ot['criticidad'] == 'Alta' else "#3B82F6"
                            html_dia += f"<div style='background:{color_badge}; color:white; font-size:0.7rem; padding:3px 5px; border-radius:4px; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' title='{ot.get('descripcion','')[:50]}'>OT #{ot['id']}</div>"
                    
                    html_dia += "</div>"
                    st.markdown(html_dia, unsafe_allow_html=True)
