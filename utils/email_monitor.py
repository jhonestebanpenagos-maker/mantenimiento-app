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
import io
import base64
from datetime import datetime, timedelta


# ==============================================================================
# 📦 PERSISTENCIA DE CORREOS PROCESADOS (Supabase)
# ==============================================================================
def _obtener_procesados():
    """Obtiene los message_id de correos ya procesados desde Supabase."""
    from utils.db import supabase
    if not supabase:
        print("⚠️ _obtener_procesados: supabase es None")
        return set()
    try:
        res = supabase.table("emails_procesados").select("message_id").execute()
        ids = {row["message_id"].strip() for row in (res.data or []) if row.get("message_id")}
        print(f"📋 Procesados en BD: {len(ids)} registros")
        for mid in list(ids)[:5]:
            print(f"   → [{mid}]")
        return ids
    except Exception as e:
        print(f"⚠️ Error obteniendo procesados: {type(e).__name__}: {e}")
        st.warning(f"⚠️ No se pudo consultar correos procesados: {e}")
        return set()


def _guardar_correo_pendiente(correo: dict):
    """Guarda un correo descargado en la tabla emails_pendientes para persistencia."""
    from utils.db import supabase
    if not supabase:
        return
    try:
        datos = {
            "message_id": correo['message_id'].strip(),
            "remitente": correo.get('remitente', ''),
            "remitente_nombre": correo.get('remitente_nombre', ''),
            "asunto": correo.get('asunto', ''),
            "fecha_correo": correo.get('fecha', ''),
            "cuerpo_corto": correo.get('cuerpo_corto', '')[:500],
            "n_adjuntos": len(correo.get('adjuntos', [])),
            "leido": correo.get('leido', False),
            "descargado_en": datetime.now().isoformat(),
        }
        supabase.table("emails_pendientes").upsert(datos).execute()
    except Exception as e:
        print(f"⚠️ Error guardando pendiente: {e}")


def _obtener_pendientes_guardados():
    """Obtiene correos pendientes previamente descargados desde la tabla emails_pendientes."""
    from utils.db import supabase
    if not supabase:
        return []
    try:
        res = supabase.table("emails_pendientes").select("*").order("descargado_en", desc=True).limit(50).execute()
        return res.data or []
    except Exception as e:
        print(f"⚠️ Error obteniendo pendientes guardados: {e}")
        return []


def _eliminar_pendiente(message_id: str):
    """Elimina un correo de la tabla emails_pendientes (porque ya se gestionó)."""
    from utils.db import supabase
    if not supabase:
        return
    try:
        supabase.table("emails_pendientes").delete().eq("message_id", message_id.strip()).execute()
    except Exception as e:
        print(f"⚠️ Error eliminando pendiente: {e}")


def _marcar_procesado(message_id: str, orden_id: int = None, accion: str = "orden"):
    """Marca un correo como procesado en Supabase (persistente)."""
    from utils.db import supabase
    if not supabase:
        print("⚠️ _marcar_procesado: supabase es None")
        st.error("❌ No hay conexión a Supabase")
        return
    message_id_limpio = message_id.strip()
    datos = {
        "message_id": message_id_limpio,
        "orden_id": orden_id,
        "accion": accion,
        "fecha_procesado": datetime.now().isoformat(),
    }
    print(f"💾 Guardando en emails_procesados: message_id=[{message_id_limpio}] accion={accion}")
    try:
        res = supabase.table("emails_procesados").upsert(datos).execute()
        print(f"✅ Guardado OK: {res.data}")
    except Exception as e:
        print(f"❌ Error guardando: {type(e).__name__}: {e}")
        st.error(f"❌ No se pudo guardar como procesado: {type(e).__name__}: {e}")


# ==============================================================================
# 🔧 CONFIGURACIÓN
# ==============================================================================
IMAP_SERVER = "imap.gmail.com"
IMAP_PORT = 993
IMAP_TIMEOUT = 30  # Timeout en segundos para operaciones IMAP


def _obtener_credenciales():
    """Obtiene credenciales de Gmail desde st.secrets."""
    cfg = st.secrets.get("gmail", {})
    correo = cfg.get("correo", "")
    password = cfg.get("password", "")
    return correo, password


def _conectar_imap():
    """
    Conecta a Gmail vía IMAP con SSL y timeout.
    Retorna el objeto IMAP4_SSL o None si falla.
    """
    import socket
    correo, password = _obtener_credenciales()

    if not correo or not password:
        st.warning("⚠️ Credenciales de Gmail no configuradas en secrets.toml [gmail]")
        return None

    try:
        # Timeout a nivel de socket para que no se cuelgue
        socket.setdefaulttimeout(IMAP_TIMEOUT)
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.socket().settimeout(IMAP_TIMEOUT)
        mail.login(correo, password)
        return mail
    except socket.timeout:
        st.error(f"❌ Timeout conectando a Gmail ({IMAP_TIMEOUT}s). Verifica tu conexión a internet.")
        return None
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
# 📤 SUBIR ADJUNTOS DEL CORREO A CLOUDINARY
# ==============================================================================
class _ArchivoDesdeBytes(io.BytesIO):
    """Wrapper que emula un UploadedFile de Streamlit para subir a Cloudinary."""
    def __init__(self, datos_bytes, nombre):
        super().__init__(datos_bytes)
        self.name = nombre
        self._name = nombre
        self._datos = datos_bytes

    def getvalue(self):
        return self._datos

    def lower(self):
        return self.name.lower()


def _subir_adjuntos_correo(adjuntos, orden_id):
    """
    Sube los adjuntos de un correo a Cloudinary y crea entradas en la bitácora.
    Retorna lista de URLs subidas exitosamente.
    """
    from utils.db import db_insert
    from utils.uploads import subir_archivo_generico

    urls_subidas = []
    if not adjuntos:
        return urls_subidas

    for att in adjuntos:
        datos_b64 = att.get('datos_b64')
        nombre = att.get('nombre', 'adjunto_sin_nombre')
        if not datos_b64:
            continue

        try:
            datos_bytes = base64.b64decode(datos_b64)
            archivo = _ArchivoDesdeBytes(datos_bytes, nombre)

            url = subir_archivo_generico(archivo)
            if url:
                urls_subidas.append(url)
                es_imagen = att.get('tipo', '').startswith('image/')
                icono = "🖼️" if es_imagen else "📎"
                db_insert("bitacora", {
                    "orden_id": orden_id,
                    "usuario_text": "CORREO (automático)",
                    "mensaje": f"{icono} Adjunto del correo: {nombre}",
                    "archivo_url": url,
                    "fecha": datetime.now().isoformat()
                })
                print(f"✅ Adjunto subido: {nombre} → {url}")
            else:
                print(f"⚠️ No se pudo subir adjunto: {nombre}")
        except Exception as e:
            print(f"❌ Error subiendo adjunto {nombre}: {e}")

    return urls_subidas


