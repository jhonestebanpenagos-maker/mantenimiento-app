# ==============================================================================
# utils/email_monitor.py — Monitoreo de correo vía Gmail IMAP
# Descarga correos reenviados desde Postobón y los presenta en el buzón de ORIÓN
# ==============================================================================
import streamlit as st
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
from datetime import datetime, timedelta


# ==============================================================================
# 📦 PERSISTENCIA DE CORREOS PROCESADOS (Supabase)
# ==============================================================================
def _obtener_procesados():
    """Obtiene los message_id de correos ya procesados desde Supabase."""
    from utils.db import supabase
    if not supabase:
        return set()
    try:
        res = supabase.table("emails_procesados").select("message_id").execute()
        ids = {row["message_id"] for row in (res.data or [])}
        print(f"📋 Correos procesados en BD: {len(ids)}")
        return ids
    except Exception as e:
        print(f"⚠️ Error obteniendo procesados: {e}")
        st.warning(f"⚠️ No se pudo consultar correos procesados: {e}")
        return set()


def _marcar_procesado(message_id: str, orden_id: int = None, accion: str = "orden"):
    """Marca un correo como procesado en Supabase (persistente)."""
    from utils.db import supabase
    if not supabase:
        return
    try:
        supabase.table("emails_procesados").upsert({
            "message_id": message_id,
            "orden_id": orden_id,
            "accion": accion,
            "fecha_procesado": datetime.now().isoformat(),
        }).execute()
        print(f"✅ Correo marcado como procesado: {message_id[:50]}... ({accion})")
    except Exception as e:
        print(f"⚠️ Error marcando correo procesado: {e}")
        st.error(f"❌ No se pudo guardar el correo como procesado: {e}")


# ==============================================================================
# 🔧 CONFIGURACIÓN
# ==============================================================================
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993


def _obtener_credenciales():
    """Obtiene credenciales de Gmail desde st.secrets."""
    cfg = st.secrets.get("gmail", {})
    correo = cfg.get("correo", "")
    password = cfg.get("password", "")
    return correo, password


def _conectar_imap():
    """
    Conecta a Gmail vía IMAP con SSL.
    Retorna el objeto IMAP4_SSL o None si falla.
    """
    correo, password = _obtener_credenciales()

    if not correo or not password:
        st.warning("⚠️ Credenciales de Gmail no configuradas en secrets.toml [gmail]")
        return None

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(correo, password)
        return mail
    except imaplib.IMAP4.error as e:
        st.error(f"❌ Error de autenticación IMAP: {str(e)[:300]}")
        st.info("💡 Verifica que la contraseña de aplicación sea correcta y que IMAP esté habilitado en Gmail.")
        return None
    except Exception as e:
        st.error(f"❌ Error conectando a Gmail: `{type(e).__name__}`: {str(e)[:300]}")
        return None


def _decodificar_header(header_val):
    """Decodifica un header de correo (asunto, remitente, etc.)."""
    if not header_val:
        return ""
    partes = decode_header(header_val)
    resultado = []
    for parte, charset in partes:
        if isinstance(parte, bytes):
            resultado.append(parte.decode(charset or 'utf-8', errors='replace'))
        else:
            resultado.append(str(parte))
    return ' '.join(resultado)


