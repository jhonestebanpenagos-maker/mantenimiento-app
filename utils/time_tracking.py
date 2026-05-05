"""
Utilidades de Time Tracking para Órdenes de Trabajo.
Registra horas reales de trabajo usando la tabla bitacora.
"""
import streamlit as st
from datetime import datetime
from utils.db import supabase


def iniciar_sesion(orden_id: int, usuario: str) -> bool:
    """Registra el inicio de una sesión de trabajo."""
    try:
        if sesion_activa(orden_id):
            st.warning("⚠️ Ya hay una sesión de trabajo activa en esta orden.")
            return False

        supabase.table("bitacora").insert({
            "orden_id": int(orden_id),
            "usuario_text": usuario,
            "mensaje": "[⏱️ INICIO] Sesión de trabajo iniciada.",
            "fecha": datetime.now().isoformat()
        }).execute()
        st.toast("⏱️ Sesión de trabajo iniciada.")
        return True
    except Exception as e:
        st.error("No se pudo iniciar la sesión de trabajo.")
        print(f"Error iniciar_sesion: {e}")
        return False


def detener_sesion(orden_id: int, usuario: str, comentario: str = "") -> bool:
    """Registra el fin de una sesión de trabajo y calcula la duración."""
    try:
        res = supabase.table("bitacora").select("*") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%[⏱️ INICIO]%") \
            .order("fecha", desc=True) \
            .limit(1).execute()

        if not res.data:
            st.warning("No hay sesión activa para detener.")
            return False

        inicio_registro = res.data[0]
        inicio_ts = datetime.fromisoformat(inicio_registro['fecha'].replace('Z', '+00:00'))
        ahora = datetime.now()

        duracion = ahora - inicio_ts
        horas = duracion.total_seconds() / 3600
        horas_fmt = f"{int(horas)}h {int((horas % 1) * 60)}m"

        msg_fin = f"[⏱️ FIN] Sesión finalizada. Duración: {horas_fmt}."
        if comentario:
            msg_fin += f" Nota: {comentario}"

        supabase.table("bitacora").insert({
            "orden_id": int(orden_id),
            "usuario_text": usuario,
            "mensaje": msg_fin,
            "fecha": ahora.isoformat()
        }).execute()

        st.toast(f"⏱️ Sesión detenida. Trabajaste {horas_fmt}.")
        return True
    except Exception as e:
        st.error("No se pudo detener la sesión.")
        print(f"Error detener_sesion: {e}")
        return False


def sesion_activa(orden_id: int, registros: list = None) -> bool:
    """Verifica si hay una sesión de trabajo activa (inicio sin fin).
    Si se proveen registros, filtra en memoria sin hacer queries."""
    try:
        if registros is not None:
            inicios = [r for r in registros if '[⏱️ INICIO]' in (r.get('mensaje') or '')]
            fines = [r for r in registros if '[⏱️ FIN]' in (r.get('mensaje') or '')]
            if not inicios:
                return False
            if not fines:
                return True
            inicios.sort(key=lambda x: x['fecha'], reverse=True)
            fines.sort(key=lambda x: x['fecha'], reverse=True)
            return inicios[0]['fecha'] > fines[0]['fecha']

        res_inicio = supabase.table("bitacora").select("id, fecha") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%[⏱️ INICIO]%") \
            .order("fecha", desc=True) \
            .limit(1).execute()

        res_fin = supabase.table("bitacora").select("id, fecha") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%[⏱️ FIN]%") \
            .order("fecha", desc=True) \
            .limit(1).execute()

        if not res_inicio.data:
            return False

        if not res_fin.data:
            return True

        ts_inicio = res_inicio.data[0]['fecha']
        ts_fin = res_fin.data[0]['fecha']
        return ts_inicio > ts_fin
    except Exception:
        return False


