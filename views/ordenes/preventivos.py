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

def render_preventivos(df_act, df_users):
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
            time.sleep(0.5)
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


