# utils/email_audit.py — Módulo de auditoría rediseñado
# Reemplaza la funcionalidad de render_auditoria_correos() de email_monitor.py
# con escaneo rápido por caché, vista previa inline y acciones directas.
#
# INSTALACIÓN:
# 1. Copiar este archivo a utils/email_audit.py
# 2. Ejecutar sql/001_email_scan_cache.sql en Supabase
# 3. En views/ordenes/__init__.py cambiar:
#      from utils.email_monitor import render_auditoria_correos
#    por:
#      from utils.email_audit import render_auditoria_correos

import streamlit as st
import imaplib
import email
from email.header import decode_header
from email.utils import parsedate_to_datetime
import re
import base64
import io
from datetime import datetime, timedelta


# =============================================================================
# 🔧 CONFIGURACIÓN
# =============================================================================
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
IMAP_TIMEOUT = 30


# =============================================================================
# 🔌 CONEXIÓN Y UTILIDADES (reusa las de email_monitor si existen)
# =============================================================================
def _obtener_credenciales():
    cfg = st.secrets.get("gmail", {})
    return cfg.get("correo", ""), cfg.get("password", "")


def _conectar_imap():
    import socket
    correo, password = _obtener_credenciales()
    if not correo or not password:
        st.warning("⚠️ Credenciales de Gmail no configuradas en secrets.toml [gmail]")
        return None
    try:
        socket.setdefaulttimeout(IMAP_TIMEOUT)
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.socket().settimeout(IMAP_TIMEOUT)
        mail.login(correo, password)
        return mail
    except socket.timeout:
        st.error(f"❌ Timeout conectando a Gmail ({IMAP_TIMEOUT}s).")
        return None
    except imaplib.IMAP4.error as e:
        st.error(f"❌ Error de autenticación IMAP: {str(e)[:200]}")
        return None
    except Exception as e:
        st.error(f"❌ Error conectando a Gmail: `{type(e).__name__}`: {str(e)[:200]}")
        return None


def _decodificar_header(header_val):
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
    if msg.is_multipart():
        for parte in msg.walk():
            ctype = parte.get_content_type()
            disposition = str(parte.get("Content-Disposition", ""))
            if ctype == "text/plain" and "attachment" not in disposition:
                payload = parte.get_payload(decode=True)
                if payload:
                    charset = parte.get_content_charset() or 'utf-8'
                    return payload.decode(charset, errors='replace')
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


def _html_a_texto(html):
    texto = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.DOTALL)
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'</?p[^>]*>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = texto.replace('&nbsp;', ' ').replace('&amp;', '&')
    texto = texto.replace('&lt;', '<').replace('&gt;', '>')
    texto = re.sub(r'[ \t]+', ' ', texto)
    texto = re.sub(r'\n\s*\n+', '\n\n', texto)
    return texto.strip()


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


def _extraer_adjuntos(msg):
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


def _parsear_fecha(date_str):
    if not date_str:
        return ""
    try:
        dt = parsedate_to_datetime(date_str)
        return dt.isoformat()
    except Exception:
        return str(date_str)[:25]


# =============================================================================
# 💾 CACHÉ EN SUPABASE
# =============================================================================
def _cache_obtener():
    """Obtiene todos los headers cacheados."""
    from utils.db import supabase
    if not supabase:
        return []
    try:
        res = supabase.table("email_scan_cache").select("*").order("fecha_correo", desc=True).execute()
        return res.data or []
    except Exception as e:
        print(f"⚠️ Error leyendo caché: {e}")
        return []


def _cache_guardar_headers(headers_list):
    """Guarda headers escaneados en la caché (upsert masivo)."""
    from utils.db import supabase
    if not supabase or not headers_list:
        return 0
    guardados = 0
    for h in headers_list:
        try:
            datos = {
                "message_id": h['message_id'].strip(),
                "asunto": h.get('asunto', ''),
                "remitente": h.get('remitente', ''),
                "fecha_correo": h.get('fecha', ''),
                "en_procesados": h.get('en_procesados', False),
                "en_pendientes": h.get('en_pendientes', False),
                "tiene_cuerpo": False,
                "escaneado_en": datetime.now().isoformat(),
            }
            supabase.table("email_scan_cache").upsert(datos).execute()
            guardados += 1
        except Exception as e:
            print(f"⚠️ Error guardando en caché: {e}")
    return guardados


def _cache_actualizar_estado(message_id, en_procesados=None, en_pendientes=None):
    """Actualiza el estado de un correo en la caché."""
    from utils.db import supabase
    if not supabase:
        return
    try:
        patch = {}
        if en_procesados is not None:
            patch["en_procesados"] = en_procesados
        if en_pendientes is not None:
            patch["en_pendientes"] = en_pendientes
        if patch:
            supabase.table("email_scan_cache").update(patch).eq("message_id", message_id.strip()).execute()
    except Exception as e:
        print(f"⚠️ Error actualizando caché: {e}")


