# utils/email_unified.py — Módulo de correo unificado
# Reemplaza render_buzon_correo (email_monitor.py) y render_auditoria_correos (email_audit.py)
# con una sola vista que unifica todo.
#
# INSTALACIÓN:
# 1. Copiar este archivo a utils/email_unified.py
# 2. En views/ordenes/__init__.py cambiar:
#      from utils.email_monitor import render_buzon_correo
#      from utils.email_audit import render_auditoria_correos
#    por:
#      from utils.email_unified import render_buzon_correo, render_auditoria_correos
#
# Reutiliza funciones de email_monitor.py e email_audit.py existentes.

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
# 📬 CARGA UNIFICADA DE CORREOS
# =============================================================================
# =============================================================================
# 📅 PARSER DE FECHAS ROBUSTO
# =============================================================================
def _normalizar_fecha(fecha_str):
    """Convierte cualquier formato de fecha a ISO 8601 para ordenamiento."""
    if not fecha_str:
        return ''
    fecha_str = str(fecha_str).strip()
    # Si ya es ISO (empieza con dígito)
    if fecha_str and fecha_str[0].isdigit():
        return fecha_str[:19]
    # RFC 2822 ("Mon, 3 Jun 2026 10:30:00 -0500")
    try:
        dt = parsedate_to_datetime(fecha_str)
        return dt.strftime('%Y-%m-%dT%H:%M:%S')
    except Exception:
        pass
    # Fltimo intento: extraer fecha con regex
    m = re.search(r'(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})', fecha_str)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return fecha_str[:19]


def _cargar_correos_unificado(sin_frescos=False):
    """
    Carga TODOS los correos pendientes de gestionar desde 3 fuentes:
    1. emails_pendientes (guardados previamente)
    2. email_scan_cache (escaneados como limbo)
    3. Gmail frescos (últimos 2 días, headers solamente)

    Deduplica por message_id y filtra los ya procesados.
    Retorna lista unificada de correos pendientes.
    """
    monitor = _mod_monitor()
    audit = _mod_audit()
    from utils.db import supabase

    # ── 1. Obtener IDs ya procesados (consulta fresca + locales) ──
    procesados_ids = monitor._obtener_procesados()
    # Complementar con procesados locales (session state) para compensar
    # el delay de consistencia del cliente Supabase
    procesados_locales = st.session_state.get('_recentemente_procesados', set())
    procesados_ids = procesados_ids | procesados_locales
    print(f"📧 _cargar_correos_unificado: {len(procesados_ids)} procesados ({len(procesados_locales)} locales)")

    # ── 2. Cargar desde emails_pendientes ──
    pendientes_guardados = []
    try:
        pendientes_guardados = monitor._obtener_pendientes_guardados()
    except Exception as e:
        print(f"⚠️ Error cargando pendientes: {e}")

    # ── 3. Cargar desde email_scan_cache ──
    todos_cache = []
    try:
        if supabase:
            res_cache = supabase.table("email_scan_cache").select("*").execute()
            todos_cache = res_cache.data or []
    except Exception as e:
        print(f"⚠️ Error cargando caché: {e}")

    # ── 4. Cargar frescos de Gmail (solo si no es sync) ──
    frescos = []
    if not sin_frescos:
        cfg = st.secrets.get("gmail", {})
        if cfg.get("correo"):
            try:
                frescos = monitor.descargar_correos_nuevos(max_correos=50, dias_atras=2)
            except Exception as e:
                print(f"⚠️ Error descargando frescos: {e}")

    # ── 5. Unificar con FILTRO TRIPLE contra procesados ──
    vistos = set()
    unificados = []

    def _esta_procesado(mid):
        """Verifica si un correo ya fue procesado (chequeo contra BD)."""
        return mid in procesados_ids

    # Fuente 1: Pendientes guardados
    for c in pendientes_guardados:
        mid = (c.get('message_id') or '').strip()
        if not mid or mid in vistos or _esta_procesado(mid):
            continue
        correo = {
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
        }
        unificados.append(correo)
        vistos.add(mid)

    # Fuente 2: Cache (excluyendo los que están en pendientes Y los procesados)
    ids_pendientes = {c.get('message_id', '').strip() for c in pendientes_guardados if c.get('message_id')}
    for c in todos_cache:
        mid = (c.get('message_id') or '').strip()
        if not mid or mid in vistos or _esta_procesado(mid):
            continue
        # Si está marcado como pendiente en la caché, saltarlo (ya viene de pendientes)
        if c.get('en_pendientes') and mid in ids_pendientes:
            continue
        correo = {
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
        }
        unificados.append(correo)
        vistos.add(mid)

    # Fuente 3: Frescos de Gmail
    for c in frescos:
        mid = (c.get('message_id') or '').strip()
        if not mid or mid in vistos or _esta_procesado(mid):
            continue
        c['fuente'] = 'gmail'
        if 'contenido_cargado' not in c:
            c['contenido_cargado'] = False
        unificados.append(c)
        vistos.add(mid)

    # ── 6. Ordenar por fecha (más reciente primero) ──
    unificados.sort(key=lambda c: _normalizar_fecha(c.get('fecha', '')), reverse=True)

    print(f"📧 Resultado: {len(unificados)} pendientes")
    print(f"   Fuentes: {len(pendientes_guardados)} pendientes, {len(todos_cache)} cache, {len(frescos)} frescos")
    print(f"   Procesados en BD: {len(procesados_ids)}")
    # Verificar intersección entre cache y procesados
    cache_ids = {c.get('message_id', '').strip() for c in todos_cache if c.get('message_id')}
    en_ambos = cache_ids & procesados_ids
    print(f"   Cache que YA está en procesados (deberían ser excluidos): {len(en_ambos)}")
    if en_ambos:
        for ejemplo in list(en_ambos)[:3]:
            print(f"   → Ejemplo excluido: [{ejemplo[:60]}]")

    return unificados, procesados_ids


