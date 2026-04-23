# views/ordenes/helpers.py — Funciones compartidas del módulo de órdenes
import streamlit as st
import time
from datetime import datetime
from utils.db import supabase, db_insert, db_update, db_delete
from utils.helpers import error_amigable, agregar_notificacion, registrar_accion_critica, navegar_a
from utils.uploads import subir_archivo_generico
from utils.email_parser import parse_email_file, construir_descripcion_email, render_email_preview


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
