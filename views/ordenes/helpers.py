# views/ordenes/helpers.py — Funciones compartidas del módulo de órdenes
import streamlit as st
import time
from datetime import datetime
from utils.db import supabase, db_insert, db_update, db_delete
from utils.helpers import error_amigable, agregar_notificacion, registrar_accion_critica, navegar_a
from utils.uploads import subir_archivo_generico
from utils.email_parser import parse_email_file, construir_descripcion_email, render_email_preview
from email.utils import parsedate_to_datetime
import re as _re


def generar_adjunto_html(url, icon_mode=False):
    if not url:
        return ""
    ul = url.lower()
    if ul.endswith(('.jpg', '.jpeg', '.png', '.webp')):
        return f"""<br><a href="{url}" target="_blank" style="color:#10B981;font-weight:bold;">🖼️ Ver Imagen</a>"""
    elif ul.endswith('.pdf'):
        return f"""<br><a href="{url}" target="_blank" style="color:#EF4444;font-weight:bold;">📄 Ver PDF</a>"""
    elif ul.endswith(('.xls', '.xlsx')):
        return f"""<br><a href="{url}" target="_blank" style="color:#16A34A;font-weight:bold;">📊 Ver Excel</a>"""
    elif ul.endswith('.msg'):
        return f"""<br><a href="{url}" target="_blank" style="color:#3B82F6;font-weight:bold;">📧 Ver Correo</a>"""
    else:
        return f"""<br><a href="{url}" target="_blank" style="color:#F59E0B;font-weight:bold;">📎 Ver Archivo</a>"""


def parse_email_callback(context_key: str):
    """Callback que se ejecuta al subir un archivo. Detecta si es correo y lo parsea."""
    archivo = st.session_state.get(f'_archivo_unif_{context_key}')
    if archivo is None:
        st.session_state.pop(f'_parsed_email_{context_key}', None)
        return

    nombre = archivo.name.lower()
    cache_key = f'_parsed_email_{context_key}'

    if nombre.endswith(('.msg', '.eml')):
        datos = parse_email_file(archivo)
        if datos:
            st.session_state[cache_key] = datos
            st.session_state['_email_desc_default'] = construir_descripcion_email(datos)
        else:
            st.session_state.pop(cache_key, None)
    else:
        st.session_state.pop(cache_key, None)


def render_archivo_unificado(context_key: str):
    """
    Un solo uploader que detecta si es correo (.msg/.eml) o archivo normal.
    Usa on_change para parsear emails inmediatamente al subir.
    """
    st.file_uploader(
        "📎 Adjunto (PDF, Excel, Foto, Correo .msg/.eml)",
        type=["pdf", "docx", "xlsx", "jpg", "png", "msg", "eml"],
        key=f"_archivo_unif_{context_key}",
        on_change=parse_email_callback,
        args=(context_key,),
    )

    archivo = st.session_state.get(f'_archivo_unif_{context_key}')
    if archivo is None:
        return None, None

    nombre = archivo.name.lower()
    cache_key = f'_parsed_email_{context_key}'

    if nombre.endswith(('.msg', '.eml')):
        datos = st.session_state.get(cache_key)
        if datos:
            render_email_preview(datos)
        return archivo, datos
    else:
        st.caption(f"📄 {archivo.name} — listo para adjuntar")
        return archivo, None


# ==============================================================================
# 📅 UTILIDADES PARA FECHA DE CORREO EN BITÁCORA
# ==============================================================================
def _parsear_fecha_correo(fecha_raw) -> str:
    """
    Convierte la fecha del correo a formato ISO 8601.
    Soporta múltiples formatos: string RFC 2822, ISO, datetime.
    Retorna la fecha actual si no puede parsear.
    """
    if not fecha_raw:
        return datetime.now().isoformat()

    if isinstance(fecha_raw, str):
        fecha_str = fecha_raw.strip()
        # Si ya parece ISO
        if fecha_str and fecha_str[0].isdigit():
            return fecha_str[:19]
        # Intentar RFC 2822
        try:
            dt = parsedate_to_datetime(fecha_str)
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            pass
        # Intentar ISO genérico
        try:
            dt = datetime.fromisoformat(fecha_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%dT%H:%M:%S')
        except Exception:
            pass

    if isinstance(fecha_raw, datetime):
        return fecha_raw.strftime('%Y-%m-%dT%H:%M:%S')

    return datetime.now().isoformat()


def construir_mensaje_bitacora_email(datos_email: dict) -> str:
    """
    Construye un mensaje estructurado para la bitácora cuando se anexa un correo.
    Usa tags [📧 CORREO]...[/📧 CORREO] que el historial detecta y renderiza
    de forma expandible.
    """
    if not datos_email:
        return "📧 Correo adjunto."

    partes = []
    partes.append("[📧 CORREO]")
    partes.append(f"Remitente: {datos_email.get('remitente', 'Desconocido')}")
    partes.append(f"Asunto: {datos_email.get('asunto', '(Sin asunto)')}")
    if datos_email.get('fecha'):
        partes.append(f"Fecha correo: {datos_email['fecha']}")
    partes.append("---")

    cuerpo = datos_email.get('cuerpo', '')
    print(f"📧 construir_mensaje_bitacora_email: cuerpo_len={len(cuerpo)}")
    if cuerpo:
        if len(cuerpo) > 2000:
            cuerpo = cuerpo[:2000] + "... [truncado]"
        partes.append(cuerpo)
    else:
        partes.append("(Contenido no disponible)")

    if datos_email.get('adjuntos'):
        partes.append(f"📎 {len(datos_email['adjuntos'])} adjunto(s) en el correo")

    partes.append("[/📧 CORREO]")
    return '\n'.join(partes)


def es_mensaje_email(mensaje: str) -> bool:
    """Detecta si un mensaje de bitácora es un correo estructurado."""
    return '[📧 CORREO]' in (mensaje or '')


def extraer_datos_email_de_mensaje(mensaje: str) -> dict:
    """
    Extrae los datos del correo desde un mensaje de bitácora estructurado.
    Retorna dict con: remitente, asunto, fecha_correo, cuerpo
    """
    datos = {}
    if not mensaje or '[📧 CORREO]' not in mensaje:
        return datos

    contenido = mensaje.split('[📧 CORREO]')[1]
    if '[/📧 CORREO]' in contenido:
        contenido = contenido.split('[/📧 CORREO]')[0]

    lineas = contenido.strip().split('\n')
    cuerpo_lineas = []
    en_cuerpo = False

    for linea in lineas:
        linea_strip = linea.strip()
        if linea_strip.startswith('Remitente:'):
            datos['remitente'] = linea_strip[len('Remitente:'):].strip()
        elif linea_strip.startswith('Asunto:'):
            datos['asunto'] = linea_strip[len('Asunto:'):].strip()
        elif linea_strip.startswith('Fecha correo:'):
            datos['fecha_correo'] = linea_strip[len('Fecha correo:'):].strip()
        elif linea_strip == '---':
            en_cuerpo = True
        elif en_cuerpo:
            cuerpo_lineas.append(linea)

    datos['cuerpo'] = '\n'.join(cuerpo_lineas).strip()
    return datos