def _extraer_texto_plano(msg):
    """Extrae el cuerpo en texto plano de un mensaje MIME."""
    if msg.is_multipart():
        for parte in msg.walk():
            ctype = parte.get_content_type()
            disposition = str(parte.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disposition:
                payload = parte.get_payload(decode=True)
                if payload:
                    charset = parte.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace')
        # Si no hay text/plain, intentar con text/html y limpiar
        for parte in msg.walk():
            ctype = parte.get_content_type()
            disposition = str(parte.get("Content-Disposition", ""))
            if ctype == "text/html" and "attachment" not in disposition:
                payload = parte.get_payload(decode=True)
                if payload:
                    charset = parte.get_content_charset() or 'utf-8'
                    html = payload.decode(charset, errors='replace')
                    return _html_a_texto(html)
    else:
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or 'utf-8'
            texto = payload.decode(charset, errors='replace')
            if msg.get_content_type() == "text/html":
                return _html_a_texto(texto)
            return texto
    return ""


def _extraer_html_raw(msg):
    """Extrae el HTML original del correo (si existe) para renderizarlo en iframe."""
    if msg.is_multipart():
        for parte in msg.walk():
            ctype = parte.get_content_type()
            disposition = str(parte.get("Content-Disposition", ""))
            if ctype == "text/html" and "attachment" not in disposition:
                payload = parte.get_payload(decode=True)
                if payload:
                    charset = parte.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace')
    else:
        if msg.get_content_type() == "text/html":
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or 'utf-8'
                return payload.decode(charset, errors='replace')
    return ""


def _html_a_texto(html):
    """Convierte HTML básico a texto plano."""
    texto = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    texto = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'</?p[^>]*>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = texto.replace('&nbsp;', ' ').replace('&amp;', '&')
    texto = texto.replace('&lt;', '<').replace('&gt;', '>')
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n\s*\n+', '\n\n', texto)
    return texto.strip()


def _extraer_adjuntos(msg):
    """Extrae adjuntos del correo incluyendo datos reales para descarga."""
    import base64
    adjuntos = []
    if msg.is_multipart():
        for parte in msg.walk():
            disposition = str(parte.get("Content-Disposition", ""))
            if "attachment" in disposition:
                nombre = parte.get_filename()
                if nombre:
                    nombre = _decodificar_header(nombre)
                    datos = parte.get_payload(decode=True)
                    adjuntos.append({
                        'nombre': nombre,
                        'tipo': parte.get_content_type() or 'desconocido',
                        'tamano': len(datos) if datos else 0,
                        'datos_b64': base64.b64encode(datos).decode('ascii') if datos else None,
                    })
    return adjuntos


def _extraer_imagenes_inline(msg):
    """Extrae imágenes embebidas (inline) del correo por Content-ID."""
    import base64
    imagenes = {}
    if msg.is_multipart():
        for parte in msg.walk():
            cid = parte.get("Content-ID")
            ctype = parte.get_content_type() or ""
            if cid and ctype.startswith("image/"):
                cid_limpio = cid.strip("<>")
                datos = parte.get_payload(decode=True)
                if datos:
                    imagenes[cid_limpio] = {
                        'tipo': ctype,
                        'datos_b64': base64.b64encode(datos).decode('ascii'),
                    }
    return imagenes


def _parsear_fecha(date_str):
    """Parsea fecha del correo a ISO format."""
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return str(date_str)[:25]


# ==============================================================================
# 📬 DESCARGA DE CORREOS
# ==============================================================================
def descargar_correos_nuevos(max_correos=20, dias_atras=3):
    """
    Descarga correos nuevos de Gmail vía IMAP.
    Retorna lista de dicts con la info de cada correo.
    """
    mail = _conectar_imap()
    if not mail:
        return []

    try:
        # Seleccionar Bandeja de Entrada
        mail.select("INBOX")

        # Calcular fecha desde hace N días
        desde = datetime.now() - timedelta(days=dias_atras)
        fecha_desde = desde.strftime("%d-%b-%Y")  # Formato IMAP: 01-Jan-2026

        # Buscar correos desde esa fecha
        status, mensajes = mail.search(None, f'(SINCE "{fecha_desde}")')
        if status != "OK":
            st.error("❌ Error buscando correos en la bandeja")
            return []

        ids = mensajes[0].split()
        if not ids:
            return []

        # Tomar los últimos N (más recientes primero)
        ids = ids[-max_correos:]
        ids.reverse()  # Más recientes primero

        resultados = []
        for msg_id in ids:
            status, datos = mail.fetch(msg_id, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(datos[0][1])

            # Extraer datos
            asunto = _decodificar_header(msg.get("Subject", ""))
            remitente_raw = _decodificar_header(msg.get("From", ""))
            fecha_raw = msg.get("Date", "")
            message_id = msg.get("Message-ID", str(msg_id.decode()))

            # Parsear remitente: "Nombre <correo>" → nombre + correo
            remitente = remitente_raw
            remitente_nombre = ""
            match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', remitente_raw)
            if match:
                remitente_nombre = match.group(1).strip()
                remitente = match.group(2).strip()
            elif "@" in remitente_raw:
                remitente = remitente_raw.strip()

            cuerpo = _extraer_texto_plano(msg)
            html_raw = _extraer_html_raw(msg)
            adjuntos = _extraer_adjuntos(msg)
            imagenes_inline = _extraer_imagenes_inline(msg)

            # Determinar si está leído
            status_flags, datos_flags = mail.fetch(msg_id, "(FLAGS)")
            leido = b'\\Seen' in (datos_flags[0] if datos_flags[0] else b'')

            resultados.append({
                'message_id': message_id,
                'remitente': remitente,
                'remitente_nombre': remitente_nombre,
                'asunto': asunto or '(Sin asunto)',
                'fecha': _parsear_fecha(fecha_raw),
                'cuerpo': cuerpo[:5000],
                'cuerpo_corto': cuerpo[:200],
                'html_raw': html_raw,
                'adjuntos': adjuntos,
                'imagenes_inline': imagenes_inline,
                'tiene_adjuntos': len(adjuntos) > 0,
                'tiene_html': bool(html_raw),
                'tiene_imagenes': len(imagenes_inline) > 0,
                'leido': leido,
            })

        return resultados

    except Exception as e:
        error_detalle = str(e)
        st.error(f"❌ Error descargando correos: `{type(e).__name__}`")
        st.code(error_detalle[:500], language="text")
        return []
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# ==============================================================================
# 🩺 DIAGNÓSTICO
# ==============================================================================
def _diagnosticar_gmail():
    """Diagnóstico paso a paso de la conexión Gmail IMAP."""
    st.markdown("#### 🩺 Diagnóstico de Conexión Gmail")

    correo, password = _obtener_credenciales()

    # Paso 1: Verificar secrets
    st.markdown("**1️⃣ Verificando configuración...**")
    if not correo:
        st.error("❌ `correo` no configurado en [gmail] de secrets.toml")
        return
    if not password:
        st.error("❌ `password` no configurado en [gmail] de secrets.toml")
        return
    # No mostrar la contraseña
    st.success(f"✅ Correo: `{correo}` | Password: `{'✅ configurada' if password else '❌ vacía'}`")

    # Paso 2: Conectar IMAP
    st.markdown("**2️⃣ Conectando a Gmail IMAP...**")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        st.success("✅ Conexión SSL establecida con imap.gmail.com")
    except Exception as e:
        st.error(f"❌ No se pudo conectar: `{type(e).__name__}`: {str(e)[:300]}")
        return

    # Paso 3: Login
    st.markdown("**3️⃣ Autenticando...**")
    try:
        mail.login(correo, password)
        st.success("✅ Login exitoso")
    except imaplib.IMAP4.error as e:
        st.error(f"❌ Autenticación falló: {str(e)[:300]}")
        st.info("💡 Posibles causas:\n- Contraseña de aplicación incorrecta\n- IMAP no habilitado en Gmail\n- Verificación en 2 pasos no activa")
        return
    except Exception as e:
        st.error(f"❌ Error: `{type(e).__name__}`: {str(e)[:300]}")
        return

    # Paso 4: Listar carpetas
    st.markdown("**4️⃣ Listando carpetas...**")
    try:
        status, carpetas = mail.list()
        if status == "OK":
            st.success(f"✅ {len(carpetas)} carpetas encontradas")
            for c in carpetas[:10]:
                st.caption(f"  📁 {c.decode() if isinstance(c, bytes) else c}")
    except Exception as e:
        st.warning(f"⚠️ No se pudieron listar carpetas: {e}")

    # Paso 5: Contar correos en INBOX
    st.markdown("**5️⃣ Leyendo bandeja de entrada...**")
    try:
        mail.select("INBOX")
        desde = datetime.now() - timedelta(days=3)
        fecha_desde = desde.strftime("%d-%b-%Y")
        status, mensajes = mail.search(None, f'(SINCE "{fecha_desde}")')
        if status == "OK":
            ids = mensajes[0].split()
            st.success(f"✅ {len(ids)} correos encontrados en los últimos 3 días")

            if ids:
                # Mostrar los últimos 5
                st.markdown("**📬 Últimos correos:**")
                for msg_id in ids[-5:]:
                    status, datos = mail.fetch(msg_id, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE)])")
                    if status == "OK":
                        header = datos[0][1].decode(errors='replace')
                        lines = header.strip().split('\n')
                        info = ' | '.join(l.strip() for l in lines[:3])
                        st.caption(f"  📧 {info[:120]}")
        else:
            st.warning("⚠️ No se pudo buscar en la bandeja")
    except Exception as e:
        st.error(f"❌ Error leyendo bandeja: `{type(e).__name__}`: {str(e)[:300]}")

    # Cerrar
    try:
        mail.logout()
    except Exception:
        pass

    # Config esperada
    st.markdown("---")
    st.markdown("**📋 Configuración en secrets.toml:**")
    st.code("""
[gmail]
correo = "orion.mantenimientoapp@gmail.com"
password = "xxxx xxxx xxxx xxxx"
""", language="toml")
    st.caption("La password es la de aplicación de 16 caracteres (no tu contraseña de Gmail)")


