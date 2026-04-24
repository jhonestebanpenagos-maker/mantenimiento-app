"""
Utilidades de Firmas Digitales para Órdenes de Trabajo.
Registra firmas del técnico y del supervisor en la bitácora.
"""
import streamlit as st
import re
from datetime import datetime
from utils.db import supabase


def registrar_firma(orden_id: int, usuario: str, tipo_firma: str, documento: str, observacion: str = "") -> bool:
    """
    Registra una firma digital en la bitácora.
    tipo_firma: 'tecnico' (cierre de trabajo) o 'supervisor' (aprobación/validación)
    """
    try:
        label = "👷 FIRMA TÉCNICO" if tipo_firma == "tecnico" else "👔 FIRMA SUPERVISOR"
        msg = f"[✍️ {label}] Confirmado por: {usuario} (Doc: {documento})"
        if observacion:
            msg += f" | Obs: {observacion}"

        supabase.table("bitacora").insert({
            "orden_id": int(orden_id),
            "usuario_text": usuario,
            "mensaje": msg,
            "fecha": datetime.now().isoformat()
        }).execute()
        return True
    except Exception as e:
        st.error("No se pudo registrar la firma.")
        print(f"Error registrar_firma: {e}")
        return False


def obtener_firmas(orden_id: int) -> dict:
    """
    Obtiene las firmas registradas para una orden.
    Retorna dict con info de firma de técnico y supervisor.
    """
    resultado = {
        "tecnico": None,
        "supervisor": None
    }

    try:
        res = supabase.table("bitacora").select("*") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%FIRMA TECNICO%") \
            .order("fecha", desc=True) \
            .limit(1).execute()

        if res.data:
            reg = res.data[0]
            msg = reg['mensaje']
            match = re.search(r'Confirmado por:\s*(.+?)\s*\(Doc:\s*(.+?)\)', msg)
            resultado["tecnico"] = {
                "usuario": match.group(1).strip() if match else reg.get('usuario_text', '?'),
                "documento": match.group(2).strip() if match else '?',
                "fecha": reg['fecha'],
                "bitacora_id": reg['id']
            }

        res2 = supabase.table("bitacora").select("*") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%FIRMA SUPERVISOR%") \
            .order("fecha", desc=True) \
            .limit(1).execute()

        if res2.data:
            reg = res2.data[0]
            msg = reg['mensaje']
            match = re.search(r'Confirmado por:\s*(.+?)\s*\(Doc:\s*(.+?)\)', msg)
            obs_match = re.search(r'Obs:\s*(.+?)$', msg)
            resultado["supervisor"] = {
                "usuario": match.group(1).strip() if match else reg.get('usuario_text', '?'),
                "documento": match.group(2).strip() if match else '?',
                "fecha": reg['fecha'],
                "observacion": obs_match.group(1).strip() if obs_match else "",
                "bitacora_id": reg['id']
            }
    except Exception as e:
        print(f"Error obtener_firmas: {e}")

    return resultado


def eliminar_firma(bitacora_id: int) -> bool:
    """Elimina una firma de la bitácora."""
    try:
        supabase.table("bitacora").delete().eq("id", bitacora_id).execute()
        return True
    except Exception:
        return False


def _es_admin_o_programador(rol: str) -> bool:
    """Verifica si el rol no requiere supervisión adicional."""
    return rol in ["Admin", "Programador"]


