# utils/email_unified.py — Módulo de correo unificado (REFACTORIZADO)
# Unifica el buzón de correos pendientes y la auditoría.

import streamlit as st
import re
import base64
import time
from datetime import datetime
from email.utils import parsedate_to_datetime

# =============================================================================
# 🔌 IMPORTS DE MÓDULOS EXISTENTES (lazy para evitar circular imports)
# =============================================================================
def _mod_monitor():
    import utils.email_monitor as m
    return m

def _mod_audit():
    import utils.email_audit as a
    return a

# =============================================================================
# 📅 UTILIDADES DE FECHA
# =============================================================================
def _normalizar_fecha(fecha_str):
    """Convierte cualquier formato de fecha a ISO 8601 para ordenamiento."""
    if not fecha_str:
        return ''
    fecha_str = str(fecha_str).strip()
    if fecha_str and fecha_str[0].isdigit():
        return fecha_str[:19]
    try:
        dt = parsedate_to_datetime(fecha_str)
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        pass
    m = re.search(r'(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})', fecha_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return fecha_str[:19]

# =============================================================================
# 📬 CARGA UNIFICADA DE CORREOS
# =============================================================================
@st.cache_data(ttl=300, show_spinner=False)
def _cargar_correos_unificado_cached(sin_frescos=False, last_sync_ts=0):
    """
    Versión cacheada de la carga unificada. 
    Se usa last_sync_ts para invalidar manualmente cuando se presiona 'Sincronizar'.
    """
    monitor = _mod_monitor()
    from utils.db import supabase

    # ── 1. Obtener IDs ya procesados (BD) ──
    # Nota: Los locales se filtran fuera del cache para ser inmediatos
    procesados_ids_db = monitor._obtener_procesados()

    # ── 2. Cargar desde emails_pendientes ──
    pendientes_guardados = []
    try:
        pendientes_guardados = monitor._obtener_pendientes_guardados()
    except Exception: pass

    # ── 3. Cargar desde email_scan_cache ──
    todos_cache = []
    try:
        if supabase:
            res_cache = supabase.table("email_scan_cache").select("*").execute()
            todos_cache = res_cache.data or []
    except Exception: pass

    # ── 4. Cargar frescos de Gmail ──
    frescos = []
    if not sin_frescos:
        cfg = st.secrets.get("gmail", {})
        if cfg.get("correo"):
            try:
                frescos = monitor.descargar_correos_nuevos(max_correos=50, dias_atras=2)
            except Exception: pass

    # ── 5. Unificar y filtrar ──
    vistos = set()
    unificados = []

    def _esta_procesado(mid):
        return mid.strip() in procesados_ids_db

    # Fuente 1: Pendientes
    for c in pendientes_guardados:
        mid = (c.get('message_id') or '').strip()
        if not mid or mid in vistos or _esta_procesado(mid):
            continue
        unificados.append({
            'message_id': mid,
            'asunto': c.get('asunto', ''),
            'remitente': c.get('remitente', ''),
            'remitente_nombre': c.get('remitente_nombre', ''),
            'fecha': _normalizar_fecha(c.get('fecha_correo', '') or c.get('fecha', '')),
            'cuerpo_corto': c.get('cuerpo_corto', ''),
            'cuerpo': c.get('cuerpo', ''),
            'adjuntos': [],
            'n_adjuntos': c.get('n_adjuntos', 0),
            'leido': c.get('leido', False),
            'contenido_cargado': False,
            'fuente': 'pendientes',
        })
        vistos.add(mid)

    # Fuente 2: Cache
    ids_pendientes = {c.get('message_id', '').strip() for c in pendientes_guardados if c.get('message_id')}
    for c in todos_cache:
        mid = (c.get('message_id') or '').strip()
        if not mid or mid in vistos or _esta_procesado(mid):
            continue
        if c.get('en_pendientes') and mid in ids_pendientes:
            continue
        unificados.append({
            'message_id': mid,
            'asunto': c.get('asunto', ''),
            'remitente': c.get('remitente', ''),
            'remitente_nombre': '',
            'fecha': _normalizar_fecha(c.get('fecha_correo', '')),
            'cuerpo_corto': c.get('cuerpo_corto', ''),
            'cuerpo': '',
            'adjuntos': [],
            'n_adjuntos': c.get('n_adjuntos', 0),
            'leido': c.get('leido', False),
            'contenido_cargado': False,
            'fuente': 'cache',
        })
        vistos.add(mid)

    # Fuente 3: Gmail
    for c in frescos:
        mid = (c.get('message_id') or '').strip()
        if not mid or mid in vistos or _esta_procesado(mid):
            continue
        c['fuente'] = 'gmail'
        if 'contenido_cargado' not in c:
            c['contenido_cargado'] = False
        unificados.append(c)
        vistos.add(mid)

    unificados.sort(key=lambda c: _normalizar_fecha(c.get('fecha', '')), reverse=True)
    return unificados, procesados_ids_db

def _cargar_correos_unificado(sin_frescos=False):
    """Wrapper no cacheado que aplica filtros de sesión inmediatos."""
    last_sync = st.session_state.get('_last_email_sync_ts', 0)
    unificados, procesados_db = _cargar_correos_unificado_cached(sin_frescos, last_sync)
    
    # Aplicar máscara de sesión (procesados recientemente)
    procesados_locales = st.session_state.get('_recentemente_procesados', set())
    todos_procesados = procesados_db | procesados_locales
    
    pendientes = [c for c in unificados if c['message_id'].strip() not in todos_procesados]
    return pendientes, todos_procesados


# =============================================================================
# 🔄 SYNC COMPLETO
# =============================================================================
def _sync_gmail_completo(max_correos=200, dias_atras=90):
    audit = _mod_audit()
    try:
        with st.spinner("📡 Sincronizando con Gmail..."):
            resultado_scan = audit.escanear_gmail_rapido(max_correos=max_correos, dias_atras=dias_atras)
    except Exception as e:
        resultado_scan = {'errores': [str(e)]}

    correos, procesados = _cargar_correos_unificado(sin_frescos=True)
    return correos, procesados, resultado_scan

# =============================================================================
# 🖼️ RENDERIZADO: CARD DE CORREO
# =============================================================================
def _render_card_correo(correo, idx, df_act, df_users, df_ordenes):
    monitor = _mod_monitor()
    audit = _mod_audit()
    message_id = correo['message_id']

    # Card visual
    remitente = correo.get('remitente_nombre') or correo.get('remitente', 'Desconocido')
    fecha_corta = (correo.get('fecha', '') or '')[:10]
    fuente_badge = {'pendientes': '💾', 'cache': '📡', 'gmail': '🆕'}.get(correo.get('fuente', '?'), '📧')

    st.markdown(f"""
    <div style="border:1px solid #374151;border-radius:10px;padding:14px 16px;margin-bottom:10px;background:#1F2937;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <span style="color:#F59E0B;font-weight:600;">{correo['asunto'][:70]}</span>
                <span style="color:#6B7280;font-size:0.7em;margin-left:6px;">{fuente_badge}</span>
            </div>
            <span style="color:#6B7280;font-size:0.8em;">{fecha_corta}</span>
        </div>
        <div style="color:#9CA3AF;font-size:0.85em;margin-top:4px;">👤 {remitente}</div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📄 Ver contenido", expanded=False):
        if not correo.get('contenido_cargado'):
            if st.button("⬇️ Cargar contenido", key=f"btn_load_{idx}", type="primary", use_container_width=True):
                res = audit.descargar_correo_por_id(message_id)
                if res:
                    correo.update(res)
                    correo['contenido_cargado'] = True
                    st.rerun()
        else:
            if correo.get('html_raw'):
                import streamlit.components.v1 as components
                html_seguro = re.sub(r'<script[^>]*>.*?</script>', '', correo['html_raw'], flags=re.DOTALL | re.IGNORECASE)
                components.html(f'<div style="background:#fff;color:#1f2937;padding:16px;border-radius:8px;">{html_seguro}</div>', height=400, scrolling=True)
            else:
                st.text_area("Texto", value=correo.get('cuerpo', ''), height=200, disabled=True, key=f"txt_{idx}")

    # Acciones
    col_crear, col_vinc, col_desc = st.columns([1, 1, 1])
    
    with col_desc:
        if st.button("🗑️ Descartar", key=f"btn_desc_{idx}", use_container_width=True):
            # 1. Marcar como procesado en BD
            monitor._marcar_procesado(message_id, accion="descartado")
            # 2. Eliminar de pendientes en BD
            monitor._eliminar_pendiente(message_id)
            # 3. Actualizar cache de auditoría
            audit._cache_actualizar_estado(message_id, en_procesados=True, en_pendientes=False)
            # 4. Actualizar estado local inmediato
            if '_recentemente_procesados' not in st.session_state:
                st.session_state._recentemente_procesados = set()
            st.session_state._recentemente_procesados.add(message_id.strip())
            # 5. Eliminar de la lista actual en memoria
            if '_correos_pendientes' in st.session_state:
                st.session_state._correos_pendientes = [c for c in st.session_state._correos_pendientes if c['message_id'] != message_id]
            
            st.toast("🗑️ Correo descartado definitivamente.")
            time.sleep(0.1)
            st.rerun()

    if col_crear.button("✅ Crear OT", key=f"btn_ot_{idx}", type="primary", use_container_width=True):
        st.session_state[f'_ucrear_ot_{idx}'] = True

    if col_vinc.button("🔗 Vincular", key=f"btn_vinc_{idx}", use_container_width=True):
        st.session_state[f'_uvinc_ot_{idx}'] = True

    # Formularios de acción (se renderizan abajo si están activos)
    if st.session_state.get(f'_uvinc_ot_{idx}'):
        monitor.render_selector_ordenes_para_vincular(idx, correo, df_ordenes, df_act)
    
    if st.session_state.get(f'_ucrear_ot_{idx}'):
        _render_form_crear_ot(correo, idx, df_act, df_users)

def _render_form_crear_ot(correo, idx, df_act, df_users):
    monitor = _mod_monitor()
    audit = _mod_audit()
    from utils.db import db_insert

    with st.form(key=f"form_ot_{idx}"):
        st.markdown("**📋 Nueva Orden desde Correo**")
        act_opciones = ["(Seleccionar activo)"] + sorted(df_act['nombre'].tolist()) if not df_act.empty else []
        activo_sel = st.selectbox("Activo", act_opciones)
        tecnicos = {u['nombre']: u['id'] for _, u in df_users.iterrows()}
        tecnico_sel = st.selectbox("Técnico", list(tecnicos.keys()))
        desc = st.text_area("Descripción", value=f"Asunto: {correo['asunto']}\n\n{correo.get('cuerpo_corto', '')}")
        
        if st.form_submit_button("✅ CREAR ORDEN", use_container_width=True):
            if activo_sel == "(Seleccionar activo)":
                st.error("Selecciona un activo")
            else:
                act_id = df_act[df_act['nombre'] == activo_sel].iloc[0]['id']
                res = db_insert("ordenes", {
                    "activo_id": act_id, "descripcion": desc, "estado": "Abierta",
                    "tecnico_asignado": str(tecnicos[tecnico_sel]), "origen": "correo",
                    "correo_message_id": correo['message_id'], "fecha_creacion": datetime.now().isoformat()
                })
                if res.data:
                    oid = res.data[0]['id']
                    monitor._marcar_procesado(correo['message_id'], orden_id=oid, accion="orden")
                    monitor._eliminar_pendiente(correo['message_id'])
                    audit._cache_actualizar_estado(correo['message_id'], en_procesados=True, en_pendientes=False)
                    
                    if '_recentemente_procesados' not in st.session_state:
                        st.session_state._recentemente_procesados = set()
                    st.session_state._recentemente_procesados.add(correo['message_id'].strip())
                    
                    st.success(f"✅ OT #{oid} creada")
                    st.rerun()

# =============================================================================
# 📧 BUZÓN PRINCIPAL
# =============================================================================
def render_buzon_correo():
    st.markdown("### 📧 Correo")
    
    col_sync, col_info = st.columns([1, 2])
    if col_sync.button("🔄 Sincronizar Gmail", type="primary", use_container_width=True):
        st.session_state._last_email_sync_ts = time.time()
        correos, _, scan = _sync_gmail_completo()
        st.session_state._correos_pendientes = correos
        st.session_state._sync_result = scan
        st.rerun()

    correos = st.session_state.get('_correos_pendientes')
    if correos is None:
        correos, _ = _cargar_correos_unificado(sin_frescos=True)
        st.session_state._correos_pendientes = correos

    # Filtrar procesados (incluyendo los de esta sesión)
    monitor = _mod_monitor()
    proc_ids = monitor._obtener_procesados() | st.session_state.get('_recentemente_procesados', set())
    pendientes = [c for c in correos if c['message_id'].strip() not in proc_ids]

    if not pendientes:
        st.info("📭 Sin correos pendientes.")
        return

    m1, m2 = st.columns(2)
    m1.metric("📬 Pendientes", len(pendientes))
    
    from utils.db import run_query
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ord = run_query("ordenes")

    for i, c in enumerate(pendientes[:15]): # Limitar a 15 por página para performance
        _render_card_correo(c, i, df_act, df_users, df_ord)

def render_auditoria_correos():
    audit = _mod_audit()
    audit.render_auditoria_correos()