# ==============================================================================
# 🎨 RENDERIZADO DEL BUZÓN
# ==============================================================================
def render_buzon_correo():
    """
    Renderiza el buzón de correo en la UI de Streamlit.
    Muestra correos pendientes y permite aprobar/rechazar para crear OT.
    """
    st.markdown("### 📧 Buzón de Correo")
    st.caption("Revisa los correos reenviados desde Postobón y decide cuáles se convierten en Órdenes de Trabajo.")

    # ── Configuración en secrets ──
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

    # ── Botones ──
    col_btn, col_diag, col_info = st.columns([1, 1, 2])
    with col_btn:
        if st.button("🔄 Revisar Correo", type="primary", use_container_width=True):
            with st.spinner("Conectando a Gmail y descargando correos..."):
                correos = descargar_correos_nuevos(max_correos=20, dias_atras=3)
                st.session_state['_correos_pendientes'] = correos
                st.rerun()

    with col_diag:
        if st.button("🩺 Diagnosticar", use_container_width=True):
            with st.spinner("Probando conexión..."):
                _diagnosticar_gmail()

    with col_info:
        st.caption("Descarga los correos de los últimos 3 días. Solo se muestran los no procesados.")

    # ── Correos pendientes ──
    correos = st.session_state.get('_correos_pendientes', [])

    if not correos:
        st.info("📭 No hay correos descargados. Haz clic en **Revisar Correo** para buscar nuevos mensajes.")
        return

    # Filtrar ya procesados (persistidos en Supabase, no en session state)
    procesados = _obtener_procesados()
    correos_pendientes = [c for c in correos if c['message_id'] not in procesados]

    # Debug visible
    if procesados:
        st.caption(f"🗄️ {len(procesados)} correo(s) registrado(s) como procesados en la base de datos — {len(correos_pendientes)} pendiente(s) de {len(correos)} descargados")

    if not correos_pendientes:
        st.success("✅ Todos los correos han sido procesados.")
        return

    st.markdown(f"#### 📬 {len(correos_pendientes)} correo(s) pendiente(s)")

    # Pre-cargar datos una sola vez
    from utils.db import run_query, db_insert
    df_act = run_query("activos")
    df_users = run_query("usuarios")

    for idx, correo in enumerate(correos_pendientes):
        msg_id = correo['message_id']

        # ── Tarjeta compacta del correo ──
        icono = '📩' if not correo['leido'] else '📧'
        remitente = correo['remitente_nombre'] or correo['remitente']
        fecha_corta = correo['fecha'][:10] if correo['fecha'] else ''
        adjuntos_txt = ', '.join(a['nombre'] for a in correo['adjuntos']) if correo['adjuntos'] else ''
        n_adjuntos = len(correos_pendientes[idx].get('adjuntos', []))

        st.markdown(f"""
        <div style="border:1px solid #374151;border-radius:10px;padding:14px 16px;margin-bottom:10px;background:#1F2937;">
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div>
                    <span style="font-size:1.1rem;">{icono}</span>
                    <span style="color:#F59E0B;font-weight:600;">{correo['asunto'][:70]}</span>
                </div>
                <span style="color:#6B7280;font-size:0.8em;">{fecha_corta}</span>
            </div>
            <div style="color:#9CA3AF;font-size:0.85em;margin-top:4px;">
                👤 {remitente} {f'&nbsp;|&nbsp; 📎 {n_adjuntos} adjunto(s)' if n_adjuntos > 0 else ''}
            </div>
            <div style="color:#D1D5DB;font-size:0.85em;margin-top:6px;background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:6px;">
                {correo['cuerpo_corto'][:150]}{'...' if len(correos_pendientes[idx].get('cuerpo_corto', '')) > 150 else ''}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Ver contenido completo + adjuntos ──
        with st.expander("📄 Ver contenido del correo", expanded=False):
            # Tabs: Vista HTML / Texto plano
            tiene_html = correo.get('tiene_html', False)
            if tiene_html:
                tab_html, tab_texto = st.tabs(["🌐 Vista original", "📝 Texto plano"])

                with tab_html:
                    import streamlit.components.v1 as components
                    html_seguro = correo.get('html_raw', '')
                    # Sanitizar: quitar scripts
                    html_seguro = re.sub(r'<script[^>]*>.*?</script>', '', html_seguro, flags=re.DOTALL | re.IGNORECASE)
                    html_seguro = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html_seguro, flags=re.DOTALL | re.IGNORECASE)
                    components.html(html_seguro, height=500, scrolling=True)

                with tab_texto:
                    if correo.get('cuerpo'):
                        st.text_area(
                            "Contenido", value=correo['cuerpo'][:3000],
                            height=200, disabled=True,
                            key=f"correo_body_{idx}",
                            label_visibility="collapsed"
                        )
            else:
                if correo.get('cuerpo'):
                    st.text_area(
                        "Contenido", value=correo['cuerpo'][:3000],
                        height=200, disabled=True,
                        key=f"correo_body_{idx}",
                        label_visibility="collapsed"
                    )

            # Imágenes embebidas (inline)
            imagenes = correo.get('imagenes_inline', {})
            if imagenes:
                st.markdown("**🖼️ Imágenes en el correo:**")
                import base64
                for cid, img in imagenes.items():
                    try:
                        img_bytes = base64.b64decode(img['datos_b64'])
                        st.image(img_bytes, use_container_width=True)
                    except Exception:
                        st.caption(f"⚠️ No se pudo mostrar imagen inline ({img['tipo']})")

            # Adjuntos con botón de descarga
            adjuntos = correo.get('adjuntos', [])
            if adjuntos:
                st.markdown(f"**📎 Adjuntos ({len(adjuntos)}):**")
                for a_idx, att in enumerate(adjuntos):
                    col_info, col_btn = st.columns([3, 1])
                    with col_info:
                        tamano_kb = att['tamano'] / 1024
                        st.caption(f"📄 {att['nombre']} — {tamano_kb:.1f} KB ({att['tipo']})")
                    with col_btn:
                        if att.get('datos_b64'):
                            import base64 as _b64
                            datos_bytes = _b64.b64decode(att['datos_b64'])
                            st.download_button(
                                "⬇️ Descargar",
                                data=datos_bytes,
                                file_name=att['nombre'],
                                mime=att['tipo'],
                                key=f"dl_{idx}_{a_idx}",
                                use_container_width=True,
                            )
                        else:
                            st.caption("Sin datos")

        # ── Botones de acción directa ──
        col_crear, col_descartar, col_espacio = st.columns([2, 2, 4])

        with col_crear:
            crear_clicked = st.button("✅ Crear Orden", key=f"btn_crear_{idx}", type="primary", use_container_width=True)

        with col_descartar:
            descartar_clicked = st.button("🗑️ Descartar", key=f"btn_descartar_{idx}", use_container_width=True)

        # ── Acción: Descartar (un click) ──
        if descartar_clicked:
            _marcar_procesado(msg_id, accion="descartado")
            # Quitar de la lista local sin perder los demás
            pendientes = st.session_state.get('_correos_pendientes', [])
            st.session_state['_correos_pendientes'] = [c for c in pendientes if c['message_id'] != msg_id]
            st.toast(f"🗑️ Correo descartado: {correo['asunto'][:40]}")
            st.rerun()

        # ── Acción: Crear Orden (muestra formulario debajo) ──
        if crear_clicked:
            st.session_state[f'_crear_ot_{idx}'] = True

        if st.session_state.get(f'_crear_ot_{idx}', False):
            with st.form(key=f"form_correo_{idx}"):
                st.markdown("**📋 Datos para la Orden de Trabajo**")

                act_opciones = ["(Seleccionar activo)"]
                if not df_act.empty:
                    act_opciones += sorted(df_act['nombre'].tolist())
                act_opciones.append("➕ Crear nuevo activo después")

                activo_sel = st.selectbox("Activo", act_opciones, key=f"correo_activo_{idx}")

                c1, c2 = st.columns(2)
                tipo = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"], key=f"correo_tipo_{idx}")
                criticidad = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], value="Media", key=f"correo_crit_{idx}")

                tech_opts = {}
                if not df_users.empty:
                    tech_opts = {u['nombre']: u['id'] for _, u in df_users.iterrows()}
                tecnico = st.selectbox("Asignar a", list(tech_opts.keys()), key=f"correo_tecnico_{idx}") if tech_opts else None

                desc_default = f"[Correo de {correo['remitente']}]\n\nAsunto: {correo['asunto']}\n\n{correo['cuerpo_corto']}"
                descripcion = st.text_area("Descripción", value=desc_default, height=100, key=f"correo_desc_{idx}")

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
                            act_id = int(df_act[df_act['nombre'] == activo_sel].iloc[0]['id']) if activo_sel != "➕ Crear nuevo activo después" else None

                            if act_id:
                                res = db_insert("ordenes", {
                                    "activo_id": act_id,
                                    "descripcion": descripcion.strip(),
                                    "criticidad": criticidad,
                                    "tipo_mantenimiento": tipo,
                                    "estado": "Abierta",
                                    "tecnico_asignado": str(tech_opts[tecnico]),
                                    "fecha_creacion": datetime.now().isoformat(),
                                    "origen": "correo",
                                    "correo_message_id": msg_id,
                                })
                                if res.data:
                                    nuevo_id = res.data[0]['id']
                                    db_insert("bitacora", {
                                        "orden_id": nuevo_id,
                                        "usuario_text": "CORREO (automático)",
                                        "mensaje": f"📧 Creada desde correo de {correo['remitente']}\nAsunto: {correo['asunto']}",
                                        "fecha": datetime.now().isoformat()
                                    })
                                    _marcar_procesado(msg_id, orden_id=nuevo_id, accion="orden")
                                    st.session_state.pop(f'_crear_ot_{idx}', None)
                                    # Quitar de la lista local sin perder los demás
                                    pendientes = st.session_state.get('_correos_pendientes', [])
                                    st.session_state['_correos_pendientes'] = [c for c in pendientes if c['message_id'] != msg_id]
                                    st.success(f"✅ Orden #{nuevo_id} creada desde correo.")
                                    st.rerun()
                            else:
                                st.warning("⚠️ Selecciona 'Crear nuevo activo después' y crea el activo primero en el módulo de Inventario.")
                        except Exception as e:
                            st.error(f"Error creando orden: {e}")

        st.markdown("---")

    # ── Estadísticas ──
    st.markdown("---")
    total_proc = len(procesados)
    total_pend = len(correos_pendientes)
    col1, col2, col3 = st.columns(3)
    col1.metric("📬 Descargados", len(correos))
    col2.metric("⏳ Pendientes", total_pend)
    col3.metric("✅ Procesados (histórico)", total_proc)