def _cache_obtener_ids():
    """Obtiene set de message_ids cacheados para evitar duplicados."""
    from utils.db import supabase
    if not supabase:
        return set()
    try:
        res = supabase.table("email_scan_cache").select("message_id").execute()
        return {r['message_id'].strip() for r in (res.data or []) if r.get('message_id')}
    except Exception:
        return set()


# =============================================================================
# 📬 ESCANEO RÁPIDO (solo headers + caché incremental)
# =============================================================================
def escanear_gmail_rapido(max_correos=200, dias_atras=90, forzar_completo=False):
    """
    Escaneo rápido de Gmail: solo headers, cachea en Supabase.
    Incremental por defecto: solo trae correos más recientes que el último cacheado.
    Retorna dict con resultados.
    """
    from utils.db import supabase

    resultado = {
        'total_gmail': 0,
        'nuevos': 0,
        'ya_en_cache': 0,
        'en_limbo': [],
        'errores': [],
        'cache_total': 0,
    }

    # Obtener IDs ya cacheados
    ids_cacheados = set()
    if not forzar_completo and supabase:
        try:
            res = supabase.table("email_scan_cache").select("message_id").execute()
            ids_cacheados = {r['message_id'].strip() for r in (res.data or []) if r.get('message_id')}
            resultado['cache_total'] = len(ids_cacheados)
        except Exception as e:
            resultado['errores'].append(f"Error leyendo caché: {e}")

    # También obtener IDs de las tablas originales
    bd_procesados = set()
    bd_pendientes = set()
    if supabase:
        try:
            res = supabase.table("emails_procesados").select("message_id").execute()
            bd_procesados = {r['message_id'].strip() for r in (res.data or []) if r.get('message_id')}
        except Exception:
            pass
        try:
            res = supabase.table("emails_pendientes").select("message_id").execute()
            bd_pendientes = {r['message_id'].strip() for r in (res.data or []) if r.get('message_id')}
        except Exception:
            pass

    # Conectar a Gmail
    mail = _conectar_imap()
    if not mail:
        resultado['errores'].append("No se pudo conectar a Gmail")
        return resultado

    try:
        mail.select("INBOX")

        # Buscar correos
        if dias_atras > 0:
            desde = datetime.now() - timedelta(days=dias_atras)
            fecha_desde = desde.strftime("%d-%b-%Y")
            status, mensajes = mail.search(None, f'(SINCE "{fecha_desde}")')
        else:
            status, mensajes = mail.search(None, "ALL")

        if status != "OK":
            resultado['errores'].append("Error buscando en Gmail")
            return resultado

        ids = mensajes[0].split()
        if not ids:
            return resultado

        ids = ids[-max_correos:]
        resultado['total_gmail'] = len(ids)

        # Escanear en batches — solo headers
        BATCH_SIZE = 50
        nuevos_headers = []
        import socket

        for batch_start in range(0, len(ids), BATCH_SIZE):
            batch_ids = ids[batch_start:batch_start + BATCH_SIZE]
            ids_str = ",".join(mid.decode() if isinstance(mid, bytes) else str(mid) for mid in batch_ids)

            try:
                socket.setdefaulttimeout(30)
                status, datos_raw = mail.fetch(ids_str, "(BODY[HEADER.FIELDS (MESSAGE-ID FROM SUBJECT DATE)])")
            except socket.timeout:
                resultado['errores'].append(f"Timeout en batch {batch_start // BATCH_SIZE + 1}")
                continue
            except Exception as e:
                resultado['errores'].append(f"Error en batch: {e}")
                continue

            if status != "OK" or not datos_raw:
                continue

            for item in datos_raw:
                try:
                    if not isinstance(item, tuple) or len(item) < 2:
                        continue
                    header_bytes = item[1]
                    if not isinstance(header_bytes, bytes) or len(header_bytes) < 20:
                        continue

                    msg_h = email.message_from_bytes(header_bytes)
                    mid = (msg_h.get("Message-ID") or "").strip()
                    if not mid:
                        continue

                    asunto = _decodificar_header(msg_h.get("Subject", ""))
                    remitente = _decodificar_header(msg_h.get("From", ""))
                    fecha = msg_h.get("Date", "")

                    # Verificar si ya existe en caché o tablas originales
                    en_cache = mid in ids_cacheados
                    en_proc = mid in bd_procesados
                    en_pend = mid in bd_pendientes

                    if en_cache:
                        resultado['ya_en_cache'] += 1
                    else:
                        nuevos_headers.append({
                            'message_id': mid,
                            'asunto': asunto,
                            'remitente': remitente,
                            'fecha': fecha,
                            'en_procesados': en_proc,
                            'en_pendientes': en_pend,
                        })
                        resultado['nuevos'] += 1

                except Exception:
                    continue

        # Guardar nuevos headers en caché
        if nuevos_headers:
            guardados = _cache_guardar_headers(nuevos_headers)
            print(f"✅ {guardados} nuevos headers guardados en caché")

        # Calcular limbo desde toda la caché
        todos_cache = _cache_obtener()
        resultado['en_limbo'] = [
            c for c in todos_cache
            if not c.get('en_procesados') and not c.get('en_pendientes')
        ]
        resultado['cache_total'] = len(todos_cache)

        return resultado

    except Exception as e:
        resultado['errores'].append(f"Error general: {e}")
        return resultado
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# =============================================================================
# 📧 DESCARGA INDIVIDUAL DE CORREO
# =============================================================================
def descargar_correo_por_id(message_id):
    """
    Descarga UN correo completo por su Message-ID.
    Retorna dict con todos los datos o None si falla.
    """
    if not message_id:
        return None

    mail = _conectar_imap()
    if not mail:
        return None

    try:
        mail.select("INBOX")
        # Buscar por Message-ID
        status, mensajes = mail.search(None, f'(HEADER Message-ID "{message_id}")')

        if status != "OK" or not mensajes[0].strip():
            # Fallback: buscar en texto
            status, mensajes = mail.search(None, f'(TEXT "{message_id}")')

        if status != "OK" or not mensajes[0].strip():
            print(f"⚠️ No se encontró el correo: {message_id[:60]}")
            return None

        # Tomar el último resultado (más relevante)
        ultimo_id = mensajes[0].split()[-1]

        import socket
        socket.setdefaulttimeout(60)
        status, datos_raw = mail.fetch(ultimo_id, "(RFC822)")

        if status != "OK" or not datos_raw:
            return None

        raw_email = None
        for item in datos_raw:
            if isinstance(item, tuple) and len(item) >= 2:
                raw_email = item[1]
                break

        if not raw_email:
            return None

        msg = email.message_from_bytes(raw_email)

        # Extraer todo
        asunto = _decodificar_header(msg.get("Subject", ""))
        remitente = _decodificar_header(msg.get("From", ""))
        remitente_nombre = ""
        remitente_email = ""
        match_rem = re.search(r'<([^>]+)>', remitente)
        if match_rem:
            remitente_nombre = remitente[:match_rem.start()].strip(' "\'')
            remitente_email = match_rem.group(1)
        else:
            remitente_email = remitente

        fecha = _parsear_fecha(msg.get("Date", ""))
        cuerpo = _extraer_texto_plano(msg)
        html_raw = _extraer_html_raw(msg)
        adjuntos = _extraer_adjuntos(msg)

        # Obtener Message-ID real (confirmar)
        real_mid = (msg.get("Message-ID") or message_id).strip()

        return {
            'message_id': real_mid,
            'asunto': asunto,
            'remitente': remitente_email,
            'remitente_nombre': remitente_nombre,
            'fecha': fecha,
            'cuerpo': cuerpo,
            'cuerpo_corto': cuerpo[:500] if cuerpo else '',
            'html_raw': html_raw,
            'adjuntos': adjuntos,
            'n_adjuntos': len(adjuntos),
            'leido': True,
        }

    except Exception as e:
        print(f"❌ Error descargando correo: {e}")
        return None
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# =============================================================================
# 🏷️ CLASIFICACIÓN Y DETECCIÓN DE SOLICITUDES
# =============================================================================
def _detectar_activo_en_asunto(asunto, cuerpo=""):
    """Intenta detectar un nombre o ID de activo en el asunto/cuerpo del correo."""
    texto = f"{asunto} {cuerpo}".lower()
    # Patrones comunes: "equipo X", "bomba Y", "motor Z", "OT-123"
    patrones = [
        r'(?:equipo|bomba|motor|compresor|valvula|sensor|transformador|generador)\s*[:\-#]?\s*(\w+)',
        r'(?:activo|maquina)\s*[:\-#]?\s*(\d+)',
        r'OT[:\-#]?\s*(\d+)',
    ]
    for patron in patrones:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            return match.group(0)
    return None