# =============================================================================
# 🔄 SYNC COMPLETO: ESCANEAR + CARGAR EN UN SOLO PASO
# =============================================================================
def _sync_gmail_completo(max_correos=200, dias_atras=90):
    """
    Escanea Gmail (headers) y retorna correos unificados listos para mostrar.
    Combina escaneo rápido (cache) + carga de pendientes.
    """
    audit = _mod_audit()

    try:
        with st.spinner("📡 Escaneando Gmail y sincronizando..."):
            resultado_scan = audit.escanear_gmail_rapido(
                max_correos=max_correos,
                dias_atras=dias_atras,
                forzar_completo=False
            )
    except Exception as e:
        resultado_scan = {'total_gmail': 0, 'nuevos': 0, 'ya_en_cache': 0, 'en_limbo': [], 'errores': [f"Error escaneando: {e}"], 'cache_total': 0}

    # Cargar correos unificados (sin conexión IMAP adicional)
    try:
        correos, procesados = _cargar_correos_unificado(sin_frescos=True)
    except Exception as e:
        correos, procesados = [], set()
        resultado_scan['errores'].append(f"Error cargando correos: {e}")

    return correos, procesados, resultado_scan


# =============================================================================
# 🖼️ RENDERIZADO: CARD DE CORREO UNIFICADA
# =============================================================================
def _render_card_correo(correo, idx, df_act, df_users, df_ordenes):
    """
    Renderiza una card de correo con todas las acciones.
    Unifica el estilo de Correo y Auditoría.
    """
    monitor = _mod_monitor()
    audit = _mod_audit()

    message_id = correo['message_id']
    state_key = f"_ucorr_{idx}_{message_id[:20]}"

    # ── Card visual ──
    icono = '📩' if not correo.get('leido') else '📧'
    remitente = correo.get('remitente_nombre') or correo.get('remitente', 'Desconocido')
    fecha_corta = (correo.get('fecha', '') or '')[:10]
    n_adjuntos = correo.get('n_adjuntos', len(correo.get('adjuntos', [])))
    fuente = correo.get('fuente', '?')
    fuente_badge = {
        'pendientes': '💾', 'cache': '📡', 'gmail': '🆕'
    }.get(fuente, '📧')

    st.markdown(f"""
    <div style="border:1px solid #374151;border-radius:10px;padding:14px 16px;margin-bottom:10px;background:#1F2937;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <span style="font-size:1.1rem;">{icono}</span>
                <span style="color:#F59E0B;font-weight:600;">{correo['asunto'][:70]}</span>
                <span style="color:#6B7280;font-size:0.7em;margin-left:6px;">{fuente_badge}</span>
            </div>
            <span style="color:#6B7280;font-size:0.8em;">{fecha_corta}</span>
        </div>
        <div style="color:#9CA3AF;font-size:0.85em;margin-top:4px;">
            👤 {remitente} {f'&nbsp;|&nbsp; 📎 {n_adjuntos} adjunto(s)' if n_adjuntos > 0 else ''}
        </div>
        <div style="color:#D1D5DB;font-size:0.85em;margin-top:6px;background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:6px;">
            {correo.get('cuerpo_corto', '')[:150] if correo.get('cuerpo_corto') else '<i style="color:#6B7280;">Contenido no cargado — haz clic en "Ver contenido" para cargar</i>'}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Contenido expandible ──
    with st.expander("📄 Ver contenido del correo", expanded=False):
        if not correo.get('contenido_cargado', False):
            st.info("📥 Contenido no descargado (solo headers).")
            if st.button("⬇️ Cargar contenido", key=f"btn_ucargar_{idx}", type="primary", use_container_width=True):
                with st.spinner("Descargando..."):
                    resultado = audit.descargar_correo_por_id(message_id)
                    if resultado:
                        correo.update(resultado)
                        correo['contenido_cargado'] = True
                        # Actualizar en session state
                        pendientes = st.session_state.get('_correos_pendientes', [])
                        for p in pendientes:
                            if p['message_id'] == message_id:
                                p.update(resultado)
                                p['contenido_cargado'] = True
                                break
                        st.session_state['_correos_pendientes'] = pendientes
                    else:
                        st.error("❌ No se pudo descargar el contenido.")
                st.rerun()
        else:
            # Mostrar contenido (HTML o texto)
            tiene_html = correo.get('tiene_html', False)
            html_raw = correo.get('html_raw', '')

            if tiene_html and html_raw:
                tab_html, tab_texto = st.tabs(["🌐 Vista original", "📝 Texto plano"])
                with tab_html:
                    import streamlit.components.v1 as components
                    html_seguro = re.sub(r'<script[^>]*>.*?</script>', '', html_raw, flags=re.DOTALL | re.IGNORECASE)
                    html_seguro = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html_seguro, flags=re.DOTALL | re.IGNORECASE)
                    components.html(
                        f'<div style="background:#fff;color:#1f2937;padding:16px;border-radius:8px;font-family:Arial,sans-serif;font-size:14px;line-height:1.6;overflow:auto;">{html_seguro}</div>',
                        height=500, scrolling=True
                    )
                with tab_texto:
                    if correo.get('cuerpo'):
                        st.text_area("Contenido", value=correo['cuerpo'][:3000], height=200, disabled=True, key=f"ucbody_{idx}", label_visibility="collapsed")
                    else:
                        st.info("Sin versión en texto plano.")
            else:
                if correo.get('cuerpo'):
                    st.text_area("Contenido", value=correo['cuerpo'][:3000], height=200, disabled=True, key=f"ucbody_{idx}", label_visibility="collapsed")
                else:
                    st.warning("⚠️ Contenido no disponible.")

            # Selector de imágenes inline
            imagenes = correo.get('imagenes_inline', {})
            if imagenes:
                monitor._render_selector_imagenes(idx, correo)

            # Adjuntos con descarga
            adjuntos = correo.get('adjuntos', [])
            if adjuntos:
                st.markdown(f"**📎 Adjuntos ({len(adjuntos)}):**")
                for a_idx, att in enumerate(adjuntos):
                    col_info, col_btn = st.columns([3, 1])
                    with col_info:
                        st.caption(f"📄 {att['nombre']} — {att['tamano'] / 1024:.1f} KB ({att['tipo']})")
                    with col_btn:
                        if att.get('datos_b64'):
                            import base64 as _b64
                            st.download_button("⬇️ Descargar", data=_b64.b64decode(att['datos_b64']), file_name=att['nombre'], mime=att['tipo'], key=f"udl_{idx}_{a_idx}", use_container_width=True)

    # ── Acciones ──
    col_crear, col_vincular, col_descartar, col_espacio = st.columns([2, 2, 2, 2])

    with col_crear:
        crear_clicked = st.button("✅ Crear Orden", key=f"ubtn_crear_{idx}", type="primary", use_container_width=True)
    with col_vincular:
        vincular_clicked = st.button("🔗 Vincular a OT", key=f"ubtn_vincular_{idx}", use_container_width=True)
    with col_descartar:
        descartar_clicked = st.button("🗑️ Descartar", key=f"ubtn_descartar_{idx}", use_container_width=True)

    if descartar_clicked:
        print(f"🗑️ DESCARTANDO: message_id=[{message_id}]")
        
        # 1. Guardado directo y seguro en base de datos
        from utils.db import supabase
        guardado_exitoso = False
        
        if supabase:
            try:
                # Omitimos 'orden_id' por completo para evitar que Supabase 
                # rechace la petición al recibir un valor nulo en una columna Integer.
                datos_procesado = {
                    "message_id": message_id.strip(),
                    "accion": "descartado",
                    "fecha_procesado": datetime.now().isoformat()
                }
                supabase.table("emails_procesados").upsert(datos_procesado).execute()
                guardado_exitoso = True
            except Exception as e:
                # Si falla, EL RERUN SE DETIENE y el error queda visible en pantalla
                st.error(f"❌ Error crítico guardando en BD: {e}")
        else:
            st.error("❌ No hay conexión a la base de datos.")

        # 2. Solo si se guardó en BD, limpiamos la memoria temporal y reiniciamos
        if guardado_exitoso:
            _eliminar_de_pendientes(message_id)
            try:
                monitor._eliminar_pendiente(message_id)
                audit._cache_actualizar_estado(message_id, en_procesados=True)
            except Exception:
                pass
            
            procesados_local = st.session_state.get('_recentemente_procesados', set())
            procesados_local.add(message_id.strip())
            st.session_state['_recentemente_procesados'] = procesados_local
            
            st.toast(f"🗑️ Descartado: {correo['asunto'][:40]}")
            time.sleep(0.5)  # Breve pausa para asentar la base de datos
            st.rerun()

    if vincular_clicked:
        st.session_state[f'_uvincular_ot_{idx}'] = True
        st.session_state.pop(f'_ucrear_ot_{idx}', None)

    if st.session_state.get(f'_uvincular_ot_{idx}', False):
        monitor.render_selector_ordenes_para_vincular(idx, correo, df_ordenes, df_act)
        # Verificar si ya fue vinculado (procesado)
        if message_id in monitor._obtener_procesados():
            _eliminar_de_pendientes(message_id)
            monitor._eliminar_pendiente(message_id)
            audit._cache_actualizar_estado(message_id, en_procesados=True)
            procesados_local = st.session_state.get('_recentemente_procesados', set())
            procesados_local.add(message_id.strip())
            st.session_state['_recentemente_procesados'] = procesados_local

    if crear_clicked:
        st.session_state[f'_ucrear_ot_{idx}'] = True

    if st.session_state.get(f'_ucrear_ot_{idx}', False):
        with st.form(key=f"uform_correo_{idx}"):
            st.markdown("**📋 Datos para la Orden de Trabajo**")
            act_opciones = ["(Seleccionar activo)"]
            if not df_act.empty:
                act_opciones += sorted(df_act['nombre'].tolist())
            act_opciones.append("➕ Crear nuevo activo después")
            activo_sel = st.selectbox("Activo", act_opciones, key=f"ucorreo_activo_{idx}")
            c1, c2 = st.columns(2)
            tipo = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"], key=f"ucorreo_tipo_{idx}")
            criticidad = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], value="Media", key=f"ucorreo_crit_{idx}")
            tech_opts = {u['nombre']: u['id'] for _, u in df_users.iterrows()} if not df_users.empty else {}
            tecnico = st.selectbox("Asignar a", list(tech_opts.keys()), key=f"ucorreo_tecnico_{idx}") if tech_opts else None
            desc_default = f"[Correo de {correo.get('remitente', '')}]\n\nAsunto: {correo['asunto']}\n\n{correo.get('cuerpo_corto', '')}"
            descripcion = st.text_area("Descripción", value=desc_default, height=100, key=f"ucorreo_desc_{idx}")
            submitted = st.form_submit_button("✅ CREAR ORDEN", type="primary", use_container_width=True)

            if submitted:
                if activo_sel == "(Seleccionar activo)":
                    st.error("Selecciona un activo.")
                elif not descripcion.strip():
                    st.error("La descripción es obligatoria.")
                elif not tecnico:
                    st.error("Asigna un técnico.")
                else:
                    try:
                        from utils.db import db_insert
                        act_id = int(df_act[df_act['nombre'] == activo_sel].iloc[0]['id']) if activo_sel != "➕ Crear nuevo activo después" else None
                        if act_id:
                            res = db_insert("ordenes", {
                                "activo_id": act_id, "descripcion": descripcion.strip(),
                                "criticidad": criticidad, "tipo_mantenimiento": tipo,
                                "estado": "Abierta", "tecnico_asignado": str(tech_opts[tecnico]),
                                "fecha_creacion": datetime.now().isoformat(),
                                "origen": "correo", "correo_message_id": message_id,
                            })
                            if res.data:
                                nuevo_id = res.data[0]['id']
                                db_insert("bitacora", {
                                    "orden_id": nuevo_id, "usuario_text": "CORREO (automático)",
                                    "mensaje": f"📧 Creada desde correo de {correo.get('remitente', '')}\nAsunto: {correo['asunto']}",
                                    "fecha": datetime.now().isoformat()
                                })
                                # Subir adjuntos
                                adjuntos_correo = correo.get('adjuntos', [])
                                if adjuntos_correo:
                                    with st.spinner(f"Subiendo {len(adjuntos_correo)} adjunto(s)..."):
                                        monitor._subir_adjuntos_correo(adjuntos_correo, nuevo_id)

                                # Subir imágenes inline seleccionadas
                                imagenes_inline = correo.get('imagenes_inline', {})
                                if imagenes_inline:
                                    imagenes_sel = monitor._obtener_seleccion_imagenes(idx, message_id, imagenes_inline)
                                    n_sel = sum(1 for v in imagenes_sel.values() if v)
                                    if n_sel > 0:
                                        monitor._subir_imagenes_inline_seleccionadas(
                                            imagenes_inline, imagenes_sel, nuevo_id,
                                            correo.get('remitente_nombre') or correo.get('remitente', 'correo')
                                        )

                                monitor._marcar_procesado(message_id, orden_id=nuevo_id, accion="orden")
                                _eliminar_de_pendientes(message_id)
                                monitor._eliminar_pendiente(message_id)
                                audit._cache_actualizar_estado(message_id, en_procesados=True)
                                procesados_local = st.session_state.get('_recentemente_procesados', set())
                                procesados_local.add(message_id.strip())
                                st.session_state['_recentemente_procesados'] = procesados_local
                                st.session_state.pop(f'_ucrear_ot_{idx}', None)
                                st.success(f"✅ Orden #{nuevo_id} creada desde correo.")
                                st.rerun()
                        else:
                            st.warning("⚠️ Crea el activo primero en el módulo de Inventario.")
                    except Exception as e:
                        st.error(f"Error creando orden: {e}")

    st.markdown("---")


# =============================================================================
# 🧹 UTILIDADES
# =============================================================================
def _eliminar_de_pendientes(message_id):
    """Elimina un correo de la lista en session state."""
    pendientes = st.session_state.get('_correos_pendientes', [])
    st.session_state['_correos_pendientes'] = [
        c for c in pendientes if c['message_id'] != message_id
    ]


def _contar_pendientes(correos):
    """Cuenta correos realmente pendientes (no procesados)."""
    monitor = _mod_monitor()
    procesados = monitor._obtener_procesados()
    return [c for c in correos if c['message_id'] not in procesados]


# =============================================================================
# 📧 RENDERIZADO PRINCIPAL: CORREO UNIFICADO
# =============================================================================
def render_buzon_correo():
    """
    Buzón de correo unificado.
    Combina: pendientes + caché de escaneo + frescos de Gmail.
    """
    st.markdown("### 📧 Correo")
    st.caption("Todos los correos pendientes de gestionar en un solo lugar.")

    cfg = st.secrets.get("gmail", {})
    if not cfg.get("correo"):
        st.info("ℹ️ Para activar el monitoreo de correo, agrega la configuración en `secrets.toml`:")
        st.code("""
[gmail]
correo = "orion.mantenimientoapp@gmail.com"
password = "xxxx xxxx xxxx xxxx"
""", language="toml")
        st.caption("Necesitas una **contraseña de aplicación** de Gmail (no tu contraseña normal)")
        return

    # ── Botón de sync unificado ──
    col_sync, col_info = st.columns([1, 2])
    with col_sync:
        if st.button("🔄 Sincronizar Gmail", type="primary", use_container_width=True):
            correos, procesados, scan_result = _sync_gmail_completo()
            st.session_state['_correos_pendientes'] = correos
            st.session_state['_sync_result'] = scan_result
            # Mostrar errores inmediatamente
            for err in scan_result.get('errores', []):
                st.error(f"❌ {err}")
            st.rerun()

    with col_info:
        sync_result = st.session_state.get('_sync_result')
        if sync_result:
            nuevos = sync_result.get('nuevos', 0)
            total = sync_result.get('total_gmail', 0)
            if nuevos > 0:
                st.caption(f"📡 Último sync: {nuevos} nuevos de {total} escaneados")
            else:
                st.caption(f"📡 Último sync: {total} revisados, sin nuevos")

    # ── Cargar correos si no están en session state ──
    correos = st.session_state.get('_correos_pendientes', None)
    if correos is None:
        try:
            with st.spinner("Cargando correos..."):
                correos, procesados = _cargar_correos_unificado(sin_frescos=True)
                st.session_state['_correos_pendientes'] = correos
        except Exception as e:
            st.error(f"❌ Error cargando correos: {e}")
            correos = []

    # ── Filtrar solo los realmente pendientes ──
    monitor = _mod_monitor()
    procesados_ids = monitor._obtener_procesados()
    procesados_locales = st.session_state.get('_recentemente_procesados', set())
    procesados_ids = procesados_ids | procesados_locales
    correos_pendientes = [c for c in correos if c['message_id'] not in procesados_ids]

    if not correos_pendientes:
        st.info("📭 Sin correos pendientes. Haz clic en **Sincronizar Gmail** para buscar nuevos mensajes.")
        return

    # ── Filtros ──
    st.markdown("##### 🔎 Filtros")
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        filtro_remitente = st.text_input("Remitente", key="uc_filtro_rem", placeholder="ej: proveedor@empresa.com")
    with col_f2:
        filtro_asunto = st.text_input("Asunto", key="uc_filtro_asunto", placeholder="ej: falla, mantenimiento")
    with col_f3:
        st.markdown("<br>", unsafe_allow_html=True)
        invertir = st.checkbox("Invertir", key="uc_invertir")

    # Aplicar filtros
    filtrados = correos_pendientes[:]
    if filtro_remitente:
        if invertir:
            filtrados = [c for c in filtrados if filtro_remitente.lower() not in (c.get('remitente', '') or '').lower()]
        else:
            filtrados = [c for c in filtrados if filtro_remitente.lower() in (c.get('remitente', '') or '').lower()]
    if filtro_asunto:
        if invertir:
            filtrados = [c for c in filtrados if filtro_asunto.lower() not in (c.get('asunto', '') or '').lower()]
        else:
            filtrados = [c for c in filtrados if filtro_asunto.lower() in (c.get('asunto', '') or '').lower()]

    # Ordenar por fecha (más reciente primero)
    filtrados.sort(key=lambda c: _normalizar_fecha(c.get('fecha', '')), reverse=True)

    # ── Métricas ──
    m1, m2, m3 = st.columns(3)
    m1.metric("📬 Pendientes", len(correos_pendientes))
    m2.metric("📋 Mostrando", len(filtrados))
    m3.metric("✅ Procesados (histórico)", len(procesados_ids))

    st.markdown("---")

    # ── Paginación ──
    ITEMS_POR_PAGINA = 10
    total_paginas = max(1, (len(filtrados) + ITEMS_POR_PAGINA - 1) // ITEMS_POR_PAGINA)
    pagina = st.session_state.get('_uc_pagina', 1)

    if total_paginas > 1:
        col_pag1, col_pag2, col_pag3 = st.columns([1, 2, 1])
        with col_pag1:
            if st.button("⬅️ Anterior", disabled=(pagina <= 1), key="uc_pag_ant"):
                st.session_state['_uc_pagina'] = pagina - 1
                st.rerun()
        with col_pag2:
            st.caption(f"Página {pagina} de {total_paginas}")
        with col_pag3:
            if st.button("Siguiente ➡️", disabled=(pagina >= total_paginas), key="uc_pag_sig"):
                st.session_state['_uc_pagina'] = pagina + 1
                st.rerun()

    inicio = (pagina - 1) * ITEMS_POR_PAGINA
    fin = min(inicio + ITEMS_POR_PAGINA, len(filtrados))

    # ── Cargar datos para acciones ──
    from utils.db import run_query
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")

    # ── Renderizar correos ──
    for i in range(inicio, fin):
        _render_card_correo(filtrados[i], i, df_act, df_users, df_ordenes)

    # ── Paginación inferior ──
    if total_paginas > 1:
        st.markdown("---")
        col_pag4, col_pag5, col_pag6 = st.columns([1, 2, 1])
        with col_pag4:
            if st.button("⬅️ Anterior", disabled=(pagina <= 1), key="uc_pag_ant_bot"):
                st.session_state['_uc_pagina'] = pagina - 1
                st.rerun()
        with col_pag5:
            st.caption(f"Página {pagina} de {total_paginas}")
        with col_pag6:
            if st.button("Siguiente ➡️", disabled=(pagina >= total_paginas), key="uc_pag_sig_bot"):
                st.session_state['_uc_pagina'] = pagina + 1
                st.rerun()

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN: AUDITORÍA Y HERRAMIENTAS (expandible)
    # ══════════════════════════════════════════════════════════════
    _render_seccion_auditoria()


# =============================================================================
# 🔍 SECCIÓN DE AUDITORÍA (incrustada en la vista de correo)
# =============================================================================
def _render_seccion_auditoria():
    """Sección de auditoría y herramientas de supervisión, integrada al final de Correo."""
    audit = _mod_audit()
    from utils.db import supabase

    # ── Escaneo avanzado ──
    with st.expander("📡 Escaneo avanzado de Gmail", expanded=False):
        st.caption("Escanea headers de Gmail y actualiza la caché. Úsalo cuando necesites buscar correos más antiguos.")

        col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 1, 1])
        with col_cfg1:
            max_corr = st.number_input("Máx. correos", min_value=20, max_value=1000, value=200, step=50, key="aud_max_corr")
        with col_cfg2:
            dias = st.number_input("Días hacia atrás", min_value=7, max_value=365, value=90, step=7, key="aud_dias")
        with col_cfg3:
            st.markdown("<br>", unsafe_allow_html=True)
            forzar = st.checkbox("Forzar re-escaneo completo", key="aud_forzar")

        col_scan, col_cache = st.columns([1, 2])
        with col_scan:
            if st.button("📡 Escanear Gmail", type="primary", use_container_width=True, key="aud_btn_scan"):
                with st.spinner(f"Escaneando ({max_corr} correos, {dias} días)..."):
                    resultado = audit.escanear_gmail_rapido(max_correos=max_corr, dias_atras=dias, forzar_completo=forzar)
                st.session_state['_auditoria_scan_result'] = resultado
                # Actualizar la lista de correos pendientes
                correos, procesados = _cargar_correos_unificado()
                st.session_state['_correos_pendientes'] = correos
                st.rerun()

        with col_cache:
            cache_total = 0
            if supabase:
                try:
                    res_cache = supabase.table("email_scan_cache").select("message_id", count="exact").execute()
                    cache_total = res_cache.count or 0
                except Exception:
                    pass
            if cache_total > 0:
                st.caption(f"💾 Caché: {cache_total} headers almacenados")
            else:
                st.caption("💡 Sin caché aún. Ejecuta un escaneo para empezar.")

        scan_result = st.session_state.get('_auditoria_scan_result')
        if scan_result:
            for err in scan_result.get('errores', []):
                st.error(f"❌ {err}")
            sr1, sr2, sr3, sr4 = st.columns(4)
            sr1.metric("📧 En Gmail", scan_result.get('total_gmail', 0))
            sr2.metric("🆕 Nuevos", scan_result.get('nuevos', 0))
            sr3.metric("💾 Ya en caché", scan_result.get('ya_en_cache', 0))
            sr4.metric("💾 Caché total", scan_result.get('cache_total', 0))

    # ── Resumen de BD ──
    with st.expander("📊 Resumen de Base de Datos", expanded=False):
        if supabase:
            try:
                res_proc = supabase.table("emails_procesados").select("*").execute()
                procesados = res_proc.data or []
            except Exception:
                procesados = []

            total_proc = len(procesados)
            acciones = {}
            con_orden = 0
            for p in procesados:
                acc = p.get('accion', 'desconocido')
                acciones[acc] = acciones.get(acc, 0) + 1
                if p.get('orden_id'):
                    con_orden += 1

            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("📨 Total Procesados", total_proc)
            mc2.metric("🔗 Con OT Asignada", con_orden)
            mc3.metric("🗑️ Descartados", acciones.get('descartado', 0))

            if acciones:
                st.caption("Por acción: " + " · ".join(f"{k}: {v}" for k, v in acciones.items()))

            try:
                res_ord = supabase.table("ordenes").select("*").eq("origen", "correo").order("id", desc=True).limit(20).execute()
                ordenes_correo = res_ord.data or []
            except Exception:
                try:
                    res_ord = supabase.table("ordenes").select("*").not_.is_("correo_message_id", "null").order("id", desc=True).limit(20).execute()
                    ordenes_correo = res_ord.data or []
                except Exception:
                    ordenes_correo = []

            if ordenes_correo:
                st.markdown(f"#### 🛠️ Órdenes desde Correo ({len(ordenes_correo)})")
                for orden in ordenes_correo:
                    estado = orden.get('estado', '?')
                    icono = {'Abierta': '🔨', 'Por Validar': '🧐', 'Concluida': '✅', 'Cancelada': '❌'}.get(estado, '📋')
                    fecha = (orden.get('fecha_creacion', '') or '')[:10]
                    desc = (orden.get('descripcion', '') or '')[:80]
                    st.markdown(
                        f'<div style="border-left:3px solid #F59E0B;padding:8px 14px;margin-bottom:6px;background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0;">'
                        f'<span>{icono} <b>OT #{orden["id"]}</b> — {estado}</span> '
                        f'<span style="color:#6B7280;font-size:0.8em;">{fecha}</span><br>'
                        f'<span style="color:#D1D5DB;font-size:0.85em;">{desc}</span></div>',
                        unsafe_allow_html=True
                    )
        else:
            st.warning("Sin conexión a base de datos.")

    # ── Historial ──
    if supabase:
        try:
            res_hist = supabase.table("emails_procesados").select("*").order("fecha_procesado", desc=True).limit(50).execute()
            historial = res_hist.data or []
        except Exception:
            historial = []

        if historial:
            with st.expander(f"📋 Historial de procesados ({len(historial)} recientes)", expanded=False):
                iconos_accion = {
                    'orden': '✅', 'avance': '🔗', 'descartado': '🗑️',
                    'rechazado': '❌', 'desconocido': '❓',
                }
                for p in historial:
                    accion = p.get('accion', '?')
                    icono = iconos_accion.get(accion, '📋')
                    orden_id = p.get('orden_id')
                    msg_id = (p.get('message_id', '?') or '')[:50]
                    fecha = (p.get('fecha_procesado', '') or '')[:16].replace('T', ' ')
                    orden_txt = f"→ OT #{orden_id}" if orden_id else ""

                    color = {
                        'orden': '#10B981', 'avance': '#3B82F6',
                        'descartado': '#6B7280', 'rechazado': '#EF4444',
                    }.get(accion, '#F59E0B')

                    st.markdown(
                        f'<div style="border-left:2px solid {color};padding:4px 10px;margin-bottom:3px;font-size:0.85em;">'
                        f'{icono} <b>{accion.upper()}</b> {orden_txt} | {msg_id} | {fecha}</div>',
                        unsafe_allow_html=True
                    )


# =============================================================================
# 🔍 render_auditoria_correos — REDIRECT (backward compat)
# =============================================================================
def render_auditoria_correos():
    """Redirige a render_buzon_correo (funcionalidad unificada)."""
    render_buzon_correo()