def obtener_tiempo_inicio(orden_id: int, registros: list = None) -> datetime | None:
    """Retorna el timestamp del inicio de la sesión activa.
    Si se proveen registros, filtra en memoria."""
    try:
        if registros is not None:
            inicios = [r for r in registros if '[⏱️ INICIO]' in (r.get('mensaje') or '')]
            if not inicios:
                return None
            inicios.sort(key=lambda x: x['fecha'], reverse=True)
            return datetime.fromisoformat(inicios[0]['fecha'].replace('Z', '+00:00'))

        res = supabase.table("bitacora").select("fecha") \
            .eq("orden_id", int(orden_id)) \
            .like("mensaje", "%[⏱️ INICIO]%") \
            .order("fecha", desc=True) \
            .limit(1).execute()
        if res.data:
            return datetime.fromisoformat(res.data[0]['fecha'].replace('Z', '+00:00'))
    except Exception:
        pass
    return None


def calcular_total_horas(orden_id: int, registros: list = None) -> float:
    """Calcula el total de horas trabajadas en una orden (sesiones completas).
    Si se proveen registros, filtra en memoria."""
    try:
        import re
        if registros is not None:
            fin_registros = [r for r in registros if '[⏱️ FIN]' in (r.get('mensaje') or '')]
        else:
            res = supabase.table("bitacora").select("mensaje") \
                .eq("orden_id", int(orden_id)) \
                .like("mensaje", "%[⏱️ FIN]%") \
                .execute()
            fin_registros = res.data if res.data else []

        total_horas = 0.0
        for reg in fin_registros:
            match = re.search(r'Duración:\s*(\d+)h\s*(\d+)m', reg['mensaje'])
            if match:
                h = int(match.group(1))
                m = int(match.group(2))
                total_horas += h + (m / 60)
        return round(total_horas, 2)
    except Exception:
        return 0.0


def obtener_resumen_sesiones(orden_id: int, registros: list = None) -> list[dict]:
    """Retorna un resumen de todas las sesiones de trabajo de una orden.
    Si se proveen registros, filtra en memoria."""
    try:
        import re
        if registros is not None:
            sesion_regs = [r for r in registros
                          if '[⏱️ INICIO]' in (r.get('mensaje') or '') or '[⏱️ FIN]' in (r.get('mensaje') or '')]
            sesion_regs.sort(key=lambda x: x['fecha'])
        else:
            res = supabase.table("bitacora").select("*") \
                .eq("orden_id", int(orden_id)) \
                .or_("mensaje.ilike.%[⏱️ INICIO]%,mensaje.ilike.%[⏱️ FIN]%") \
                .order("fecha") \
                .execute()
            sesion_regs = res.data if res.data else []

        sesiones = []
        sesion_actual = None

        for reg in sesion_regs:
            if "[⏱️ INICIO]" in reg['mensaje']:
                sesion_actual = {
                    "inicio": reg['fecha'],
                    "usuario": reg.get('usuario_text', '?'),
                    "bitacora_inicio_id": reg['id']
                }
            elif "[⏱️ FIN]" in reg['mensaje'] and sesion_actual:
                match = re.search(r'Duración:\s*(\d+)h\s*(\d+)m', reg['mensaje'])
                duracion_str = f"{match.group(1)}h {match.group(2)}m" if match else "N/A"

                nota_match = re.search(r'Nota:\s*(.+)$', reg['mensaje'])
                nota = nota_match.group(1) if nota_match else ""

                sesion_actual.update({
                    "fin": reg['fecha'],
                    "duracion": duracion_str,
                    "nota": nota,
                    "bitacora_fin_id": reg['id']
                })
                sesiones.append(sesion_actual)
                sesion_actual = None

        if sesion_actual:
            sesion_actual["fin"] = None
            sesion_actual["duracion"] = "⏱️ En curso..."
            sesion_actual["nota"] = ""
            sesiones.append(sesion_actual)

        return sesiones
    except Exception as e:
        print(f"Error obtener_resumen_sesiones: {e}")
        return []