def sincronizar_adjuntos_correo(orden_id, correo_message_id):
    """
    Descarga un correo específico por su Message-ID desde Gmail,
    extrae los adjuntos y los sube a la OT existente.
    Retorna (n_subidos, n_total) o (0, 0) si falla.
    """
    from utils.db import db_insert

    if not correo_message_id:
        return 0, 0

    mail = _conectar_imap()
    if not mail:
        return 0, 0

    try:
        mail.select("INBOX")
        # Buscar por Message-ID
        status, mensajes = mail.search(None, f'(HEADER Message-ID "{correo_message_id}")')
        if status != "OK" or not mensajes[0].strip():
            # Intentar búsqueda más amplia por texto
            status, mensajes = mail.search(None, f'(TEXT "{correo_message_id}")')
        if status != "OK" or not mensajes[0].strip():
            print(f"⚠️ No se encontró el correo con Message-ID: {correo_message_id}")
            return 0, 0

        ids = mensajes[0].split()
        msg_id = ids[-1]  # Tomar el más reciente si hay múltiples

        status, datos = mail.fetch(msg_id, "(RFC822)")
        if status != "OK":
            return 0, 0

        msg = email.message_from_bytes(datos[0][1])
        adjuntos = _extraer_adjuntos(msg)
        imagenes_inline = _extraer_imagenes_inline(msg)

        if not adjuntos and not imagenes_inline:
            return 0, 0

        n_total = len(adjuntos) + len(imagenes_inline)
        n_subidos = 0

        # Subir adjuntos
        if adjuntos:
            urls = _subir_adjuntos_correo(adjuntos, orden_id)
            n_subidos += len(urls)

        # Subir imágenes inline
        if imagenes_inline:
            from utils.uploads import subir_archivo_generico as _subir_img
            for cid, img in imagenes_inline.items():
                try:
                    img_bytes = base64.b64decode(img['datos_b64'])
                    archivo_img = _ArchivoDesdeBytes(img_bytes, f"inline_{cid}.jpg")
                    url_img = _subir_img(archivo_img)
                    if url_img:
                        db_insert("bitacora", {
                            "orden_id": orden_id,
                            "usuario_text": "CORREO (sincronización)",
                            "mensaje": f"🖼️ Imagen embebida del correo (CID: {cid})",
                            "archivo_url": url_img,
                            "fecha": datetime.now().isoformat()
                        })
                        n_subidos += 1
                except Exception as e_img:
                    print(f"⚠️ Error subiendo inline {cid}: {e_img}")

        # Registrar en bitácora que se sincronizaron adjuntos
        db_insert("bitacora", {
            "orden_id": orden_id,
            "usuario_text": "SISTEMA",
            "mensaje": f"🔄 Sincronización de adjuntos: {n_subidos}/{n_total} archivos subidos desde correo original.",
            "fecha": datetime.now().isoformat()
        })

        return n_subidos, n_total

    except Exception as e:
        print(f"❌ Error sincronizando adjuntos: {e}")
        return 0, 0
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# ==============================================================================
# 📬 DESCARGA DE CORREOS
# ==============================================================================
def _parsear_correos_batch(datos_raw):
    """
    Parsea la respuesta de IMAP fetch batch de forma robusta.
    IMAP devuelve una lista donde:
    - Los pares (bytes_header, b'') son tuplas con los datos
    - El último elemento puede ser b')' (cierre del literal)
    Retorna lista de dicts con la metadata parseada.
    """
    resultados = []
    if not datos_raw:
        return resultados

    for item in datos_raw:
        try:
            # Solo procesar tuplas (header_bytes, suffix)
            if not isinstance(item, tuple) or len(item) < 2:
                continue
            header_bytes = item[1]
            if not isinstance(header_bytes, bytes) or len(header_bytes) < 20:
                continue

            msg_header = email.message_from_bytes(header_bytes)

            asunto = _decodificar_header(msg_header.get("Subject", ""))
            remitente_raw = _decodificar_header(msg_header.get("From", ""))
            fecha_raw = msg_header.get("Date", "")
            message_id = (msg_header.get("Message-ID") or "").strip()
            if not message_id:
                continue

            remitente = remitente_raw
            remitente_nombre = ""
            match = re.match(r'^"?([^"<]*)"?\s*<([^>]+)>', remitente_raw)
            if match:
                remitente_nombre = match.group(1).strip()
                remitente = match.group(2).strip()
            elif "@" in remitente_raw:
                remitente = remitente_raw.strip()

            correo_data = {
                'message_id': message_id,
                'imap_id': '',
                'remitente': remitente,
                'remitente_nombre': remitente_nombre,
                'asunto': asunto or '(Sin asunto)',
                'fecha': _parsear_fecha(fecha_raw),
                'cuerpo': '',
                'cuerpo_corto': '',
                'html_raw': '',
                'adjuntos': [],
                'imagenes_inline': {},
                'tiene_adjuntos': False,
                'tiene_html': False,
                'tiene_imagenes': False,
                'leido': False,
                'contenido_cargado': False,
            }
            resultados.append(correo_data)
        except Exception as e:
            print(f"⚠️ Error parseando item batch: {e}")
            continue

    return resultados


