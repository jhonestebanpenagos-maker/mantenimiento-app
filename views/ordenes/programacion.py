import streamlit as st
import pandas as pd
import datetime
import calendar
import time
from utils.db import db_update, db_insert
from utils.helpers import navegar_a

def render_programacion(df_ordenes, df_users, df_activos):
    st.markdown("### 📅 Torre de Control: Planificador de Mantenimiento")
    st.caption("Modo Administrador: Asigna fechas, divide órdenes para trabajos en conjunto y visualiza la ejecución.")

    # ── 1. Protecciones y Preparación de Datos ──
    if 'fecha_programada' not in df_ordenes.columns:
        st.warning("⚠️ Falta la columna 'fecha_programada' en BD. Ejecuta el script SQL.")
        return

    if 'estado_disponibilidad' not in df_users.columns:
        df_users['estado_disponibilidad'] = 'Activo'
    if 'tipo_personal' not in df_users.columns:
        df_users['tipo_personal'] = 'Técnico Interno'

    df_ordenes['fecha_programada'] = df_ordenes['fecha_programada'].fillna("")
    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy()
    mapa_activos = dict(zip(df_activos['id'], df_activos['nombre'])) if not df_activos.empty else {}

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
                ot_seleccionada = sin_fecha[sin_fecha['id'] == sel_ot_id].iloc[0]
                
                st.markdown("---")
                c1, c2, c3 = st.columns(3)
                
                with c1:
                    fecha_prog = st.date_input(
                        "📅 Fecha(s) de Ejecución", 
                        value=[], 
                        help="Clic en un día para una tarea rápida, o en inicio y fin para crear un rango."
                    )
                    
                with c2:
                    if not usuarios_activos.empty:
                        tech_opts = {f"{u['nombre']} ({u['tipo_personal']})": u['id'] for _, u in usuarios_activos.iterrows()}
                        # 🔥 MAGIA: Selector Múltiple para trabajos en conjunto
                        nuevos_tech_names = st.multiselect(
                            "👷‍♂️ Asignar a (Puedes elegir varios)", 
                            list(tech_opts.keys()),
                            help="Si eliges más de uno, la orden se dividirá automáticamente en sub-órdenes para cada persona."
                        )
                    else:
                        st.error("No hay personal activo.")
                        nuevos_tech_names = []
                    
                with c3:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🚀 PROGRAMAR ORDEN", type="primary", use_container_width=True, disabled=(len(nuevos_tech_names) == 0)):
                        
                        str_fechas = ""
                        if isinstance(fecha_prog, (list, tuple)):
                            if len(fecha_prog) == 2:
                                start_d, end_d = fecha_prog
                                delta = end_d - start_d
                                str_fechas = ",".join([str(start_d + datetime.timedelta(days=i)) for i in range(delta.days + 1)])
                            elif len(fecha_prog) == 1:
                                str_fechas = str(fecha_prog[0])
                        else:
                            str_fechas = str(fecha_prog)
                            
                        if not str_fechas:
                            st.warning("⚠️ Debes seleccionar al menos una fecha.")
                            st.stop()

                        # 🔥 MAGIA: Lógica de Clonación
                        primer_tech = tech_opts[nuevos_tech_names[0]]
                        desc_original = str(ot_seleccionada.get('descripcion', ''))
                        es_multiple = len(nuevos_tech_names) > 1
                        
                        # Agregamos etiqueta visual si son varios técnicos
                        desc_actualizada = f"[CONJUNTO] {desc_original}" if es_multiple and not desc_original.startswith("[CONJUNTO]") else desc_original

                        # 1. Actualizar la OT principal para el primer técnico seleccionado
                        db_update("ordenes", {
                            "fecha_programada": str_fechas, 
                            "tecnico_asignado": str(primer_tech),
                            "descripcion": desc_actualizada
                        }, "id", sel_ot_id)
                        
                        # 2. Clonar la OT para los demás técnicos seleccionados
                        if es_multiple:
                            for extra_tech_name in nuevos_tech_names[1:]:
                                extra_tech_id = tech_opts[extra_tech_name]
                                act_id = ot_seleccionada.get('activo_id')
                                
                                tipo_mto = ot_seleccionada.get('tipo_mantenimiento', 'Correctivo')
                                if pd.isna(tipo_mto): tipo_mto = 'Correctivo'
                                
                                crit = ot_seleccionada.get('criticidad', 'Normal')
                                if pd.isna(crit): crit = 'Normal'
                                
                                nueva_orden = {
                                    "descripcion": desc_actualizada,
                                    "tipo_mantenimiento": tipo_mto,
                                    "criticidad": crit,
                                    "estado": "Abierta",
                                    "tecnico_asignado": str(extra_tech_id),
                                    "fecha_programada": str_fechas
                                }
                                
                                if pd.notna(act_id):
                                    nueva_orden["activo_id"] = int(act_id)
                                    
                                db_insert("ordenes", nueva_orden)
                                
                        if es_multiple:
                            st.toast(f"✅ OT #{sel_ot_id} programada y dividida en {len(nuevos_tech_names)} sub-órdenes.")
                        else:
                            st.toast(f"✅ OT #{sel_ot_id} programada exitosamente.")
                            
                        time.sleep(1)
                        st.rerun()
        else:
            st.success("✨ Todas las órdenes abiertas ya tienen una fecha asignada.")

        st.markdown("---")
        st.markdown("#### 📆 Agenda Diaria por Equipos")
        
        col_fecha, _ = st.columns([1, 3])
        with col_fecha:
            dia_seleccionado = st.date_input("🔍 Ver agenda del día:", value=datetime.date.today(), key="agenda_date")
        
        con_fecha = df_abiertas[df_abiertas['fecha_programada'].str.contains(str(dia_seleccionado), na=False, regex=False)]
        
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
                                st.markdown(f'''
                                <div style="border:1px solid #374151; border-radius:6px; padding:10px; margin-bottom:8px; background:rgba(255,255,255,0.02);">
                                    <strong style="color:#E5E7EB;">OT #{ot['id']}</strong><br>
                                    <span style="font-size:0.75rem; color:#9CA3AF;">🔧 {mapa_activos.get(ot.get('activo_id'), 'Desconocido')}</span><br>
                                    <span style="color:{color_crit}; font-size:0.75rem;">● {ot['criticidad']}</span>
                                </div>
                                ''', unsafe_allow_html=True)

        render_grupo_personal("Técnicos Internos", usuarios_activos[usuarios_activos['tipo_personal'] == 'Técnico Interno'], "👷‍♂️")
        render_grupo_personal("Contratistas / Terceros", usuarios_activos[usuarios_activos['tipo_personal'] == 'Contratista Externo'], "🤝")
        render_grupo_personal("Administrativos", usuarios_activos[usuarios_activos['tipo_personal'] == 'Administrador'], "🏢")

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

        cal = calendar.Calendar(firstweekday=0)
        semanas = cal.monthdatescalendar(anio_actual, mes_actual)

        dias = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
        
        cols_dias = st.columns(7)
        for i, d in enumerate(dias):
            cols_dias[i].markdown(f"<div style='text-align:center; font-weight:bold; color:#9CA3AF; margin-bottom:10px;'>{d}</div>", unsafe_allow_html=True)

        for semana in semanas:
            cols = st.columns(7)
            for i, dia in enumerate(semana):
                with cols[i]:
                    es_otro_mes = dia.month != mes_actual
                    es_hoy = dia == datetime.date.today()
                    
                    bg_color = "rgba(55, 65, 81, 0.2)" if es_otro_mes else ("rgba(16, 185, 129, 0.15)" if es_hoy else "#1F2937")
                    border = "1px solid #10B981" if es_hoy else "1px solid #374151"

                    html_dia = f"<div style='background:{bg_color}; border:{border}; border-radius:6px; padding:6px; min-height:100px; margin-bottom:10px;'>"
                    html_dia += f"<div style='text-align:right; font-size:0.8rem; color:#D1D5DB; margin-bottom:5px;'><b>{dia.day}</b></div>"

                    ots_dia = df_abiertas[df_abiertas['fecha_programada'].str.contains(str(dia), na=False, regex=False)]
                    
                    if not ots_dia.empty:
                        for _, ot in ots_dia.iterrows():
                            color_badge = "#EF4444" if ot['criticidad'] == 'Crítica' else "#F59E0B" if ot['criticidad'] == 'Alta' else "#3B82F6"
                            html_dia += f"<div style='background:{color_badge}; color:white; font-size:0.7rem; padding:3px 5px; border-radius:4px; margin-bottom:4px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;' title='{ot.get('descripcion','')[:50]}'>OT #{ot['id']}</div>"
                    
                    html_dia += "</div>"
                    st.markdown(html_dia, unsafe_allow_html=True)
