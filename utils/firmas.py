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
            .or_("mensaje.ilike.%FIRMA TECNICO%,mensaje.ilike.%FIRMA SUPERVISOR%") \
            .order("fecha", desc=True) \
            .execute()

        if not res.data:
            return resultado

        for reg in res.data:
            msg = reg['mensaje']
            if resultado["tecnico"] is None and "FIRMA TECNICO" in msg.upper():
                match = re.search(r'Confirmado por:\s*(.+?)\s*\(Doc:\s*(.+?)\)', msg)
                resultado["tecnico"] = {
                    "usuario": match.group(1).strip() if match else reg.get('usuario_text', '?'),
                    "documento": match.group(2).strip() if match else '?',
                    "fecha": reg['fecha'],
                    "bitacora_id": reg['id']
                }
            if resultado["supervisor"] is None and "FIRMA SUPERVISOR" in msg.upper():
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


def render_firmas_cierre(orden_id: int, usuario: str, rol: str, estado_orden: str):
    """
    Renderiza el widget de firmas para una orden.
    - Técnico puede firmar cuando la orden está Abierta
    - Supervisor puede firmar cuando la orden está Por Validar
    """
    st.markdown("##### ✍️ Firmas de Cierre")

    firmas = obtener_firmas(orden_id)
    firma_tecnico = firmas["tecnico"]
    firma_supervisor = firmas["supervisor"]

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
        if firma_supervisor:
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

    # Firma del técnico (cuando la orden está abierta y es técnico)
    if estado_orden == "Abierta" and not firma_tecnico:
        if rol in ["Tecnico", "Admin", "Programador"]:
            with st.expander("✍️ Firmar como Técnico (Cerrar trabajo)"):
                with st.form(f"form_firma_tecnico_{orden_id}", clear_on_submit=True):
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
                                st.toast("✅ Firma de técnico registrada.")
                                st.rerun()

    # Firma del supervisor (cuando está por validar)
    if estado_orden == "Por Validar" and not firma_supervisor:
        if rol in ["Admin", "Programador"]:
            with st.expander("✍️ Firmar como Supervisor (Aprobar trabajo)"):
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
                                st.toast("✅ Firma de supervisor registrada. Orden aprobada.")
                                st.rerun()

    # ── Progreso de firmas ──
    st.markdown("---")
    n_firmas = (1 if firma_tecnico else 0) + (1 if firma_supervisor else 0)
    st.progress(n_firmas / 2, text=f"Firmas: {n_firmas}/2 completadas")