def render_time_tracker(orden_id: int, usuario: str, registros: list = None):
    """Renderiza el widget de time tracking para una orden.
    Si se proveen registros (pre-filtrados por orden_id), evita queries individuales."""
    st.markdown("##### ⏱️ Control de Tiempo")

    activa = sesion_activa(orden_id, registros)
    total_horas = calcular_total_horas(orden_id, registros)
    sesiones = obtener_resumen_sesiones(orden_id, registros)

    c_estado, c_total = st.columns(2)
    with c_estado:
        if activa:
            inicio_ts = obtener_tiempo_inicio(orden_id, registros)
            if inicio_ts:
                transcurrido = datetime.now() - inicio_ts
                h_trans = int(transcurrido.total_seconds() // 3600)
                m_trans = int((transcurrido.total_seconds() % 3600) // 60)
                st.markdown(f"""
                <div style="background:rgba(16,185,129,0.15);border:1px solid #10B981;border-radius:8px;padding:10px;text-align:center;">
                    <div style="color:#10B981;font-weight:700;">🟢 SESIÓN ACTIVA</div>
                    <div style="color:white;font-size:1.5rem;font-weight:800;">{h_trans}h {m_trans}m</div>
                    <div style="color:#9CA3AF;font-size:0.75rem;">desde {inicio_ts.strftime('%H:%M')}</div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div style="background:rgba(107,114,128,0.15);border:1px solid #6B7280;border-radius:8px;padding:10px;text-align:center;">
                <div style="color:#9CA3AF;font-weight:700;">⏸️ SIN SESIÓN ACTIVA</div>
            </div>
            """, unsafe_allow_html=True)

    with c_total:
        st.markdown(f"""
        <div style="background:rgba(59,130,246,0.15);border:1px solid #3B82F6;border-radius:8px;padding:10px;text-align:center;">
            <div style="color:#60A5FA;font-weight:700;">⏱️ TOTAL TRABAJADO</div>
            <div style="color:white;font-size:1.5rem;font-weight:800;">{total_horas}h</div>
            <div style="color:#9CA3AF;font-size:0.75rem;">{len(sesiones)} sesión(es)</div>
        </div>
        """, unsafe_allow_html=True)

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if not activa:
            if st.button("▶️ INICIAR TRABAJO", key=f"start_timer_{orden_id}", type="primary", use_container_width=True):
                iniciar_sesion(orden_id, usuario)
                st.rerun()
    with c_btn2:
        if activa:
            with st.form(key=f"form_stop_{orden_id}", clear_on_submit=True):
                nota = st.text_input("Nota (opcional)", placeholder="¿Qué hiciste en esta sesión?")
                if st.form_submit_button("⏹️ DETENER", type="secondary", use_container_width=True):
                    detener_sesion(orden_id, usuario, nota)
                    st.rerun()

    if sesiones:
        st.markdown("---")
        st.markdown("**📜 Historial de Sesiones**")
        for s in reversed(sesiones):
            icono = "🟢" if s.get('fin') is None else "✅"
            inicio_fmt = s['inicio'][:16].replace('T', ' ')
            st.markdown(f"""
            <div style="background:rgba(255,255,255,0.03);border-left:3px solid {'#10B981' if s.get('fin') else '#F59E0B'};padding:8px 12px;margin-bottom:4px;border-radius:0 6px 6px 0;">
                <div style="display:flex;justify-content:space-between;font-size:0.8rem;">
                    <span style="color:#E5E7EB;">{icono} {s.get('usuario', '?')}</span>
                    <span style="color:#9CA3AF;">{inicio_fmt}</span>
                </div>
                <div style="color:#60A5FA;font-size:0.85rem;font-weight:600;">{s.get('duracion', 'N/A')}</div>
                {f'<div style="color:#9CA3AF;font-size:0.75rem;">{s.get("nota", "")}</div>' if s.get('nota') else ''}
            </div>
            """, unsafe_allow_html=True)