def _detectar_tipo_mantenimiento(asunto, cuerpo=""):
    """Detecta si el correo sugiere preventivo o correctivo."""
    texto = f"{asunto} {cuerpo}".lower()
    if any(kw in texto for kw in ['preventivo', 'programado', 'rutina', 'inspección', 'calendario']):
        return 'Preventivo'
    if any(kw in texto for kw in ['falla', 'avería', 'emergencia', 'urgente', 'roto', 'dañado', 'fuga']):
        return 'Correctivo'
    return 'Correctivo'  # Default


def _detectar_criticidad(asunto, cuerpo=""):
    """Detecta criticidad basada en palabras clave."""
    texto = f"{asunto} {cuerpo}".lower()
    if any(kw in texto for kw in ['emergencia', 'crítico', 'paro total', 'peligro', 'riesgo']):
        return 'Crítica'
    if any(kw in texto for kw in ['urgente', 'importante', 'prioridad alta']):
        return 'Alta'
    if any(kw in texto for kw in ['moderado', 'media']):
        return 'Media'
    return 'Media'  # Default


# =============================================================================
# ➕ CREAR ORDEN DESDE CORREO
# =============================================================================
def _crear_orden_desde_correo(correo, activo_id=None, tecnico_id=None):
    """
    Crea una orden de trabajo directamente desde un correo descargado.
    Retorna el ID de la orden creada o None.
    """
    from utils.db import db_insert

    try:
        tipo = _detectar_tipo_mantenimiento(correo.get('asunto', ''), correo.get('cuerpo', ''))
        criticidad = _detectar_criticidad(correo.get('asunto', ''), correo.get('cuerpo', ''))

        # Construir descripción
        desc_partes = []
        if correo.get('asunto'):
            desc_partes.append(f"Asunto: {correo['asunto']}")
        if correo.get('remitente'):
            desc_partes.append(f"De: {correo.get('remitente_nombre', correo['remitente'])}")
        if correo.get('cuerpo'):
            desc_partes.append(f"\n{correo['cuerpo'][:2000]}")

        orden_datos = {
            'descripcion': '\n'.join(desc_partes)[:5000],
            'tipo_mantenimiento': tipo,
            'criticidad': criticidad,
            'estado': 'Abierta',
            'fecha_creacion': datetime.now().isoformat(),
            'origen': 'correo',
            'correo_message_id': correo.get('message_id', ''),
        }

        if activo_id:
            orden_datos['activo_id'] = int(activo_id)
        if tecnico_id:
            orden_datos['tecnico_asignado'] = int(tecnico_id)

        resultado = db_insert("ordenes", orden_datos)
        if resultado and resultado.data:
            orden_id = resultado.data[0]['id']

            # Registrar en bitácora
            db_insert("bitacora", {
                "orden_id": orden_id,
                "usuario_text": "CORREO (automático)",
                "mensaje": f"📧 Orden creada desde correo: {correo.get('asunto', 'Sin asunto')}",
                "fecha": datetime.now().isoformat(),
            })

            # Marcar correo como procesado
            try:
                from utils.db import supabase
                if supabase:
                    supabase.table("emails_procesados").upsert({
                        "message_id": correo['message_id'].strip(),
                        "orden_id": orden_id,
                        "accion": "orden",
                        "fecha_procesado": datetime.now().isoformat(),
                    }).execute()
                    # Actualizar caché
                    _cache_actualizar_estado(correo['message_id'], en_procesados=True)
            except Exception as e:
                print(f"⚠️ Error marcando como procesado: {e}")

            return orden_id
        return None

    except Exception as e:
        st.error(f"❌ Error creando orden: {e}")
        return None


