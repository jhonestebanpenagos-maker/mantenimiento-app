"""
utils/email_parser.py — Parseo automático de correos electrónicos (.msg / .eml)
Extrae: remitente, asunto, fecha, cuerpo y adjuntos.
"""
import streamlit as st
import email
import email.policy
import io
import re
from datetime import datetime


def parse_email_file(uploaded_file) -> dict | None:
    """
    Parsea un archivo de correo (.msg o .eml) y retorna un dict con los datos.
    Retorna None si no puede parsear.
    """
    if uploaded_file is None:
        return None

    nombre = uploaded_file.name.lower()

    try:
        if nombre.endswith('.msg'):
            return _parse_msg(uploaded_file)
        elif nombre.endswith('.eml'):
            return _parse_eml(uploaded_file)
        else:
            return None
    except Exception as e:
        print(f"Error parseando correo {uploaded_file.name}: {e}")
        return None


def _parse_msg(uploaded_file) -> dict:
    """Parsea archivos .msg de Outlook."""
    import extract_msg

    bytes_data = uploaded_file.getvalue()
    msg = extract_msg.Message(io.BytesIO(bytes_data))

    remitente = msg.sender or "Desconocido"
    asunto = msg.subject or "(Sin asunto)"
    fecha = msg.date or ""

    # Intentar extraer cuerpo de múltiples formas
    cuerpo = msg.body or ""
    if not cuerpo:
        # Fallback: intentar con htmlBody
        try:
            cuerpo = msg.htmlBody or ""
            if cuerpo:
                cuerpo = _html_a_texto(cuerpo)
        except Exception:
            pass
    if not cuerpo:
        # Fallback: intentar con rtfBody
        try:
            cuerpo = msg.rtfBody or ""
        except Exception:
            pass

    print(f"📧 Parseando .msg: asunto='{asunto}', cuerpo_len={len(cuerpo)}")

    # Limpiar cuerpo
    cuerpo = _limpiar_cuerpo(cuerpo)

    # Extraer adjuntos del correo
    adjuntos = []
    for att in msg.attachments:
        adjuntos.append({
            'nombre': att.longFilename or att.shortFilename or "adjunto",
            'datos': att.data,
            'tipo': _detectar_mime(att.longFilename or att.shortFilename or ""),
        })

    return {
        'remitente': remitente,
        'asunto': asunto,
        'fecha': fecha,
        'cuerpo': cuerpo,
        'adjuntos': adjuntos,
        'formato': 'msg',
    }


def _parse_eml(uploaded_file) -> dict:
    """Parsea archivos .eml (estándar RFC 822)."""
    bytes_data = uploaded_file.getvalue()
    msg = email.message_from_bytes(bytes_data, policy=email.policy.default)

    remitente = msg['from'] or "Desconocido"
    asunto = msg['subject'] or "(Sin asunto)"
    fecha = msg['date'] or ""

    # Extraer cuerpo
    cuerpo = ""
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == 'text/plain':
                cuerpo = part.get_content()
                break
            elif ctype == 'text/html' and not cuerpo:
                cuerpo = _html_a_texto(part.get_content())
    else:
        cuerpo = msg.get_content() or ""

    cuerpo = _limpiar_cuerpo(cuerpo)

    # Extraer adjuntos
    adjuntos = []
    if msg.is_multipart():
        for part in msg.walk():
            cd = str(part.get("Content-Disposition", ""))
            if "attachment" in cd:
                nombre_att = part.get_filename() or "adjunto"
                datos = part.get_payload(decode=True)
                if datos:
                    adjuntos.append({
                        'nombre': nombre_att,
                        'datos': datos,
                        'tipo': part.get_content_type(),
                    })

    return {
        'remitente': remitente,
        'asunto': asunto,
        'fecha': fecha,
        'cuerpo': cuerpo,
        'adjuntos': adjuntos,
        'formato': 'eml',
    }


