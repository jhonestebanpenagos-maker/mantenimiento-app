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
from utils.time_tracking import render_time_tracker
from utils.costos import render_costos
from utils.firmas import render_firmas_cierre
from utils.uploads import subir_archivo_generico
from pdf_utils import render_pdf_viewer

def render_mis_gestiones(df_act, df_users, df_ordenes):
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

        # ══════════════════════════════════════════════════════════════════
        # 📄 DESCARGA DE PDF INDIVIDUAL
        # ══════════════════════════════════════════════════════════════════
        try:
            from pdf_utils import generar_pdf_orden
            tecnico_nombre = usuario
            if not df_users.empty:
                tech_match = df_users[df_users['id'].astype(str) == str(row.get('tecnico_asignado', ''))]
                if not tech_match.empty:
                    tecnico_nombre = tech_match.iloc[0]['nombre']

            pdf_data = generar_pdf_orden(row, nombre_activo, tecnico_nombre)
            st.download_button(
                "📄 Descargar PDF de esta Orden",
                data=pdf_data,
                file_name=f"Reporte_OT_{row['id']}.pdf",
                mime="application/pdf",
                key=f"btn_pdf_mg_{row['id']}",
                use_container_width=True
            )
        except Exception as e:
            print(f"Error PDF en mis_gestiones: {e}")

        # ── Sincronizar adjuntos del correo original ──
        correo_msg_id = row.get('correo_message_id') if 'correo_message_id' in row.index else None
        if correo_msg_id:
            try:
                bit_check = supabase.table("bitacora").select("id") \
                    .eq("orden_id", int(row['id'])) \
                    .not_.is_("archivo_url", "null") \
                    .neq("archivo_url", "") \
                    .execute()
                tiene_adjuntos = len(bit_check.data or []) > 0
            except Exception:
                tiene_adjuntos = False

            if not tiene_adjuntos:
                if st.button("📎 Sincronizar adjuntos del correo", key=f"sync_att_mg_{row['id']}",
                             use_container_width=True, type="secondary"):
                    with st.spinner("Conectando a Gmail y descargando adjuntos..."):
                        from utils.email_monitor import sincronizar_adjuntos_correo
                        n_ok, n_total = sincronizar_adjuntos_correo(int(row['id']), correo_msg_id)
                        if n_total == 0:
                            st.warning("⚠️ No se encontraron adjuntos en el correo original o el correo ya no está disponible.")
                        elif n_ok > 0:
                            st.success(f"✅ {n_ok}/{n_total} adjunto(s) sincronizados.")
                            st.rerun()
                        else:
                            st.error("❌ No se pudieron subir los adjuntos.")

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

                        # HTML del adjunto con visor para PDFs
                        adjunto_html = ""

                        if url:
                            ul = url.lower()
                            if ul.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#10B981;font-weight:bold;">🖼️ Ver Imagen</a>"""
                            elif ul.endswith('.pdf'):
                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#EF4444;font-weight:bold;">📄 Ver PDF</a>"""

                            elif ul.endswith(('.xls', '.xlsx')):
                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#16A34A;font-weight:bold;">📊 Ver Excel</a>"""
                            elif ul.endswith('.msg'):
                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#3B82F6;font-weight:bold;">📧 Ver Correo</a>"""
                            else:
                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#F59E0B;font-weight:bold;">📎 Ver Archivo</a>"""

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

            # Visor inline para PDFs (fuera de columnas para evitar conflictos)
            try:
                pdf_adjuntos = [b for b in (bitacora.data or []) if (b.get('archivo_url') or '').lower().endswith('.pdf')]
                for pa in pdf_adjuntos:
                    with st.expander(f"👁️ Ver PDF adjunto — {pa.get('usuario_text', '?')} ({pa['fecha'][:10]})", expanded=False):
                        render_pdf_viewer(pa['archivo_url'], titulo=f"Adjunto de {pa.get('usuario_text', '?')}")
            except Exception as e_pdf:
                print(f"Error visor PDF: {e_pdf}")

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
                time.sleep(0.3)
                st.rerun()