# =============================================================================
# 🔗 VINCULAR A ORDEN EXISTENTE
# =============================================================================
def _vincular_a_orden(message_id, orden_id):
    """Vincula un correo a una orden existente."""
    from utils.db import db_insert, supabase
    if not supabase:
        return False
    try:
        supabase.table("emails_procesados").upsert({
            "message_id": message_id.strip(),
            "orden_id": int(orden_id),
            "accion": "avance",
            "fecha_procesado": datetime.now().isoformat(),
        }).execute()

        db_insert("bitacora", {
            "orden_id": int(orden_id),
            "usuario_text": "CORREO (vinculado)",
            "mensaje": f"📧 Correo vinculado: {message_id[:50]}",
            "fecha": datetime.now().isoformat(),
        })

        _cache_actualizar_estado(message_id, en_procesados=True)
        return True
    except Exception as e:
        st.error(f"❌ Error vinculando: {e}")
        return False


# =============================================================================
# 🗑️ DESCARTAR CORREO
# =============================================================================
def _descartar_correo(message_id):
    """Marca un correo como descartado."""
    from utils.db import supabase
    if not supabase:
        return False
    try:
        supabase.table("emails_procesados").upsert({
            "message_id": message_id.strip(),
            "orden_id": None,
            "accion": "descartado",
            "fecha_procesado": datetime.now().isoformat(),
        }).execute()
        _cache_actualizar_estado(message_id, en_procesados=True)
        return True
    except Exception as e:
        st.error(f"❌ Error descartando: {e}")
        return False