def render_firmas_cierre(orden_id: int, usuario: str, rol: str, estado_orden: str):
    """
    Renderiza el widget de firmas para una orden.
    
    Flujo según rol:
    - Admin/Programador: firma como técnico → orden se cierra DIRECTAMENTE (sin firma supervisor)
    - Técnico: firma como técnico → orden pasa a "Por Validar" → Admin/Programador firma como supervisor
    """
    st.markdown("##### ✍️ Firmas de Cierre")

    firmas = obtener_firmas(orden_id)
    firma_tecnico = firmas["tecnico"]
    firma_supervisor = firmas["supervisor"]

    es_admin = _es_admin_o_programador(rol)

    # ── Estado visual de las firmas ──
    col_tec, col_sup = st.columns(2)

    with col_tec:
        if firma_tecnico:
            fecha_fmt = firma_tecnico['fecha'][:16].replace('T', ' ')
            st.markdown(f"""
            <div style="background:rgba(16,185,129,0.12);border:1px solid #10B981;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:1.5rem;margin-bottom:4px;">✅</div>
                <div style="color:#10B981;font-weight:700;font-size:0.85rem;">FIRMA TÉCNICO</div>
                <div style="color:#E5E7EB;font-weight:600;margin-top:6px;">{firma_tecnico['usuario']}</div>
                <div style="color:#9CA3AF;font-size:0.75rem;">Doc: {firma_tecnico['documento']}</div>
                <div style="color:#6B7280;font-size:0.7rem;margin-top:4px;">{fecha_fmt}</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(107,114,128,0.1);border:1px dashed #6B7280;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:1.5rem;margin-bottom:4px;">⬜</div>
                <div style="color:#9CA3AF;font-weight:700;font-size:0.85rem;">FIRMA TÉCNICO</div>
                <div style="color:#6B7280;font-size:0.75rem;margin-top:4px;">Pendiente</div>
            </div>
            """, unsafe_allow_html=True)

    with col_sup:
        # Solo mostrar firma de supervisor si NO es admin (admin no necesita supervisor)
        if es_admin:
            st.markdown(f"""
            <div style="background:rgba(107,114,128,0.05);border:1px solid #374151;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:1.5rem;margin-bottom:4px;">➖</div>
                <div style="color:#6B7280;font-weight:700;font-size:0.85rem;">SUPERVISOR</div>
                <div style="color:#6B7280;font-size:0.75rem;margin-top:4px;">No requerido para {rol}</div>
            </div>
            """, unsafe_allow_html=True)
        elif firma_supervisor:
            fecha_fmt = firma_supervisor['fecha'][:16].replace('T', ' ')
            st.markdown(f"""
            <div style="background:rgba(59,130,246,0.12);border:1px solid #3B82F6;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:1.5rem;margin-bottom:4px;">✅</div>
                <div style="color:#3B82F6;font-weight:700;font-size:0.85rem;">FIRMA SUPERVISOR</div>
                <div style="color:#E5E7EB;font-weight:600;margin-top:6px;">{firma_supervisor['usuario']}</div>
                <div style="color:#9CA3AF;font-size:0.75rem;">Doc: {firma_supervisor['documento']}</div>
                <div style="color:#6B7280;font-size:0.7rem;margin-top:4px;">{fecha_fmt}</div>
                {f'<div style="color:#9CA3AF;font-size:0.7rem;margin-top:4px;font-style:italic;">{firma_supervisor.get("observacion", "")}</div>' if firma_supervisor.get('observacion') else ''}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(107,114,128,0.1);border:1px dashed #6B7280;border-radius:10px;padding:14px;text-align:center;">
                <div style="font-size:1.5rem;margin-bottom:4px;">⬜</div>
                <div style="color:#9CA3AF;font-weight:700;font-size:0.85rem;">FIRMA SUPERVISOR</div>
                <div style="color:#6B7280;font-size:0.75rem;margin-top:4px;">Pendiente</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Botones de firma según rol y estado ──
    st.markdown("")

    # Firma del técnico (cuando la orden está abierta)
    if estado_orden == "Abierta" and not firma_tecnico:
        if rol in ["Tecnico", "Admin", "Programador"]:
            # Texto del botón según rol
            if es_admin:
                label_boton = "✍️ FIRMAR Y CERRAR ORDEN (Admin)"
                ayuda = "Como Admin, tu firma cierra la orden directamente."
            else:
                label_boton = "✍️ Firmar como Técnico (Cerrar trabajo)"
                ayuda = "Tu firma enviará la orden a validación del supervisor."

            if st.toggle(label_boton, key=f"toggle_firma_tec_{orden_id}", help=ayuda):
                with st.form(f"form_firma_tecnico_{orden_id}", clear_on_submit=True):
                    if es_admin:
                        st.markdown("**Confirma que el trabajo fue realizado correctamente. Como Admin, la orden se cerrará directamente.**")
                    else:
                        st.markdown("**Confirma que el trabajo fue realizado correctamente.**")
                    doc_confirm = st.text_input(
                        "Tu número de documento",
                        placeholder="Ingresa tu documento para confirmar",
                        help="Debe coincidir con tu documento registrado en el sistema"
                    )
                    observacion = st.text_area(
                        "Observación final (opcional)",
                        placeholder="Ej: Se reemplazó el rodamiento, equipo funcionando correctamente.",
                        height=80
                    )

                    if st.form_submit_button("✍️ FIRMAR Y CERRAR TRABAJO", type="primary", use_container_width=True):
                        if not doc_confirm:
                            st.error("Debe ingresar su número de documento para firmar.")
                        else:
                            if registrar_firma(orden_id, usuario, "tecnico", doc_confirm, observacion):
                                from utils.db import db_update, db_insert
                                # Admin/Programador: cierra la orden directamente
                                # Técnico: pasa a "Por Validar"
                                if es_admin:
                                    db_update("ordenes", {
                                        "estado": "Concluida",
                                        "fecha_cierre": datetime.now().isoformat()
                                    }, "id", int(orden_id))
                                    db_insert("bitacora", {
                                        "orden_id": int(orden_id),
                                        "usuario_text": usuario,
                                        "mensaje": f"🏁 Orden CERRADA por Admin ({usuario}). Firma de supervisor no requerida.",
                                        "fecha": datetime.now().isoformat()
                                    })
                                    st.toast("✅ Orden cerrada directamente. Firma de supervisor no requerida.")
                                else:
                                    db_update("ordenes", {
                                        "estado": "Por Validar"
                                    }, "id", int(orden_id))
                                    st.toast("✅ Firma registrada. Orden enviada a validación del supervisor.")
                                st.rerun()

    # Firma del supervisor (cuando está por validar) — solo si NO es admin
    if not es_admin and estado_orden == "Por Validar" and not firma_supervisor:
        if rol in ["Admin", "Programador"]:
            if st.toggle("✍️ Firmar como Supervisor (Aprobar trabajo)", key=f"toggle_firma_sup_{orden_id}"):
                with st.form(f"form_firma_supervisor_{orden_id}", clear_on_submit=True):
                    st.markdown("**Aprueba que el trabajo fue ejecutado satisfactoriamente.**")

                    col_doc, col_obs = st.columns(2)
                    doc_confirm_sup = col_doc.text_input(
                        "Tu número de documento",
                        placeholder="Documento para confirmar"
                    )
                    obs_sup = col_obs.text_input(
                        "Observación (opcional)",
                        placeholder="Ej: Trabajo verificado OK"
                    )

                    if st.form_submit_button("👔 FIRMAR Y APROBAR", type="primary", use_container_width=True):
                        if not doc_confirm_sup:
                            st.error("Debe ingresar su número de documento para firmar.")
                        else:
                            if registrar_firma(orden_id, usuario, "supervisor", doc_confirm_sup, obs_sup):
                                from utils.db import db_update, db_insert
                                db_update("ordenes", {
                                    "estado": "Concluida",
                                    "fecha_cierre": datetime.now().isoformat()
                                }, "id", int(orden_id))
                                db_insert("bitacora", {
                                    "orden_id": int(orden_id),
                                    "usuario_text": usuario,
                                    "mensaje": "🏁 Orden APROBADA por supervisor.",
                                    "fecha": datetime.now().isoformat()
                                })
                                st.toast("✅ Firma de supervisor registrada. Orden aprobada.")
                                st.rerun()

    # ── Progreso de firmas ──
    st.markdown("---")
    if es_admin:
        n_firmas = 1 if firma_tecnico else 0
        st.progress(n_firmas, text=f"Firma: {n_firmas}/1 completada (Admin no requiere supervisor)")
    else:
        n_firmas = (1 if firma_tecnico else 0) + (1 if firma_supervisor else 0)
        st.progress(n_firmas / 2, text=f"Firmas: {n_firmas}/2 completadas")
