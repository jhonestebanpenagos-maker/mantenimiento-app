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
from pdf_utils import generar_pdf_orden
from utils.time_tracking import render_time_tracker
from utils.costos import render_costos
from utils.firmas import render_firmas_cierre

def render_gestion_global(df_act, df_users, df_ordenes):
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
    _filtro_tecnico = st.session_state.pop('_filtro_tecnico', None)
    if _filtro_estado and _filtro_estado != "Todas":
        opciones = ["Todas", "Abierta", "Por Validar", "Concluida", "Cancelada"]
        idx_default = opciones.index(_filtro_estado) if _filtro_estado in opciones else 0
        filtro_estado = col_filtros[0].selectbox("Filtrar Estado", opciones, index=idx_default)
    else:
        filtro_estado = col_filtros[0].selectbox("Filtrar Estado", ["Todas", "Abierta", "Por Validar", "Concluida", "Cancelada"], index=0)

    # Filtro por técnico (viene del semáforo del dashboard)
    if _filtro_tecnico and not df_users.empty:
        tech_match = df_users[df_users['id'].astype(str) == str(_filtro_tecnico)]
        if not tech_match.empty:
            tech_nombre = tech_match.iloc[0]['nombre']
            st.info(f"👷 Filtrando por técnico: **{tech_nombre}** — Ordena por 'Limpiar filtro' para ver todas")
            query_filters['tecnico_asignado'] = str(_filtro_tecnico)

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

        # ── Sincronizar adjuntos del correo original ──
        correo_msg_id = orden_actual.get('correo_message_id')

        # DEBUG temporal — quitar después
        with st.expander("🔍 Debug correo", expanded=False):
            st.write(f"correo_message_id = `{correo_msg_id}`")
            st.write(f"tipo = {type(correo_msg_id).__name__}")
            st.write(f"campos orden = {list(orden_actual.index) if hasattr(orden_actual, 'index') else 'N/A'}")

        if correo_msg_id:
            # Verificar si ya tiene adjuntos en bitácora
            try:
                bit_check = supabase.table("bitacora").select("id") \
                    .eq("orden_id", int(id_orden_selec)) \
                    .not_.is_("archivo_url", "null") \
                    .neq("archivo_url", "") \
                    .execute()
                tiene_adjuntos = len(bit_check.data or []) > 0
            except Exception:
                tiene_adjuntos = False

            if not tiene_adjuntos:
                if st.button("📎 Sincronizar adjuntos del correo", key=f"sync_att_{id_orden_selec}",
                             use_container_width=True, type="secondary"):
                    with st.spinner("Conectando a Gmail y descargando adjuntos..."):
                        from utils.email_monitor import sincronizar_adjuntos_correo
                        n_ok, n_total = sincronizar_adjuntos_correo(
                            int(id_orden_selec), correo_msg_id
                        )
                        if n_total == 0:
                            st.warning("⚠️ No se encontraron adjuntos en el correo original o el correo ya no está disponible.")
                        elif n_ok > 0:
                            st.success(f"✅ {n_ok}/{n_total} adjunto(s) sincronizados. Recarga la página para verlos.")
                            st.rerun()
                        else:
                            st.error("❌ No se pudieron subir los adjuntos. Revisa la conexión.")

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
            confirm_del_g = st.text_input("Escriba ELIMINAR para confirmar", key=f"confirm_del_g_{id_orden_selec}", placeholder="ELIMINAR")
            if st.button("ELIMINAR DEFINITIVAMENTE", key=f"del_g_{id_orden_selec}", type="secondary", use_container_width=True, disabled=(confirm_del_g.strip().upper() != "ELIMINAR")):
                db_delete("ordenes", "id", int(id_orden_selec))
                registrar_accion_critica("ELIMINAR_ORDEN", st.session_state.get('usuario', '?'), f"Orden #{id_orden_selec} eliminada (Gestión Global)")
                st.toast("Eliminado.")
                time.sleep(0.3)
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
                    adjunto_html = generar_adjunto_html(url, icon_mode=True)
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
# 📧 COMPONENTE UNIFICADO: ARCHIVO / CORREO (CON CALLBACK)
# ==============================================================================