# =============================================================================
# 🖼️ RENDERIZADO: VISTA PREVIA INLINE
# =============================================================================
def _render_preview_correo(correo, idx):
    """Renderiza la vista previa de un correo descargado.
    Replica el estilo del módulo Correo original."""
    asunto = correo.get('asunto', 'Sin asunto')
    remitente = correo.get('remitente', '')
    remitente_nombre = correo.get('remitente_nombre', '')
    fecha = correo.get('fecha', '')[:16].replace('T', ' ')
    cuerpo = correo.get('cuerpo', '')
    n_adj = correo.get('n_adjuntos', 0)

    remitente_display = remitente_nombre if remitente_nombre else remitente

    # ── Cabecera del correo ──
    st.markdown(f"""
    <div style="background:rgba(59,130,246,0.08);border:1px solid rgba(59,130,246,0.2);border-radius:8px;padding:16px;margin:8px 0;">
        <div style="font-size:1.1rem;font-weight:600;color:#E5E7EB;">📧 {asunto}</div>
        <div style="color:#9CA3AF;font-size:0.9rem;margin-top:4px;">
            👤 {remitente_display} &nbsp;·&nbsp; 📅 {fecha}
            {" &nbsp;·&nbsp; 📎 " + str(n_adj) + " adjunto(s)" if n_adj > 0 else ""}
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Contenido del correo (igual que módulo Correo) ──
    html_raw = correo.get('html_raw', '')
    tiene_html = bool(html_raw and html_raw.strip())

    if tiene_html:
        tab_html, tab_texto = st.tabs(["🌐 Vista original", "📝 Texto plano"])
        with tab_html:
            import streamlit.components.v1 as components
            import re as _re
            html_seguro = _re.sub(r'<script[^>]*>.*?</script>', '', html_raw, flags=_re.DOTALL | _re.IGNORECASE)
            html_seguro = _re.sub(r'<iframe[^>]*>.*?</iframe>', '', html_seguro, flags=_re.DOTALL | _re.IGNORECASE)
            components.html(
                f'<div style="background:#fff;color:#1f2937;padding:16px;border-radius:8px;font-family:Arial,sans-serif;font-size:14px;line-height:1.6;overflow:auto;">{html_seguro}</div>',
                height=500,
                scrolling=True
            )
        with tab_texto:
            if cuerpo:
                st.text_area(
                    "Contenido",
                    value=cuerpo[:3000],
                    height=250,
                    disabled=True,
                    key=f"preview_cuerpo_{idx}",
                    label_visibility="collapsed",
                )
            else:
                st.info("Sin versión en texto plano.")
    else:
        if cuerpo:
            st.text_area(
                "Contenido",
                value=cuerpo[:3000],
                height=250,
                disabled=True,
                key=f"preview_cuerpo_{idx}",
                label_visibility="collapsed",
            )
        else:
            st.warning("⚠️ Contenido no disponible (solo headers).")

    # ── Adjuntos con descarga (igual que módulo Correo) ──
    adjuntos = correo.get('adjuntos', [])
    if adjuntos:
        st.markdown(f"**📎 Adjuntos ({len(adjuntos)}):**")
        for a_idx, att in enumerate(adjuntos):
            nombre = att.get('nombre', '?')
            tamano = att.get('tamano', 0)
            tamano_str = f"{tamano / 1024:.1f} KB" if tamano < 1024 * 1024 else f"{tamano / (1024 * 1024):.1f} MB"
            col_info, col_btn = st.columns([3, 1])
            with col_info:
                st.caption(f"📄 {nombre} — {tamano_str} ({att.get('tipo', '?')})")
            with col_btn:
                if att.get('datos_b64'):
                    import base64 as _b64
                    st.download_button(
                        "⬇️ Descargar",
                        data=_b64.b64decode(att['datos_b64']),
                        file_name=nombre,
                        mime=att.get('tipo', 'application/octet-stream'),
                        key=f"dl_audit_{idx}_{a_idx}",
                        use_container_width=True
                    )


# =============================================================================
# 🖼️ RENDERIZADO: CARD DE CORREO EN LIMBO
# =============================================================================
def _render_card_limbo(correo_cache, idx, df_ordenes=None):
    """Renderiza una card de correo en limbo con acciones inline."""
    message_id = correo_cache.get('message_id', '')
    asunto = (correo_cache.get('asunto', '') or '')[:70]
    remitente = (correo_cache.get('remitente', '') or '')[:50]
    fecha = (correo_cache.get('fecha_correo', '') or '')[:25]

    # Key única para session state
    state_key = f"_limbo_{idx}_{message_id[:20]}"

    # Card visual
    col_info, col_acc = st.columns([5, 3])

    with col_info:
        st.markdown(f"""
        <div style="border-left:3px solid #EF4444;padding:10px 14px;background:rgba(239,68,68,0.05);border-radius:0 6px 6px 0;">
            <div style="color:#EF4444;font-weight:600;font-size:0.95em;">📧 {asunto}</div>
            <div style="color:#9CA3AF;font-size:0.8em;margin-top:3px;">👤 {remitente} &nbsp;·&nbsp; {fecha}</div>
        </div>
        """, unsafe_allow_html=True)

    with col_acc:
        # Botones con texto visible (no solo emoji) — el tooltip no se ve en tema oscuro
        btn_cols = st.columns(4)

        with btn_cols[0]:
            if st.button("👁️ Ver", key=f"prev_{state_key}", use_container_width=True):
                st.session_state[f"_preview_active_{state_key}"] = not st.session_state.get(f"_preview_active_{state_key}", False)
                st.rerun()

        with btn_cols[1]:
            if st.button("➕ OT", key=f"crear_{state_key}", use_container_width=True):
                st.session_state[f"_crear_active_{state_key}"] = True
                st.session_state[f"_preview_active_{state_key}"] = False
                st.rerun()

        with btn_cols[2]:
            if st.button("🔗 Vincular", key=f"vinc_{state_key}", use_container_width=True):
                st.session_state[f"_vincular_active_{state_key}"] = not st.session_state.get(f"_vincular_active_{state_key}", False)
                st.rerun()

        with btn_cols[3]:
            if st.button("🗑️", key=f"desc_{state_key}", use_container_width=True):
                if _descartar_correo(message_id):
                    st.toast(f"🗑️ Descartado: {asunto[:30]}")
                    st.rerun()

    # ── Vista previa expandida ──
    if st.session_state.get(f"_preview_active_{state_key}", False):
        with st.container():
            correo_completo = st.session_state.get(f"_correo_descargado_{state_key}")
            if not correo_completo:
                with st.spinner("Descargando correo..."):
                    correo_completo = descargar_correo_por_id(message_id)
                    if correo_completo:
                        st.session_state[f"_correo_descargado_{state_key}"] = correo_completo

            if correo_completo:
                _render_preview_correo(correo_completo, idx)
            else:
                st.warning("⚠️ No se pudo descargar el contenido del correo.")

    # ── Crear orden inline ──
    if st.session_state.get(f"_crear_active_{state_key}", False):
        with st.container():
            st.markdown("##### ➕ Crear Orden desde este correo")

            correo_completo = st.session_state.get(f"_correo_descargado_{state_key}")
            if not correo_completo:
                with st.spinner("Descargando correo para crear orden..."):
                    correo_completo = descargar_correo_por_id(message_id)
                    if correo_completo:
                        st.session_state[f"_correo_descargado_{state_key}"] = correo_completo

            if not correo_completo:
                st.error("❌ No se pudo descargar el correo.")
                if st.button("Cancelar", key=f"cancel_crear_{state_key}"):
                    st.session_state[f"_crear_active_{state_key}"] = False
                    st.rerun()
            else:
                # Detectar activo automáticamente
                activo_detectado = _detectar_activo_en_asunto(
                    correo_completo.get('asunto', ''),
                    correo_completo.get('cuerpo', '')
                )

                col_a, col_b = st.columns(2)
                with col_a:
                    tipo = _detectar_tipo_mantenimiento(
                        correo_completo.get('asunto', ''),
                        correo_completo.get('cuerpo', '')
                    )
                    tipo_sel = st.selectbox(
                        "Tipo",
                        ["Correctivo", "Preventivo"],
                        index=0 if tipo == "Correctivo" else 1,
                        key=f"tipo_{state_key}"
                    )

                with col_b:
                    criticidad = _detectar_criticidad(
                        correo_completo.get('asunto', ''),
                        correo_completo.get('cuerpo', '')
                    )
                    crit_opciones = ["Baja", "Media", "Alta", "Crítica"]
                    crit_idx = crit_opciones.index(criticidad) if criticidad in crit_opciones else 1
                    criticidad_sel = st.selectbox(
                        "Criticidad",
                        crit_opciones,
                        index=crit_idx,
                        key=f"crit_{state_key}"
                    )

                # Selector de activo (opcional)
                activo_id = None
                if df_ordenes is not None:
                    try:
                        from utils.db import run_query
                        df_act = run_query("activos")
                        if not df_act.empty:
                            opciones_act = ["(Sin activo)"] + [
                                f"{row['id']} - {row['nombre']}" for _, row in df_act.iterrows()
                            ]
                            idx_act = 0
                            if activo_detectado:
                                for i, op in enumerate(opciones_act):
                                    if activo_detectado.lower() in op.lower():
                                        idx_act = i
                                        break
                            act_sel = st.selectbox(
                                "Activo (opcional)",
                                opciones_act,
                                index=idx_act,
                                key=f"act_{state_key}"
                            )
                            if act_sel != "(Sin activo)":
                                activo_id = int(act_sel.split(" - ")[0])
                    except Exception:
                        pass

                desc_editable = st.text_area(
                    "Descripción",
                    value=correo_completo.get('cuerpo', '')[:2000],
                    height=120,
                    key=f"desc_{state_key}"
                )

                col_go, col_cancel = st.columns([1, 1])
                with col_go:
                    if st.button("✅ Crear Orden", key=f"go_crear_{state_key}", type="primary", use_container_width=True):
                        # Actualizar descripción editable
                        correo_completo['cuerpo'] = desc_editable
                        orden_id = _crear_orden_desde_correo(correo_completo, activo_id=activo_id)
                        if orden_id:
                            st.success(f"✅ Orden #{orden_id} creada exitosamente.")
                            # Limpiar estados
                            st.session_state[f"_crear_active_{state_key}"] = False
                            st.session_state.pop(f"_correo_descargado_{state_key}", None)
                            st.rerun()
                        else:
                            st.error("❌ No se pudo crear la orden.")

                with col_cancel:
                    if st.button("Cancelar", key=f"cancel2_{state_key}", use_container_width=True):
                        st.session_state[f"_crear_active_{state_key}"] = False
                        st.rerun()

    # ── Vincular a orden existente ──
    if st.session_state.get(f"_vincular_active_{state_key}", False):
        with st.container():
            st.markdown("##### 🔗 Vincular a Orden existente")
            try:
                from utils.db import run_query
                df_ord = run_query("ordenes")
                if df_ord.empty:
                    st.info("No hay órdenes registradas.")
                else:
                    opciones_ord = [
                        f"{row['id']} - {(row.get('descripcion', '') or '')[:40]}"
                        for _, row in df_ord.sort_values('id', ascending=False).head(50).iterrows()
                    ]
                    ord_sel = st.selectbox("Seleccionar Orden", opciones_ord, key=f"ord_sel_{state_key}")
                    orden_id = int(ord_sel.split(" - ")[0])

                    col_vinc, col_cancel_v = st.columns([1, 1])
                    with col_vinc:
                        if st.button("🔗 Vincular", key=f"go_vinc_{state_key}", type="primary", use_container_width=True):
                            if _vincular_a_orden(message_id, orden_id):
                                st.success(f"✅ Correo vinculado a OT #{orden_id}")
                                st.session_state[f"_vincular_active_{state_key}"] = False
                                st.rerun()
                    with col_cancel_v:
                        if st.button("Cancelar", key=f"cancel_vinc_{state_key}", use_container_width=True):
                            st.session_state[f"_vincular_active_{state_key}"] = False
                            st.rerun()
            except Exception as e:
                st.error(f"Error cargando órdenes: {e}")

    st.markdown("<div style='margin-bottom:8px;'></div>", unsafe_allow_html=True)


# =============================================================================
# 🔍 RENDERIZADO PRINCIPAL: AUDITORÍA
# =============================================================================
def render_auditoria_correos():
    """Página de auditoría rediseñada: escaneo rápido + acciones directas."""
    st.markdown("### 🔍 Auditoría de Correos")
    st.caption("Escanea Gmail, detecta correos sin gestionar, y actúa directamente desde aquí.")

    from utils.db import supabase

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 1: RESUMEN DE BASE DE DATOS
    # ══════════════════════════════════════════════════════════════
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
        else:
            st.warning("Sin conexión a base de datos.")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 2: ESCANEO RÁPIDO
    # ══════════════════════════════════════════════════════════════
    st.markdown("#### 📡 Escaneo Rápido de Gmail")
    st.caption("Solo descarga headers (rápido). Los resultados se cachean para no re-escanear.")

    col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 1, 1])
    with col_cfg1:
        max_corr = st.number_input("Máx. correos", min_value=20, max_value=1000, value=200, step=50, key="aud_max_corr")
    with col_cfg2:
        dias = st.number_input("Días hacia atrás", min_value=7, max_value=365, value=90, step=7, key="aud_dias")
    with col_cfg3:
        st.markdown("<br>", unsafe_allow_html=True)
        forzar = st.checkbox("Forzar re-escaneo completo", key="aud_forzar")

    col_scan, col_cache_info = st.columns([1, 2])
    with col_scan:
        ejecutar_scan = st.button("📡 Escanear Gmail", type="primary", use_container_width=True, key="aud_btn_scan")

    # Mostrar info de caché
    cache_total = 0
    if supabase:
        try:
            res_cache = supabase.table("email_scan_cache").select("message_id", count="exact").execute()
            cache_total = res_cache.count or 0
        except Exception:
            pass

    with col_cache_info:
        if cache_total > 0:
            st.caption(f"💾 Caché: {cache_total} headers almacenados. El escaneo incremental solo trae los nuevos.")
        else:
            st.caption("💡 Primera vez: se escanearán todos los correos del rango seleccionado.")

    # Ejecutar escaneo
    if ejecutar_scan:
        with st.spinner(f"📡 Escaneando headers de Gmail ({max_corr} correos, {dias} días)..."):
            resultado_scan = escanear_gmail_rapido(
                max_correos=max_corr,
                dias_atras=dias,
                forzar_completo=forzar
            )
        st.session_state['_auditoria_scan_result'] = resultado_scan

    # Mostrar resultado del escaneo
    scan_result = st.session_state.get('_auditoria_scan_result')
    if scan_result:
        for err in scan_result.get('errores', []):
            st.error(f"❌ {err}")

        sr1, sr2, sr3, sr4 = st.columns(4)
        sr1.metric("📧 En Gmail", scan_result.get('total_gmail', 0))
        sr2.metric("🆕 Nuevos", scan_result.get('nuevos', 0))
        sr3.metric("💾 Ya en caché", scan_result.get('ya_en_cache', 0))
        sr4.metric("💾 Caché total", scan_result.get('cache_total', 0))

        if scan_result.get('nuevos', 0) > 0:
            st.success(f"✅ {scan_result['nuevos']} nuevos headers agregados a la caché.")
        elif scan_result.get('total_gmail', 0) > 0:
            st.info("ℹ️ Sin nuevos correos. Todo ya estaba en caché.")

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 3: CORREOS EN LIMBO (acciones directas)
    # ══════════════════════════════════════════════════════════════
    st.markdown("#### ⚠️ Correos sin Gestionar (en LIMBO)")
    st.caption("Correos en Gmail que no están en `emails_procesados` ni `emails_pendientes`.")

    # Obtener limbo desde caché
    todos_cache = _cache_obtener()
    en_limbo = [c for c in todos_cache if not c.get('en_procesados') and not c.get('en_pendientes')]

    # Verificar también contra tablas originales por si se actualizó fuera de la caché
    if supabase and en_limbo:
        try:
            res_proc = supabase.table("emails_procesados").select("message_id").execute()
            ids_proc = {r['message_id'].strip() for r in (res_proc.data or [])}
            en_limbo = [c for c in en_limbo if c['message_id'].strip() not in ids_proc]
        except Exception:
            pass

    if not en_limbo:
        if cache_total > 0:
            st.success("✅ **Sin correos en limbo.** Todos los correos escaneados están gestionados.")
        else:
            st.info("💡 Primero ejecuta un escaneo para detectar correos en limbo.")
    else:
        # Métricas
        st.error(f"⚠️ **{len(en_limbo)} correos están en LIMBO** — en Gmail pero no gestionados.")

        # ── Filtros ──
        st.markdown("##### 🔎 Filtros")
        col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
        with col_f1:
            filtro_remitente = st.text_input("Filtrar por remitente", key="aud_filtro_rem", placeholder="ej: proveedor@empresa.com")
        with col_f2:
            filtro_asunto = st.text_input("Filtrar por asunto", key="aud_filtro_asunto", placeholder="ej: falla, mantenimiento")
        with col_f3:
            st.markdown("<br>", unsafe_allow_html=True)
            invertir = st.checkbox("Invertir", key="aud_invertir", help="Mostrar solo los que NO coinciden")

        # Aplicar filtros
        limbo_filtrado = en_limbo[:]
        if filtro_remitente:
            if invertir:
                limbo_filtrado = [c for c in limbo_filtrado if filtro_remitente.lower() not in (c.get('remitente', '') or '').lower()]
            else:
                limbo_filtrado = [c for c in limbo_filtrado if filtro_remitente.lower() in (c.get('remitente', '') or '').lower()]
        if filtro_asunto:
            if invertir:
                limbo_filtrado = [c for c in limbo_filtrado if filtro_asunto.lower() not in (c.get('asunto', '') or '').lower()]
            else:
                limbo_filtrado = [c for c in limbo_filtrado if filtro_asunto.lower() in (c.get('asunto', '') or '').lower()]

        # ── Acciones masivas ──
        if len(limbo_filtrado) > 1:
            st.markdown("##### 📦 Acciones masivas")
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                if st.button(f"💾 Guardar {len(limbo_filtrado)} como pendientes", use_container_width=True, key="aud_mas_guardar"):
                    guardados = 0
                    for c in limbo_filtrado:
                        try:
                            from utils.email_monitor import _guardar_correo_pendiente
                            _guardar_correo_pendiente({
                                'message_id': c['message_id'],
                                'remitente': c.get('remitente', ''),
                                'remitente_nombre': '',
                                'asunto': c.get('asunto', ''),
                                'fecha': c.get('fecha_correo', ''),
                                'cuerpo_corto': '',
                                'adjuntos': [],
                                'leido': False,
                            })
                            _cache_actualizar_estado(c['message_id'], en_pendientes=True)
                            guardados += 1
                        except Exception:
                            pass
                    st.success(f"✅ {guardados} guardados como pendientes.")
                    st.rerun()
            with col_m2:
                if st.button(f"🗑️ Descartar {len(limbo_filtrado)} correos", use_container_width=True, key="aud_mas_descartar"):
                    descartados = 0
                    for c in limbo_filtrado:
                        if _descartar_correo(c['message_id']):
                            descartados += 1
                    st.success(f"🗑️ {descartados} descartados.")
                    st.rerun()
            with col_m3:
                st.metric("Mostrando", f"{len(limbo_filtrado)} / {len(en_limbo)}")

        st.markdown("---")

        # ── Lista de correos en limbo ──
        st.markdown(f"##### 📋 Lista ({len(limbo_filtrado)} correos)")

        # Cargar df_ordenes para el selector de vincular
        df_ordenes = None
        try:
            from utils.db import run_query
            df_ordenes = run_query("ordenes")
        except Exception:
            pass

        # Paginación
        ITEMS_POR_PAGINA = 10
        total_paginas = max(1, (len(limbo_filtrado) + ITEMS_POR_PAGINA - 1) // ITEMS_POR_PAGINA)
        pagina = st.session_state.get('_auditoria_pagina', 1)

        col_pag1, col_pag2, col_pag3 = st.columns([1, 2, 1])
        with col_pag1:
            if st.button("⬅️ Anterior", disabled=(pagina <= 1), key="aud_pag_ant"):
                st.session_state['_auditoria_pagina'] = pagina - 1
                st.rerun()
        with col_pag2:
            st.caption(f"Página {pagina} de {total_paginas}")
        with col_pag3:
            if st.button("Siguiente ➡️", disabled=(pagina >= total_paginas), key="aud_pag_sig"):
                st.session_state['_auditoria_pagina'] = pagina + 1
                st.rerun()

        inicio = (pagina - 1) * ITEMS_POR_PAGINA
        fin = min(inicio + ITEMS_POR_PAGINA, len(limbo_filtrado))

        for i in range(inicio, fin):
            _render_card_limbo(limbo_filtrado[i], i, df_ordenes=df_ordenes)

    st.markdown("---")

    # ══════════════════════════════════════════════════════════════
    # SECCIÓN 4: HISTORIAL DE PROCESADOS
    # ══════════════════════════════════════════════════════════════
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