def descargar_correos_nuevos(max_correos=20, dias_atras=7):
    """
    Descarga SOLO HEADERS de correos nuevos (ultra rápido, sin adjuntos).
    El contenido completo se carga bajo demanda con cargar_contenido_correo().
    Retorna lista de dicts con metadata básica.
    """
    import socket

    mail = _conectar_imap()
    if not mail:
        return []

    try:
        mail.select("INBOX", readonly=True)

        desde = datetime.now() - timedelta(days=dias_atras)
        fecha_desde = desde.strftime("%d-%b-%Y")

        status, mensajes = mail.search(None, f'(SINCE "{fecha_desde}")')
        if status != "OK":
            st.error("❌ Error buscando correos en la bandeja")
            return []

        ids = mensajes[0].split()
        if not ids:
            return []

        ids = ids[-max_correos:]
        ids.reverse()

        # ── Batch: descargar solo headers en una sola llamada ──
        ids_str = ",".join(mid.decode() if isinstance(mid, bytes) else str(mid) for mid in ids)
        try:
            mail.socket().settimeout(30)
            status, datos_raw = mail.fetch(ids_str, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")
        except socket.timeout:
            st.error(f"❌ Timeout descargando headers ({30}s). Intenta con menos días.")
            return []
        except Exception as e:
            st.error(f"❌ Error en fetch batch: `{type(e).__name__}`: {e}")
            return []

        if status != "OK" or not datos_raw:
            st.error("❌ Error obteniendo headers de Gmail")
            return []

        resultados = _parsear_correos_batch(datos_raw)
        print(f"✅ Headers parseados: {len(resultados)} de {len(ids)} solicitados")

        # Guardar en tabla de pendientes
        for correo_data in resultados:
            _guardar_correo_pendiente(correo_data)

        return resultados

    except Exception as e:
        st.error(f"❌ Error descargando correos: `{type(e).__name__}`")
        st.code(str(e)[:500], language="text")
        return []
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def cargar_contenido_correo(correo: dict) -> dict:
    """
    Carga el contenido completo de UN correo si no fue descargado en el batch.
    Retorna el correo actualizado con el contenido.
    """
    # Si ya se descargó en el batch, no hacer nada
    if correo.get('contenido_cargado'):
        return correo

    import socket

    message_id = correo.get('message_id', '').strip()
    if not message_id:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = '[No disponible - sin Message-ID]'
        return correo

    mail = _conectar_imap()
    if not mail:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = '[Error conectando a Gmail]'
        return correo

    try:
        mail.select("INBOX", readonly=True)
        mail.socket().settimeout(IMAP_TIMEOUT)

        # Buscar por Message-ID
        status, mensajes = mail.search(None, f'(HEADER Message-ID "{message_id}")')
        if status != "OK" or not mensajes[0].strip():
            # Fallback: búsqueda por texto
            status, mensajes = mail.search(None, f'(TEXT "{message_id}")')

        if status != "OK" or not mensajes[0].strip():
            correo['contenido_cargado'] = True
            correo['cuerpo'] = '[Correo no encontrado en Gmail]'
            return correo

        ids = mensajes[0].split()
        msg_id = ids[-1]  # Más reciente

        status, datos = mail.fetch(msg_id, "(RFC822)")
        if status != "OK" or not datos or not datos[0]:
            correo['contenido_cargado'] = True
            correo['cuerpo'] = '[Error descargando contenido]'
            return correo

        msg = email.message_from_bytes(datos[0][1])
        cuerpo = _extraer_texto_plano(msg)
        html_raw = _extraer_html_raw(msg)
        adjuntos = _extraer_adjuntos(msg)
        imagenes_inline = _extraer_imagenes_inline(msg)

        correo['cuerpo'] = cuerpo[:5000]
        correo['cuerpo_corto'] = cuerpo[:200]
        correo['html_raw'] = html_raw
        correo['adjuntos'] = adjuntos
        correo['imagenes_inline'] = imagenes_inline
        correo['tiene_adjuntos'] = len(adjuntos) > 0
        correo['tiene_html'] = bool(html_raw)
        correo['tiene_imagenes'] = len(imagenes_inline) > 0
        correo['contenido_cargado'] = True

        # Actualizar en session_state
        pendientes = st.session_state.get('_correos_pendientes', [])
        for c in pendientes:
            if c['message_id'] == correo['message_id']:
                c.update(correo)
                break

        return correo

    except socket.timeout:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = '[Timeout descargando contenido]'
        return correo
    except Exception as e:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = f'[Error: {e}]'
        return correo
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# ==============================================================================
# 🔍 COMPARACIÓN GMAIL vs BASE DE DATOS
# ==============================================================================
def comparar_gmail_vs_bd(max_correos=100, dias_atras=30):
    """
    Compara TODOS los correos de la bandeja de Gmail contra la base de datos
    (emails_procesados + emails_pendientes) para encontrar correos en limbo.
    """
    import socket
    from utils.db import supabase

    resultado = {
        'gmail_total': 0,
        'gmail_headers': [],
        'bd_procesados': set(),
        'bd_pendientes': set(),
        'en_limbo': [],
        'en_bd_no_gmail': [],
        'errores': [],
    }

    # 1. Obtener message_ids de la BD
    if supabase:
        try:
            res_proc = supabase.table("emails_procesados").select("message_id").execute()
            resultado['bd_procesados'] = {r['message_id'].strip() for r in (res_proc.data or []) if r.get('message_id')}
        except Exception as e:
            resultado['errores'].append(f"Error emails_procesados: {e}")

        try:
            res_pend = supabase.table("emails_pendientes").select("message_id").execute()
            resultado['bd_pendientes'] = {r['message_id'].strip() for r in (res_pend.data or []) if r.get('message_id')}
        except Exception as e:
            resultado['errores'].append(f"Error emails_pendientes: {e}")

    bd_todos = resultado['bd_procesados'] | resultado['bd_pendientes']

    # 2. Conectar a Gmail y obtener headers
    mail = _conectar_imap()
    if not mail:
        resultado['errores'].append("No se pudo conectar a Gmail")
        return resultado

    try:
        mail.select("INBOX")

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
        resultado['gmail_total'] = len(ids)

        gmail_message_ids = set()

        for i, msg_id in enumerate(ids):
            try:
                socket.setdefaulttimeout(15)
                status, datos = mail.fetch(msg_id, "(BODY[HEADER.FIELDS (MESSAGE-ID FROM SUBJECT DATE)])")
                if status != "OK" or not datos or not datos[0]:
                    continue

                header_bytes = datos[0][1] if isinstance(datos[0], tuple) else datos[0]
                if not isinstance(header_bytes, bytes):
                    continue

                msg_h = email.message_from_bytes(header_bytes)
                mid = (msg_h.get("Message-ID") or "").strip()
                if not mid:
                    mid = f"imap_{msg_id.decode()}"

                asunto = _decodificar_header(msg_h.get("Subject", ""))
                remitente = _decodificar_header(msg_h.get("From", ""))
                fecha = msg_h.get("Date", "")

                gmail_message_ids.add(mid)

                en_procesados = mid in resultado['bd_procesados']
                en_pendientes = mid in resultado['bd_pendientes']

                resultado['gmail_headers'].append({
                    'message_id': mid,
                    'asunto': asunto,
                    'remitente': remitente,
                    'fecha': fecha,
                    'en_procesados': en_procesados,
                    'en_pendientes': en_pendientes,
                    'en_alguna_tabla': en_procesados or en_pendientes,
                })

            except socket.timeout:
                continue
            except Exception as e:
                resultado['errores'].append(f"Error header {i}: {e}")
                continue

        # 3. Correos en limbo
        resultado['en_limbo'] = [
            h for h in resultado['gmail_headers']
            if not h['en_alguna_tabla']
        ]

        # 4. En BD pero no en Gmail
        resultado['en_bd_no_gmail'] = [
            mid for mid in bd_todos
            if mid not in gmail_message_ids
        ]

        return resultado

    except Exception as e:
        resultado['errores'].append(f"Error general: {e}")
        return resultado
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def render_comparacion_gmail_bd():
    """Renderiza la comparación completa Gmail vs Base de Datos."""
    st.markdown("### 🔍 Comparación Gmail vs Base de Datos")
    st.caption("Compara la bandeja de Gmail con las tablas de la BD para encontrar correos en limbo.")

    col1, col2 = st.columns(2)
    with col1:
        max_corr = st.number_input("Máximo correos", min_value=10, max_value=500, value=100, step=10, key="cmp_max")
    with col2:
        dias = st.number_input("Días hacia atrás", min_value=1, max_value=365, value=30, step=1, key="cmp_dias")

    if st.button("🔍 Ejecutar Comparación", type="primary", use_container_width=True, key="cmp_btn"):
        with st.spinner(f"Conectando a Gmail y comparando (hasta {max_corr} correos, {dias} días)..."):
            datos = comparar_gmail_vs_bd(max_correos=max_corr, dias_atras=dias)

        for err in datos['errores']:
            st.error(f"❌ {err}")

        gmail_total = datos['gmail_total']
        procesados = len(datos['bd_procesados'])
        pendientes = len(datos['bd_pendientes'])
        en_limbo = len(datos['en_limbo'])
        en_bd_no_gmail = len(datos['en_bd_no_gmail'])

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("📧 Gmail", gmail_total)
        c2.metric("✅ Procesados", procesados)
        c3.metric("💾 Pendientes", pendientes)
        c4.metric("⚠️ En Limbo", en_limbo)
        c5.metric("👻 BD sin Gmail", en_bd_no_gmail)

        st.markdown("---")

        if datos['en_limbo']:
            st.markdown(f"#### ⚠️ Correos en LIMBO ({en_limbo})")
            st.caption("En Gmail pero NO en `emails_procesados` ni `emails_pendientes`.")
            for h in datos['en_limbo']:
                asunto = (h.get('asunto', '') or '')[:70]
                remitente = (h.get('remitente', '') or '')[:50]
                fecha = (h.get('fecha', '') or '')[:25]
                mid = h.get('message_id', '?')[:60]
                st.markdown(f"""
                <div style="border-left:3px solid #EF4444;padding:10px 14px;margin-bottom:6px;background:rgba(239,68,68,0.05);border-radius:0 6px 6px 0;">
                    <div style="display:flex;justify-content:space-between;">
                        <span style="color:#EF4444;font-weight:600;">📧 {asunto}</span>
                        <span style="color:#6B7280;font-size:0.8em;">{fecha}</span>
                    </div>
                    <div style="color:#9CA3AF;font-size:0.85em;">👤 {remitente}</div>
                    <div style="color:#6B7280;font-size:0.75em;">ID: {mid}</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")
            if st.button("💾 Guardar todos como PENDIENTES", type="secondary", use_container_width=True, key="cmp_guardar"):
                guardados = 0
                for h in datos['en_limbo']:
                    try:
                        _guardar_correo_pendiente({
                            'message_id': h['message_id'],
                            'remitente': h.get('remitente', ''),
                            'remitente_nombre': '',
                            'asunto': h.get('asunto', ''),
                            'fecha': h.get('fecha', ''),
                            'cuerpo_corto': '',
                            'adjuntos': [],
                            'leido': False,
                        })
                        guardados += 1
                    except Exception:
                        pass
                st.success(f"✅ {guardados} correos guardados como pendientes.")
                st.rerun()
        else:
            st.success("✅ Sin correos en limbo.")

        if datos['en_bd_no_gmail']:
            st.markdown(f"#### 👻 En BD pero NO en Gmail ({en_bd_no_gmail})")
            for mid in datos['en_bd_no_gmail'][:20]:
                st.caption(f"📧 {mid[:80]}")

        if datos['gmail_headers']:
            with st.expander(f"📋 Todos los {len(datos['gmail_headers'])} correos", expanded=False):
                for h in datos['gmail_headers']:
                    icon = "✅" if h['en_procesados'] else "💾" if h['en_pendientes'] else "⚠️"
                    txt = "Procesado" if h['en_procesados'] else "Pendiente" if h['en_pendientes'] else "LIMBO"
                    color = "#10B981" if h['en_procesados'] else "#3B82F6" if h['en_pendientes'] else "#EF4444"
                    st.markdown(f'<div style="border-left:2px solid {color};padding:4px 10px;margin-bottom:3px;font-size:0.85em;">{icon} <b>{txt}</b> | {(h.get("asunto",""))[:50]} | 👤 {(h.get("remitente",""))[:30]}</div>', unsafe_allow_html=True)


# ==============================================================================
# 🩺 DIAGNÓSTICO Y AUDITORÍA
# ==============================================================================
def barrido_base_datos_correos():
    """
    Barrido completo de la base de datos de correos.
    Muestra el estado REAL de todos los correos: procesados, rechazados,
    vinculados, pendientes, y cruza con órdenes creadas.
    Retorna un dict con toda la info para renderizar.
    """
    from utils.db import supabase

    resultado = {
        'procesados': [],
        'ordenes_desde_correo': [],
        'solicitudes_correo': [],
        'resumen': {},
    }

    if not supabase:
        return resultado

    # 1. Todos los correos procesados
    try:
        res = supabase.table("emails_procesados").select("*").order("fecha_procesado", desc=True).execute()
        resultado['procesados'] = res.data or []
    except Exception as e:
        print(f"⚠️ Error consultando emails_procesados: {e}")

    # 2. Órdenes creadas desde correo (campo origen='correo' o que tengan correo_message_id)
    try:
        res_ord = supabase.table("ordenes").select("*").eq("origen", "correo").order("id", desc=True).execute()
        resultado['ordenes_desde_correo'] = res_ord.data or []
    except Exception as e:
        print(f"⚠️ Error consultando órdenes desde correo: {e}")
        # Fallback: buscar por correo_message_id no nulo
        try:
            res_ord2 = supabase.table("ordenes").select("*").not_.is_("correo_message_id", "null").order("id", desc=True).execute()
            resultado['ordenes_desde_correo'] = res_ord2.data or []
        except Exception:
            pass

    # 3. Solicitudes que vienen de correo (si existe el campo)
    try:
        res_sol = supabase.table("solicitudes").select("*").order("id", desc=True).limit(100).execute()
        resultado['solicitudes_correo'] = [
            s for s in (res_sol.data or [])
            if s.get('origen') == 'correo' or s.get('chat_id', '').startswith('email')
        ]
    except Exception:
        pass

    # 4. Resumen estadístico
    procesados = resultado['procesados']
    ordenes = resultado['ordenes_desde_correo']

    acciones = {}
    for p in procesados:
        acc = p.get('accion', 'desconocido')
        acciones[acc] = acciones.get(acc, 0) + 1

    resultado['resumen'] = {
        'total_procesados': len(procesados),
        'total_ordenes_correo': len(ordenes),
        'por_accion': acciones,
        'con_orden': len([p for p in procesados if p.get('orden_id')]),
        'sin_orden': len([p for p in procesados if not p.get('orden_id')]),
    }

    return resultado


def render_auditoria_correos():
    """
    Renderiza la página de auditoría completa de correos.
    Muestra: procesados, rechazados, vinculados, pendientes, cruza con OTs,
    Y detecta correos en limbo comparando con Gmail en tiempo real.
    """
    st.markdown("### 🔍 Auditoría de Correos")
    st.caption("Estado real de todos los correos + detección de correos en limbo vs Gmail.")

    datos = barrido_base_datos_correos()
    resumen = datos['resumen']

    # ── Métricas principales ──
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📨 Total Procesados", resumen['total_procesados'])
    col2.metric("🛠️ Órdenes desde Correo", resumen['total_ordenes_correo'])
    col3.metric("🔗 Con OT Asignada", resumen['con_orden'])
    col4.metric("⚠️ Sin OT Asignada", resumen['sin_orden'])

    st.markdown("---")

    # ── Desglose por acción ──
    por_accion = resumen.get('por_accion', {})
    iconos_accion = {
        'orden': '✅', 'avance': '🔗', 'descartado': '🗑️',
        'rechazado': '❌', 'desconocido': '❓',
    }
    if por_accion:
        st.markdown("#### 📊 Desglose por Acción")
        acc_cols = st.columns(len(por_accion))
        for i, (accion, count) in enumerate(por_accion.items()):
            with acc_cols[i]:
                icono = iconos_accion.get(accion, '📋')
                st.metric(f"{icono} {accion.capitalize()}", count)

    st.markdown("---")

    # ── 🔍 DETECCIÓN DE CORREOS EN LIMBO (comparar Gmail vs BD) ──
    st.markdown("#### 🩺 Detección de Correos en Limbo")
    st.caption("Compara la bandeja de Gmail con la base de datos para encontrar correos que se escaparon.")

    col_cfg1, col_cfg2, col_cfg3 = st.columns([1, 1, 1])
    with col_cfg1:
        max_corr_aud = st.number_input("Máx. correos Gmail", min_value=20, max_value=500, value=100, step=10, key="aud_max_corr")
    with col_cfg2:
        dias_aud = st.number_input("Días hacia atrás", min_value=1, max_value=365, value=30, step=1, key="aud_dias")
    with col_cfg3:
        st.markdown("<br>", unsafe_allow_html=True)
        ejecutar_cmp = st.button("🔍 Escanear Gmail vs BD", type="primary", use_container_width=True, key="aud_btn_cmp")

    if ejecutar_cmp:
        with st.spinner(f"Conectando a Gmail y comparando (hasta {max_corr_aud} correos, {dias_aud} días)..."):
            datos_cmp = comparar_gmail_vs_bd(max_correos=max_corr_aud, dias_atras=dias_aud)

        for err in datos_cmp['errores']:
            st.error(f"❌ {err}")

        gmail_total = datos_cmp['gmail_total']
        en_limbo = len(datos_cmp['en_limbo'])
        bd_proc = len(datos_cmp['bd_procesados'])
        bd_pend = len(datos_cmp['bd_pendientes'])

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("📧 Gmail", gmail_total)
        m2.metric("✅ BD Procesados", bd_proc)
        m3.metric("💾 BD Pendientes", bd_pend)
        m4.metric("🔴 En LIMBO", en_limbo, delta=f"-{en_limbo} sin gestionar" if en_limbo > 0 else None,
                   delta_color="inverse" if en_limbo > 0 else "off")

        if datos_cmp['en_limbo']:
            st.error(f"⚠️ **{en_limbo} correos están en LIMBO** — en Gmail pero no en `emails_procesados` ni `emails_pendientes`.")
            st.markdown(f"##### 📋 Correos en LIMBO ({en_limbo})")

            for i, h in enumerate(datos_cmp['en_limbo']):
                asunto = (h.get('asunto', '') or '')[:70]
                remitente = (h.get('remitente', '') or '')[:50]
                fecha = (h.get('fecha', '') or '')[:25]
                mid = h.get('message_id', '?')[:60]

                col_info_l, col_acc_l = st.columns([4, 2])
                with col_info_l:
                    st.markdown(f"""
                    <div style="border-left:3px solid #EF4444;padding:8px 12px;margin-bottom:4px;background:rgba(239,68,68,0.05);border-radius:0 6px 6px 0;">
                        <div style="color:#EF4444;font-weight:600;font-size:0.9em;">📧 {asunto}</div>
                        <div style="color:#9CA3AF;font-size:0.8em;">👤 {remitente} · {fecha}</div>
                        <div style="color:#6B7280;font-size:0.7em;">ID: {mid}</div>
                    </div>
                    """, unsafe_allow_html=True)
                with col_acc_l:
                    c_desc_l, c_pend_l = st.columns(2)
                    with c_desc_l:
                        if st.button("🗑️", key=f"aud_desc_{i}", help="Descartar", use_container_width=True):
                            _marcar_procesado(h['message_id'], accion="descartado")
                            st.toast(f"🗑️ Descartado: {asunto[:30]}")
                            st.rerun()
                    with c_pend_l:
                        if st.button("💾", key=f"aud_pend_{i}", help="Guardar como pendiente", use_container_width=True):
                            _guardar_correo_pendiente({
                                'message_id': h['message_id'],
                                'remitente': h.get('remitente', ''),
                                'remitente_nombre': '',
                                'asunto': h.get('asunto', ''),
                                'fecha': h.get('fecha', ''),
                                'cuerpo_corto': '',
                                'adjuntos': [],
                                'leido': False,
                            })
                            st.toast(f"💾 Guardado como pendiente: {asunto[:30]}")
                            st.rerun()

            # Acciones masivas
            st.markdown("---")
            col_mas1, col_mas2 = st.columns(2)
            with col_mas1:
                if st.button("💾 Guardar TODOS como pendientes", type="secondary", use_container_width=True, key="aud_guardar_todos"):
                    guardados = 0
                    for h in datos_cmp['en_limbo']:
                        try:
                            _guardar_correo_pendiente({
                                'message_id': h['message_id'],
                                'remitente': h.get('remitente', ''),
                                'remitente_nombre': '',
                                'asunto': h.get('asunto', ''),
                                'fecha': h.get('fecha', ''),
                                'cuerpo_corto': '',
                                'adjuntos': [],
                                'leido': False,
                            })
                            guardados += 1
                        except Exception:
                            pass
                    st.success(f"✅ {guardados} correos guardados como pendientes.")
                    st.rerun()
            with col_mas2:
                if st.button("🗑️ Descartar TODOS los limbo", type="secondary", use_container_width=True, key="aud_desc_todos"):
                    descartados = 0
                    for h in datos_cmp['en_limbo']:
                        try:
                            _marcar_procesado(h['message_id'], accion="descartado")
                            descartados += 1
                        except Exception:
                            pass
                    st.success(f"🗑️ {descartados} correos descartados.")
                    st.rerun()
        else:
            st.success("✅ **Sin correos en limbo.** Todos los correos de Gmail están en la base de datos.")

        # ── En BD pero no en Gmail ──
        if datos_cmp['en_bd_no_gmail']:
            st.markdown(f"##### 👻 En BD pero NO en Gmail ({len(datos_cmp['en_bd_no_gmail'])})")
            st.caption("Estos message_ids están en la BD pero Gmail ya no los tiene (eliminados o movidos).")
            for mid in datos_cmp['en_bd_no_gmail'][:20]:
                st.caption(f"📧 {mid[:80]}")

        # ── Tabla completa ──
        if datos_cmp['gmail_headers']:
            with st.expander(f"📋 Ver todos los {len(datos_cmp['gmail_headers'])} correos escaneados", expanded=False):
                for h in datos_cmp['gmail_headers']:
                    icon = "✅" if h['en_procesados'] else "💾" if h['en_pendientes'] else "⚠️"
                    txt = "Procesado" if h['en_procesados'] else "Pendiente" if h['en_pendientes'] else "LIMBO"
                    color = "#10B981" if h['en_procesados'] else "#3B82F6" if h['en_pendientes'] else "#EF4444"
                    st.markdown(f'<div style="border-left:2px solid {color};padding:4px 10px;margin-bottom:3px;font-size:0.85em;">{icon} <b>{txt}</b> | {(h.get("asunto",""))[:50]} | 👤 {(h.get("remitente",""))[:30]}</div>', unsafe_allow_html=True)

        st.markdown("---")

    # ── Tabla detallada de procesados ──
    procesados = datos['procesados']
    if procesados:
        st.markdown("#### 📋 Historial Completo de Correos Procesados")

        # Filtro por acción
        acciones_disponibles = ['Todas'] + list(por_accion.keys())
        filtro_accion = st.selectbox("Filtrar por acción", acciones_disponibles, key="filtro_accion_correo")

        filtrados = procesados
        if filtro_accion != 'Todas':
            filtrados = [p for p in procesados if p.get('accion') == filtro_accion]

        for p in filtrados:
            accion = p.get('accion', '?')
            icono = iconos_accion.get(accion, '📋')
            orden_id = p.get('orden_id')
            msg_id = p.get('message_id', '?')[:40]
            fecha = (p.get('fecha_procesado', '') or '')[:16].replace('T', ' ')

            color_accion = {
                'orden': '#10B981', 'avance': '#3B82F6', 'descartado': '#6B7280',
                'rechazado': '#EF4444',
            }.get(accion, '#F59E0B')

            orden_link = f"→ **OT #{orden_id}**" if orden_id else "→ Sin OT asignada"

            st.markdown(f"""
            <div style="border-left:3px solid {color_accion};padding:8px 14px;margin-bottom:6px;background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0;">
                <div style="display:flex;justify-content:space-between;">
                    <span>{icono} <b>{accion.upper()}</b> {orden_link}</span>
                    <span style="color:#6B7280;font-size:0.8em;">{fecha}</span>
                </div>
                <div style="color:#9CA3AF;font-size:0.8em;margin-top:2px;">Message-ID: {msg_id}...</div>
            </div>
            """, unsafe_allow_html=True)

    # ── Órdenes creadas desde correo ──
    ordenes_correo = datos['ordenes_desde_correo']
    if ordenes_correo:
        st.markdown("---")
        st.markdown(f"#### 🛠️ Órdenes Creadas desde Correo ({len(ordenes_correo)})")

        for orden in ordenes_correo:
            estado = orden.get('estado', '?')
            icono_estado = {'Abierta': '🔨', 'Por Validar': '🧐', 'Concluida': '✅', 'Cancelada': '❌'}.get(estado, '📋')
            fecha = (orden.get('fecha_creacion', '') or '')[:10]
            desc = (orden.get('descripcion', '') or '')[:80]
            msg_id = orden.get('correo_message_id', '')

            st.markdown(f"""
            <div style="border-left:3px solid #F59E0B;padding:8px 14px;margin-bottom:6px;background:rgba(255,255,255,0.02);border-radius:0 6px 6px 0;">
                <div style="display:flex;justify-content:space-between;">
                    <span>{icono_estado} <b>OT #{orden['id']}</b> — {estado}</span>
                    <span style="color:#6B7280;font-size:0.8em;">{fecha}</span>
                </div>
                <div style="color:#D1D5DB;font-size:0.85em;margin-top:2px;">{desc}</div>
                {'<div style="color:#6B7280;font-size:0.75em;">📧 ' + msg_id[:50] + '</div>' if msg_id else ''}
            </div>
            """, unsafe_allow_html=True)

    # ── Correos huérfanos (en procesados pero sin orden ni acción clara) ──
    huerfanos = [p for p in procesados if not p.get('orden_id') and p.get('accion') not in ('descartado', 'rechazado')]
    if huerfanos:
        st.markdown("---")
        st.markdown(f"#### ⚠️ Correos Huérfanos — Procesados sin OT ({len(huerfanos)})")
        st.caption("Estos correos están marcados como procesados pero no tienen orden asignada ni fueron descartados explícitamente.")
        for p in huerfanos:
            msg_id = p.get('message_id', '?')[:50]
            fecha = (p.get('fecha_procesado', '') or '')[:16].replace('T', ' ')
            accion = p.get('accion', '?')
            st.warning(f"📧 {msg_id} — Acción: {accion} — Fecha: {fecha}")

    # ── Si no hay nada ──
    if not procesados and not ordenes_correo and not ejecutar_cmp:
        st.info("📭 No hay registros de correos procesados en la base de datos. Usa **Escanear Gmail vs BD** arriba para comparar directamente con Gmail.")


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
# 🔗 VINCULACIÓN DE CORREOS A ÓRDENES EXISTENTES
# ==============================================================================
def vincular_correo_a_orden(correo: dict, orden_id: int) -> bool:
    """
    Vincula un correo del buzón como avance de una orden de trabajo existente.
    - Crea una entrada compacta en bitácora con resumen
    - Sube el correo completo como archivo adjunto (HTML)
    - Sube adjuntos e imágenes inline del correo
    - Marca el correo como procesado con accion='avance'
    Retorna True si fue exitoso.
    """
    from utils.db import db_insert

    try:
        remitente = correo.get('remitente_nombre') or correo.get('remitente', 'Desconocido')
        asunto = correo.get('asunto', '(Sin asunto)')
        fecha_correo = (correo.get('fecha', '') or '')[:16].replace('T', ' ')

        # 1. Generar archivo HTML del correo completo y subirlo
        url_correo = _generar_y_subir_correo_html(correo, orden_id)

        # 2. Entrada compacta en bitácora
        n_adj = len(correo.get('adjuntos', []))
        adj_tag = f" · 📎 {n_adj} adjunto(s)" if n_adj > 0 else ""
        cuerpo_corto = (correo.get('cuerpo', '') or '')[:150].replace('\n', ' ')
        if len((correo.get('cuerpo', '') or '')) > 150:
            cuerpo_corto += "..."

        mensaje = f"📧 {asunto}{adj_tag}"
        if cuerpo_corto:
            mensaje += f"\n💬 \"{cuerpo_corto}\""

        datos_bitacora = {
            "orden_id": orden_id,
            "usuario_text": f"📧 {remitente}",
            "mensaje": mensaje,
            "fecha": datetime.now().isoformat(),
        }
        if url_correo:
            datos_bitacora["archivo_url"] = url_correo
        db_insert("bitacora", datos_bitacora)

        # 3. Subir adjuntos del correo
        adjuntos = correo.get('adjuntos', [])
        if adjuntos:
            _subir_adjuntos_correo(adjuntos, orden_id)

        # 4. Subir imágenes inline
        imagenes_inline = correo.get('imagenes_inline', {})
        if imagenes_inline:
            from utils.uploads import subir_archivo_generico as _subir_img
            for cid, img in imagenes_inline.items():
                try:
                    img_bytes = base64.b64decode(img['datos_b64'])
                    archivo_img = _ArchivoDesdeBytes(img_bytes, f"inline_{cid}.jpg")
                    url_img = _subir_img(archivo_img)
                    if url_img:
                        db_insert("bitacora", {
                            "orden_id": orden_id,
                            "usuario_text": f"📧 {remitente}",
                            "mensaje": f"🖼️ Imagen del correo",
                            "archivo_url": url_img,
                            "fecha": datetime.now().isoformat(),
                        })
                except Exception as e_img:
                    print(f"⚠️ Error subiendo inline {cid}: {e_img}")

        # 5. Marcar correo como procesado
        _marcar_procesado(correo['message_id'], orden_id=orden_id, accion="avance")
        print(f"✅ Correo vinculado a OT #{orden_id}: {asunto[:50]}")
        return True

    except Exception as e:
        print(f"❌ Error vinculando correo a OT #{orden_id}: {e}")
        return False


def _generar_y_subir_correo_html(correo: dict, orden_id: int) -> str | None:
    """
    Genera un archivo HTML con el contenido completo del correo y lo sube a Cloudinary.
    Retorna la URL del archivo subido, o None si falla.
    """
    from utils.uploads import subir_archivo_generico

    try:
        remitente = correo.get('remitente_nombre') or correo.get('remitente', 'Desconocido')
        asunto = correo.get('asunto', '(Sin asunto)')
        fecha_correo = correo.get('fecha', '')
        cuerpo = correo.get('cuerpo', '') or ''
        html_raw = correo.get('html_raw', '')

        # Si hay HTML original, usarlo; si no, generar uno limpio
        if html_raw:
            contenido = html_raw
        else:
            # Convertir texto plano a HTML básico
            import html as html_mod
            cuerpo_escapado = html_mod.escape(cuerpo).replace('\n', '<br>')
            contenido = f"""
            <div style="font-family:Arial,sans-serif;max-width:700px;padding:20px;">
                <div style="border-bottom:2px solid #3B82F6;padding-bottom:12px;margin-bottom:16px;">
                    <h2 style="color:#1E40AF;margin:0;">📧 {html_mod.escape(asunto)}</h2>
                    <p style="color:#6B7280;margin:4px 0 0;">De: {html_mod.escape(remitente)} · {html_mod.escape(fecha_correo)}</p>
                </div>
                <div style="line-height:1.6;color:#374151;">{cuerpo_escapado}</div>
            </div>
            """

        # Sanitizar scripts
        contenido = re.sub(r'<script[^>]*>.*?</script>', '', contenido, flags=re.DOTALL | re.IGNORECASE)
        contenido = re.sub(r'<iframe[^>]*>.*?</iframe>', '', contenido, flags=re.DOTALL | re.IGNORECASE)

        # Envolver en documento HTML completo
        html_completo = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{asunto}</title></head>
<body style="margin:0;padding:0;background:#f9fafb;">{contenido}</body></html>"""

        # Subir como archivo
        archivo_bytes = html_completo.encode('utf-8')
        nombre_archivo = f"correo_{orden_id}_{asunto[:30].replace(' ', '_')}.html"
        archivo = _ArchivoDesdeBytes(archivo_bytes, nombre_archivo)
        url = subir_archivo_generico(archivo)
        return url

    except Exception as e:
        print(f"⚠️ Error generando HTML del correo: {e}")
        return None


def obtener_correos_no_vinculados():
    """
    Obtiene correos del buzón que aún no están vinculados a ninguna orden.
    Retorna lista de correos pendientes (no procesados).
    """
    correos = st.session_state.get('_correos_pendientes', [])
    if not correos:
        return []

    procesados = _obtener_procesados()
    return [c for c in correos if c['message_id'] not in procesados]


# ==============================================================================
# 🔄 MIGRACIÓN: CONVERTIR ENTRADAS ANTIGUAS DE BITÁCORA A FORMATO COMPACTO
# ==============================================================================
def migrar_correos_antiguos_bitacora(orden_id: int = None):
    """
    Busca entradas antiguas en la bitácora donde el correo fue vinculado
    con el formato viejo (todo el cuerpo en el mensaje) y las convierte
    al formato compacto (resumen + archivo HTML adjunto).

    Si orden_id se especifica, solo migra esa orden. Si es None, migra todas.
    Retorna (n_migrados, n_total_encontrados).
    """
    from utils.db import supabase, db_update

    try:
        # Buscar entradas con el formato antiguo
        # Patrón: usuario_text empieza con "CORREO (" y el mensaje contiene
        # "📧 Correo de seguimiento vinculado" o tiene más de 300 chars
        query = supabase.table("bitacora").select("*")
        if orden_id:
            query = query.eq("orden_id", int(orden_id))

        res = query.execute()
        if not res.data:
            return 0, 0

        entradas_antiguas = []
        for b in res.data:
            usuario = b.get('usuario_text', '') or ''
            mensaje = b.get('mensaje', '') or ''

            # Detectar formato antiguo: usuario_text = "CORREO (...)" y mensaje largo
            es_correo_antiguo = (
                usuario.startswith('CORREO (')
                and ('📧 Correo de seguimiento vinculado' in mensaje or len(mensaje) > 300)
                and 'Creada desde correo' not in mensaje  # Excluir la entrada de creación
            )
            if es_correo_antiguo:
                entradas_antiguas.append(b)

        if not entradas_antiguas:
            return 0, 0

        n_migrados = 0
        for entrada in entradas_antiguas:
            try:
                # Extraer datos del mensaje antiguo
                mensaje_viejo = entrada.get('mensaje', '') or ''
                usuario_viejo = entrada.get('usuario_text', '') or ''

                # Extraer remitente del usuario_text: "CORREO (nombre)" → "nombre"
                remitente = usuario_viejo
                if usuario_viejo.startswith('CORREO (') and usuario_viejo.endswith(')'):
                    remitente = usuario_viejo[8:-1]

                # Extraer asunto del mensaje
                asunto = '(Sin asunto)'
                for linea in mensaje_viejo.split('\n'):
                    if linea.startswith('Asunto:'):
                        asunto = linea[7:].strip()
                        break

                # Extraer cuerpo (todo después de la primera línea vacía)
                cuerpo = ''
                lineas = mensaje_viejo.split('\n')
                en_cuerpo = False
                cuerpo_lineas = []
                for linea in lineas:
                    if en_cuerpo:
                        cuerpo_lineas.append(linea)
                    elif linea.strip() == '' and 'Asunto:' in mensaje_viejo:
                        en_cuerpo = True
                cuerpo = '\n'.join(cuerpo_lineas).strip()

                # Limpiar HTML del cuerpo (puede venir del correo original)
                cuerpo = _html_a_texto(cuerpo) if '<' in cuerpo else cuerpo
                # Quitar líneas vacías excesivas
                cuerpo = re.sub(r'\n{3,}', '\n\n', cuerpo).strip()

                # Generar archivo HTML y subirlo
                import html as html_mod
                cuerpo_escapado = html_mod.escape(cuerpo).replace('\n', '<br>')
                html_content = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{html_mod.escape(asunto)}</title></head>
<body style="margin:0;padding:0;background:#f9fafb;">
<div style="font-family:Arial,sans-serif;max-width:700px;padding:20px;">
    <div style="border-bottom:2px solid #3B82F6;padding-bottom:12px;margin-bottom:16px;">
        <h2 style="color:#1E40AF;margin:0;">📧 {html_mod.escape(asunto)}</h2>
        <p style="color:#6B7280;margin:4px 0 0;">De: {html_mod.escape(remitente)}</p>
    </div>
    <div style="line-height:1.6;color:#374151;">{cuerpo_escapado}</div>
</div>
</body></html>"""

                url_correo = None
                try:
                    from utils.uploads import subir_archivo_generico
                    archivo_bytes = html_content.encode('utf-8')
                    nombre_archivo = f"correo_{entrada['orden_id']}_{asunto[:30].replace(' ', '_')}.html"
                    archivo = _ArchivoDesdeBytes(archivo_bytes, nombre_archivo)
                    url_correo = subir_archivo_generico(archivo)
                except Exception as e_html:
                    print(f"⚠️ Error subiendo HTML migrado: {e_html}")

                # Construir mensaje compacto
                cuerpo_corto = cuerpo[:150].replace('\n', ' ').strip()
                if len(cuerpo) > 150:
                    cuerpo_corto += "..."
                mensaje_nuevo = f"📧 {asunto}"
                if cuerpo_corto:
                    mensaje_nuevo += f'\n💬 "{cuerpo_corto}"'

                # Actualizar registro
                datos_update = {
                    "usuario_text": f"📧 {remitente}",
                    "mensaje": mensaje_nuevo,
                }
                if url_correo:
                    datos_update["archivo_url"] = url_correo

                db_update("bitacora", datos_update, "id", entrada['id'])
                n_migrados += 1
                print(f"✅ Migrado bitácora #{entrada['id']} (OT #{entrada['orden_id']})")

            except Exception as e_entry:
                print(f"⚠️ Error migrando entrada #{entrada.get('id')}: {e_entry}")

        return n_migrados, len(entradas_antiguas)

    except Exception as e:
        print(f"❌ Error en migración de bitácora: {e}")
        return 0, 0


def render_selector_ordenes_para_vincular(correo_idx: int, correo: dict, df_ordenes, df_act):
    """
    Renderiza un selector con búsqueda para que el usuario elija a qué orden vincular un correo.
    Permite buscar por ID, nombre de activo o descripción.
    """
    from utils.db import db_insert

    # Filtrar órdenes activas
    ordenes_activas = df_ordenes[df_ordenes['estado'].isin(['Abierta', 'Por Validar'])].copy()

    if ordenes_activas.empty:
        st.info("No hay órdenes abiertas para vincular. Crea una orden primero.")
        return

    # Mapear activos
    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    ordenes_activas['Activo'] = ordenes_activas['activo_id'].map(map_act).fillna("Sin activo")

    st.markdown("**🔗 Vincular a orden existente:**")

    # ── Búsqueda por texto ──
    col_buscar, col_filtro = st.columns([3, 2])
    with col_buscar:
        texto_busqueda = st.text_input(
            "🔍 Buscar",
            placeholder="ID, activo o descripción...",
            key=f"vincular_buscar_{correo_idx}",
            label_visibility="collapsed",
        )
    with col_filtro:
        activos_filtro = ["Todos"] + sorted(
            [a for a in ordenes_activas['Activo'].unique() if a != "Sin activo"]
        )
        filtro_activo = st.selectbox(
            "Filtrar activo",
            activos_filtro,
            key=f"vincular_filtro_act_{correo_idx}",
            label_visibility="collapsed",
        )

    # ── Aplicar filtros ──
    df_filtrado = ordenes_activas.copy()

    if filtro_activo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Activo'] == filtro_activo]

    if texto_busqueda.strip():
        q = texto_busqueda.strip().lower()
        # Buscar por ID exacto
        if q.isdigit():
            df_filtrado = df_filtrado[df_filtrado['id'] == int(q)]
        else:
            # Buscar en activo y descripción
            mask = (
                df_filtrado['Activo'].str.lower().str.contains(q, na=False) |
                df_filtrado['descripcion'].str.lower().str.contains(q, na=False)
            )
            df_filtrado = df_filtrado[mask]

    # ── Mostrar resultados ──
    if df_filtrado.empty:
        st.warning("No se encontraron órdenes con ese criterio.")
        return

    st.caption(f"{len(df_filtrado)} orden(es) encontrada(s)")

    # Construir opciones
    opciones = []
    opciones_map = {}
    for _, row in df_filtrado.iterrows():
        oid = int(row['id'])
        desc_corta = (row.get('descripcion', '') or '')[:50]
        estado = row.get('estado', '?')
        icono = "🔨" if estado == "Abierta" else "🧐"
        label = f"{icono} OT #{oid} — {row.get('Activo', '?')} — {desc_corta}"
        opciones.append(label)
        opciones_map[label] = oid

    orden_sel = st.selectbox(
        "Seleccionar orden",
        opciones,
        key=f"vincular_sel_{correo_idx}",
        label_visibility="collapsed",
    )

    col_vinc, col_cancel = st.columns([2, 2])
    with col_vinc:
        vincular_clicked = st.button(
            "✅ Vincular como avance",
            key=f"btn_vincular_confirm_{correo_idx}",
            type="primary",
            use_container_width=True,
        )
    with col_cancel:
        cancelar_clicked = st.button(
            "❌ Cancelar",
            key=f"btn_cancelar_vinc_confirm_{correo_idx}",
            use_container_width=True,
        )

    if cancelar_clicked:
        st.session_state.pop(f'_vincular_ot_{correo_idx}', None)
        st.rerun()

    if vincular_clicked:
        orden_id = opciones_map[orden_sel]
        with st.spinner(f"Vinculando correo a OT #{orden_id}..."):
            exito = vincular_correo_a_orden(correo, orden_id)
        if exito:
            # Quitar de la lista local
            pendientes = st.session_state.get('_correos_pendientes', [])
            st.session_state['_correos_pendientes'] = [
                c for c in pendientes if c['message_id'] != correo['message_id']
            ]
            _eliminar_pendiente(correo['message_id'])
            st.session_state.pop(f'_vincular_ot_{correo_idx}', None)
            st.success(f"✅ Correo vinculado como avance de OT #{orden_id}")
            st.rerun()
        else:
            st.error("❌ No se pudo vincular el correo. Intenta de nuevo.")


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
    col_btn, col_info, col_cmp = st.columns([1, 2, 1])
    with col_btn:
        if st.button("🔄 Revisar Correo", type="primary", use_container_width=True):
            # Diagnóstico paso a paso
            st.markdown("---")
            st.markdown("#### 🩺 Diagnóstico en tiempo real")

            # Paso 1: Credenciales
            st.markdown("**1️⃣ Verificando credenciales...**")
            correo_cfg, password_cfg = _obtener_credenciales()
            if not correo_cfg:
                st.error("❌ `correo` no configurado en [gmail] de secrets.toml")
                st.stop()
            if not password_cfg:
                st.error("❌ `password` no configurado en [gmail] de secrets.toml")
                st.stop()
            st.success(f"✅ Credenciales OK: `{correo_cfg}`")

            # Paso 2: Conexión IMAP
            st.markdown("**2️⃣ Conectando a Gmail IMAP...**")
            import socket
            try:
                socket.setdefaulttimeout(IMAP_TIMEOUT)
                mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
                mail.socket().settimeout(IMAP_TIMEOUT)
                st.success("✅ Conexión SSL establecida")
            except Exception as e:
                st.error(f"❌ No se pudo conectar: `{type(e).__name__}`: {e}")
                st.stop()

            # Paso 3: Login
            st.markdown("**3️⃣ Autenticando...**")
            try:
                mail.login(correo_cfg, password_cfg)
                st.success("✅ Login exitoso")
            except Exception as e:
                st.error(f"❌ Login falló: `{type(e).__name__}`: {str(e)[:300]}")
                st.info("💡 Verifica que la contraseña de aplicación sea correcta")
                try:
                    mail.logout()
                except Exception:
                    pass
                st.stop()

            # Paso 4: Seleccionar INBOX
            st.markdown("**4️⃣ Seleccionando INBOX...**")
            try:
                status_select, data_select = mail.select("INBOX", readonly=True)
                if status_select == "OK":
                    n_msgs = int(data_select[0]) if data_select and data_select[0] else 0
                    st.success(f"✅ INBOX seleccionada — {n_msgs} mensajes totales")
                else:
                    st.error(f"❌ No se pudo seleccionar INBOX: {status_select}")
                    mail.logout()
                    st.stop()
            except Exception as e:
                st.error(f"❌ Error seleccionando INBOX: `{type(e).__name__}`: {e}")
                try:
                    mail.logout()
                except Exception:
                    pass
                st.stop()

            # Paso 5: Buscar correos
            st.markdown("**5️⃣ Buscando correos (últimos 7 días)...**")
            desde = datetime.now() - timedelta(days=7)
            fecha_desde = desde.strftime("%d-%b-%Y")
            try:
                status_search, mensajes = mail.search(None, f'(SINCE "{fecha_desde}")')
                if status_search != "OK":
                    st.error(f"❌ Error en search: {status_search}")
                    mail.logout()
                    st.stop()

                ids = mensajes[0].split()
                if not ids:
                    st.warning(f"⚠️ Search devolvió 0 resultados para SINCE {fecha_desde}")

                    # Intentar búsqueda más amplia
                    st.markdown("**5️⃣b Intentando búsqueda SINCE 30 días...**")
                    desde30 = datetime.now() - timedelta(days=30)
                    fecha30 = desde30.strftime("%d-%b-%Y")
                    status30, mensajes30 = mail.search(None, f'(SINCE "{fecha30}")')
                    ids30 = mensajes30[0].split() if status30 == "OK" and mensajes30[0] else []
                    st.info(f"Búsqueda 30 días: {len(ids30)} resultados")

                    if not ids30:
                        # Intentar ALL
                        st.markdown("**5️⃣c Intentando ALL...**")
                        status_all, mensajes_all = mail.search(None, "ALL")
                        ids_all = mensajes_all[0].split() if status_all == "OK" and mensajes_all[0] else []
                        st.info(f"Búsqueda ALL: {len(ids_all)} resultados")

                        if ids_all:
                            st.warning(f"⚠️ Hay {len(ids_all)} correos en total, pero ninguno de los últimos 30 días. Último correo probablemente es antiguo.")
                        else:
                            st.error("❌ La bandeja está vacía o no se puede leer")
                            mail.logout()
                            st.stop()
                    else:
                        ids = ids30[-20:]
                        ids.reverse()
                else:
                    st.success(f"✅ {len(ids)} correos encontrados")
                    ids = ids[-20:]
                    ids.reverse()

            except Exception as e:
                st.error(f"❌ Error en search: `{type(e).__name__}`: {e}")
                try:
                    mail.logout()
                except Exception:
                    pass
                st.stop()

            # Paso 6: Descargar HEADERS en batch (ultra rápido, sin adjuntos)
            st.markdown(f"**6️⃣ Descargando {len(ids)} headers (rápido)...**")
            status_text = st.empty()
            status_text.caption("Descargando headers de Gmail...")
            resultados = []
            errores = 0

            # Construir lista de IDs para fetch batch: "1,2,3,4,..."
            ids_str = ",".join(mid.decode() if isinstance(mid, bytes) else str(mid) for mid in ids)

            try:
                mail.socket().settimeout(30)
                status, datos_raw = mail.fetch(ids_str, "(BODY[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])")
            except socket.timeout:
                st.error("❌ Timeout descargando headers (30s). Intenta con menos días o menos correos.")
                status, datos_raw = "TIMEOUT", None
            except Exception as e:
                st.error(f"❌ Error en fetch batch: `{type(e).__name__}`: {e}")
                status, datos_raw = "ERROR", None

            if status == "OK" and datos_raw:
                status_text.caption("Procesando headers...")
                resultados = _parsear_correos_batch(datos_raw)
                errores = len(ids) - len(resultados)
            else:
                errores = len(ids)
                print(f"⚠️ Fetch batch falló: status={status}")

            status_text.empty()

            try:
                mail.logout()
            except Exception:
                pass

            # Marcar como NO cargados (solo headers, contenido bajo demanda)
            for r in resultados:
                r['contenido_cargado'] = False

            # Fusionar con correos ya guardados en session_state (no perder los ya descargados)
            existentes = {c['message_id']: c for c in st.session_state.get('_correos_pendientes', []) if c.get('contenido_cargado')}
            for r in resultados:
                if r['message_id'] in existentes:
                    # Preservar contenido ya cargado
                    r.update(existentes[r['message_id']])
                    r['contenido_cargado'] = True

            st.session_state['_correos_pendientes'] = resultados

            # Guardar en tabla de pendientes para persistencia
            for correo_data in resultados:
                _guardar_correo_pendiente(correo_data)

            if resultados:
                st.success(f"✅ {len(resultados)} correo(s) descargado(s)")
                if errores > 0:
                    st.warning(f"⚠️ {errores} correo(s) con timeout/error (omitidos)")
                for r in resultados[:3]:
                    st.caption(f"📧 {r['asunto'][:60]} — 👤 {r['remitente'][:40]}")
                st.caption("💡 **Tip:** Haz clic en 'Ver contenido' en cada correo para cargar el contenido completo bajo demanda.")
            else:
                st.error(f"❌ 0 correos descargados. {errores} errores. La conexión puede estar inestable.")
                st.info("💡 Intenta de nuevo — si persiste, puede ser un problema de red con el servidor de Gmail.")

            st.markdown("---")
            st.rerun()

    with col_info:
        st.caption("Descarga correos de los últimos 7 días. Solo se muestran los no procesados.")

    with col_cmp:
        if st.button("🔄 Comparar Gmail vs BD", use_container_width=True):
            st.session_state['_mostrar_comparacion'] = True
            st.rerun()

    # ── Mostrar comparación si se solicitó ──
    if st.session_state.get('_mostrar_comparacion', False):
        render_comparacion_gmail_bd()
        if st.button("❌ Cerrar comparación", use_container_width=True):
            st.session_state['_mostrar_comparacion'] = False
            st.rerun()
        st.markdown("---")

    # ── Correos pendientes ──
    correos = st.session_state.get('_correos_pendientes', [])

    # Si no hay correos en session_state, intentar restaurar desde BD
    if not correos:
        pendientes_guardados = _obtener_pendientes_guardados()
        if pendientes_guardados:
            st.info(f"💾 Se encontraron {len(pendientes_guardados)} correo(s) guardado(s) de una sesión anterior. Haz clic en **Revisar Correo** para actualizar o usa los guardados.")
            # Mostrar resumen de los guardados (sin datos completos de adjuntos/HTML)
            procesados = _obtener_procesados()
            pendientes_filtrados = [p for p in pendientes_guardados if p['message_id'] not in procesados]

            if not pendientes_filtrados:
                st.success("✅ Todos los correos guardados ya fueron procesados.")
                return

            st.markdown(f"#### 💾 {len(pendientes_filtrados)} correo(s) guardado(s) pendiente(s)")
            st.caption("⚠️ Estos son los metadatos guardados. Para ver contenido completo y adjuntos, haz clic en **Revisar Correo**.")

            for idx, pg in enumerate(pendientes_filtrados):
                icono = '📩' if not pg.get('leido') else '📧'
                remitente = pg.get('remitente_nombre') or pg.get('remitente', '?')
                fecha_corta = (pg.get('fecha_correo', '') or '')[:10]
                n_adj = pg.get('n_adjuntos', 0)

                st.markdown(f"""
                <div style="border:1px solid #374151;border-radius:10px;padding:14px 16px;margin-bottom:10px;background:#1F2937;">
                    <div style="display:flex;justify-content:space-between;align-items:center;">
                        <div>
                            <span style="font-size:1.1rem;">{icono}</span>
                            <span style="color:#F59E0B;font-weight:600;">{pg.get('asunto', '(Sin asunto)')[:70]}</span>
                        </div>
                        <span style="color:#6B7280;font-size:0.8em;">{fecha_corta}</span>
                    </div>
                    <div style="color:#9CA3AF;font-size:0.85em;margin-top:4px;">
                        👤 {remitente} {f'&nbsp;|&nbsp; 📎 {n_adj} adjunto(s)' if n_adj > 0 else ''}
                    </div>
                    <div style="color:#D1D5DB;font-size:0.85em;margin-top:6px;background:rgba(255,255,255,0.03);padding:6px 10px;border-radius:6px;">
                        {(pg.get('cuerpo_corto', '') or '')[:150]}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                msg_id_guardado = pg['message_id']
                col_descartar_guardado = st.columns([8, 2])[1]
                with col_descartar_guardado:
                    if st.button("🗑️ Descartar", key=f"btn_desc_guardado_{idx}", use_container_width=True):
                        _marcar_procesado(msg_id_guardado, accion="descartado")
                        _eliminar_pendiente(msg_id_guardado)
                        st.toast(f"🗑️ Correo descartado")
                        st.rerun()

            st.markdown("---")
            return

        st.info("📭 No hay correos descargados. Haz clic en **Revisar Correo** para buscar nuevos mensajes.")
        return

    # Filtrar ya procesados (persistidos en Supabase)
    procesados = _obtener_procesados()
    correos_pendientes = [c for c in correos if c['message_id'] not in procesados]

    if not correos_pendientes:
        st.success("✅ Todos los correos han sido procesados.")
        return

    st.markdown(f"#### 📬 {len(correos_pendientes)} correo(s) pendiente(s)")

    # Pre-cargar datos una sola vez
    from utils.db import run_query, db_insert
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")

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
                {correo.get('cuerpo_corto', '')[:150] if correo.get('cuerpo_corto') else '<i style="color:#6B7280;">Contenido no cargado — haz clic en "Ver contenido" para cargar</i>'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Ver contenido completo + adjuntos ──
        with st.expander("📄 Ver contenido del correo", expanded=False):
            # Si el contenido NO se ha cargado aún, mostrar botón de carga
            if not correo.get('contenido_cargado', False):
                st.info("📥 Este correo aún no tiene su contenido descargado (solo headers).")
                if st.button(f"⬇️ Cargar contenido completo", key=f"btn_cargar_{idx}", type="primary", use_container_width=True):
                    with st.spinner("Descargando contenido del correo..."):
                        correo = cargar_contenido_correo(correo)
                    st.rerun()
            else:
                # Contenido ya cargado — mostrar normalmente
                tiene_html = correo.get('tiene_html', False)
                if tiene_html:
                    tab_html, tab_texto = st.tabs(["🌐 Vista original", "📝 Texto plano"])

                    with tab_html:
                        import streamlit.components.v1 as components
                        html_seguro = correo.get('html_raw', '')
                        html_seguro = re.sub(r'<script[^>]*>.*?</script>', '', html_seguro, flags=re.DOTALL | re.IGNORECASE)
                        html_seguro = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html_seguro, flags=re.DOTALL | re.IGNORECASE)
                        html_envuelto = f"""
                        <div style="background:#ffffff;color:#1f2937;padding:16px;border-radius:8px;font-family:Arial,sans-serif;font-size:14px;line-height:1.6;overflow:auto;">
                            {html_seguro}
                        </div>
                        """
                        components.html(html_envuelto, height=500, scrolling=True)

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
        col_crear, col_vincular, col_descartar, col_espacio = st.columns([2, 2, 2, 2])

        with col_crear:
            crear_clicked = st.button("✅ Crear Orden", key=f"btn_crear_{idx}", type="primary", use_container_width=True)

        with col_vincular:
            vincular_clicked = st.button("🔗 Vincular a OT", key=f"btn_vincular_{idx}", use_container_width=True)

        with col_descartar:
            descartar_clicked = st.button("🗑️ Descartar", key=f"btn_descartar_{idx}", use_container_width=True)

        # ── Acción: Descartar (un click) ──
        if descartar_clicked:
            _marcar_procesado(msg_id, accion="descartado")
            _eliminar_pendiente(msg_id)
            # Quitar de la lista local sin perder los demás
            pendientes = st.session_state.get('_correos_pendientes', [])
            st.session_state['_correos_pendientes'] = [c for c in pendientes if c['message_id'] != msg_id]
            st.toast(f"🗑️ Correo descartado: {correo['asunto'][:40]}")
            st.rerun()

        # ── Acción: Vincular a OT existente (muestra selector debajo) ──
        if vincular_clicked:
            st.session_state[f'_vincular_ot_{idx}'] = True
            st.session_state.pop(f'_crear_ot_{idx}', None)  # Cerrar form crear si está abierto

        if st.session_state.get(f'_vincular_ot_{idx}', False):
            render_selector_ordenes_para_vincular(idx, correo, df_ordenes, df_act)
            st.markdown("---")

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

                                    # ── Subir adjuntos del correo a la orden ──
                                    adjuntos_correo = correo.get('adjuntos', [])
                                    if adjuntos_correo:
                                        with st.spinner(f"Subiendo {len(adjuntos_correo)} adjunto(s) del correo..."):
                                            urls = _subir_adjuntos_correo(adjuntos_correo, nuevo_id)
                                            if urls:
                                                print(f"✅ {len(urls)} adjunto(s) subido(s) a la OT #{nuevo_id}")

                                    # ── Subir imágenes inline del correo ──
                                    imagenes_inline = correo.get('imagenes_inline', {})
                                    if imagenes_inline:
                                        from utils.uploads import subir_archivo_generico as _subir_img
                                        for cid, img in imagenes_inline.items():
                                            try:
                                                img_bytes = base64.b64decode(img['datos_b64'])
                                                archivo_img = _ArchivoDesdeBytes(img_bytes, f"inline_{cid}.jpg")
                                                url_img = _subir_img(archivo_img)
                                                if url_img:
                                                    db_insert("bitacora", {
                                                        "orden_id": nuevo_id,
                                                        "usuario_text": "CORREO (automático)",
                                                        "mensaje": f"🖼️ Imagen embebida del correo (CID: {cid})",
                                                        "archivo_url": url_img,
                                                        "fecha": datetime.now().isoformat()
                                                    })
                                            except Exception as e_img:
                                                print(f"⚠️ Error subiendo inline {cid}: {e_img}")

                                    _marcar_procesado(msg_id, orden_id=nuevo_id, accion="orden")
                                    _eliminar_pendiente(msg_id)
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