def _limpiar_cuerpo(cuerpo: str) -> str:
    """Limpia el cuerpo del correo: quita exceso de líneas vacías, signatures, etc."""
    if not cuerpo:
        return ""

    # Quitar líneas de firma comunes
    lineas = cuerpo.split('\n')
    limpias = []
    en_firma = False
    for linea in lineas:
        if linea.strip().startswith('-- ') or linea.strip() == '--':
            en_firma = True
        if not en_firma:
            limpias.append(linea)

    resultado = '\n'.join(limpias).strip()

    # Limitar a 2000 chars para no saturar la descripción
    if len(resultado) > 2000:
        resultado = resultado[:2000] + "\n... [contenido truncado]"

    return resultado


def _html_a_texto(html: str) -> str:
    """Convierte HTML básico a texto plano."""
    # Quitar scripts y styles
    texto = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
    texto = re.sub(r'<script[^>]*>.*?</script>', '', texto, flags=re.DOTALL)
    # Convertir saltos de línea HTML
    texto = re.sub(r'<br\s*/?>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'</?p[^>]*>', '\n', texto, flags=re.IGNORECASE)
    texto = re.sub(r'</?div[^>]*>', '\n', texto, flags=re.IGNORECASE)
    # Quitar tags HTML
    texto = re.sub(r'<[^>]+>', ' ', texto)
    # Decodificar entidades comunes
    texto = texto.replace('&nbsp;', ' ').replace('&amp;', '&')
    texto = texto.replace('&lt;', '<').replace('&gt;', '>')
    texto = texto.replace('&quot;', '"').replace('&#39;', "'")
    # Colapsar espacios múltiples
    texto = re.sub(r'[ \t]+', ' ', texto)
    # Colapsar saltos de línea múltiples
    texto = re.sub(r'\n\s*\n+', '\n\n', texto)
    return texto.strip()


def _detectar_mime(nombre: str) -> str:
    """Detecta el MIME type por extensión."""
    nombre = nombre.lower()
    if nombre.endswith(('.jpg', '.jpeg')):
        return 'image/jpeg'
    elif nombre.endswith('.png'):
        return 'image/png'
    elif nombre.endswith('.pdf'):
        return 'application/pdf'
    elif nombre.endswith(('.xls', '.xlsx')):
        return 'application/vnd.ms-excel'
    elif nombre.endswith('.msg'):
        return 'application/vnd.ms-outlook'
    else:
        return 'application/octet-stream'


def construir_descripcion_email(datos: dict) -> str:
    """
    Construye un texto de descripción formateado a partir de los datos del correo.
    Listo para pegar en el campo de descripción de la orden.
    """
    partes = []
    partes.append(f"📧 [Correo recibido]")
    partes.append(f"De: {datos['remitente']}")
    partes.append(f"Asunto: {datos['asunto']}")
    if datos.get('fecha'):
        partes.append(f"Fecha: {datos['fecha']}")
    partes.append("")
    partes.append("--- Mensaje ---")
    partes.append(datos['cuerpo'])

    if datos.get('adjuntos'):
        partes.append("")
        partes.append(f"📎 Adjuntos en el correo ({len(datos['adjuntos'])}):")
        for att in datos['adjuntos']:
            partes.append(f"  • {att['nombre']}")

    return '\n'.join(partes)


def render_email_preview(datos: dict):
    """Renderiza una vista previa del correo parseado en Streamlit."""
    st.markdown(f"""
    <div style="background:rgba(59,130,246,0.1);border:1px solid #3B82F6;border-radius:8px;padding:14px;margin-bottom:12px;">
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="font-size:1.3rem;">📧</span>
            <span style="color:#60A5FA;font-weight:700;font-size:0.95rem;">Correo parseado automáticamente</span>
        </div>
        <div style="font-size:0.85rem;color:#E5E7EB;">
            <div><b>De:</b> {_escape(datos['remitente'])}</div>
            <div><b>Asunto:</b> {_escape(datos['asunto'])}</div>
            {f"<div><b>Fecha:</b> {_escape(str(datos['fecha']))}</div>" if datos.get('fecha') else ''}
        </div>
    </div>
    """, unsafe_allow_html=True)

    if datos['cuerpo']:
        with st.expander("📝 Ver cuerpo del correo", expanded=False):
            st.text(datos['cuerpo'][:1000])

    if datos.get('adjuntos'):
        st.caption(f"📎 {len(datos['adjuntos'])} adjunto(s) detectados en el correo")


def _escape(texto: str) -> str:
    """Escapa HTML básico."""
    import html
    return html.escape(str(texto))
