import streamlit as st
import pandas as pd
import datetime
from utils.db import db_update
from utils.helpers import navegar_a

def render_programacion(df_ordenes, df_users, df_activos):
    st.markdown("### 📅 Torre de Control: Planificador Diario")
    st.caption("Modo Administrador: Asigna fechas de ejecución y visualiza la carga de trabajo diaria de cada técnico.")

    # 1. Protección inicial
    if 'fecha_programada' not in df_ordenes.columns:
        st.warning("⚠️ Falta la columna 'fecha_programada' en la base de datos. Por favor ejecuta el script SQL en Supabase.")
        return

    # Limpiamos los datos nulos para evitar errores de Pandas
    df_ordenes['fecha_programada'] = df_ordenes['fecha_programada'].fillna("")
    
    # Trabajamos solo con las órdenes que están abiertas
    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy()
    
    # =========================================================================
    # 📥 SECCIÓN 1: BANDEJA DE ENTRADA (Órdenes sin programar)
    # =========================================================================
    st.markdown("#### 📥 Órdenes en Espera (Sin fecha asignada)")
    sin_fecha = df_abiertas[df_abiertas['fecha_programada'] == ""]

    if not sin_fecha.empty:
        with st.container(border=True):
            # Selector de orden
            opciones_ot = [f"OT #{row['id']} - {str(row['descripcion'])[:50]}..." for _, row in sin_fecha.iterrows()]
            sel_ot_str = st.selectbox("Selecciona la Orden de Trabajo a programar:", opciones_ot)
            sel_ot_id = int(sel_ot_str.split(" ")[1].replace("#", ""))
            
            ot_seleccionada = sin_fecha[sin_fecha['id'] == sel_ot_id].iloc[0]
            
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            
            with c1:
                fecha_prog = st.date_input("📅 Fecha de Ejecución", value=datetime.date.today())
                
            with c2:
                # Diccionario de técnicos para el selector
                tech_opts = {u['nombre']: u['id'] for _, u in df_users.iterrows()}
                curr_tech_id = ot_seleccionada['tecnico_asignado']
                
                # Buscar el nombre del técnico actual
                curr_tech_name = [k for k, v in tech_opts.items() if str(v) == str(curr_tech_id)]
                curr_tech_name = curr_tech_name[0] if curr_tech_name else list(tech_opts.keys())[0]
                idx_tech = list(tech_opts.keys()).index(curr_tech_name)
                
                nuevo_tech_name = st.selectbox("👷‍♂️ Asignar a Técnico", list(tech_opts.keys()), index=idx_tech)
                
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("🚀 PROGRAMAR ORDEN", type="primary", use_container_width=True):
                    # Actualizar en BD
                    id_tecnico_nuevo = tech_opts[nuevo_tech_name]
                    db_update("ordenes", {
                        "fecha_programada": str(fecha_prog), 
                        "tecnico_asignado": str(id_tecnico_nuevo)
                    }, "id", sel_ot_id)
                    
                    st.toast(f"✅ OT #{sel_ot_id} programada exitosamente.")
                    st.rerun()
    else:
        st.success("✨ ¡Excelente! Todas las órdenes abiertas ya tienen una fecha asignada.")

    st.markdown("<br>", unsafe_allow_html=True)

    # =========================================================================
    # 📆 SECCIÓN 2: AGENDA DIARIA POR TÉCNICO
    # =========================================================================
    st.markdown("#### 📆 Agenda de Ejecución")
    
    col_fecha, col_vacia = st.columns([1, 3])
    with col_fecha:
        dia_seleccionado = st.date_input("🔍 Ver agenda del día:", value=datetime.date.today(), key="agenda_date")
    
    # Filtrar las órdenes programadas para el día seleccionado
    con_fecha = df_abiertas[df_abiertas['fecha_programada'] == str(dia_seleccionado)]
    
    # Crear un diccionario rápido de activos para mostrar el nombre
    mapa_activos = dict(zip(df_activos['id'], df_activos['nombre'])) if not df_activos.empty else {}

    if not df_users.empty:
        # Creamos una columna para cada técnico
        cols_tecnicos = st.columns(len(df_users))
        
        for idx, (_, tech) in enumerate(df_users.iterrows()):
            with cols_tecnicos[idx]:
                st.markdown(f"<div style='text-align:center; background:#1F2937; padding:10px; border-radius:6px; margin-bottom:10px;'><b>👷‍♂️ {tech['nombre']}</b></div>", unsafe_allow_html=True)
                
                ots_del_tecnico = con_fecha[con_fecha['tecnico_asignado'] == str(tech['id'])]
                
                if ots_del_tecnico.empty:
                    st.markdown("<div style='text-align:center; color:#6B7280; font-size:0.9rem; padding:20px; border: 1px dashed #374151; border-radius:6px;'>Libre</div>", unsafe_allow_html=True)
                else:
                    for _, ot in ots_del_tecnico.iterrows():
                        with st.container(border=True):
                            st.markdown(f"**OT #{ot['id']}** — {ot.get('tipo_mantenimiento', '')}")
                            
                            nombre_activo = mapa_activos.get(ot.get('activo_id'), 'Activo Desconocido')
                            st.caption(f"🔧 {nombre_activo}")
                            
                            color_crit = "#EF4444" if ot['criticidad'] == 'Crítica' else "#F59E0B" if ot['criticidad'] == 'Alta' else "#3B82F6"
                            st.markdown(f"<span style='color:{color_crit}; font-size:0.8rem;'>● Prioridad {ot['criticidad']}</span>", unsafe_allow_html=True)
                            
                            if st.button("Abrir OT", key=f"abrir_{ot['id']}", use_container_width=True):
                                navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=ot['id'])
