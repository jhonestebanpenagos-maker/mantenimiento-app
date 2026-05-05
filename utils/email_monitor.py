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
IMAP_TIMEOUT = 30


def _obtener_credenciales():
    """Obtiene credenciales de Gmail desde st.secrets."""
    cfg = st.secrets.get("gmail", {})
    correo = cfg.get("correo", "")
    password = cfg.get("password", "")
    return correo, password


def _conectar_imap():
    """Conecta a Gmail vía IMAP con SSL y timeout."""
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
    texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.DOTALL)
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
                    # Intentar extraer nombre del archivo
                    nombre = parte.get_filename()
                    if nombre:
                        nombre = _decodificar_header(nombre)
                    else:
                        # Inferir nombre del tipo
                        ext = ctype.split('/')[-1].split(';')[0]
                        nombre = f"imagen_{cid_limpio[:8]}.{ext}"

                    imagenes[cid_limpio] = {
                        'tipo': ctype,
                        'datos_b64': base64.b64encode(datos).decode('ascii'),
                        'tamano': len(datos),
                        'nombre': nombre,
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
# 🖼️ CLASIFICACIÓN AUTOMÁTICA DE IMÁGENES
# ==============================================================================
def _clasificar_imagen(cid: str, img: dict, html_raw: str) -> str:
    """
    Clasifica una imagen inline en una de estas categorías:
    - 'firma': firma digital, sello, firma escaneada
    - 'logo': logotipos, banners de empresa
    - 'tracking': pixel de rastreo (1x1 o muy pequeñas)
    - 'contenido': imagen relevante del correo (evidencia, fotos, diagramas)
    - 'desconocido': no se pudo clasificar

    Retorna la categoría como string.
    """
    tamano = img.get('tamano', 0)
    nombre = (img.get('nombre', '') or '').lower()
    cid_lower = cid.lower()
    tipo = (img.get('tipo', '') or '').lower()

    # 1. Tracking pixels: imágenes muy pequeñas (< 2KB típicamente 1x1 gifs)
    if tamano < 2048:
        return 'tracking'

    # 2. Por nombre del archivo
    if nombre:
        # Firmas
        if any(kw in nombre for kw in ['firma', 'firmsign', 'signature', 'sign', 'sello', 'firma_']):
            return 'firma'
        # Logos
        if any(kw in nombre for kw in ['logo', 'banner', 'header', 'footer', 'brand', 'corporativo']):
            return 'logo'
        # Tracking
        if any(kw in nombre for kw in ['pixel', 'track', 'open', 'beacon', 'spacer', 'blank', 'transparent']):
            return 'tracking'

    # 3. Por Content-ID
    if cid_lower:
        if any(kw in cid_lower for kw in ['firma', 'sign', 'signature']):
            return 'firma'
        if any(kw in cid_lower for kw in ['logo', 'brand', 'header', 'footer']):
            return 'logo'
        if any(kw in cid_lower for kw in ['image001', 'image002']):
            # Muchos clientes de correo usan image001 para firmas/logos
            # Pero no siempre — marcar como desconocido para que el usuario decida
            pass

    # 4. Por contexto en el HTML (si la imagen aparece en un <a> con href de firma)
    if html_raw:
        # Buscar si el CID aparece cerca de texto de firma
        cid_pattern = re.escape(cid)
        # Buscar en un radio de 500 chars alrededor del CID
        for match in re.finditer(cid_pattern, html_raw, re.IGNORECASE):
            start = max(0, match.start() - 500)
            end = min(len(html_raw), match.end() + 500)
            contexto = html_raw[start:end].lower()
            if any(kw in contexto for kw in ['firma', 'signature', 'attorney', 'abogado', 'legal']):
                return 'firma'
            if any(kw in contexto for kw in ['logo', 'brand', 'company', 'empresa']):
                return 'logo'

    # 5. Por tamaño: imágenes muy grandes suelen ser contenido real
    if tamano > 50000:  # > 50KB
        return 'contenido'

    # 6. Imágenes medianas (2KB - 50KB) — probablemente logos o firmas pequeñas
    if tamano < 50000:
        return 'desconocido'

    return 'contenido'


def _obtener_seleccion_imagenes(correo_idx: int, message_id: str, imagenes: dict) -> dict:
    """
    Obtiene el estado de selección de imágenes para un correo.
    Retorna dict[cid] -> bool (True = seleccionada para subir).
    Inicializa todas como seleccionadas por defecto.
    """
    key = f'_img_sel_{correo_idx}_{message_id}'
    if key not in st.session_state:
        # Por defecto: contenido seleccionado, tracking NO, el resto según clasificación
        seleccion = {}
        for cid, img in imagenes.items():
            categoria = _clasificar_imagen(cid, img, '')
            if categoria == 'tracking':
                seleccion[cid] = False
            elif categoria == 'contenido':
                seleccion[cid] = True
            else:
                # firma, logo, desconocido — seleccionados por defecto, usuario decide
                seleccion[cid] = True
        st.session_state[key] = seleccion
    return st.session_state[key]


def _guardar_seleccion_imagenes(correo_idx: int, message_id: str, seleccion: dict):
    """Guarda el estado de selección de imágenes en session_state."""
    key = f'_img_sel_{correo_idx}_{message_id}'
    st.session_state[key] = seleccion


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
    """Sube los adjuntos de un correo a Cloudinary y crea entradas en la bitácora."""
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


def _subir_imagenes_inline_seleccionadas(imagenes_inline: dict, seleccion: dict, orden_id: int, remitente: str = "correo"):
    """
    Sube SOLO las imágenes inline seleccionadas por el usuario.
    Retorna lista de URLs subidas.
    """
    from utils.db import db_insert
    from utils.uploads import subir_archivo_generico

    urls_subidas = []
    if not imagenes_inline or not seleccion:
        return urls_subidas

    for cid, img in imagenes_inline.items():
        if not seleccion.get(cid, False):
            continue  # Saltar imágenes no seleccionadas

        try:
            img_bytes = base64.b64decode(img['datos_b64'])
            nombre = img.get('nombre', f"inline_{cid[:8]}.jpg")
            archivo_img = _ArchivoDesdeBytes(img_bytes, nombre)
            url_img = subir_archivo_generico(archivo_img)
            if url_img:
                urls_subidas.append(url_img)
                db_insert("bitacora", {
                    "orden_id": orden_id,
                    "usuario_text": f"📧 {remitente}",
                    "mensaje": f"🖼️ Imagen del correo: {nombre}",
                    "archivo_url": url_img,
                    "fecha": datetime.now().isoformat()
                })
        except Exception as e_img:
            print(f"⚠️ Error subiendo inline {cid}: {e_img}")

    return urls_subidas


def sincronizar_adjuntos_correo(orden_id, correo_message_id):
    """Descarga un correo específico por su Message-ID desde Gmail y sube adjuntos."""
    from utils.db import db_insert

    if not correo_message_id:
        return 0, 0

    mail = _conectar_imap()
    if not mail:
        return 0, 0

    try:
        mail.select("INBOX")
        status, mensajes = mail.search(None, f'(HEADER Message-ID "{correo_message_id}")')
        if status != "OK" or not mensajes[0].strip():
            status, mensajes = mail.search(None, f'(TEXT "{correo_message_id}")')
        if status != "OK" or not mensajes[0].strip():
            print(f"⚠️ No se encontró el correo con Message-ID: {correo_message_id}")
            return 0, 0

        ids = mensajes[0].split()
        msg_id = ids[-1]

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

        if adjuntos:
            urls = _subir_adjuntos_correo(adjuntos, orden_id)
            n_subidos += len(urls)

        if imagenes_inline:
            # Subir todas las inline (sin filtro en sincronización automática)
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
    """Parsea la respuesta de IMAP fetch batch de forma robusta."""
    resultados = []
    if not datos_raw:
        return resultados

    for item in datos_raw:
        try:
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
    """Descarga SOLO HEADERS de correos nuevos (ultra rápido, sin adjuntos)."""
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
    """Carga el contenido completo de UN correo si no fue descargado en el batch."""
    import socket

    if correo.get('contenido_cargado'):
        return correo

    message_id = correo.get('message_id', '').strip()
    if not message_id:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = '[No disponible - sin Message-ID]'
        _actualizar_correo_en_session(correo)
        return correo

    mail = _conectar_imap()
    if not mail:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = '[Error conectando a Gmail - verifica credenciales]'
        _actualizar_correo_en_session(correo)
        return correo

    try:
        mail.select("INBOX", readonly=True)
        mail.socket().settimeout(IMAP_TIMEOUT)

        status, mensajes = mail.search(None, f'(HEADER Message-ID "{message_id}")')
        if status != "OK" or not mensajes[0].strip():
            status, mensajes = mail.search(None, f'(TEXT "{message_id}")')

        if status != "OK" or not mensajes[0].strip():
            correo['contenido_cargado'] = True
            correo['cuerpo'] = '[Correo no encontrado en Gmail - puede haber sido eliminado]'
            _actualizar_correo_en_session(correo)
            return correo

        ids = mensajes[0].split()
        msg_id = ids[-1]

        status, datos = mail.fetch(msg_id, "(RFC822)")
        if status != "OK" or not datos or not datos[0]:
            correo['contenido_cargado'] = True
            correo['cuerpo'] = '[Error descargando contenido de Gmail]'
            _actualizar_correo_en_session(correo)
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

        _actualizar_correo_en_session(correo)
        print(f"✅ Contenido cargado: {correo['asunto'][:50]} | Adjuntos: {len(adjuntos)} | Inline: {len(imagenes_inline)}")
        return correo

    except socket.timeout:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = '[Timeout descargando contenido - el correo puede ser muy pesado]'
        _actualizar_correo_en_session(correo)
        return correo
    except Exception as e:
        correo['contenido_cargado'] = True
        correo['cuerpo'] = f'[Error: {type(e).__name__}: {str(e)[:200]}]'
        _actualizar_correo_en_session(correo)
        return correo
    finally:
        try:
            mail.logout()
        except Exception:
            pass


def _actualizar_correo_en_session(correo: dict):
    """Actualiza un correo en session_state['_correos_pendientes'] de forma segura."""
    pendientes = st.session_state.get('_correos_pendientes', [])
    for i, c in enumerate(pendientes):
        if c['message_id'] == correo['message_id']:
            pendientes[i] = correo
            break
    st.session_state['_correos_pendientes'] = pendientes


def _descargar_correos_por_message_ids(message_ids: list) -> list:
    """Descarga el contenido completo de una lista de correos por sus Message-IDs."""
    import socket

    if not message_ids:
        return []

    mail = _conectar_imap()
    if not mail:
        return []

    resultados = []
    try:
        mail.select("INBOX", readonly=True)
        total = len(message_ids)

        for i, mid in enumerate(message_ids):
            try:
                mail.socket().settimeout(IMAP_TIMEOUT)

                status, mensajes = mail.search(None, f'(HEADER Message-ID "{mid}")')
                if status != "OK" or not mensajes[0].strip():
                    status, mensajes = mail.search(None, f'(TEXT "{mid}")')
                if status != "OK" or not mensajes[0].strip():
                    print(f"⚠️ [{i+1}/{total}] No encontrado: {mid[:50]}")
                    continue

                ids = mensajes[0].split()
                msg_id = ids[-1]

                status, datos = mail.fetch(msg_id, "(RFC822)")
                if status != "OK" or not datos or not datos[0]:
                    continue

                raw_bytes = datos[0][1] if isinstance(datos[0], tuple) else datos[0]
                if not isinstance(raw_bytes, bytes):
                    continue

                msg = email.message_from_bytes(raw_bytes)

                asunto = _decodificar_header(msg.get("Subject", ""))
                remitente_raw = _decodificar_header(msg.get("From", ""))
                fecha_raw = msg.get("Date", "")
                message_id = (msg.get("Message-ID") or mid).strip()

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

                correo_data = {
                    'message_id': message_id,
                    'imap_id': '',
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
                    'leido': False,
                    'contenido_cargado': True,
                }
                resultados.append(correo_data)
                print(f"✅ [{i+1}/{total}] Descargado: {asunto[:40]}")

            except socket.timeout:
                print(f"⚠️ [{i+1}/{total}] Timeout: {mid[:50]}")
                continue
            except Exception as e:
                print(f"⚠️ [{i+1}/{total}] Error: {e}")
                continue

        return resultados

    except Exception as e:
        print(f"❌ Error en _descargar_correos_por_message_ids: {e}")
        return resultados
    finally:
        try:
            mail.logout()
        except Exception:
            pass


# ==============================================================================
# 🔗 VINCULACIÓN DE CORREOS A ÓRDENES EXISTENTES
# ==============================================================================
def vincular_correo_a_orden(correo: dict, orden_id: int, imagenes_seleccionadas: dict = None) -> bool:
    """
    Vincula un correo del buzón como avance de una orden de trabajo existente.
    imagenes_seleccionadas: dict[cid] -> bool para filtrar imágenes inline.
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
        imagenes_inline = correo.get('imagenes_inline', {})

        # Contar imágenes seleccionadas
        n_img_total = len(imagenes_inline)
        if imagenes_seleccionadas:
            n_img_seleccionadas = sum(1 for v in imagenes_seleccionadas.values() if v)
        else:
            n_img_seleccionadas = n_img_total

        adj_tag = ""
        if n_adj > 0:
            adj_tag += f" · 📎 {n_adj} adjunto(s)"
        if n_img_seleccionadas > 0:
            adj_tag += f" · 🖼️ {n_img_seleccionadas} imagen(es)"
        if n_img_total > n_img_seleccionadas:
            adj_tag += f" (filtradas {n_img_total - n_img_seleccionadas})"

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
        if n_adj > 0:
            _subir_adjuntos_correo(correo.get('adjuntos', []), orden_id)

        # 4. Subir SOLO las imágenes inline seleccionadas
        if imagenes_inline and n_img_seleccionadas > 0:
            _subir_imagenes_inline_seleccionadas(
                imagenes_inline, imagenes_seleccionadas or {}, orden_id, remitente
            )

        # 5. Marcar correo como procesado
        _marcar_procesado(correo['message_id'], orden_id=orden_id, accion="avance")
        print(f"✅ Correo vinculado a OT #{orden_id}: {asunto[:50]}")
        return True

    except Exception as e:
        print(f"❌ Error vinculando correo a OT #{orden_id}: {e}")
        return False


def _generar_y_subir_correo_html(correo: dict, orden_id: int) -> str | None:
    """Genera un archivo HTML con el contenido completo del correo y lo sube a Cloudinary."""
    from utils.uploads import subir_archivo_generico

    try:
        remitente = correo.get('remitente_nombre') or correo.get('remitente', 'Desconocido')
        asunto = correo.get('asunto', '(Sin asunto)')
        fecha_correo = correo.get('fecha', '')
        cuerpo = correo.get('cuerpo', '') or ''
        html_raw = correo.get('html_raw', '')

        if html_raw:
            contenido = html_raw
        else:
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

        contenido = re.sub(r'<script[^>]*>.*?</script>', '', contenido, flags=re.DOTALL | re.IGNORECASE)
        contenido = re.sub(r'<iframe[^>]*>.*?</iframe>', '', contenido, flags=re.DOTALL | re.IGNORECASE)

        html_completo = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{asunto}</title></head>
<body style="margin:0;padding:0;background:#f9fafb;">{contenido}</body></html>"""

        archivo_bytes = html_completo.encode('utf-8')
        nombre_archivo = f"correo_{orden_id}_{asunto[:30].replace(' ', '_')}.html"
        archivo = _ArchivoDesdeBytes(archivo_bytes, nombre_archivo)
        url = subir_archivo_generico(archivo)
        return url

    except Exception as e:
        print(f"⚠️ Error generando HTML del correo: {e}")
        return None


def obtener_correos_no_vinculados():
    """Obtiene correos del buzón que aún no están vinculados a ninguna orden."""
    correos = st.session_state.get('_correos_pendientes', [])
    if not correos:
        return []

    procesados = _obtener_procesados()
    return [c for c in correos if c['message_id'] not in procesados]


# ==============================================================================
# 🔄 MIGRACIÓN: CONVERTIR ENTRADAS ANTIGUAS DE BITÁCORA A FORMATO COMPACTO
# ==============================================================================
def migrar_correos_antiguos_bitacora(orden_id: int = None):
    """Migra entradas antiguas de bitácora al formato compacto."""
    from utils.db import supabase, db_update

    try:
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
            es_correo_antiguo = (
                usuario.startswith('CORREO (')
                and ('📧 Correo de seguimiento vinculado' in mensaje or len(mensaje) > 300)
                and 'Creada desde correo' not in mensaje
            )
            if es_correo_antiguo:
                entradas_antiguas.append(b)

        if not entradas_antiguas:
            return 0, 0

        n_migrados = 0
        for entrada in entradas_antiguas:
            try:
                mensaje_viejo = entrada.get('mensaje', '') or ''
                usuario_viejo = entrada.get('usuario_text', '') or ''

                remitente = usuario_viejo
                if usuario_viejo.startswith('CORREO (') and usuario_viejo.endswith(')'):
                    remitente = usuario_viejo[8:-1]

                asunto = '(Sin asunto)'
                for linea in mensaje_viejo.split('\n'):
                    if linea.startswith('Asunto:'):
                        asunto = linea[7:].strip()
                        break

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

                cuerpo = _html_a_texto(cuerpo) if '<' in cuerpo else cuerpo
                cuerpo = re.sub(r'\n{3,}', '\n\n', cuerpo).strip()

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

                cuerpo_corto = cuerpo[:150].replace('\n', ' ').strip()
                if len(cuerpo) > 150:
                    cuerpo_corto += "..."
                mensaje_nuevo = f"📧 {asunto}"
                if cuerpo_corto:
                    mensaje_nuevo += f'\n💬 "{cuerpo_corto}"'

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
    """Renderiza un selector con búsqueda para vincular un correo a una orden."""
    from utils.db import db_insert

    ordenes_activas = df_ordenes[df_ordenes['estado'].isin(['Abierta', 'Por Validar'])].copy()

    if ordenes_activas.empty:
        st.info("No hay órdenes abiertas para vincular. Crea una orden primero.")
        return

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    ordenes_activas['Activo'] = ordenes_activas['activo_id'].map(map_act).fillna("Sin activo")

    st.markdown("**🔗 Vincular a orden existente:**")

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

    df_filtrado = ordenes_activas.copy()

    if filtro_activo != "Todos":
        df_filtrado = df_filtrado[df_filtrado['Activo'] == filtro_activo]

    if texto_busqueda.strip():
        q = texto_busqueda.strip().lower()
        if q.isdigit():
            df_filtrado = df_filtrado[df_filtrado['id'] == int(q)]
        else:
            mask = (
                df_filtrado['Activo'].str.lower().str.contains(q, na=False) |
                df_filtrado['descripcion'].str.lower().str.contains(q, na=False)
            )
            df_filtrado = df_filtrado[mask]

    if df_filtrado.empty:
        st.warning("No se encontraron órdenes con ese criterio.")
        return

    st.caption(f"{len(df_filtrado)} orden(es) encontrada(s)")

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
        # Obtener selección de imágenes del session_state
        imagenes_sel = _obtener_seleccion_imagenes(correo_idx, correo['message_id'], correo.get('imagenes_inline', {}))
        with st.spinner(f"Vinculando correo a OT #{orden_id}..."):
            exito = vincular_correo_a_orden(correo, orden_id, imagenes_sel)
        if exito:
            pendientes = st.session_state.get('_correos_pendientes', [])
            st.session_state['_correos_pendientes'] = [
                c for c in pendientes if c['message_id'] != correo['message_id']
            ]
            _eliminar_pendiente(correo['message_id'])
            st.session_state.pop(f'_vincular_ot_{correo_idx}', None)
            # Limpiar selección de imágenes
            st.session_state.pop(f'_img_sel_{correo_idx}_{correo["message_id"]}', None)
            st.success(f"✅ Correo vinculado como avance de OT #{orden_id}")
            st.rerun()
        else:
            st.error("❌ No se pudo vincular el correo. Intenta de nuevo.")


# ==============================================================================
# 🖼️ RENDERIZADO DEL SELECTOR DE IMÁGENES
# ==============================================================================
def _render_selector_imagenes(correo_idx: int, correo: dict):
    """
    Muestra todas las imágenes inline del correo con checkboxes para que el
    usuario seleccione cuáles quiere conservar antes de vincular/crear orden.
    """
    imagenes = correo.get('imagenes_inline', {})
    if not imagenes:
        return

    message_id = correo['message_id']
    html_raw = correo.get('html_raw', '')

    # Obtener o inicializar selección
    seleccion = _obtener_seleccion_imagenes(correo_idx, message_id, imagenes)

    # Clasificar todas las imágenes
    clasificaciones = {}
    for cid, img in imagenes.items():
        clasificaciones[cid] = _clasificar_imagen(cid, img, html_raw)

    iconos_categoria = {
        'contenido': '📸',
        'firma': '✍️',
        'logo': '🏢',
        'tracking': '👁️',
        'desconocido': '❓',
    }
    colores_categoria = {
        'contenido': '#10B981',
        'firma': '#F59E0B',
        'logo': '#6B7280',
        'tracking': '#EF4444',
        'desconocido': '#9CA3AF',
    }
    labels_categoria = {
        'contenido': 'Contenido',
        'firma': 'Firma',
        'logo': 'Logo/Banner',
        'tracking': 'Pixel rastreo',
        'desconocido': 'Sin clasificar',
    }

    n_total = len(imagenes)
    n_seleccionadas = sum(1 for v in seleccion.values() if v)
    n_tracking = sum(1 for c in clasificaciones.values() if c == 'tracking')

    st.markdown(f"""
    <div style="background:rgba(59,130,246,0.08);border:1px solid #374151;border-radius:10px;padding:14px;margin-bottom:12px;">
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <span style="color:#60A5FA;font-weight:700;">🖼️ Imágenes del correo ({n_total})</span>
            <span style="color:#9CA3AF;font-size:0.85em;">{n_seleccionadas} seleccionadas · {n_tracking} tracking auto-descartados</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # Botones de acción masiva
    col_todas, col_ninguna, col_solo_contenido, col_invertir = st.columns(4)
    with col_todas:
        if st.button("✅ Todas", key=f"img_all_{correo_idx}", use_container_width=True):
            for cid in imagenes:
                seleccion[cid] = True
            _guardar_seleccion_imagenes(correo_idx, message_id, seleccion)
            st.rerun()
    with col_ninguna:
        if st.button("❌ Ninguna", key=f"img_none_{correo_idx}", use_container_width=True):
            for cid in imagenes:
                seleccion[cid] = False
            _guardar_seleccion_imagenes(correo_idx, message_id, seleccion)
            st.rerun()
    with col_solo_contenido:
        if st.button("📸 Solo contenido", key=f"img_content_{correo_idx}", use_container_width=True):
            for cid, cat in clasificaciones.items():
                seleccion[cid] = (cat == 'contenido')
            _guardar_seleccion_imagenes(correo_idx, message_id, seleccion)
            st.rerun()
    with col_invertir:
        if st.button("🔄 Invertir", key=f"img_inv_{correo_idx}", use_container_width=True):
            for cid in imagenes:
                seleccion[cid] = not seleccion.get(cid, False)
            _guardar_seleccion_imagenes(correo_idx, message_id, seleccion)
            st.rerun()

    # Mostrar cada imagen con checkbox
    cids = list(imagenes.keys())
    cols_per_row = 3
    for row_start in range(0, len(cids), cols_per_row):
        row_cids = cids[row_start:row_start + cols_per_row]
        cols = st.columns(cols_per_row)
        for i, cid in enumerate(row_cids):
            img = imagenes[cid]
            cat = clasificaciones[cid]
            icono = iconos_categoria.get(cat, '❓')
            color = colores_categoria.get(cat, '#9CA3AF')
            label_cat = labels_categoria.get(cat, 'Sin clasificar')
            tamano_kb = img.get('tamano', 0) / 1024

            with cols[i]:
                try:
                    img_bytes = base64.b64decode(img['datos_b64'])
                    st.image(img_bytes, use_container_width=True)
                except Exception:
                    st.caption("⚠️ No se pudo mostrar")

                # Checkbox para seleccionar
                checked = st.checkbox(
                    f"{icono} {label_cat} ({tamano_kb:.0f}KB)",
                    value=seleccion.get(cid, True),
                    key=f"img_chk_{correo_idx}_{cid}",
                )
                seleccion[cid] = checked

    # Guardar selección actualizada
    _guardar_seleccion_imagenes(correo_idx, message_id, seleccion)

    # Resumen final
    n_final = sum(1 for v in seleccion.values() if v)
    n_descartadas = n_total - n_final
    if n_descartadas > 0:
        st.info(f"ℹ️ {n_descartadas} imagen(es) serán descartadas. Se subirán {n_final} imagen(es) al vincular/crear la orden.")
    else:
        st.success(f"✅ Todas las {n_total} imágenes serán incluidas.")


# ==============================================================================
# 🎨 RENDERIZADO DEL BUZÓN
# ==============================================================================

def _es_correo_de_hoy(correo: dict, hoy) -> bool:
    """Determina si un correo es de hoy basándose en su fecha."""
    fecha_str = correo.get('fecha', '')
    if not fecha_str:
        return True
    try:
        fecha_dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
        return fecha_dt.date() == hoy
    except Exception:
        return True


def render_buzon_correo():
    """
    Buzón de correo — flujo automático.
    1. Descarga headers de últimos 2 días (batch, rápido)
    2. Filtra contra emails_procesados automáticamente
    3. Muestra solo correos pendientes (hoy + anteriores)
    4. Contenido se carga bajo demanda
    5. Selector de imágenes antes de vincular/crear
    """
    st.markdown("### 📧 Buzón de Correo")
    st.caption("Revisa correos y decide cuáles se convierten en Órdenes de Trabajo.")

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

    if st.button("🔄 Revisar Correo", type="primary", use_container_width=True):
        with st.spinner("Conectando a Gmail y descargando headers (últimos 2 días)..."):
            todos_headers = descargar_correos_nuevos(max_correos=50, dias_atras=2)

        if not todos_headers:
            st.error("❌ No se pudieron descargar correos. Verifica la conexión a Gmail.")
        else:
            procesados = _obtener_procesados()
            pendientes = [c for c in todos_headers if c['message_id'] not in procesados]

            existentes = {c['message_id']: c for c in st.session_state.get('_correos_pendientes', []) if c.get('contenido_cargado')}
            for p in pendientes:
                if p['message_id'] in existentes:
                    p.update(existentes[p['message_id']])

            st.session_state['_correos_pendientes'] = pendientes

            n_total = len(todos_headers)
            n_pend = len(pendientes)

            if n_pend == 0:
                st.success(f"✅ {n_total} correos revisados — todos gestionados.")
            else:
                hoy = datetime.now().date()
                pend_hoy = [c for c in pendientes if _es_correo_de_hoy(c, hoy)]
                pend_antiguos = [c for c in pendientes if not _es_correo_de_hoy(c, hoy)]

                msg = f"📬 {n_pend} correo(s) pendiente(s) de {n_total} revisados"
                if pend_antiguos:
                    msg += f" — ⚠️ {len(pend_antiguos)} de días anteriores"
                st.warning(msg)

        st.rerun()

    correos = st.session_state.get('_correos_pendientes', [])

    procesados = _obtener_procesados()
    correos_pendientes = [c for c in correos if c['message_id'] not in procesados]

    if not correos_pendientes:
        st.info("📭 Sin correos pendientes. Haz clic en **Revisar Correo** para buscar nuevos mensajes.")
        return

    hoy = datetime.now().date()
    pend_hoy = [c for c in correos_pendientes if _es_correo_de_hoy(c, hoy)]
    pend_antiguos = [c for c in correos_pendientes if not _es_correo_de_hoy(c, hoy)]

    if pend_antiguos:
        st.warning(f"⚠️ **{len(pend_antiguos)} correo(s) de días anteriores** sin gestionar. Revísalos abajo para que no se acumulen.")

    sin_contenido = [c for c in correos_pendientes if not c.get('contenido_cargado')]
    if sin_contenido:
        if st.button(f"📥 Cargar contenido de TODOS ({len(sin_contenido)} correos)", type="secondary", use_container_width=True, key="btn_cargar_todos"):
            progress = st.progress(0, text="Cargando contenido...")
            cargados = 0
            for i, c in enumerate(sin_contenido):
                progress.progress((i + 1) / len(sin_contenido), text=f"Cargando {i+1}/{len(sin_contenido)}: {c['asunto'][:40]}...")
                try:
                    resultado = cargar_contenido_correo(c)
                    if resultado.get('contenido_cargado') and '[Error' not in (resultado.get('cuerpo') or ''):
                        cargados += 1
                except Exception as e:
                    print(f"⚠️ Error cargando contenido: {e}")
            progress.empty()
            if cargados > 0:
                st.success(f"✅ {cargados} correo(s) con contenido cargado.")
            st.rerun()

    st.markdown("---")

    from utils.db import run_query, db_insert
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")

    listas_a_renderizar = []
    if pend_hoy:
        listas_a_renderizar.append(("📨 Correos de hoy", pend_hoy))
    if pend_antiguos:
        listas_a_renderizar.append(("⏰ Correos anteriores sin gestionar", pend_antiguos))

    idx_global = 0
    for titulo, lista in listas_a_renderizar:
        st.markdown(f"#### {titulo} ({len(lista)})")

        for correo in lista:
            idx = idx_global
            idx_global += 1
            msg_id = correo['message_id']

            icono = '📩' if not correo['leido'] else '📧'
            remitente = correo['remitente_nombre'] or correo['remitente']
            fecha_corta = correo['fecha'][:10] if correo['fecha'] else ''
            n_adjuntos = len(correo.get('adjuntos', []))

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

            with st.expander("📄 Ver contenido del correo", expanded=False):
                if not correo.get('contenido_cargado', False):
                    st.info("📥 Contenido no descargado (solo headers).")
                    if st.button(f"⬇️ Cargar contenido", key=f"btn_cargar_{idx}", type="primary", use_container_width=True):
                        with st.spinner("Descargando..."):
                            correo = cargar_contenido_correo(correo)
                        st.rerun()
                else:
                    tiene_html = correo.get('tiene_html', False)
                    if tiene_html:
                        tab_html, tab_texto = st.tabs(["🌐 Vista original", "📝 Texto plano"])
                        with tab_html:
                            import streamlit.components.v1 as components
                            html_seguro = re.sub(r'<script[^>]*>.*?</script>', '', correo.get('html_raw', ''), flags=re.DOTALL | re.IGNORECASE)
                            html_seguro = re.sub(r'<iframe[^>]*>.*?</iframe>', '', html_seguro, flags=re.DOTALL | re.IGNORECASE)
                            components.html(f'<div style="background:#fff;color:#1f2937;padding:16px;border-radius:8px;font-family:Arial,sans-serif;font-size:14px;line-height:1.6;overflow:auto;">{html_seguro}</div>', height=500, scrolling=True)
                        with tab_texto:
                            if correo.get('cuerpo'):
                                st.text_area("Contenido", value=correo['cuerpo'][:3000], height=200, disabled=True, key=f"correo_body_{idx}", label_visibility="collapsed")
                    else:
                        if correo.get('cuerpo'):
                            st.text_area("Contenido", value=correo['cuerpo'][:3000], height=200, disabled=True, key=f"correo_body_{idx}", label_visibility="collapsed")

                    # ── Selector de imágenes inline ──
                    imagenes = correo.get('imagenes_inline', {})
                    if imagenes:
                        _render_selector_imagenes(idx, correo)

                    adjuntos = correo.get('adjuntos', [])
                    if adjuntos:
                        st.markdown(f"**📎 Adjuntos ({len(adjuntos)}):**")
                        for a_idx, att in enumerate(adjuntos):
                            col_info, col_btn = st.columns([3, 1])
                            with col_info:
                                st.caption(f"📄 {att['nombre']} — {att['tamano']/1024:.1f} KB ({att['tipo']})")
                            with col_btn:
                                if att.get('datos_b64'):
                                    import base64 as _b64
                                    st.download_button("⬇️ Descargar", data=_b64.b64decode(att['datos_b64']), file_name=att['nombre'], mime=att['tipo'], key=f"dl_{idx}_{a_idx}", use_container_width=True)

            # ── Acciones ──
            col_crear, col_vincular, col_descartar, col_espacio = st.columns([2, 2, 2, 2])

            with col_crear:
                crear_clicked = st.button("✅ Crear Orden", key=f"btn_crear_{idx}", type="primary", use_container_width=True)
            with col_vincular:
                vincular_clicked = st.button("🔗 Vincular a OT", key=f"btn_vincular_{idx}", use_container_width=True)
            with col_descartar:
                descartar_clicked = st.button("🗑️ Descartar", key=f"btn_descartar_{idx}", use_container_width=True)

            if descartar_clicked:
                _marcar_procesado(msg_id, accion="descartado")
                pendientes_actual = st.session_state.get('_correos_pendientes', [])
                st.session_state['_correos_pendientes'] = [c for c in pendientes_actual if c['message_id'] != msg_id]
                st.toast(f"🗑️ Descartado: {correo['asunto'][:40]}")
                st.rerun()

            if vincular_clicked:
                st.session_state[f'_vincular_ot_{idx}'] = True
                st.session_state.pop(f'_crear_ot_{idx}', None)

            if st.session_state.get(f'_vincular_ot_{idx}', False):
                render_selector_ordenes_para_vincular(idx, correo, df_ordenes, df_act)

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
                    tech_opts = {u['nombre']: u['id'] for _, u in df_users.iterrows()} if not df_users.empty else {}
                    tecnico = st.selectbox("Asignar a", list(tech_opts.keys()), key=f"correo_tecnico_{idx}") if tech_opts else None
                    desc_default = f"[Correo de {correo['remitente']}]\n\nAsunto: {correo['asunto']}\n\n{correo.get('cuerpo_corto', '')}"
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
                                        "activo_id": act_id, "descripcion": descripcion.strip(),
                                        "criticidad": criticidad, "tipo_mantenimiento": tipo,
                                        "estado": "Abierta", "tecnico_asignado": str(tech_opts[tecnico]),
                                        "fecha_creacion": datetime.now().isoformat(),
                                        "origen": "correo", "correo_message_id": msg_id,
                                    })
                                    if res.data:
                                        nuevo_id = res.data[0]['id']
                                        db_insert("bitacora", {
                                            "orden_id": nuevo_id, "usuario_text": "CORREO (automático)",
                                            "mensaje": f"📧 Creada desde correo de {correo['remitente']}\nAsunto: {correo['asunto']}",
                                            "fecha": datetime.now().isoformat()
                                        })
                                        # Subir adjuntos
                                        adjuntos_correo = correo.get('adjuntos', [])
                                        if adjuntos_correo:
                                            with st.spinner(f"Subiendo {len(adjuntos_correo)} adjunto(s)..."):
                                                _subir_adjuntos_correo(adjuntos_correo, nuevo_id)

                                        # Subir SOLO imágenes seleccionadas
                                        imagenes_inline = correo.get('imagenes_inline', {})
                                        if imagenes_inline:
                                            imagenes_sel = _obtener_seleccion_imagenes(idx, msg_id, imagenes_inline)
                                            n_sel = sum(1 for v in imagenes_sel.values() if v)
                                            if n_sel > 0:
                                                _subir_imagenes_inline_seleccionadas(
                                                    imagenes_inline, imagenes_sel, nuevo_id,
                                                    correo.get('remitente_nombre') or correo.get('remitente', 'correo')
                                                )

                                        _marcar_procesado(msg_id, orden_id=nuevo_id, accion="orden")
                                        pendientes_actual = st.session_state.get('_correos_pendientes', [])
                                        st.session_state['_correos_pendientes'] = [c for c in pendientes_actual if c['message_id'] != msg_id]
                                        st.session_state.pop(f'_crear_ot_{idx}', None)
                                        st.success(f"✅ Orden #{nuevo_id} creada desde correo.")
                                        st.rerun()
                                else:
                                    st.warning("⚠️ Crea el activo primero en el módulo de Inventario.")
                            except Exception as e:
                                st.error(f"Error creando orden: {e}")

            st.markdown("---")

    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    col1.metric("📬 Descargados", len(correos))
    col2.metric("⏳ Pendientes", len(correos_pendientes))
    col3.metric("✅ Procesados (histórico)", len(procesados))


# ==============================================================================
# 🔍 COMPARACIÓN GMAIL vs BASE DE DATOS
# ==============================================================================
def comparar_gmail_vs_bd(max_correos=100, dias_atras=30):
    """Compara TODOS los correos de Gmail contra la base de datos."""
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

        BATCH_SIZE = 50
        gmail_message_ids = set()

        for batch_start in range(0, len(ids), BATCH_SIZE):
            batch_ids = ids[batch_start:batch_start + BATCH_SIZE]
            ids_str = ",".join(mid.decode() if isinstance(mid, bytes) else str(mid) for mid in batch_ids)

            try:
                socket.setdefaulttimeout(30)
                status, datos_raw = mail.fetch(ids_str, "(BODY[HEADER.FIELDS (MESSAGE-ID FROM SUBJECT DATE)])")
            except socket.timeout:
                resultado['errores'].append(f"Timeout en batch {batch_start//BATCH_SIZE + 1}")
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
                except Exception as e:
                    continue

        resultado['en_limbo'] = [
            h for h in resultado['gmail_headers']
            if not h['en_alguna_tabla']
        ]

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
    """Barrido completo de la base de datos de correos."""
    from utils.db import supabase

    resultado = {
        'procesados': [],
        'ordenes_desde_correo': [],
        'solicitudes_correo': [],
        'resumen': {},
    }

    if not supabase:
        return resultado

    try:
        res = supabase.table("emails_procesados").select("*").order("fecha_procesado", desc=True).execute()
        resultado['procesados'] = res.data or []
    except Exception as e:
        print(f"⚠️ Error consultando emails_procesados: {e}")

    try:
        res_ord = supabase.table("ordenes").select("*").eq("origen", "correo").order("id", desc=True).execute()
        resultado['ordenes_desde_correo'] = res_ord.data or []
    except Exception as e:
        print(f"⚠️ Error consultando órdenes desde correo: {e}")
        try:
            res_ord2 = supabase.table("ordenes").select("*").not_.is_("correo_message_id", "null").order("id", desc=True).execute()
            resultado['ordenes_desde_correo'] = res_ord2.data or []
        except Exception:
            pass

    try:
        res_sol = supabase.table("solicitudes").select("*").order("id", desc=True).limit(100).execute()
        resultado['solicitudes_correo'] = [
            s for s in (res_sol.data or [])
            if s.get('origen') == 'correo' or s.get('chat_id', '').startswith('email')
        ]
    except Exception:
        pass

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
    """Renderiza la página de auditoría completa de correos."""
    st.markdown("### 🔍 Auditoría de Correos")
    st.caption("Estado real de todos los correos + detección de correos en limbo vs Gmail.")

    datos = barrido_base_datos_correos()
    resumen = datos['resumen']

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("📨 Total Procesados", resumen['total_procesados'])
    col2.metric("🛠️ Órdenes desde Correo", resumen['total_ordenes_correo'])
    col3.metric("🔗 Con OT Asignada", resumen['con_orden'])
    col4.metric("⚠️ Sin OT Asignada", resumen['sin_orden'])

    st.markdown("---")

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

    from utils.db import supabase as _supa
    tabla_pendientes_ok = False
    if _supa:
        try:
            _supa.table("emails_pendientes").select("message_id").limit(1).execute()
            tabla_pendientes_ok = True
        except Exception:
            tabla_pendientes_ok = False

    if not tabla_pendientes_ok:
        st.warning("⚠️ La tabla `emails_pendientes` no existe en Supabase.")
        with st.expander("📋 SQL para crear la tabla", expanded=False):
            st.code("""
CREATE TABLE IF NOT EXISTS emails_pendientes (
    message_id TEXT PRIMARY KEY,
    remitente TEXT DEFAULT '',
    remitente_nombre TEXT DEFAULT '',
    asunto TEXT DEFAULT '',
    fecha_correo TEXT DEFAULT '',
    cuerpo_corto TEXT DEFAULT '',
    n_adjuntos INTEGER DEFAULT 0,
    leido BOOLEAN DEFAULT FALSE,
    descargado_en TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_emails_pendientes_message_id
    ON emails_pendientes(message_id);
ALTER TABLE emails_pendientes ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all" ON emails_pendientes FOR ALL USING (true);
""", language="sql")

    st.markdown("---")

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

    datos_cmp = st.session_state.get('_auditoria_cmp_resultados', None)
    if ejecutar_cmp:
        with st.spinner(f"Conectando a Gmail y comparando (hasta {max_corr_aud} correos, {dias_aud} días)..."):
            datos_cmp = comparar_gmail_vs_bd(max_correos=max_corr_aud, dias_atras=dias_aud)
        st.session_state['_auditoria_cmp_resultados'] = datos_cmp

    if datos_cmp:
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
            st.error(f"⚠️ **{en_limbo} correos están en LIMBO** — en Gmail pero no gestionados.")

            st.markdown("---")
            st.markdown("##### 📋 Acciones sobre correos en limbo")

            col_cargar, col_guardar, col_descartar = st.columns(3)
            with col_cargar:
                if st.button(f"📥 Cargar {en_limbo} correos para REVISAR", type="primary", use_container_width=True, key="aud_cargar_limbo"):
                    with st.spinner(f"Descargando contenido de {en_limbo} correos desde Gmail..."):
                        correos_limbo = _descargar_correos_por_message_ids(
                            [h['message_id'] for h in datos_cmp['en_limbo']]
                        )
                    if correos_limbo:
                        st.session_state['_correos_pendientes'] = correos_limbo
                        st.success(f"✅ {len(correos_limbo)} correo(s) cargado(s). Cambia a la pestaña **📧 Correo** para revisarlos.")
                        st.session_state['_auditoria_cmp_resultados'] = None
                    else:
                        st.error("❌ No se pudieron descargar los correos.")
            with col_guardar:
                if tabla_pendientes_ok:
                    if st.button(f"💾 Guardar {en_limbo} como pendientes", type="secondary", use_container_width=True, key="aud_guardar_limbo"):
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
                else:
                    st.button("💾 Guardar (tabla no existe)", disabled=True, use_container_width=True, key="aud_guardar_limbo_dis")
            with col_descartar:
                if st.button(f"🗑️ Descartar TODOS los limbo", type="secondary", use_container_width=True, key="aud_desc_limbo"):
                    descartados = 0
                    for h in datos_cmp['en_limbo']:
                        try:
                            _marcar_procesado(h['message_id'], accion="descartado")
                            descartados += 1
                        except Exception:
                            pass
                    st.success(f"🗑️ {descartados} correos descartados.")
                    st.session_state['_auditoria_cmp_resultados'] = None
                    st.rerun()

            st.markdown("---")

            with st.expander(f"📋 Ver detalle de los {en_limbo} correos en limbo", expanded=False):
                for i, h in enumerate(datos_cmp['en_limbo']):
                    asunto = (h.get('asunto', '') or '')[:70]
                    remitente = (h.get('remitente', '') or '')[:50]
                    fecha = (h.get('fecha', '') or '')[:25]

                    col_info_l, col_acc_l = st.columns([4, 1])
                    with col_info_l:
                        st.markdown(f"""
                        <div style="border-left:3px solid #EF4444;padding:6px 10px;margin-bottom:3px;background:rgba(239,68,68,0.05);border-radius:0 6px 6px 0;">
                            <div style="color:#EF4444;font-weight:600;font-size:0.85em;">📧 {asunto}</div>
                            <div style="color:#9CA3AF;font-size:0.75em;">👤 {remitente} · {fecha}</div>
                        </div>
                        """, unsafe_allow_html=True)
                    with col_acc_l:
                        if st.button("🗑️", key=f"aud_desc_ind_{i}", help="Descartar", use_container_width=True):
                            _marcar_procesado(h['message_id'], accion="descartado")
                            datos_cmp['en_limbo'] = [x for x in datos_cmp['en_limbo'] if x['message_id'] != h['message_id']]
                            st.session_state['_auditoria_cmp_resultados'] = datos_cmp
                            st.toast(f"🗑️ Descartado: {asunto[:30]}")
                            st.rerun()

        else:
            st.success("✅ **Sin correos en limbo.** Todos los correos de Gmail están en la base de datos.")

        if datos_cmp['en_bd_no_gmail']:
            st.markdown(f"##### 👻 En BD pero NO en Gmail ({len(datos_cmp['en_bd_no_gmail'])})")
            for mid in datos_cmp['en_bd_no_gmail'][:20]:
                st.caption(f"📧 {mid[:80]}")

        if datos_cmp['gmail_headers']:
            with st.expander(f"📋 Ver todos los {len(datos_cmp['gmail_headers'])} correos escaneados", expanded=False):
                for h in datos_cmp['gmail_headers']:
                    icon = "✅" if h['en_procesados'] else "💾" if h['en_pendientes'] else "⚠️"
                    txt = "Procesado" if h['en_procesados'] else "Pendiente" if h['en_pendientes'] else "LIMBO"
                    color = "#10B981" if h['en_procesados'] else "#3B82F6" if h['en_pendientes'] else "#EF4444"
                    st.markdown(f'<div style="border-left:2px solid {color};padding:4px 10px;margin-bottom:3px;font-size:0.85em;">{icon} <b>{txt}</b> | {(h.get("asunto",""))[:50]} | 👤 {(h.get("remitente",""))[:30]}</div>', unsafe_allow_html=True)

        st.markdown("---")

    procesados = datos['procesados']
    if procesados:
        st.markdown("#### 📋 Historial Completo de Correos Procesados")

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

    huerfanos = [p for p in procesados if not p.get('orden_id') and p.get('accion') not in ('descartado', 'rechazado')]
    if huerfanos:
        st.markdown("---")
        st.markdown(f"#### ⚠️ Correos Huérfanos — Procesados sin OT ({len(huerfanos)})")
        for p in huerfanos:
            msg_id = p.get('message_id', '?')[:50]
            fecha = (p.get('fecha_procesado', '') or '')[:16].replace('T', ' ')
            accion = p.get('accion', '?')
            st.warning(f"📧 {msg_id} — Acción: {accion} — Fecha: {fecha}")

    if not procesados and not ordenes_correo and not datos_cmp:
        st.info("📭 No hay registros de correos procesados en la base de datos.")


def _diagnosticar_gmail():
    """Diagnóstico paso a paso de la conexión Gmail IMAP."""
    st.markdown("#### 🩺 Diagnóstico de Conexión Gmail")

    correo, password = _obtener_credenciales()

    st.markdown("**1️⃣ Verificando configuración...**")
    if not correo:
        st.error("❌ `correo` no configurado en [gmail] de secrets.toml")
        return
    if not password:
        st.error("❌ `password` no configurado en [gmail] de secrets.toml")
        return
    st.success(f"✅ Correo: `{correo}` | Password: `{'✅ configurada' if password else '❌ vacía'}`")

    st.markdown("**2️⃣ Conectando a Gmail IMAP...**")
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        st.success("✅ Conexión SSL establecida con imap.gmail.com")
    except Exception as e:
        st.error(f"❌ No se pudo conectar: `{type(e).__name__}`: {str(e)[:300]}")
        return

    st.markdown("**3️⃣ Autenticando...**")
    try:
        mail.login(correo, password)
        st.success("✅ Login exitoso")
    except imaplib.IMAP4.error as e:
        st.error(f"❌ Autenticación falló: {str(e)[:300]}")
        return
    except Exception as e:
        st.error(f"❌ Error: `{type(e).__name__}`: {str(e)[:300]}")
        return

    st.markdown("**4️⃣ Listando carpetas...**")
    try:
        status, carpetas = mail.list()
        if status == "OK":
            st.success(f"✅ {len(carpetas)} carpetas encontradas")
            for c in carpetas[:10]:
                st.caption(f"  📁 {c.decode() if isinstance(c, bytes) else c}")
    except Exception as e:
        st.warning(f"⚠️ No se pudieron listar carpetas: {e}")

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

    try:
        mail.logout()
    except Exception:
        pass

    st.markdown("---")
    st.markdown("**📋 Configuración en secrets.toml:**")
    st.code("""
[gmail]
correo = "orion.mantenimientoapp@gmail.com"
password = "xxxx xxxx xxxx xxxx"
""", language="toml")
    st.caption("La password es la de aplicación de 16 caracteres (no tu contraseña de Gmail)")
