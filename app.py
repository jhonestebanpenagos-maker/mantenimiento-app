# ==============================================================================
# PROYECTO: ORIÓN - Mantenimiento Inteligente
# AUTOR: [JHON ESTEBAN PENAGOS]
# VERSIÓN: CORREGIDA Y DEPURADA
# ==============================================================================
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
import io
import os
import requests
import urllib.parse
import json
import qrcode
import cv2
import numpy as np
import time
import hashlib
import uuid
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import tempfile
from pdf_utils import generar_hoja_vida_pdf, generar_pdf_orden

def hashear_password(password: str) -> str:
    """Convierte una contraseña en texto plano a SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

# --- IMPORTS PARA CLOUDINARY ---
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Orión | Mantenimiento", layout="wide", initial_sidebar_state="collapsed")
st.write("Streamlit version:", st.__version__)

# ==============================================================================
# ☁️ CONFIGURACIÓN DE CLOUDINARY
# ==============================================================================
try:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key    = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure     = True
    )
except KeyError:
    st.warning("⚠️ ADVERTENCIA: No se encontraron las credenciales de Cloudinary en secrets.toml.")
except Exception as e:
    st.error(f"Error configurando Cloudinary: {e}")

# ==============================================================================
# 🎨 CARGA DE ESTILOS Y TEMA (CSS)
# ==============================================================================
def cargar_css():
    try:
        with open("styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("⚠️ No se encontró el archivo styles.css en la carpeta.")

cargar_css()

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"❌ ERROR CRÍTICO: La clave {e} no se encuentra en secrets.toml.")
        return None
    except Exception as e:
        st.error(f"❌ Error desconocido al conectar a Supabase: {e}")
        return None

supabase = init_supabase()
if not supabase:
    st.stop()

# ==============================================================================
# 🔔 SISTEMA DE NOTIFICACIONES
# ==============================================================================
def agregar_notificacion(tipo, mensaje):
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    st.session_state.notifications.append({'type': tipo, 'message': mensaje})

def mostrar_notificaciones():
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    for notif in st.session_state.notifications[:]:
        if notif['type'] == 'success':
            st.success(f"✅ {notif['message']}")
        elif notif['type'] == 'error':
            st.error(f"❌ {notif['message']}")
        elif notif['type'] == 'warning':
            st.warning(f"⚠️ {notif['message']}")
        elif notif['type'] == 'delete':
            st.error(f"🗑️ {notif['message']}")
    st.session_state.notifications = []

# --- 3. FUNCIONES AUXILIARES ---

def subir_archivo_generico(archivo):
    """Sube archivos forzando acceso PÚBLICO para evitar el error 401."""
    if archivo:
        try:
            nombre_original = archivo.name.lower()
            ext_imagenes = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
            es_imagen_visual = nombre_original.endswith(ext_imagenes)

            if es_imagen_visual:
                tipo_recurso   = "image"
                carpeta        = "orion_evidencias"
                public_id_manual = None
                use_unique     = True
            else:
                tipo_recurso   = "raw"
                carpeta        = "orion_documentos"
                nombre_base, extension = os.path.splitext(archivo.name)
                nombre_limpio  = "".join(c for c in nombre_base if c.isalnum() or c in ('_', '-')).strip()
                timestamp      = int(time.time())
                public_id_manual = f"{nombre_limpio}_{timestamp}{extension}"
                use_unique     = False

            respuesta = cloudinary.uploader.upload(
                archivo.getvalue(),
                folder        = carpeta,
                resource_type = tipo_recurso,
                public_id     = public_id_manual,
                use_filename  = True,
                unique_filename = use_unique,
                type          = "upload",
                access_mode   = "public"
            )
            return respuesta.get("secure_url")
        except Exception as e:
            st.error(f"Error subiendo archivo: {e}")
            return None
    return None


# FIX 1: Se eliminó la función _run_query_live_data con código muerto.
def run_query(table_name, filters=None, order_by="id"):
    tablas_maestras = ["usuarios", "activos", "categorias", "ubicaciones", "inventario"]
    if table_name in tablas_maestras:
        return pd.DataFrame(_run_query_internal(table_name, filters, order_by))
    else:
        return pd.DataFrame(_run_query_live_data(table_name, filters, order_by))

@st.cache_data(ttl=600)
def _run_query_internal(table_name, filters, order_by):
    query = supabase.table(table_name).select("*")
    if filters:
        for key, value in filters.items():
            query = query.eq(key, value)
    res = query.order(order_by).execute()
    return res.data if res.data else []

# FIX 2: Eliminado el código muerto (líneas inalcanzables después del return).
def _run_query_live_data(table_name, filters, order_by):
    try:
        query = supabase.table(table_name).select("*")
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        res = query.order(order_by).execute()
        return res.data if res.data else []
    except Exception as e:
        st.error(f"Error en consulta {table_name}: {e}")
        return []


def subir_imagen(archivo, carpeta="orion_evidencias"):
    """Sube imágenes a Cloudinary. Retorna la URL segura (https)."""
    if archivo:
        try:
            file_to_upload = archivo.getvalue() if hasattr(archivo, 'getvalue') else archivo
            respuesta = cloudinary.uploader.upload(
                file_to_upload,
                folder        = carpeta,
                resource_type = "image",
                transformation = [
                    {'width': 1000, 'crop': "limit"},
                    {'quality': "auto"},
                    {'fetch_format': "auto"}
                ]
            )
            return respuesta.get("secure_url")
        except Exception as e:
            st.error(f"Error al subir imagen a la nube: {e}")
            return None
    return None


def generar_qr_activo(id_activo, nombre_activo):
    base_url = "https://mantenimiento-app-esw6r3vpeqxngz3ifyp5ey.streamlit.app"
    link = f"{base_url}/?id_activo_qr={id_activo}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return subir_imagen(img_byte_arr.getvalue(), "orion_codigos_qr")


def leer_qr_imagen(uploaded_image):
    try:
        file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        if data:
            parsed_url = urllib.parse.urlparse(data)
            params = urllib.parse.parse_qs(parsed_url.query)
            if 'id_activo_qr' in params:
                return params['id_activo_qr'][0]
        return None
    except:
        return None


def convertir_tipos_python(data_dict):
    converted = {}
    for key, value in data_dict.items():
        if value is None:
            converted[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            converted[key] = value.isoformat()
        elif isinstance(value, (np.integer, np.int64)):
            converted[key] = int(value)
        elif isinstance(value, (np.floating, np.float64)):
            converted[key] = float(value)
        elif isinstance(value, (np.bool_, bool)):
            converted[key] = bool(value)
        elif isinstance(value, (np.ndarray, pd.Series)):
            converted[key] = value.tolist()
        else:
            converted[key] = value
    return converted

# ==============================================================================
# 🛡️ FUNCIONES DE VALIDACIÓN DE USUARIOS
# ==============================================================================

def validar_usuario_unico(nuevo_documento, id_ignorar=None):
    try:
        res = supabase.table("usuarios").select("*").eq("documento", nuevo_documento).execute()
        if res.data:
            usuario_existente = res.data[0]
            if id_ignorar and str(usuario_existente['id']) == str(id_ignorar):
                return True
            return False
        return True
    except Exception as e:
        st.error(f"Error validando usuario: {e}")
        return False


def check_open_orders(user_id):
    try:
        res = supabase.table("ordenes").select("id")\
            .eq("tecnico_asignado", user_id)\
            .in_("estado", ["Abierta", "Por Validar"])\
            .execute()
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error checking orders: {e}")
        return False

# ==============================================================================
# 🔔 FUNCIÓN TELEGRAM
# ==============================================================================
def notificar_telegram(chat_id, mensaje, foto_url=None):
    token_raw = st.secrets["telegram"]["bot_token"]
    token = token_raw.split("/bot")[-1].split("/")[0] if "/bot" in token_raw else token_raw
    if not chat_id:
        return
    try:
        base_url = f"https://api.telegram.org/bot{token}"
        payload  = {"chat_id": chat_id, "parse_mode": "Markdown"}
        if foto_url:
            payload["caption"] = mensaje
            payload["photo"]   = foto_url
            url_envio = f"{base_url}/sendPhoto"
        else:
            payload["text"] = mensaje
            url_envio = f"{base_url}/sendMessage"
        requests.post(url_envio, data=payload)
    except Exception as e:
        print(f"Error Telegram: {e}")

# --- MÉTRICAS INTELIGENTES ---
def mostrar_metricas_inteligentes(df_ordenes, df_users, df_solicitudes):
    n_solicitudes = 0
    if not df_solicitudes.empty:
        df_solicitudes['estado'] = df_solicitudes['estado'].astype(str).str.strip()
        n_solicitudes = len(df_solicitudes[df_solicitudes['estado'] == 'Pendiente'])

    total = len(df_ordenes)
    pendientes = por_validar = concluidas = devueltas_calidad = 0
    porcentaje_concluidas = 0

    if not df_ordenes.empty:
        df_ordenes['estado'] = df_ordenes['estado'].astype(str).str.strip()
        pendientes    = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
        por_validar   = len(df_ordenes[df_ordenes['estado'] == 'Por Validar'])
        concluidas    = len(df_ordenes[df_ordenes['estado'] == 'Concluida'])
        devueltas_calidad = len(df_ordenes[
            (df_ordenes['estado'] == 'Abierta') &
            (df_ordenes['comentarios_validacion'].notnull()) &
            (df_ordenes['comentarios_validacion'] != "")
        ])
        porcentaje_concluidas = (concluidas / total * 100) if total > 0 else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        color_sol = "normal" if n_solicitudes == 0 else "inverse"
        st.metric("📬 Solicitudes", n_solicitudes, "Nuevas en Buzón", delta_color=color_sol)
    with c2:
        st.metric("🔨 En Ejecución", pendientes,
                  f"{devueltas_calidad} Devueltas" if devueltas_calidad > 0 else None,
                  delta_color="inverse")
    with c3:
        st.metric("🧐 Calidad", por_validar, "Por Aprobar")
    with c4:
        st.metric("✅ Finalizadas", concluidas, f"{porcentaje_concluidas:.0f}%")
    with c5:
        st.metric("📦 Total OTs", total)

# --- GRÁFICOS ---
# FIX 3: Se eliminó la definición vacía/duplicada de graficar_ordenes_por_tecnico.
def graficar_ordenes_por_tecnico(df_ordenes, df_users):
    """Muestra gráfico compacto de órdenes por técnico."""
    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_users   = pd.DataFrame(df_users)   if not isinstance(df_users,   pd.DataFrame) else df_users

    if df_ordenes.empty or df_users.empty:
        st.info("No hay datos suficientes para mostrar la carga por técnico.")
        return

    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre']))
    df_tecnicos = df_ordenes.copy()
    df_tecnicos['tecnico_nombre'] = df_tecnicos['tecnico_asignado'].astype(str).map(user_map).fillna('Sin asignar')

    conteo_tecnicos = df_tecnicos.groupby(['tecnico_nombre', 'estado']).size().reset_index(name='cantidad')
    abiertas    = conteo_tecnicos[conteo_tecnicos['estado'] == 'Abierta']
    concluidas  = conteo_tecnicos[conteo_tecnicos['estado'] == 'Concluida']
    tecnicos_unicos = df_tecnicos['tecnico_nombre'].unique()

    datos_final = []
    for tecnico in tecnicos_unicos:
        abierta_count   = abiertas[abiertas['tecnico_nombre']   == tecnico]['cantidad'].sum()
        concluida_count = concluidas[concluidas['tecnico_nombre'] == tecnico]['cantidad'].sum()
        total_tecnico   = abierta_count + concluida_count
        datos_final.append({
            'Técnico':   tecnico,
            'Abiertas':  abierta_count,
            'Concluidas': concluida_count,
            'Total':     total_tecnico
        })

    df_final = pd.DataFrame(datos_final).sort_values('Total', ascending=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name='Concluidas', y=df_final['Técnico'], x=df_final['Concluidas'],
        orientation='h', marker=dict(color='#10B981', line=dict(width=0)),
        text=df_final['Concluidas'], textposition='inside',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{y}</b><br>Concluidas: %{x}<extra></extra>'
    ))
    fig.add_trace(go.Bar(
        name='Abiertas', y=df_final['Técnico'], x=df_final['Abiertas'],
        orientation='h', marker=dict(color='#F59E0B', line=dict(width=0)),
        text=df_final['Abiertas'], textposition='inside',
        textfont=dict(color='white', size=12),
        hovertemplate='<b>%{y}</b><br>Abiertas: %{x}<extra></extra>'
    ))
    fig.update_layout(
        barmode='stack', paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', size=12), height=250,
        margin=dict(l=0, r=0, t=10, b=0), showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="center", x=0.5,
                    font=dict(color='white', size=12), bgcolor='rgba(0,0,0,0)'),
        xaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)', title=None),
        yaxis=dict(title=None, tickfont=dict(size=11))
    )
    fig.update_layout(dragmode=False, hovermode='y unified')
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})


def graficar_criticidad(df):
    if df.empty:
        return
    conteo = df['criticidad'].value_counts().reset_index()
    conteo.columns = ['Nivel', 'Cantidad']
    conteo['Nivel'] = conteo['Nivel'].astype(str).str.strip()

    orden_oficial = ["Baja", "Media", "Alta", "Crítica"]
    colores = {"Baja": "#10B981", "Media": "#F59E0B", "Alta": "#EA580C", "Crítica": "#EF4444"}
    conteo  = conteo[conteo['Nivel'].isin(orden_oficial)]

    fig = px.bar(conteo, x='Nivel', y='Cantidad', color='Nivel',
                 color_discrete_map=colores, text='Cantidad',
                 category_orders={"Nivel": orden_oficial})
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(title=None),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    fig.update_traces(textfont_size=14, textposition='outside', marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)


def graficar_gantt_mantenimiento(df_ordenes, df_users):
    if df_ordenes.empty:
        st.info("No hay datos para generar el calendario.")
        return

    df_gantt = df_ordenes.copy()
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    df_gantt['Tecnico']      = df_gantt['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
    df_gantt['Inicio']       = pd.to_datetime(df_gantt['fecha_creacion'])
    now = datetime.now()
    df_gantt['Final_Real']   = pd.to_datetime(df_gantt['fecha_cierre'])
    df_gantt['Final_Visual'] = df_gantt['Final_Real'].fillna(now)
    df_gantt['Duracion_Horas'] = ((df_gantt['Final_Visual'] - df_gantt['Inicio'])
                                  .dt.total_seconds() / 3600).round(1)

    fig = px.timeline(
        df_gantt, x_start="Inicio", x_end="Final_Visual", y="Tecnico",
        color="criticidad",
        color_discrete_map={"Alta": "#EF4444", "Media": "#F59E0B", "Baja": "#10B981", "Crítica": "#7F1D1D"},
        hover_data=["id", "descripcion", "estado", "Duracion_Horas"],
        title="📅 Línea de Tiempo de Ejecución", height=400
    )
    fig.update_yaxes(categoryorder="total ascending", title=None)
    fig.update_xaxes(title="Tiempo de Ejecución")
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.05)',
        font=dict(color='white'), legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=40, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)


def mostrar_tops_ordenes(df_ordenes):
    if df_ordenes.empty:
        return
    now = datetime.now()
    df_ordenes['fecha_dt'] = pd.to_datetime(df_ordenes['fecha_creacion'])
    df_abiertas = df_ordenes[df_ordenes['estado'] != 'Concluida'].copy()

    if df_abiertas.empty:
        st.toast("¡Increíble! No hay órdenes pendientes antiguas.")
        return

    df_abiertas['dias_abierta'] = (now - df_abiertas['fecha_dt']).dt.days

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### 🐢 Top 10 Más Antiguas")
        df_old = df_abiertas.sort_values('dias_abierta', ascending=False).head(10)
        st.dataframe(
            df_old[['id', 'descripcion', 'dias_abierta', 'tecnico_asignado']],
            column_config={
                "id":            st.column_config.NumberColumn("ID", format="#%d", width="small"),
                "descripcion":   st.column_config.TextColumn("Problema", width="medium"),
                "dias_abierta":  st.column_config.ProgressColumn("Días Esperando",
                                     format="%d días", min_value=0, max_value=30),
                "tecnico_asignado": st.column_config.TextColumn("Técnico ID")
            },
            hide_index=True, use_container_width=True, height=300
        )
    with c2:
        st.markdown("### 🔥 Top Críticas Pendientes")
        df_crit = df_abiertas[df_abiertas['criticidad'].isin(['Alta', 'Crítica'])]\
                    .sort_values('fecha_dt').head(10)
        if df_crit.empty:
            st.info("No hay órdenes críticas pendientes.")
        else:
            st.dataframe(
                df_crit[['id', 'criticidad', 'descripcion', 'estado']],
                column_config={
                    "id":          st.column_config.NumberColumn("ID", format="#%d", width="small"),
                    "criticidad":  st.column_config.TextColumn("Nivel"),
                    "descripcion": st.column_config.TextColumn("Problema"),
                    "estado":      st.column_config.TextColumn("Estado")
                },
                hide_index=True, use_container_width=True, height=300
            )


def graficar_torta_tipo(df):
    if df.empty:
        return
    conteo = df['tipo_mantenimiento'].value_counts().reset_index()
    conteo.columns = ['Tipo', 'Cantidad']
    colores_torta = ["#3B82F6", "#8B5CF6", "#EC4899"]
    fig = go.Figure(data=[go.Pie(
        labels=conteo['Tipo'], values=conteo['Cantidad'], hole=.5,
        marker=dict(colors=colores_torta, line=dict(color='#111827', width=2)),
        textinfo='label+percent', textfont=dict(color='white')
    )])
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', font=dict(color='white'),
        height=250, showlegend=False, margin=dict(l=0, r=0, t=10, b=10)
    )
    st.plotly_chart(fig, use_container_width=True)


def graficar_estado_barras(df):
    if df.empty:
        return
    conteo = df['estado'].value_counts().reset_index()
    conteo.columns = ['Estado', 'Cantidad']
    colores = {"Abierta": "#F59E0B", "Concluida": "#10B981"}
    fig = px.bar(conteo, x='Cantidad', y='Estado', orientation='h',
                 color='Estado', color_discrete_map=colores, text='Cantidad')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(showgrid=False), yaxis=dict(title=None)
    )
    fig.update_traces(textfont_size=14, textposition='inside')
    st.plotly_chart(fig, use_container_width=True)


def graficar_alternativas_visuales(df_ordenes, df_users):
    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_users   = pd.DataFrame(df_users)   if not isinstance(df_users,   pd.DataFrame) else df_users

    if df_ordenes.empty:
        st.info("No hay datos para graficar.")
        return

    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    df_vis = df_ordenes.copy()
    df_vis['Tecnico']    = df_vis['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
    now = datetime.now()
    df_vis['Inicio']     = pd.to_datetime(df_vis['fecha_creacion'])
    df_vis['Cierre_Calc'] = pd.to_datetime(df_vis['fecha_cierre']).fillna(now)
    df_vis['Dias_Activa'] = ((df_vis['Cierre_Calc'] - df_vis['Inicio'])
                              .dt.total_seconds() / 86400).round(1)

    color_map_crit = {"Alta": "#EF4444", "Media": "#F59E0B", "Baja": "#10B981", "Crítica": "#7F1D1D"}

    st.markdown("### 🌊 Flujo de Distribución")
    st.caption("Sigue las líneas: Técnico ➔ Criticidad ➔ Estado actual.")
    fig_flow = px.parallel_categories(
        df_vis, dimensions=['Tecnico', 'criticidad', 'estado'],
        color="Dias_Activa", color_continuous_scale=px.colors.sequential.Inferno,
        labels={'Tecnico': 'Personal', 'criticidad': 'Urgencia', 'estado': 'Situación'}
    )
    fig_flow.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', margin=dict(l=20, r=20, t=20, b=20),
        font=dict(color='white'), height=350
    )
    st.plotly_chart(fig_flow, use_container_width=True)

    st.markdown("---")
    st.markdown("### 🏎️ Tiempos de Respuesta (La Carrera)")
    st.caption("Cada punto es una Orden. Izquierda = Reciente/Rápido. Derecha = Antiguo/Lento.")
    fig_race = px.strip(
        df_vis, x="Dias_Activa", y="Tecnico", color="criticidad",
        color_discrete_map=color_map_crit, orientation="h", stripmode="overlay",
        hover_data=["id", "descripcion", "estado"]
    )
    fig_race.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(255,255,255,0.05)',
        font=dict(color='white'), height=300,
        xaxis=dict(title="Días desde creación", showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(title=None)
    )
    fig_race.add_vline(x=7, line_width=1, line_dash="dash", line_color="white",
                       annotation_text="Límite 7 días")
    st.plotly_chart(fig_race, use_container_width=True)


def render_orion_svg(color):
    ORION_SVG = f"""
        <svg width="250" height="250" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
            <style>
                .star {{ fill: white; filter: drop-shadow(0 0 2px white); }}
                .belt {{ stroke: {color}; filter: drop-shadow(0 0 5px {color}); stroke-width: 2; opacity: 0.8; }}
                .line {{ stroke: {color}; stroke-width: 1; opacity: 0.4; }}
            </style>
            <path class="line" d="M100 150 L200 50 L300 150 L250 250 L150 250 L100 150 Z"/>
            <line class="belt" x1="160" y1="180" x2="200" y2="200"/>
            <line class="belt" x1="200" y1="200" x2="240" y2="220"/>
            <circle class="star" cx="200" cy="50"  r="5"/>
            <circle class="star" cx="100" cy="150" r="4"/>
            <circle class="star" cx="240" cy="220" r="6"/>
            <circle class="star" cx="200" cy="200" r="6"/>
            <circle class="star" cx="160" cy="180" r="6"/>
            <circle class="star" cx="300" cy="150" r="5"/>
            <circle class="star" cx="250" cy="250" r="7"/>
        </svg>
    """
    st.markdown(f"""
        <div style="display: flex; justify-content: center; margin-bottom: -30px;">
            {ORION_SVG}
        </div>
    """, unsafe_allow_html=True)

# ==============================================================================
# ⏱️ MOTOR DE ALERTAS SLA
# ==============================================================================
def verificar_sla_y_alertar(df_ordenes, df_users, df_act):
    if st.session_state.get('sla_verificado'):
        return

    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_users   = pd.DataFrame(df_users)   if not isinstance(df_users,   pd.DataFrame) else df_users
    df_act     = pd.DataFrame(df_act)     if not isinstance(df_act,     pd.DataFrame) else df_act

    LIMITES_SLA = {"Crítica": 4, "Alta": 24, "Media": 72, "Baja": 168}

    if df_ordenes.empty:
        st.session_state['sla_verificado'] = True
        return

    ahora = datetime.now()
    df_abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'].copy() \
        if 'estado' in df_ordenes.columns else pd.DataFrame()

    if df_abiertas.empty:
        st.session_state['sla_verificado'] = True
        return

    df_abiertas['fecha_dt']       = pd.to_datetime(df_abiertas['fecha_creacion'])
    df_abiertas['horas_abiertas'] = (ahora - df_abiertas['fecha_dt']).dt.total_seconds() / 3600

    map_act  = dict(zip(df_act['id'],             df_act['nombre']))          if not df_act.empty  else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre']))      if not df_users.empty else {}

    alertas_enviadas = 0
    for _, orden in df_abiertas.iterrows():
        limite = LIMITES_SLA.get(orden['criticidad'], 999)
        if orden['horas_abiertas'] > limite:
            nombre_activo  = map_act.get(orden['activo_id'],              "Desconocido")
            nombre_tecnico = map_user.get(str(orden['tecnico_asignado']), "Sin asignar")
            horas_str = f"{orden['horas_abiertas']:.0f}h"
            mensaje = (
                f"🚨 *ALERTA SLA — OT #{orden['id']}*\n\n"
                f"📍 *Activo:* {nombre_activo}\n"
                f"🔴 *Criticidad:* {orden['criticidad']}\n"
                f"⏱️ *Tiempo abierta:* {horas_str} (límite: {limite}h)\n"
                f"👷 *Técnico:* {nombre_tecnico}\n\n"
                f"⚠️ Esta orden requiere atención inmediata."
            )
            if orden.get('chat_id'):
                notificar_telegram(orden.get('chat_id'), mensaje)
            alertas_enviadas += 1

    if alertas_enviadas > 0:
        st.session_state['sla_alertas_count'] = alertas_enviadas
    st.session_state['sla_verificado'] = True

# ==============================================================================
# 🚀 INTERCEPTOR PÚBLICO (ACCESO QR)
# ==============================================================================
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    try:
        datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    except:
        st.error("Error de conexión.")
        st.stop()

    if datos_activo.data:
        activo = datos_activo.data[0]
        st.markdown(f"<h1 style='text-align: center;'>ORIÓN: {activo['nombre']}</h1>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="card-style">
                <span class="chart-header">Ficha Técnica</span>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)
        st.markdown("<h3 style='margin-top:20px;'>Historial</h3>", unsafe_allow_html=True)
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr)\
                  .order("id", desc=True).limit(5).execute()
            if ots.data:
                st.table(pd.DataFrame(ots.data)[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Sin registros.")
        except:
            pass
        st.markdown("---")
        if st.button("🏠 Inicio"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error("❌ Activo no encontrado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    st.stop()

# ==============================================================================
# 🚀 LOGIN & GESTIÓN DE SESIÓN
# ==============================================================================
if 'usuario'           not in st.session_state: st.session_state['usuario']           = None
if 'rol'               not in st.session_state: st.session_state['rol']               = None
if 'user_doc'          not in st.session_state: st.session_state['user_doc']          = None
if 'session_token'     not in st.session_state: st.session_state['session_token']     = None
if 'sla_alertas_count' not in st.session_state: st.session_state['sla_alertas_count'] = 0
if 'login_intentos'    not in st.session_state: st.session_state['login_intentos']    = 0
if 'login_bloqueado'   not in st.session_state: st.session_state['login_bloqueado']   = None


def logout():
    st.session_state['usuario']           = None
    st.session_state['rol']               = None
    st.session_state['user_doc']          = None
    st.session_state['session_token']     = None
    st.session_state['sla_verificado']    = False
    st.session_state['sla_alertas_count'] = 0
    st.query_params.clear()
    st.rerun()


if st.session_state['usuario'] is None:
    query_params = st.query_params
    if "session_id" in query_params:
        token_url      = query_params["session_id"]
        token_guardado = st.session_state.get('session_token')
        doc_guardado   = st.session_state.get('user_doc')
        if token_guardado and token_url == token_guardado and doc_guardado:
            try:
                res = supabase.table("usuarios").select("*").eq("documento", doc_guardado).execute()
                if res.data:
                    user = res.data[0]
                    st.session_state['usuario'] = user['nombre']
                    st.session_state['rol']     = user['rol']
                    if "last_page" in query_params:
                        st.session_state.current_page = query_params["last_page"]
                    st.rerun()
            except Exception as e:
                st.error(f"Error recuperando sesión: {e}")

# ==============================================================================
# 🔒 PANTALLA DE ACCESO (LOGIN)
# ==============================================================================
if st.session_state['usuario'] is None:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        render_orion_svg("#F59E0B")
        st.markdown(f"""
            <h1 style='text-align: center; font-size: 3.5rem; margin-bottom: -15px; text-shadow: 0 0 10px #F59E0B;'>ORIÓN</h1>
            <p style='text-align: center; color: #E5E7EB; font-size: 1.2rem; letter-spacing: 2px; margin-top: 5px; margin-bottom: 20px; font-weight: 300;'>
                PLATAFORMA INTEGRAL DE MANTENIMIENTO
            </p>
        """, unsafe_allow_html=True)
        st.markdown(f"""
            <div class='card-style' style='padding: 10px; margin-top: 0px; margin-bottom: 30px; text-align: center; font-size: 0.85em; color:#F59E0B; border: none; box-shadow: none; background: transparent;'>
                <p style='margin: 0;'>Desarrollado por: <b>Jhonestebanpenagos@gmail.com</b></p>
            </div>
            <hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, #F59E0B, transparent); margin-bottom: 30px;">
        """, unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>ACCESO DE USUARIOS</h3>", unsafe_allow_html=True)

        with st.form("login_form"):
            documento = st.text_input("Usuario")
            password  = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("ACCEDER AL SISTEMA", type="primary", use_container_width=True)

            if submitted:
                MAX_INTENTOS    = 3
                BLOQUEO_MINUTOS = 5

                bloqueo = st.session_state.get('login_bloqueado')
                if bloqueo:
                    segundos_restantes = (bloqueo - datetime.now()).total_seconds()
                    if segundos_restantes > 0:
                        minutos  = int(segundos_restantes // 60)
                        segundos = int(segundos_restantes % 60)
                        st.error(f"🔒 Cuenta bloqueada. Intenta en {minutos}m {segundos}s.")
                        st.stop()
                    else:
                        st.session_state['login_intentos']  = 0
                        st.session_state['login_bloqueado'] = None

                with st.spinner("Conectando y validando credenciales..."):
                    time.sleep(1)

                try:
                    password_hash = hashear_password(password)
                    response = supabase.table("usuarios").select("*")\
                        .eq("documento", documento)\
                        .eq("password",  password_hash)\
                        .execute()

                    if response.data:
                        st.session_state['login_intentos']  = 0
                        st.session_state['login_bloqueado'] = None
                        user = response.data[0]
                        st.session_state['usuario']  = user['nombre']
                        st.session_state['rol']      = user['rol']
                        st.session_state['user_doc'] = documento
                        token_sesion = str(uuid.uuid4())
                        st.session_state['session_token'] = token_sesion
                        st.query_params["session_id"] = token_sesion
                        st.query_params["last_page"]  = "Tablero de Mando"
                        st.rerun()
                    else:
                        st.session_state['login_intentos'] += 1
                        intentos_restantes = MAX_INTENTOS - st.session_state['login_intentos']
                        if st.session_state['login_intentos'] >= MAX_INTENTOS:
                            st.session_state['login_bloqueado'] = (
                                datetime.now() + pd.Timedelta(minutes=BLOQUEO_MINUTOS)
                            )
                            st.error(f"🔒 Demasiados intentos. Cuenta bloqueada por {BLOQUEO_MINUTOS} minutos.")
                        else:
                            st.error(f"❌ Usuario o contraseña incorrectos. Te quedan {intentos_restantes} intento(s).")
                except Exception as e:
                    st.error(f"Error de conexión. Intente nuevamente. Detalles: {e}")
    st.stop()

# ==============================================================================
# 🚀 DASHBOARD PRIVADO
# ==============================================================================
rol     = st.session_state['rol']
usuario = st.session_state['usuario']

with st.sidebar:
    st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <p style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">👋 {usuario}</p>
            <p style="color: #F59E0B; margin: 5px 0 0 0; font-size: 0.9rem;">{rol.upper()}</p>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🔓 Salir", use_container_width=True, type="secondary"):
        logout()

    st.divider()

    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Tablero de Mando"

    if rol == "Admin":
        menu   = [("📊","Tablero"),("📦","Inventario Activos"),("🛠️","Órdenes de Trabajo"),("🔩","Repuestos"),("👤","Usuarios")]
        valores = ["Tablero de Mando","Inventario Activos","Ordenes de Trabajo","Repuestos","Usuarios"]
    elif rol == "Programador":
        menu   = [("📊","Tablero"),("🛠️","Órdenes de Trabajo"),("🔩","Repuestos"),("👤","Usuarios")]
        valores = ["Tablero de Mando","Ordenes de Trabajo","Repuestos","Usuarios"]
    elif rol == "Tecnico":
        menu   = [("🛠️","Órdenes de Trabajo")]
        valores = ["Ordenes de Trabajo"]

    for (icono, texto), valor in zip(menu, valores):
        activo = st.session_state.current_page == valor
        tipo   = "primary" if activo else "secondary"
        if st.button(f"{icono} {texto}", key=f"menu_{valor}", use_container_width=True, type=tipo):
            st.session_state.current_page = valor
            doc_actual = st.query_params.get("session_id", "")
            st.query_params["session_id"] = doc_actual
            st.query_params["last_page"]  = valor
            st.rerun()

    choice = st.session_state.current_page

# ==============================================================================
# 📅 MÓDULO DE MANTENIMIENTO PREVENTIVO
# ==============================================================================
def render_tab_preventivos(df_act, df_users):
    st.markdown("### 🗓️ Planes de Mantenimiento Recurrente")

    filtro_id_externo = None
    if st.session_state.get('jump_target') == 'preventivo' and st.session_state.get('jump_id'):
        filtro_id_externo = st.session_state.jump_id
        st.info(f"📍 Has sido redirigido al Plan #{filtro_id_externo}.")
        st.session_state.jump_target = None
        st.session_state.jump_id     = None

    st.info("Aquí configuras las tareas que se repiten (ej: Limpieza mensual).")

    with st.expander("➕ Crear Nuevo Plan Preventivo"):
        with st.form("form_plan_prev"):
            c1, c2 = st.columns(2)
            act_nombres = df_act['nombre'].values if not df_act.empty else []
            act_sel = c1.selectbox("Activo", act_nombres)
            users_dict = dict(zip(df_users['nombre'], df_users['id'])) if not df_users.empty else {}
            tec_sel = c2.selectbox("Técnico Sugerido", list(users_dict.keys()))
            desc = st.text_input("Tarea a realizar (Ej: Cambio de filtros)")
            c3, c4 = st.columns(2)
            dias       = c3.number_input("Frecuencia (Días)", min_value=1, value=30)
            fecha_base = c4.date_input("Fecha de Inicio / Última vez hecho")

            if st.form_submit_button("GUARDAR PLAN"):
                id_act = df_act[df_act['nombre'] == act_sel].iloc[0]['id']
                id_tec = users_dict[tec_sel]
                try:
                    supabase.table("planes_mantenimiento").insert({
                        "activo_id":      int(id_act),
                        "descripcion":    desc,
                        "frecuencia_dias": int(dias),
                        "ultima_ejecucion": fecha_base.isoformat(),
                        "tecnico_default": str(id_tec)
                    }).execute()
                    st.toast("Plan guardado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()

    df_planes = run_query("planes_mantenimiento")
    if filtro_id_externo:
        df_planes = df_planes[df_planes['id'].astype(str) == str(filtro_id_externo)]

    if df_planes.empty:
        st.warning("No hay planes configurados.")
        return

    df_planes['ultima_ejecucion'] = pd.to_datetime(df_planes['ultima_ejecucion'])
    df_planes['proxima_fecha']    = df_planes['ultima_ejecucion'] + pd.to_timedelta(df_planes['frecuencia_dias'], unit='D')
    df_planes['dias_restantes']   = (df_planes['proxima_fecha'] - datetime.now()).dt.days

    def color_estado(dias):
        if dias < 0:    return "🔴 Vencido"
        elif dias <= 5: return "🟡 Próximo"
        else:           return "🟢 A tiempo"

    df_planes['Estado'] = df_planes['dias_restantes'].apply(color_estado)
    map_act = dict(zip(df_act['id'], df_act['nombre']))
    df_planes['Activo'] = df_planes['activo_id'].map(map_act)

    st.dataframe(
        df_planes[['id','Activo','descripcion','frecuencia_dias','ultima_ejecucion','proxima_fecha','Estado']],
        column_config={
            "ultima_ejecucion": st.column_config.DateColumn("Última vez"),
            "proxima_fecha":    st.column_config.DateColumn("Próxima"),
            "frecuencia_dias":  st.column_config.NumberColumn("Cada (días)"),
            "descripcion":      "Tarea"
        },
        use_container_width=True, hide_index=True
    )

    st.markdown("### 🤖 Generador Automático")
    c_gen1, c_gen2 = st.columns([3, 1])
    c_gen1.caption("Buscará todos los planes 'Vencidos' o 'Próximos' y creará Órdenes de Trabajo automáticamente.")

    if c_gen2.button("🚀 EJECUTAR RUTINA", type="primary"):
        contador    = 0
        now         = datetime.now()
        progress_bar = st.progress(0)

        for idx, plan in df_planes.iterrows():
            if plan['proxima_fecha'] <= now:
                try:
                    supabase.table("ordenes").insert({
                        "activo_id":         int(plan['activo_id']),
                        "descripcion":       f"[PREVENTIVO] {plan['descripcion']}",
                        "criticidad":        "Media",
                        "tipo_mantenimiento": "Preventivo",
                        "estado":            "Abierta",
                        "tecnico_asignado":  str(plan['tecnico_default']),
                        "fecha_creacion":    now.isoformat()
                    }).execute()
                    supabase.table("planes_mantenimiento").update({
                        "ultima_ejecucion": now.isoformat()
                    }).eq("id", plan['id']).execute()
                    contador += 1
                except Exception as e:
                    st.error(f"Error en plan {plan['id']}: {e}")
            progress_bar.progress((idx + 1) / len(df_planes))

        if contador > 0:
            st.toast(f"✅ Se generaron {contador} órdenes de mantenimiento preventivo.")
            time.sleep(2)
            st.rerun()
        else:
            st.info("👍 Todo al día. No hay mantenimientos pendientes para hoy.")

# ==============================================================================
# 📊 GENERADOR DE EXCEL
# ==============================================================================
def generar_excel_historial(df_ordenes, df_act, df_users):
    buffer    = io.BytesIO()
    df_export = df_ordenes.copy()

    map_act  = dict(zip(df_act['id'],             df_act['nombre']))          if not df_act.empty  else {}
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre']))      if not df_users.empty else {}

    df_export['Activo']  = df_export['activo_id'].map(map_act).fillna('Desconocido')
    df_export['Tecnico'] = df_export['tecnico_asignado'].map(map_user).fillna('Sin asignar')
    df_export['fecha_creacion'] = pd.to_datetime(df_export['fecha_creacion'])
    df_export['fecha_cierre']   = pd.to_datetime(df_export['fecha_cierre'])
    df_export['Duracion_Horas'] = ((df_export['fecha_cierre'] - df_export['fecha_creacion'])
                                   .dt.total_seconds() / 3600).round(1)

    cols = ['id','fecha_creacion','fecha_cierre','Duracion_Horas','Activo','Tecnico',
            'tipo_mantenimiento','criticidad','estado','descripcion','comentarios_cierre']
    nombres_col = {
        'id': 'ID Orden', 'fecha_creacion': 'Fecha Apertura', 'fecha_cierre': 'Fecha Cierre',
        'Duracion_Horas': 'Duración (Horas)', 'Activo': 'Activo', 'Tecnico': 'Técnico',
        'tipo_mantenimiento': 'Tipo', 'criticidad': 'Criticidad', 'estado': 'Estado',
        'descripcion': 'Descripción', 'comentarios_cierre': 'Informe de Cierre'
    }
    df_final = df_export[cols].rename(columns=nombres_col).sort_values('ID Orden', ascending=False)

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False, sheet_name='Historial OTs')
        worksheet = writer.sheets['Historial OTs']
        for col in worksheet.columns:
            max_len = max(len(str(col[0].value)),
                          *[len(str(cell.value)) if cell.value else 0 for cell in col[1:]])
            worksheet.column_dimensions[col[0].column_letter].width = min(max_len + 3, 50)

    buffer.seek(0)
    return buffer

# ==============================================================================
# 🏭 KPIs INDUSTRIALES — MTTR & MTBF
# ==============================================================================
def mostrar_kpis_industriales(df_ordenes, df_act):
    df_ordenes = pd.DataFrame(df_ordenes) if not isinstance(df_ordenes, pd.DataFrame) else df_ordenes
    df_act     = pd.DataFrame(df_act)     if not isinstance(df_act,     pd.DataFrame) else df_act

    if df_ordenes.empty:
        st.info("No hay órdenes suficientes para calcular KPIs.")
        return

    map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
    df_k    = df_ordenes[df_ordenes['estado'] == 'Concluida'].copy()

    if df_k.empty:
        st.info("Sin órdenes concluidas para calcular KPIs industriales.")
        return

    df_k['fecha_creacion'] = pd.to_datetime(df_k['fecha_creacion'])
    df_k['fecha_cierre']   = pd.to_datetime(df_k['fecha_cierre'])
    df_k['duracion_horas'] = ((df_k['fecha_cierre'] - df_k['fecha_creacion'])
                               .dt.total_seconds() / 3600)
    df_k['Activo'] = df_k['activo_id'].map(map_act).fillna('Desconocido')

    mttr = df_k.groupby('Activo')['duracion_horas'].mean().reset_index()
    mttr.columns = ['Activo', 'MTTR_horas']
    mttr = mttr.sort_values('MTTR_horas', ascending=False).head(10)
    mttr['MTTR_horas'] = mttr['MTTR_horas'].round(1)

    df_sorted = df_k.sort_values(['Activo', 'fecha_creacion'])
    df_sorted['tiempo_entre_fallas'] = (
        df_sorted.groupby('Activo')['fecha_creacion'].diff().dt.total_seconds() / 3600
    )
    mtbf = df_sorted.groupby('Activo')['tiempo_entre_fallas'].mean().reset_index()
    mtbf.columns = ['Activo', 'MTBF_horas']
    mtbf = mtbf.dropna().sort_values('MTBF_horas', ascending=False).head(10)
    mtbf['MTBF_horas'] = mtbf['MTBF_horas'].round(1)

    st.markdown("### 🏭 KPIs Industriales")
    col_r1, col_r2, col_r3, col_r4 = st.columns(4)
    mttr_prom        = df_k['duracion_horas'].mean()
    mtbf_prom        = df_sorted['tiempo_entre_fallas'].mean()
    activo_critico   = mttr['Activo'].iloc[0]  if not mttr.empty else "N/A"
    activo_confiable = mtbf['Activo'].iloc[-1] if not mtbf.empty else "N/A"

    col_r1.metric("⏱️ MTTR Promedio",         f"{mttr_prom:.1f}h")
    col_r2.metric("🔁 MTBF Promedio",         f"{mtbf_prom:.1f}h" if not pd.isna(mtbf_prom) else "N/A")
    col_r3.metric("🔴 Más Difícil de Reparar", activo_critico.split()[0]   if activo_critico   != "N/A" else "N/A")
    col_r4.metric("🟢 Más Confiable",          activo_confiable.split()[0] if activo_confiable != "N/A" else "N/A")

    st.markdown("---")
    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.markdown("<span class='chart-header'>⏱️ MTTR — Tiempo Medio de Reparación</span>", unsafe_allow_html=True)
        st.caption("Menos horas = más fácil de reparar")
        if not mttr.empty:
            fig_mttr = px.bar(mttr, x='MTTR_horas', y='Activo', orientation='h',
                              color='MTTR_horas', color_continuous_scale='Reds', text='MTTR_horas')
            fig_mttr.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                   font=dict(color='white'), height=300, showlegend=False,
                                   coloraxis_showscale=False, margin=dict(l=0,r=0,t=10,b=0),
                                   yaxis=dict(title=None), xaxis=dict(title="Horas promedio"))
            fig_mttr.update_traces(texttemplate='%{text}h', textposition='outside')
            st.plotly_chart(fig_mttr, use_container_width=True)
        else:
            st.info("Sin datos suficientes.")

    with col_m2:
        st.markdown("<span class='chart-header'>🔁 MTBF — Tiempo Medio Entre Fallas</span>", unsafe_allow_html=True)
        st.caption("Más horas = equipo más confiable")
        if not mtbf.empty:
            fig_mtbf = px.bar(mtbf, x='MTBF_horas', y='Activo', orientation='h',
                              color='MTBF_horas', color_continuous_scale='Greens', text='MTBF_horas')
            fig_mtbf.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                                   font=dict(color='white'), height=300, showlegend=False,
                                   coloraxis_showscale=False, margin=dict(l=0,r=0,t=10,b=0),
                                   yaxis=dict(title=None), xaxis=dict(title="Horas promedio"))
            fig_mtbf.update_traces(texttemplate='%{text}h', textposition='outside')
            st.plotly_chart(fig_mtbf, use_container_width=True)
        else:
            st.info("Sin datos suficientes para MTBF (se necesitan 2+ fallas por activo).")

# ==============================================================================
# 🚦 SEMÁFORO DE CARGA DE TÉCNICOS
# ==============================================================================
def semaforo_tecnicos(df_ordenes, df_users):
    if df_ordenes.empty or df_users.empty:
        return

    LIMITE_OCUPADO      = 3
    LIMITE_SOBRECARGADO = 6

    abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta']
    conteo   = abiertas.groupby('tecnico_asignado').size().reset_index(name='ordenes_abiertas')
    conteo['tecnico_asignado'] = conteo['tecnico_asignado'].astype(str)

    st.markdown("### 🚦 Estado de Carga — Técnicos")
    st.caption("Basado en órdenes con estado Abierta.")

    cols = st.columns(len(df_users))
    for i, (_, user) in enumerate(df_users.iterrows()):
        uid   = str(user['id'])
        nom   = user['nombre']
        rol_u = user['rol']
        fila  = conteo[conteo['tecnico_asignado'] == uid]
        n     = int(fila['ordenes_abiertas'].values[0]) if not fila.empty else 0

        if n == 0:
            color, estado, icono, barra = "#10B981", "LIBRE",     "🟢", 0
        elif n <= LIMITE_OCUPADO:
            color, estado, icono, barra = "#F59E0B", "OCUPADO",   "🟡", 40
        elif n <= LIMITE_SOBRECARGADO:
            color, estado, icono, barra = "#EA580C", "CARGADO",   "🟠", 70
        else:
            color, estado, icono, barra = "#EF4444", "CRÍTICO",   "🔴", 100

        with cols[i]:
            st.markdown(f"""
            <div style="background-color:rgba(30,41,59,0.8);border:2px solid {color};border-radius:12px;padding:15px 10px;text-align:center;margin:5px 0;">
                <div style="font-size:1.8rem;margin-bottom:5px;">{icono}</div>
                <div style="color:white;font-weight:700;font-size:0.9rem;margin-bottom:2px;">{nom.split()[0]}</div>
                <div style="color:#9CA3AF;font-size:0.75rem;margin-bottom:8px;">{rol_u}</div>
                <div style="color:{color};font-weight:800;font-size:1.8rem;line-height:1;">{n}</div>
                <div style="color:#9CA3AF;font-size:0.7rem;margin-bottom:8px;">órdenes</div>
                <div style="background-color:rgba(255,255,255,0.1);border-radius:4px;height:4px;margin:5px 0;">
                    <div style="background-color:{color};width:{barra}%;height:4px;border-radius:4px;"></div>
                </div>
                <div style="color:{color};font-size:0.7rem;font-weight:700;letter-spacing:1px;margin-top:4px;">{estado}</div>
            </div>
            """, unsafe_allow_html=True)

# ==============================================================================
# 🤖 ASIGNACIÓN INTELIGENTE DE TÉCNICOS
# ==============================================================================
def sugerir_tecnico(df_ordenes, df_users):
    if df_users.empty:
        return None, None, 0

    df_tec = df_users[df_users['rol'].isin(['Tecnico', 'Programador'])].copy()
    if df_tec.empty:
        df_tec = df_users.copy()

    abiertas = df_ordenes[df_ordenes['estado'] == 'Abierta'] if not df_ordenes.empty else pd.DataFrame()
    conteo   = {}
    for _, u in df_tec.iterrows():
        uid = str(u['id'])
        n   = len(abiertas[abiertas['tecnico_asignado'] == uid]) if not abiertas.empty else 0
        conteo[uid] = {'nombre': u['nombre'], 'ordenes': n, 'id': u['id']}

    ordenado = sorted(conteo.values(), key=lambda x: x['ordenes'])
    mejor    = ordenado[0]
    return mejor['id'], mejor['nombre'], mejor['ordenes']


def render_sugerencia_tecnico(df_ordenes, df_users):
    id_sug, nom_sug, n_sug = sugerir_tecnico(df_ordenes, df_users)
    if not nom_sug:
        return None

    if n_sug == 0:
        color, estado = "#10B981", "LIBRE"
    elif n_sug <= 3:
        color, estado = "#F59E0B", "DISPONIBLE"
    else:
        color, estado = "#EA580C", "CARGADO"

    st.markdown(f"""
    <div style="background-color:rgba(16,185,129,0.1);border:1px solid {color};border-radius:8px;padding:12px 16px;margin-bottom:10px;display:flex;align-items:center;gap:15px;">
        <div style="font-size:1.5rem;">🤖</div>
        <div>
            <div style="color:{color};font-weight:700;font-size:0.85rem;">SUGERENCIA AUTOMÁTICA</div>
            <div style="color:white;font-size:1rem;font-weight:600;">{nom_sug}</div>
            <div style="color:#9CA3AF;font-size:0.8rem;">{n_sug} órdenes abiertas — {estado}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    return nom_sug

# ==============================================================================
# 📊 PANTALLAS
# ==============================================================================

if choice == "Tablero de Mando":
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()

    df           = run_query("ordenes")
    df_users     = run_query("usuarios")
    df_solicitudes = run_query("solicitudes")
    df_act_sla   = run_query("activos")

    verificar_sla_y_alertar(pd.DataFrame(df), df_users, df_act_sla)

    if st.session_state.get('sla_alertas_count', 0) > 0:
        n = st.session_state['sla_alertas_count']
        st.toast(f"🚨 {n} órdenes superaron su límite de tiempo", icon="⚠️")
        st.session_state['sla_alertas_count'] = 0

    mostrar_metricas_inteligentes(df, df_users, df_solicitudes)

    if not df.empty:
        col_exp1, col_exp2, col_exp3 = st.columns([3, 1, 1])
        with col_exp3:
            try:
                buffer_excel = generar_excel_historial(df, df_act_sla, df_users)
                st.download_button(
                    label     = "📊 Exportar Excel",
                    data      = buffer_excel,
                    file_name = f"Historial_OTs_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime      = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
            except Exception as e:
                st.caption(f"Excel no disponible: {e}")

        st.write("")
        st.markdown("---")
        graficar_alternativas_visuales(df, df_users)
        st.markdown("---")
        mostrar_tops_ordenes(df)
        st.markdown("---")
        mostrar_kpis_industriales(df, df_act_sla)
        st.markdown("---")
        st.markdown("### 📊 Análisis Global")
        c_left, c_mid, c_right = st.columns(3)

        with c_left:
            st.markdown("<div class='card-style'><span class='chart-header'>Progreso Global</span>", unsafe_allow_html=True)
            graficar_estado_barras(df)
            st.markdown("</div>", unsafe_allow_html=True)
        with c_mid:
            st.markdown("<div class='card-style'><span class='chart-header'>Nivel de Riesgo</span>", unsafe_allow_html=True)
            graficar_criticidad(df)
            st.markdown("</div>", unsafe_allow_html=True)
        with c_right:
            st.markdown("<div class='card-style'><span class='chart-header'>Por Categoría</span>", unsafe_allow_html=True)
            graficar_torta_tipo(df)
            st.markdown("</div>", unsafe_allow_html=True)

        st.markdown("### 👥 Carga por Técnico")
        with st.container():
            graficar_ordenes_por_tecnico(df, df_users)
        st.markdown("---")
        semaforo_tecnicos(df, df_users)
    else:
        st.info("No hay órdenes registradas. El tablero se activará con datos.")

elif choice == "Inventario Activos":
    st.title("INVENTARIO DE ACTIVOS")
    mostrar_notificaciones()

    areas_data = {
        "Producción": [
            "Agua Cristal","B&B","Calderas","Cuarto de Lubricación","Equipos Auxiliares",
            "Laboratorio Fisico Quimico","Laboratorio Microbiológico","Linea 1","Linea 2",
            "Linea 3","Linea 10","Linea 8 Jugos","Oficinas Técnicas","Pasillo Técnico",
            "Ptap","Ptar","Sala de Jarabe Simple","Sala de Jarabe Terminado",
            "Sala de Jarabes Jugos","Sub Estación Eléctrica","Taller de Mantenimiento"
        ],
        "Administración": ["Administración","Auditorio","Casino","Portería Vehicular","Servicios Generales"],
        "Ventas":        ["Bodega Carrera 8va","Bodega Publicidad","Dispensadores","Ventas"],
        "Logística":     ["Almacen Materia Prima","Almacén Producto Terminado","Lavadero de Vehiculos",
                          "Punto de Canje","Taller de Reparación de Estibas","Taller Vehicular"]
    }
    categorias_list = sorted([
        "Aire Acondicionado","CCTV","Control de Acceso","Eléctrico","Estanterías",
        "Extraccion","Hidrosanitario","Infraestructura","Mecánico","Muelles",
        "Red Contra Incendio","Refrigeración Industrial","Ventilacion"
    ])

    df_act = pd.DataFrame(run_query("activos"))

    if 'specs_data'  not in st.session_state:
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
    if 'draft_data'  not in st.session_state:
        st.session_state.draft_data = {}

    tab_lista, tab_nuevo, tab_edit = st.tabs(["📋 LISTA DE ACTIVOS", "➕ NUEVO ACTIVO", "✏️ EDITAR / QR"])

    with tab_lista:
        if not df_act.empty:
            @st.dialog("📸 Detalle Visual del Activo")
            def mostrar_visor(nombre, foto, qr):
                st.subheader(nombre)
                st.markdown("---")
                c_zoom1, c_zoom2 = st.columns(2)
                with c_zoom1:
                    st.markdown("**Fotografía Real**")
                    if foto and isinstance(foto, str): st.image(foto, use_container_width=True)
                    else: st.warning("Sin foto")
                with c_zoom2:
                    st.markdown("**Código QR**")
                    if qr: st.image(qr, width=250)
                    else: st.warning("Sin QR")
                st.caption("Presione 'Esc' o la 'X' para cerrar.")

            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            col_kpi1.metric("Total Activos",    len(df_act))
            col_kpi2.metric("Áreas Activas",    df_act['area'].nunique())
            col_kpi3.metric("Categorías",       df_act['categoria'].nunique())
            con_foto = df_act['foto_url'].notnull().sum()
            col_kpi4.metric("Con Fotografía",   f"{con_foto}/{len(df_act)}")

            st.markdown("---")
            st.markdown("#### 🔍 Explorador de Activos")
            c_fil1, c_fil2, c_fil3, c_fil4 = st.columns([2, 1, 1, 1])
            search_term  = c_fil1.text_input("Buscar por nombre", placeholder="Escribe y presiona Enter...")
            area_opts    = ["Todas"] + sorted(areas_data.keys())
            filtro_area  = c_fil2.selectbox("Filtrar Área", area_opts)
            sub_opts     = ["Todas"] + (sorted(areas_data[filtro_area]) if filtro_area != "Todas" else [])
            filtro_sub   = c_fil3.selectbox("Filtrar Sub-área", sub_opts)
            cat_opts     = ["Todas"] + categorias_list
            filtro_cat   = c_fil4.selectbox("Filtrar Categoría", cat_opts)

            df_filtered = df_act.copy()
            if search_term:  df_filtered = df_filtered[df_filtered['nombre'].str.contains(search_term, case=False, na=False)]
            if filtro_area != "Todas": df_filtered = df_filtered[df_filtered['area'] == filtro_area]
            if filtro_sub  != "Todas": df_filtered = df_filtered[df_filtered['ubicacion'].str.contains(f"\[{filtro_sub}\]", regex=True, na=False)]
            if filtro_cat  != "Todas": df_filtered = df_filtered[df_filtered['categoria'] == filtro_cat]

            @st.fragment
            def fragmento_tabla_estable(dataframe_filtrado):
                if not dataframe_filtrado.empty:
                    st.markdown(f"###### 🧬 Resultados: {len(dataframe_filtrado)}")
                    st.info("👆 **Haga clic en una fila** para ver Foto y QR.")
                    if 'last_viewed_id' not in st.session_state:
                        st.session_state.last_viewed_id = None
                    altura_final = min(max(len(dataframe_filtrado) * 35 + 38, 100), 600)
                    event = st.dataframe(
                        dataframe_filtrado[['id','foto_url','nombre','categoria','area','ubicacion','qr_url']],
                        column_config={
                            "foto_url":  st.column_config.ImageColumn("Foto",       width="small"),
                            "qr_url":    st.column_config.ImageColumn("QR",         width="small"),
                            "id":        st.column_config.NumberColumn("ID",        format="%d", width="small"),
                            "nombre":    st.column_config.TextColumn("Nombre",      width="medium"),
                            "categoria": st.column_config.TextColumn("Categoría",   width="small"),
                            "area":      st.column_config.TextColumn("Área",        width="small"),
                            "ubicacion": st.column_config.TextColumn("Ubicación",   width="medium"),
                        },
                        use_container_width=True, hide_index=True, height=altura_final,
                        selection_mode="single-row", on_select="rerun", key="tabla_maestra_activos"
                    )
                    if len(event.selection.rows) > 0:
                        idx      = event.selection.rows[0]
                        sel_data = dataframe_filtrado.iloc[idx]
                        sel_id   = sel_data['id']
                        if st.session_state.last_viewed_id != sel_id:
                            st.session_state.last_viewed_id = sel_id
                            mostrar_visor(sel_data['nombre'], sel_data['foto_url'], sel_data['qr_url'])
                    else:
                        st.session_state.last_viewed_id = None
                else:
                    if search_term or filtro_area != "Todas" or filtro_cat != "Todas":
                        st.warning("⚠️ No se encontraron activos con estos filtros.")

            fragmento_tabla_estable(df_filtered)
        else:
            st.info("Aún no hay activos registrados.")

    with tab_nuevo:
        if 'activo_creado_info' in st.session_state and st.session_state.activo_creado_info is not None:
            info = st.session_state.activo_creado_info
            st.markdown(f"""
                <div style="background-color:rgba(6,78,59,0.5);border:1px solid #10B981;border-radius:10px;padding:20px;margin-bottom:20px;">
                    <h2 style="color:#10B981;text-align:center;margin:0;">✨ ACTIVO REGISTRADO</h2>
                    <p style="text-align:center;color:#D1FAE5;">Verifique los datos a continuación</p>
                </div>
            """, unsafe_allow_html=True)

            c_foto, c_datos, c_qr = st.columns([1, 1.5, 1])
            with c_foto:
                st.markdown("#### 🖼️ Foto")
                foto_local = info.get('foto_bytes')
                foto_nube  = info.get('foto_url')
                if foto_local is not None:
                    try:   st.image(foto_local, use_container_width=True, caption="Previsualización")
                    except: st.warning("No se pudo cargar la vista previa local.")
                elif pd.notna(foto_nube) and isinstance(foto_nube, str) and len(foto_nube) > 10:
                    try:   st.image(foto_nube, use_container_width=True)
                    except: st.error("Error al cargar imagen desde la nube.")
                else:
                    st.info("ℹ️ Sin imagen disponible.")
            with c_datos:
                st.markdown(f"### {info['nombre']}")
                st.markdown(f"**📍 Ubicación:** {info['area']} / {info['ubicacion']}")
                st.markdown(f"**🔧 Categoría:** {info['categoria']}")
                st.markdown("---")
                detalles = info['detalles']
                if detalles and isinstance(detalles, dict) and len(detalles) > 0:
                    st.table(pd.DataFrame(list(detalles.items()), columns=["Característica", "Dato"]))
            with c_qr:
                if info.get('qr_url'): st.image(info['qr_url'], caption="QR Asignado", width=180)

            st.markdown("---")
            b1, b2, b3 = st.columns(3)
            with b1:
                if st.button("✅ FINALIZAR Y NUEVO", type="primary", use_container_width=True):
                    del st.session_state['activo_creado_info']
                    st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
                    st.session_state.draft_data = {}
                    st.rerun()
            with b2:
                if st.button("✏️ EDITAR (CORREGIR)", use_container_width=True):
                    supabase.table("activos").delete().eq("id", info['id']).execute()
                    st.cache_data.clear()
                    st.session_state.draft_data = info
                    if info['detalles']:
                        st.session_state.specs_data = pd.DataFrame(list(info['detalles'].items()), columns=["Componente/Dato","Valor"])
                    del st.session_state['activo_creado_info']
                    st.rerun()
            with b3:
                if st.button("🗑️ DESHACER", type="secondary", use_container_width=True):
                    supabase.table("activos").delete().eq("id", info['id']).execute()
                    st.cache_data.clear()
                    del st.session_state['activo_creado_info']
                    st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
                    st.session_state.draft_data = {}
                    agregar_notificacion('warning', 'Registro cancelado.')
                    st.rerun()
        else:
            st.markdown("### Registrar Nuevo Activo")
            draft = st.session_state.get('draft_data', {})

            st.info("📍 Paso 1: Definir Ubicación")
            c_loc1, c_loc2 = st.columns(2)
            keys_areas   = sorted(areas_data.keys())
            idx_area_def = keys_areas.index(draft.get('area')) if draft.get('area') in keys_areas else 0
            area_principal = c_loc1.selectbox("Área Principal", keys_areas, index=idx_area_def, key="new_asset_area_out")

            sub_areas = sorted(areas_data[area_principal])
            d_sub_prev = ""
            if draft.get('ubicacion'):
                parts = draft['ubicacion'].split('] ', 1)
                d_sub_prev = parts[0].replace('[', '')
            idx_sub_def = sub_areas.index(d_sub_prev) if d_sub_prev in sub_areas else 0
            sub_area = c_loc2.selectbox("Sub-área", sub_areas, index=idx_sub_def, key="new_asset_sub_out")

            st.write("")
            with st.form("form_crear_activo", clear_on_submit=False):
                st.markdown("📝 **Paso 2: Detalles del Activo**")
                c1, c2 = st.columns(2)

                def get_idx(opts, val):
                    try:    return list(opts).index(val)
                    except: return 0

                nom = c1.text_input("Nombre del Activo", value=draft.get('nombre', ''))
                d_det_prev = ""
                if draft.get('ubicacion'):
                    parts = draft['ubicacion'].split('] ', 1)
                    if len(parts) > 1: d_det_prev = parts[1]
                ubic_detalle = c2.text_input("Ubicación Exacta / Detalle (Opcional)", value=d_det_prev)
                cat = c1.selectbox("Categoría", categorias_list, index=get_idx(categorias_list, draft.get('categoria')))

                st.markdown("---")
                st.markdown("#### 📸 Fotografía (Obligatorio)")
                if draft.get('foto_url'):
                    st.image(draft['foto_url'], width=100, caption="Foto actual (Draft)")
                foto_archivo = st.file_uploader("Subir imagen", type=["jpg", "png", "jpeg"])

                st.markdown("---")
                st.markdown("#### ⚙️ Especificaciones")
                edited_df = st.data_editor(st.session_state.specs_data, num_rows="dynamic", use_container_width=True)
                st.markdown("<br>", unsafe_allow_html=True)
                enviado = st.form_submit_button("💾 GUARDAR ACTIVO", type="primary", use_container_width=True)

            if enviado:
                final_url = None
                if foto_archivo:
                    with st.spinner("Subiendo foto a Cloudinary..."):
                        final_url = subir_imagen(foto_archivo)
                elif draft.get('foto_url'):
                    final_url = draft['foto_url']

                if not nom or not final_url:
                    agregar_notificacion('error', '⚠️ El Nombre y la Foto son obligatorios.')
                else:
                    try:
                        detalles_json = {
                            row["Componente/Dato"]: row["Valor"]
                            for i, row in edited_df.iterrows()
                            if row["Componente/Dato"] and row["Valor"]
                        }
                        ubic_final = f"[{sub_area}] {ubic_detalle}" if ubic_detalle else f"[{sub_area}]"
                        res = supabase.table("activos").insert({
                            "nombre":    nom,
                            "area":      area_principal,
                            "ubicacion": ubic_final,
                            "categoria": cat,
                            "foto_url":  final_url,
                            "detalles":  detalles_json
                        }).execute()
                        if res.data:
                            nid = res.data[0]['id']
                            qr  = generar_qr_activo(nid, nom)
                            supabase.table("activos").update({"qr_url": qr}).eq("id", nid).execute()
                            st.cache_data.clear()
                            st.session_state.draft_data = {}
                            img_local = foto_archivo.getvalue() if foto_archivo else None
                            st.session_state.activo_creado_info = {
                                "id": nid, "nombre": nom, "area": area_principal,
                                "ubicacion": ubic_final, "categoria": cat,
                                "foto_url": final_url, "foto_bytes": img_local,
                                "detalles": detalles_json, "qr_url": qr
                            }
                            st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error guardando en base de datos: {e}')

    with tab_edit:
        if not df_act.empty:
            all_assets = df_act['nombre'].values
            sel_asset  = st.selectbox("🔍 Buscar Activo para Ver o Editar", all_assets)
            dat        = df_act[df_act['nombre'] == sel_asset].iloc[0]
            id_suffix  = dat['id']

            st.markdown("---")
            st.subheader(f"Editando: {dat['nombre']}")

            c1, c2 = st.columns(2)
            current_area_idx = list(sorted(areas_data.keys())).index(dat['area']) if dat['area'] in areas_data else 0
            edit_area = c1.selectbox("Área", sorted(areas_data.keys()), index=current_area_idx, key=f"edit_area_{id_suffix}")

            curr_sub, curr_det = "", ""
            if dat['ubicacion']:
                parts    = dat['ubicacion'].split('] ', 1)
                curr_sub = parts[0].replace('[', '')
                curr_det = parts[1] if len(parts) > 1 else ""

            sub_areas_edit  = sorted(areas_data[edit_area])
            curr_sub_idx    = sub_areas_edit.index(curr_sub) if curr_sub in sub_areas_edit else 0
            edit_sub        = c2.selectbox("Sub-área", sub_areas_edit, index=curr_sub_idx, key=f"edit_sub_{id_suffix}")
            edit_nom        = c1.text_input("Nombre", value=dat['nombre'], key=f"edit_nom_{id_suffix}")
            edit_det        = c2.text_input("Ubicación Detalle", value=curr_det, key=f"edit_det_{id_suffix}")
            curr_cat_idx    = categorias_list.index(dat['categoria']) if dat['categoria'] in categorias_list else 0
            edit_cat        = c1.selectbox("Categoría", categorias_list, index=curr_cat_idx, key=f"edit_cat_{id_suffix}")

            st.markdown("---")
            nueva_foto_temp = st.file_uploader("Subir nueva foto", type=["jpg","png"], key=f"edit_up_{id_suffix}")

            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                st.markdown("#### 🖼️ Visualización")
                if nueva_foto_temp:
                    st.image(nueva_foto_temp, use_container_width=True, caption="Nueva imagen (Sin guardar)")
                else:
                    url_db = dat.get('foto_url')
                    if pd.notna(url_db) and isinstance(url_db, str) and len(url_db.strip()) > 10:
                        try:   st.image(url_db, use_container_width=True, caption="Imagen actual")
                        except: st.error("Error al cargar la imagen desde la nube.")
                    else:
                        st.info("Sin imagen asignada.")
            with col_f2:
                st.markdown("#### 🔄 Estado de Carga")
                if nueva_foto_temp:
                    st.toast("✅ Foto lista para actualizar.")
                else:
                    st.caption("Selecciona un archivo arriba si deseas cambiar la foto actual.")

            edit_foto_file = nueva_foto_temp

            st.markdown("---")
            st.markdown("#### ⚙️ Editar Especificaciones")
            current_specs_df = pd.DataFrame(columns=["Componente/Dato", "Valor"])
            if dat.get('detalles') and isinstance(dat['detalles'], dict):
                current_specs_df = pd.DataFrame(list(dat['detalles'].items()), columns=["Componente/Dato","Valor"])
            edited_specs = st.data_editor(
                current_specs_df, num_rows="dynamic", use_container_width=True,
                column_config={
                    "Componente/Dato": st.column_config.TextColumn("Característica"),
                    "Valor":           st.column_config.TextColumn("Valor")
                },
                key=f"editor_edit_{id_suffix}"
            )

            st.markdown("<br>", unsafe_allow_html=True)
            bc1, bc2 = st.columns([2, 1])
            with bc1:
                if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True, key=f"btn_save_{id_suffix}"):
                    if not edit_nom:
                        agregar_notificacion("error", "El nombre no puede estar vacío")
                    else:
                        try:
                            with st.spinner("Actualizando activo..."):
                                final_edit_url  = dat['foto_url']
                                if edit_foto_file:
                                    final_edit_url = subir_imagen(edit_foto_file)
                                final_edit_ubic  = f"[{edit_sub}] {edit_det}" if edit_det else f"[{edit_sub}]"
                                final_specs_json = {
                                    row["Componente/Dato"]: row["Valor"]
                                    for i, row in edited_specs.iterrows()
                                    if row["Componente/Dato"] and row["Valor"]
                                }
                                supabase.table("activos").update({
                                    "nombre": edit_nom, "area": edit_area, "ubicacion": final_edit_ubic,
                                    "categoria": edit_cat, "foto_url": final_edit_url, "detalles": final_specs_json
                                }).eq("id", dat['id']).execute()
                                st.cache_data.clear()
                                agregar_notificacion("success", f"Activo '{edit_nom}' actualizado correctamente")
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
            with bc2:
                with st.expander("🗑️ Zona de Peligro", expanded=True):
                    st.warning("Acciones críticas.")
                    ids_planes = ids_solic = ids_activas = ids_historial = []

                    if dat.get('id'):
                        res = supabase.table("planes_mantenimiento").select("id").eq("activo_id", dat['id']).execute()
                        ids_planes = [str(x['id']) for x in res.data]
                        res = supabase.table("solicitudes").select("id").eq("activo_id", dat['id']).execute()
                        ids_solic  = [str(x['id']) for x in res.data]
                        res = supabase.table("ordenes").select("id, estado").eq("activo_id", dat['id']).execute()
                        ids_activas   = [str(o['id']) for o in res.data if o['estado'] in ['Abierta','Por Validar']]
                        ids_historial = [str(o['id']) for o in res.data if o['estado'] not in ['Abierta','Por Validar']]

                    bloqueo_total = ids_planes or ids_activas or ids_solic

                    if bloqueo_total:
                        st.markdown("""
                        <div style="background-color:rgba(239,68,68,0.1);border-left:4px solid #EF4444;padding:10px;margin-bottom:10px;">
                            <strong style="color:#EF4444;">🛑 NO SE PUEDE BORRAR</strong>
                            <p style="font-size:0.85em;margin:0;">Hay tareas pendientes activas.</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if ids_planes:
                            st.caption(f"📅 Planes ({len(ids_planes)})")
                            df_l = pd.DataFrame({'ID': ids_planes, 'Ir': ['Ver Plan']*len(ids_planes)})
                            sel  = st.dataframe(df_l, selection_mode='single-row', on_select='rerun',
                                                use_container_width=True, hide_index=True, key=f"lk_p_{id_suffix}")
                            if len(sel.selection.rows) > 0:
                                st.session_state.current_page = "Ordenes de Trabajo"
                                st.session_state.jump_target  = "preventivo"
                                st.session_state.jump_id      = df_l.iloc[sel.selection.rows[0]]['ID']
                                st.rerun()
                        if ids_activas:
                            st.caption(f"🛠️ Órdenes Activas ({len(ids_activas)})")
                            df_l = pd.DataFrame({'ID': ids_activas, 'Ir': ['Ver Orden']*len(ids_activas)})
                            sel  = st.dataframe(df_l, selection_mode='single-row', on_select='rerun',
                                                use_container_width=True, hide_index=True, key=f"lk_o_{id_suffix}")
                            if len(sel.selection.rows) > 0:
                                st.session_state.current_page = "Ordenes de Trabajo"
                                st.session_state.jump_target  = "orden"
                                st.session_state.jump_id      = df_l.iloc[sel.selection.rows[0]]['ID']
                                st.rerun()
                        if ids_solic:
                            st.caption(f"📬 Solicitudes ({len(ids_solic)}) — Gestionar en Buzón")
                    else:
                        if ids_historial:
                            st.markdown(f"""
                            <div style="background-color:rgba(245,158,11,0.1);border-left:4px solid #F59E0B;padding:10px;margin-bottom:10px;">
                                <strong style="color:#F59E0B;">⚠️ TIENE HISTORIAL</strong>
                                <p style="font-size:0.85em;margin:0;">Este equipo tiene <b>{len(ids_historial)}</b> órdenes cerradas.</p>
                            </div>
                            """, unsafe_allow_html=True)
                            try:
                                if 'df_users_cache' not in st.session_state:
                                    st.session_state.df_users_cache = run_query("usuarios")
                                data_hist = supabase.table("ordenes").select("*").in_("id", ids_historial)\
                                            .order("fecha_creacion", desc=True).execute()
                                if data_hist.data:
                                    pdf_bytes = generar_hoja_vida_pdf(dat, data_hist.data, st.session_state.df_users_cache)
                                    st.download_button(
                                        label     = "📄 DESCARGAR HOJA DE VIDA (PDF)",
                                        data      = pdf_bytes,
                                        file_name = f"Hoja_Vida_{dat['nombre']}.pdf",
                                        mime      = "application/pdf",
                                        use_container_width=True
                                    )
                            except Exception as e:
                                st.error(f"Error generando PDF: {e}")
                        else:
                            st.toast("✅ Equipo limpio (Sin historial).")

                        st.markdown("---")
                        if st.button("🗑️ CONFIRMAR ELIMINACIÓN", type="secondary",
                                     use_container_width=True, key=f"fin_del_{id_suffix}"):
                            try:
                                if ids_historial:
                                    supabase.table("ordenes").delete().in_("id", ids_historial).execute()
                                supabase.table("activos").delete().eq("id", dat['id']).execute()
                                st.cache_data.clear()
                                agregar_notificacion("delete", "Activo eliminado correctamente.")
                                time.sleep(1.5)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error técnico: {e}")

            st.markdown("---")
            if dat.get('qr_url'):
                st.caption("Código QR del Activo")
                st.image(dat['qr_url'], width=150)
        else:
            st.info("No hay activos registrados para editar.")

# ==============================================================================
# FIX 4 (CRÍTICO): CARGA DE DATOS ANTES DEL INTERCEPTOR + st.tabs() DEFINIDO
# ==============================================================================
elif choice == "Ordenes de Trabajo":
    st.title("GESTIÓN DE MANTENIMIENTO")
    mostrar_notificaciones()

    # ── 1. CARGA DE DATOS (SIEMPRE PRIMERO) ──────────────────────────────────
    df_act    = run_query("activos")
    df_users  = run_query("usuarios")
    df_ordenes = run_query("ordenes")
    df_solicitudes = run_query("solicitudes")

    # ── 2. INTERCEPTOR (ahora tiene df_act y df_users disponibles) ────────────
    if 'jump_target' in st.session_state and st.session_state.jump_target:
        target_type = st.session_state.jump_target
        target_id   = st.session_state.jump_id

        st.markdown(f"""
        <div style="background-color:#1F2937;padding:15px;border-radius:8px;border-left:5px solid #3B82F6;margin-bottom:20px;">
            <h3 style="color:#60A5FA;margin:0;">🛠️ Gestión de Dependencia #{target_id}</h3>
            <p style="margin:0;color:#9CA3AF;font-size:0.9em;">Edita o reasigna este registro para liberar el activo original.</p>
        </div>
        """, unsafe_allow_html=True)

        if st.button("⬅️ VOLVER A EDICIÓN DE ACTIVO", use_container_width=True):
            st.session_state.current_page = "Inventario Activos"
            st.session_state.jump_target  = None
            st.session_state.jump_id      = None
            st.rerun()

        st.markdown("---")

        if target_type == "orden":
            try:
                res = supabase.table("ordenes").select("*").eq("id", target_id).execute()
                if res.data:
                    orden_actual = res.data[0]
                    with st.form(key=f"form_focus_orden_{target_id}"):
                        c_edit1, c_edit2, c_edit3 = st.columns(3)
                        est_opts    = ["Abierta","Por Validar","Concluida","Cancelada"]
                        idx_est     = est_opts.index(orden_actual['estado']) if orden_actual['estado'] in est_opts else 0
                        nuevo_estado = c_edit1.selectbox("Estado", est_opts, index=idx_est)

                        lista_tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin','Programador'])]
                        tech_dict      = dict(zip(lista_tecnicos['nombre'], lista_tecnicos['id']))
                        tech_actual_id = str(orden_actual['tecnico_asignado'])
                        nombre_tech    = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), "Seleccionar...")

                        act_dict       = dict(zip(df_act['nombre'], df_act['id']))
                        act_actual_id  = orden_actual['activo_id']
                        nombre_act     = next((k for k, v in act_dict.items() if v == act_actual_id), list(act_dict.keys())[0])

                        nuevo_act_nom = c_edit2.selectbox("Reasignar Activo", list(act_dict.keys()),
                                                           index=list(act_dict.keys()).index(nombre_act))
                        nuevo_tec_nom = c_edit3.selectbox("Técnico", list(tech_dict.keys()),
                                                           index=list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0)
                        nueva_desc = st.text_area("Descripción / Reporte", value=orden_actual['descripcion'])
                        nueva_crit = st.select_slider("Criticidad", ["Baja","Media","Alta","Crítica"], value=orden_actual['criticidad'])

                        if st.form_submit_button("💾 GUARDAR CAMBIOS Y REASIGNAR", type="primary", use_container_width=True):
                            supabase.table("ordenes").update({
                                "estado":            nuevo_estado,
                                "tecnico_asignado":  str(tech_dict[nuevo_tec_nom]),
                                "activo_id":         int(act_dict[nuevo_act_nom]),
                                "criticidad":        nueva_crit,
                                "descripcion":       nueva_desc
                            }).eq("id", target_id).execute()
                            st.toast("✅ Orden actualizada correctamente.")
                            time.sleep(1.2)
                            st.rerun()

                    st.markdown("### 🗑️ Opciones Críticas")
                    if st.button("ELIMINAR ORDEN DEFINITIVAMENTE", type="secondary", use_container_width=True):
                        supabase.table("ordenes").delete().eq("id", target_id).execute()
                        st.toast("🗑️ Orden eliminada.")
                        st.session_state.jump_target = None
                        time.sleep(1.2)
                        st.rerun()
                else:
                    st.error("Orden no encontrada.")
            except Exception as e:
                st.error(f"Error: {e}")

        elif target_type == "preventivo":
            try:
                res = supabase.table("planes_mantenimiento").select("*").eq("id", target_id).execute()
                if res.data:
                    plan_focus = res.data[0]
                    with st.form("form_focus_prev"):
                        c1, c2   = st.columns(2)
                        act_dict = dict(zip(df_act['nombre'], df_act['id']))
                        nombre_act_actual = next((k for k, v in act_dict.items() if v == plan_focus['activo_id']), list(act_dict.keys())[0])
                        nuevo_act_nom = c1.selectbox("Reasignar a Activo", list(act_dict.keys()),
                                                      index=list(act_dict.keys()).index(nombre_act_actual))
                        tech_dict  = dict(zip(df_users['nombre'], df_users['id']))
                        nombre_tech = next((k for k, v in tech_dict.items() if str(v) == str(plan_focus['tecnico_default'])), list(tech_dict.keys())[0])
                        nuevo_tec_nom = c2.selectbox("Técnico Encargado", list(tech_dict.keys()),
                                                      index=list(tech_dict.keys()).index(nombre_tech))
                        desc_p = st.text_input("Tarea", value=plan_focus['descripcion'])
                        dias_p = st.number_input("Frecuencia (Días)", value=plan_focus['frecuencia_dias'])

                        if st.form_submit_button("💾 GUARDAR Y REASIGNAR", type="primary", use_container_width=True):
                            supabase.table("planes_mantenimiento").update({
                                "activo_id":       int(act_dict[nuevo_act_nom]),
                                "tecnico_default": str(tech_dict[nuevo_tec_nom]),
                                "descripcion":     desc_p,
                                "frecuencia_dias": dias_p
                            }).eq("id", target_id).execute()
                            st.toast("✅ Plan actualizado.")
                            time.sleep(1.2)
                            st.rerun()

                    if st.button("🗑️ ELIMINAR PLAN DEFINITIVAMENTE", type="secondary", use_container_width=True):
                        supabase.table("planes_mantenimiento").delete().eq("id", target_id).execute()
                        st.session_state.jump_target = None
                        st.rerun()
            except Exception as e:
                st.error(f"Error en preventivo: {e}")

        st.stop()  # Detiene el resto de la página mientras el interceptor está activo

    # ── 3. DEFINICIÓN DE TABS (ANTES de los bloques with) ────────────────────
    tab_mis_gestiones, tab_buzon, tab_calidad, tab_gestion, tab_crear_directa, tab_preventivos = st.tabs([
        "📂 Mis Gestiones",
        "📥 Buzón Solicitudes",
        "🧐 Control Calidad",
        "🎛️ Gestión Global",
        "➕ Crear Directa",
        "🗓️ Preventivos"
    ])

    # ── 4. CONTENIDO DE CADA TAB ──────────────────────────────────────────────
    with tab_mis_gestiones:
        st.info("Aquí administras las órdenes asignadas a ti (Cotizaciones, Compras, Trámites).")

        @st.dialog("✏️ Editar Avance")
        def editar_avance_dialog(item_id, texto_actual, url_actual):
            st.write(f"Editando registro #{item_id}")
            nuevo_texto  = st.text_area("Corrección", value=texto_actual, height=100)
            st.markdown("---")
            st.caption("📎 Gestión de Archivos")
            borrar_archivo = False
            if url_actual:
                st.markdown(f"**Archivo actual:** [Ver documento]({url_actual})")
                borrar_archivo = st.checkbox("🗑️ Borrar archivo actual", value=False)
            archivo_nuevo = st.file_uploader("Cambiar archivo (Opcional)",
                                              type=["pdf","docx","xlsx","jpg","png","msg"])
            if st.button("💾 GUARDAR CAMBIOS", type="primary"):
                with st.spinner("Procesando..."):
                    try:
                        datos_update = {"mensaje": nuevo_texto}
                        if borrar_archivo:
                            datos_update["archivo_url"] = None
                        if archivo_nuevo:
                            url_subida = subir_archivo_generico(archivo_nuevo)
                            if url_subida:
                                datos_update["archivo_url"] = url_subida
                        supabase.table("bitacora").update(datos_update).eq("id", item_id).execute()
                        st.toast("Registro actualizado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {e}")

        mi_id_admin = None
        if not df_users.empty:
            user_match = df_users[df_users['nombre'] == usuario]
            if not user_match.empty:
                mi_id_admin = user_match.iloc[0]['id']

        if mi_id_admin:
            mis_gestiones = df_ordenes[
                (df_ordenes['tecnico_asignado'] == str(mi_id_admin)) &
                (df_ordenes['estado'] != 'Concluida')
            ]
            if mis_gestiones.empty:
                st.toast("🎉 No tienes gestiones administrativas pendientes.")
            else:
                for idx, row in mis_gestiones.iterrows():
                    nombre_activo = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "Activo"
                    with st.expander(f"📂 {nombre_activo} | {row['descripcion'][:50]}... (ID: {row['id']})", expanded=False):
                        color_borde = "#3B82F6"
                        if row['criticidad'] == 'Alta':    color_borde = "#F59E0B"
                        if row['criticidad'] == 'Crítica': color_borde = "#EF4444"

                        st.markdown(f"""
                        <div style="background-color:#1F2937;border-left:4px solid {color_borde};padding:15px;border-radius:4px;margin-bottom:20px;">
                            <h5 style="color:#9CA3AF;margin:0;font-size:0.9em;">📋 Detalle del Requerimiento</h5>
                            <p style="color:#F3F4F6;font-size:1.1em;margin:8px 0;font-weight:500;">"{row['descripcion']}"</p>
                            <div style="display:flex;gap:20px;font-size:0.85em;color:#9CA3AF;border-top:1px solid #374151;padding-top:8px;margin-top:10px;">
                                <span>📅 <b>Creada:</b> {row['fecha_creacion'][:10]}</span>
                                <span>🚨 <b>Criticidad:</b> {row['criticidad']}</span>
                                <span>🔧 <b>Tipo:</b> {row['tipo_mantenimiento']}</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

                        st.markdown("##### 📜 Historial de Gestión")
                        try:
                            bitacora = supabase.table("bitacora").select("*")\
                                       .eq("orden_id", row['id']).order("fecha", desc=True).execute()
                            if bitacora.data:
                                for b in bitacora.data:
                                    c_info, c_actions = st.columns([5, 1])
                                    with c_info:
                                        fecha_fmt    = b['fecha'][:10] + " " + b['fecha'][11:16]
                                        usuario_log  = b.get('usuario_text', 'Usuario')
                                        url          = b['archivo_url']
                                        adjunto_html = ""
                                        if url:
                                            ul = url.lower()
                                            if ul.endswith(('.jpg','.jpeg','.png','.webp')):
                                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#10B981;">🖼️ <b>Ver Imagen</b></a>"""
                                            elif ul.endswith('.pdf'):
                                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#EF4444;">📄 <b>Descargar PDF</b></a>"""
                                            elif ul.endswith('.msg'):
                                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#3B82F6;">📧 <b>Descargar Correo</b></a>"""
                                            elif ul.endswith(('.xls','.xlsx')):
                                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#16A34A;">📊 <b>Descargar Excel</b></a>"""
                                            else:
                                                adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#F59E0B;">📎 <b>Descargar Archivo</b></a>"""
                                        st.markdown(f"""
                                        <div style="background-color:rgba(255,255,255,0.05);border-left:3px solid #F59E0B;padding:10px;border-radius:0 5px 5px 0;margin-bottom:5px;">
                                            <div style="display:flex;justify-content:space-between;color:#9CA3AF;font-size:0.85em;">
                                                <span>📅 {fecha_fmt}</span><span>👤 <b>{usuario_log}</b></span>
                                            </div>
                                            <div style="margin-top:5px;color:#E5E7EB;white-space:pre-wrap;">{b['mensaje']}</div>
                                            {adjunto_html}
                                        </div>
                                        """, unsafe_allow_html=True)
                                    with c_actions:
                                        if st.button("✏️", key=f"btn_edit_{b['id']}", help="Editar"):
                                            editar_avance_dialog(b['id'], b['mensaje'], b['archivo_url'])
                                        if st.button("🗑️", key=f"btn_del_{b['id']}", help="Eliminar"):
                                            supabase.table("bitacora").delete().eq("id", b['id']).execute()
                                            st.toast("Eliminado")
                                            time.sleep(0.5)
                                            st.rerun()
                            else:
                                st.caption("No hay avances registrados aún.")
                        except Exception as e:
                            st.error(f"Error cargando historial: {e}")

                        st.divider()
                        st.markdown("##### ➕ Registrar Nuevo Avance")
                        with st.form(key=f"form_bitacora_{row['id']}", clear_on_submit=True):
                            c_msg, c_file   = st.columns([2, 1])
                            nuevo_mensaje   = c_msg.text_area("Detalle del avance", height=100)
                            archivo_gestion = c_file.file_uploader("Adjuntar archivo",
                                                type=["pdf","docx","xlsx","jpg","png","msg"],
                                                key=f"file_{row['id']}")
                            if st.form_submit_button("💾 GUARDAR AVANCE", type="primary", use_container_width=True):
                                if not nuevo_mensaje:
                                    st.error("⚠️ El mensaje no puede estar vacío.")
                                else:
                                    url_doc = None
                                    if archivo_gestion:
                                        with st.spinner("Subiendo archivo..."):
                                            url_doc = subir_archivo_generico(archivo_gestion)
                                    supabase.table("bitacora").insert({
                                        "orden_id":     row['id'],
                                        "usuario_text": usuario,
                                        "mensaje":      nuevo_mensaje,
                                        "archivo_url":  url_doc,
                                        "fecha":        datetime.now().isoformat()
                                    }).execute()
                                    st.toast("✅ Avance registrado correctamente.")
                                    time.sleep(1)
                                    st.rerun()

                        st.markdown("---")
                        activar_cierre = st.checkbox("✅ Habilitar opciones de Finalizar / Cerrar", key=f"check_fin_{row['id']}")
                        if activar_cierre:
                            st.markdown("""
                            <div style="background-color:rgba(16,185,129,0.1);padding:10px;border-radius:5px;border-left:3px solid #10B981;margin:10px 0;">
                                <small>Al finalizar, la orden pasará a estado <b>Concluida</b>.</small>
                            </div>
                            """, unsafe_allow_html=True)
                            motivo_cierre = st.text_input("Comentario final de cierre (Opcional)", key=f"cierre_text_{row['id']}")
                            if st.button("CONFIRMAR Y FINALIZAR ORDEN", key=f"btn_fin_seguro_{row['id']}", type="primary", use_container_width=True):
                                msg_final = f"[CIERRE ADMIN] {motivo_cierre}" if motivo_cierre else "[CIERRE ADMIN] Gestión finalizada."
                                supabase.table("ordenes").update({
                                    "estado": "Concluida", "comentarios_cierre": msg_final,
                                    "fecha_cierre": datetime.now().isoformat()
                                }).eq("id", row['id']).execute()
                                supabase.table("bitacora").insert({
                                    "orden_id":     row['id'],
                                    "usuario_text": usuario,
                                    "mensaje":      "🏁 Orden finalizada administrativamente.",
                                    "fecha":        datetime.now().isoformat()
                                }).execute()
                                st.balloons()
                                st.toast("🏆 Orden finalizada correctamente.")
                                time.sleep(1.5)
                                st.rerun()

    with tab_buzon:
        if df_solicitudes.empty:
            st.markdown("<div style='text-align:center;padding:40px;color:#6B7280;'><h3>✨ Todo limpio</h3><p>No hay solicitudes pendientes.</p></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"### 📥 Solicitudes Pendientes ({len(df_solicitudes)})")
            if not df_act.empty:
                act_map_nombre_id   = dict(zip(df_act['nombre'], df_act['id']))
                lista_nombres_activos = sorted(list(act_map_nombre_id.keys()))

                for idx, sol in df_solicitudes.iterrows():
                    with st.form(key=f"form_sol_{sol['id']}"):
                        st.markdown(f"""
                        <div style="border:1px solid #374151;border-radius:8px;padding:15px;margin-bottom:15px;background-color:#1F2937;">
                            <div style="display:flex;justify-content:space-between;">
                                <h4 style="color:#F59E0B;margin:0;">Solicitud #{sol['id']}</h4>
                                <span style="color:#6B7280;font-size:0.8em;">📅 {sol['fecha_solicitud'][:10]}</span>
                            </div>
                            <p style="margin:5px 0;color:#D1D5DB;">👤 <b>Solicita:</b> {sol['solicitante_id']}</p>
                            <p style="margin:5px 0;color:#E5E7EB;background:rgba(255,255,255,0.05);padding:8px;border-radius:4px;">📝 <i>"{sol['descripcion']}"</i></p>
                        </div>
                        """, unsafe_allow_html=True)

                        cols_val = st.columns([1, 2, 2, 1])
                        with cols_val[0]:
                            if sol['foto_url']: st.image(sol['foto_url'], width=80)
                            else: st.caption("Sin foto")
                        with cols_val[1]:
                            activo_final_nombre = st.selectbox("Vincular Activo", lista_nombres_activos,
                                                                index=None, placeholder="🔍 Buscar activo...")
                            tipo_ot = st.selectbox("Tipo Mant.", ["Correctivo","Preventivo","Predictivo","Mejora"],
                                                    index=None, placeholder="Seleccionar tipo...")
                        with cols_val[2]:
                            tech_options = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
                            _, nom_sug_b, _ = sugerir_tecnico(df_ordenes, df_users)
                            tech_keys_b = list(tech_options.keys())
                            idx_sug_b   = tech_keys_b.index(nom_sug_b) if nom_sug_b and nom_sug_b in tech_keys_b else 0
                            asignar_a   = st.selectbox("Asignar a", tech_keys_b, index=idx_sug_b)
                            sug         = sol['prioridad_sugerida']
                            val_defecto = sug if sug in ["Baja","Media","Alta","Crítica"] else "Media"
                            criticidad_final = st.select_slider("Definir Criticidad",
                                                                  options=["Baja","Media","Alta","Crítica"],
                                                                  value=val_defecto)
                        with cols_val[3]:
                            st.markdown("<br>", unsafe_allow_html=True)
                            btn_crear    = st.form_submit_button("✅ CREAR",    type="primary",    use_container_width=True)
                            btn_rechazar = st.form_submit_button("❌ RECHAZAR", type="secondary",  use_container_width=True)

                        if btn_crear:
                            if not activo_final_nombre or not tipo_ot or not asignar_a:
                                st.error("⚠️ Falta seleccionar: Activo, Tipo o Técnico.")
                            else:
                                try:
                                    res_orden = supabase.table("ordenes").insert({
                                        "activo_id":         int(act_map_nombre_id[activo_final_nombre]),
                                        "chat_id":           sol.get('chat_id'),
                                        "descripcion":       f"[Solicitud #{sol['id']}] {sol['descripcion']}",
                                        "criticidad":        criticidad_final,
                                        "tipo_mantenimiento": tipo_ot,
                                        "estado":            "Abierta",
                                        "tecnico_asignado":  str(tech_options[asignar_a]),
                                        "fecha_creacion":    datetime.now().isoformat(),
                                    }).execute()
                                    if res_orden.data:
                                        nuevo_id = res_orden.data[0]['id']
                                        if sol.get('foto_url'):
                                            es_imagen = sol['foto_url'].lower().endswith(('.png','.jpg','.jpeg','.webp'))
                                            icono_msg = "📸" if es_imagen else "📎"
                                            supabase.table("bitacora").insert({
                                                "orden_id":     nuevo_id,
                                                "usuario_text": f"Solicitante: {sol['solicitante_id']}",
                                                "mensaje":      f"{icono_msg} Evidencia original del reporte.",
                                                "archivo_url":  sol['foto_url'],
                                                "fecha":        datetime.now().isoformat()
                                            }).execute()
                                        msj_ok = f"✅ **¡Solicitud Aprobada!**\n\nOrden **#{nuevo_id}** ({tipo_ot}). Prioridad: {criticidad_final}."
                                        notificar_telegram(sol.get('chat_id'), msj_ok)
                                        supabase.table("solicitudes").update({"estado": "Aprobada"}).eq("id", sol['id']).execute()
                                        st.toast(f"✅ Orden #{nuevo_id} creada.")
                                        time.sleep(1)
                                        st.rerun()
                                    else:
                                        st.error("Error: No se generó el ID de la orden.")
                                except Exception as e:
                                    st.error(f"Error: {e}")

                        if btn_rechazar:
                            supabase.table("solicitudes").update({"estado": "Rechazada"}).eq("id", sol['id']).execute()
                            notificar_telegram(sol.get('chat_id'), "🚫 Solicitud Rechazada.")
                            st.warning("Rechazada.")
                            st.rerun()

    with tab_calidad:
        df_revision = run_query("ordenes", {"estado": "Por Validar"})
        if df_revision.empty:
            st.markdown("<div style='text-align:center;padding:40px;color:#10B981;'><h3>✨ Todo revisado</h3><p>No hay trabajos pendientes.</p></div>", unsafe_allow_html=True)
        else:
            st.markdown(f"### 🧐 Auditoría de Trabajos ({len(df_revision)})")
            for idx, row in df_revision.iterrows():
                nombre_activo  = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "N/A"
                tecnico_nombre = "Desconocido"
                if not df_users.empty:
                    t_data = df_users[df_users['id'].astype(str) == row['tecnico_asignado']]
                    if not t_data.empty: tecnico_nombre = t_data.iloc[0]['nombre']

                with st.container():
                    st.markdown(f"""
                    <div style="border:1px solid #4B5563;border-radius:8px;padding:20px;margin-bottom:20px;background-color:#1F2937;">
                        <h3 style="color:#60A5FA;margin:0;">OT #{row['id']} | {nombre_activo}</h3>
                        <p style="color:#9CA3AF;">👷 Realizado por: <b>{tecnico_nombre}</b></p>
                        <hr style="border-color:#374151;">
                    """, unsafe_allow_html=True)

                    col_rev1, col_rev2 = st.columns([1, 1])
                    with col_rev1:
                        st.markdown("**📸 EVIDENCIA:**")
                        if row.get('foto_cierre_url'): st.image(row['foto_cierre_url'], use_container_width=True)
                        else: st.warning("Sin foto.")
                    with col_rev2:
                        st.markdown("**📝 REPORTE:**")
                        st.info(f"{row.get('comentarios_cierre', 'Sin reporte')}")
                        st.markdown("---")
                        if st.button("✅ APROBAR Y CERRAR", key=f"apr_fin_{row['id']}", type="primary", use_container_width=True):
                            supabase.table("ordenes").update({"estado": "Concluida"}).eq("id", row['id']).execute()
                            if row.get('chat_id'):
                                notificar_telegram(row.get('chat_id'),
                                    f"🎉 **¡Solucionado!**\n\nOrden **#{row['id']}** cerrada.",
                                    row.get('foto_cierre_url'))
                            st.toast("Orden cerrada.")
                            st.rerun()
                        st.markdown("<br>", unsafe_allow_html=True)
                        with st.expander("↩️ Devolver (Rechazar)"):
                            motivo = st.text_input("Motivo", key=f"mot_{row['id']}")
                            if st.button("CONFIRMAR DEVOLUCIÓN", key=f"dev_{row['id']}", type="secondary", use_container_width=True):
                                if motivo:
                                    supabase.table("ordenes").update({
                                        "estado": "Abierta",
                                        "comentarios_validacion": f"DEVUELTA: {motivo}"
                                    }).eq("id", row['id']).execute()
                                    st.warning("Devuelta.")
                                    st.rerun()
                                else:
                                    st.error("Falta motivo.")
                    st.markdown("</div>", unsafe_allow_html=True)

    with tab_gestion:
        st.markdown("### 🎛️ Control Central de Órdenes")

        filtro_ot_externo = None
        if st.session_state.get('jump_target') == 'orden' and st.session_state.get('jump_id'):
            filtro_ot_externo = st.session_state.jump_id
            st.toast(f"📍 Filtrando Orden #{filtro_ot_externo}", icon="🔍")
            st.session_state.jump_target = None
            st.session_state.jump_id     = None

        col_filtros  = st.columns(3)
        filtro_estado = col_filtros[0].selectbox("Filtrar Estado",
                            ["Todas","Abierta","Por Validar","Concluida"], index=0)

        df_display = df_ordenes.copy()
        if filtro_estado != "Todas":
            df_display = df_display[df_display['estado'] == filtro_estado]
        if filtro_ot_externo:
            df_display = df_display[df_display['id'].astype(str) == str(filtro_ot_externo)]

        if not df_display.empty:
            map_act  = dict(zip(df_act['id'],             df_act['nombre']))          if not df_act.empty  else {}
            map_user = dict(zip(df_users['id'].astype(str), df_users['nombre']))      if not df_users.empty else {}
            df_display['Activo Nombre']  = df_display['activo_id'].map(map_act).fillna("Desconocido")
            df_display['Técnico Nombre'] = df_display['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
            df_display = df_display.sort_values('id', ascending=False)

            event = st.dataframe(
                df_display[['id','estado','Activo Nombre','descripcion','Técnico Nombre','criticidad','fecha_creacion']],
                use_container_width=True, hide_index=True,
                selection_mode="single-row", on_select="rerun", height=250
            )

            if len(event.selection.rows) > 0:
                idx_tabla       = event.selection.rows[0]
                id_orden_selec  = df_display.iloc[idx_tabla]['id']
                orden_actual    = df_ordenes[df_ordenes['id'] == id_orden_selec].iloc[0]

                st.divider()
                col_izq, col_der = st.columns([1.5, 1])

                with col_izq:
                    st.markdown(f"#### ✏️ Gestionar Orden #{id_orden_selec}")
                    if orden_actual['estado'] in ['Concluida', 'Por Validar']:
                        try:
                            pdf_data = generar_pdf_orden(orden_actual,
                                                          df_display.iloc[idx_tabla]['Activo Nombre'],
                                                          df_display.iloc[idx_tabla]['Técnico Nombre'])
                            st.download_button("📄 Descargar PDF Reporte", data=pdf_data,
                                               file_name=f"Reporte_OT_{id_orden_selec}.pdf",
                                               mime="application/pdf",
                                               key=f"btn_pdf_g_{id_orden_selec}")
                        except: pass

                    with st.form(key=f"form_edit_orden_g_{id_orden_selec}"):
                        c_edit1, c_edit2, c_edit3 = st.columns(3)
                        est_opts = ["Abierta","Por Validar","Concluida","Cancelada"]
                        idx_est  = est_opts.index(orden_actual['estado']) if orden_actual['estado'] in est_opts else 0
                        nuevo_estado = c_edit1.selectbox("Estado", est_opts, index=idx_est)

                        lista_tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin','Programador'])]
                        tech_dict      = dict(zip(lista_tecnicos['nombre'], lista_tecnicos['id']))
                        tech_actual_id = str(orden_actual['tecnico_asignado'])
                        nombre_tech    = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), "Seleccionar...")
                        idx_tech       = list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0
                        nuevo_tec_nom  = c_edit2.selectbox("Reasignar Técnico", list(tech_dict.keys()), index=idx_tech)
                        nueva_crit     = c_edit3.select_slider("Criticidad", ["Baja","Media","Alta","Crítica"],
                                                                value=orden_actual['criticidad'])
                        st.markdown("**Descripción / Falla:**")
                        nueva_desc = st.text_area("Descripción", value=orden_actual['descripcion'], height=100)
                        st.markdown("<br>", unsafe_allow_html=True)

                        if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True):
                            try:
                                supabase.table("ordenes").update({
                                    "estado":           nuevo_estado,
                                    "tecnico_asignado": str(tech_dict[nuevo_tec_nom]),
                                    "criticidad":       nueva_crit,
                                    "descripcion":      nueva_desc
                                }).eq("id", int(id_orden_selec)).execute()
                                st.toast("Orden actualizada correctamente.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al actualizar: {e}")

                    if orden_actual['estado'] in ['Concluida', 'Cancelada']:
                        st.markdown("---")
                        st.markdown("#### 🔓 Reactivar Orden")
                        st.info("Utiliza este botón si cerraste la orden por error.")
                        if st.button("🔄 RE-ABRIR ORDEN", key=f"reopen_{id_orden_selec}", type="secondary", use_container_width=True):
                            try:
                                id_limpio = int(id_orden_selec)
                                supabase.table("ordenes").update({
                                    "estado": "Abierta", "fecha_cierre": None
                                }).eq("id", id_limpio).execute()
                                supabase.table("bitacora").insert({
                                    "orden_id":     id_limpio,
                                    "usuario_text": str(usuario),
                                    "mensaje":      "🔄 Orden RE-ABIERTA administrativamente.",
                                    "fecha":        datetime.now().isoformat()
                                }).execute()
                                st.toast("✅ Orden reactivada.")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al re-abrir: {e}")

                    with st.expander("🗑️ Zona de Peligro (Eliminar)"):
                        if st.button("ELIMINAR DEFINITIVAMENTE", key=f"del_g_{id_orden_selec}", type="secondary", use_container_width=True):
                            supabase.table("ordenes").delete().eq("id", int(id_orden_selec)).execute()
                            st.toast("Eliminado.")
                            time.sleep(1)
                            st.rerun()

                with col_der:
                    st.markdown("#### 📜 Bitácora y Adjuntos")
                    st.caption("Historial de avances y archivos cargados.")
                    with st.container(height=500, border=True):
                        try:
                            bitacora_res = supabase.table("bitacora").select("*")\
                                           .eq("orden_id", id_orden_selec).order("fecha", desc=True).execute()
                            if bitacora_res.data:
                                for b in bitacora_res.data:
                                    fecha_fmt   = b['fecha'][:10] + " " + b['fecha'][11:16]
                                    usuario_log = b.get('usuario_text', 'Sistema')
                                    url         = b.get('archivo_url')
                                    adjunto_html = ""
                                    icon_bit     = "💬"
                                    if url:
                                        ul = url.lower()
                                        if ul.endswith(('.jpg','.jpeg','.png','.webp')):
                                            icon_bit     = "📸"
                                            adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#10B981;font-weight:bold;">🖼️ Ver Imagen</a>"""
                                        elif ul.endswith('.pdf'):
                                            icon_bit     = "📄"
                                            adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#EF4444;font-weight:bold;">📄 Ver PDF</a>"""
                                        elif ul.endswith(('.xls','.xlsx')):
                                            icon_bit     = "📊"
                                            adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#16A34A;font-weight:bold;">📊 Ver Excel</a>"""
                                        elif ul.endswith('.msg'):
                                            icon_bit     = "📧"
                                            adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#3B82F6;font-weight:bold;">📧 Ver Correo</a>"""
                                        else:
                                            icon_bit     = "📎"
                                            adjunto_html = f"""<br><a href="{url}" target="_blank" style="color:#F59E0B;font-weight:bold;">📎 Ver Archivo</a>"""
                                    st.markdown(f"""
                                    <div style="background-color:rgba(255,255,255,0.05);padding:10px;border-radius:6px;margin-bottom:8px;border-left:3px solid #60A5FA;">
                                        <div style="font-size:0.8em;color:#9CA3AF;display:flex;justify-content:space-between;">
                                            <span>{icon_bit} {usuario_log}</span><span>{fecha_fmt}</span>
                                        </div>
                                        <div style="color:#E5E7EB;margin-top:4px;font-size:0.95em;">{b['mensaje']}</div>
                                        {adjunto_html}
                                    </div>
                                    """, unsafe_allow_html=True)
                            else:
                                st.info("No hay registros en la bitácora para esta orden.")
                        except Exception as e:
                            st.error(f"Error cargando bitácora: {e}")
        else:
            st.info("No hay órdenes registradas con los filtros actuales.")

    with tab_crear_directa:
        st.info("Creación rápida: Los campos se limpiarán automáticamente al guardar.")
        if not df_act.empty:
            act_dict     = dict(zip(df_act['nombre'], df_act['id']))
            nom_sugerido = render_sugerencia_tecnico(df_ordenes, df_users)

            with st.form("ot_directa", clear_on_submit=True):
                sel_act_dir = st.selectbox("Activo", sorted(act_dict.keys()))
                c1, c2     = st.columns(2)
                tipo_d     = c1.selectbox("Tipo", ["Correctivo","Preventivo","Predictivo","Mejora"])
                crit_d     = c2.select_slider("Criticidad", ["Baja","Media","Alta","Crítica"])
                desc_d     = st.text_area("Descripción")

                tech_opts_d = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
                idx_sug     = 0
                if nom_sugerido and nom_sugerido in list(tech_opts_d.keys()):
                    idx_sug = list(tech_opts_d.keys()).index(nom_sugerido)
                asig_d = st.selectbox("Asignar Técnico", list(tech_opts_d.keys()), index=idx_sug,
                                       help="🤖 Preseleccionado automáticamente por menor carga")

                st.markdown("---")
                st.markdown("##### 📎 Adjuntos Iniciales")
                archivo_inicial = st.file_uploader("Soporte (PDF, Excel, Foto, Correo)",
                                                    type=["pdf","docx","xlsx","jpg","png","msg"])
                st.markdown("<br>", unsafe_allow_html=True)

                if st.form_submit_button("CREAR ORDEN", type="primary", use_container_width=True):
                    if not desc_d:
                        st.error("La descripción es obligatoria.")
                    else:
                        try:
                            res_orden = supabase.table("ordenes").insert({
                                "activo_id":         int(act_dict[sel_act_dir]),
                                "descripcion":       desc_d,
                                "criticidad":        crit_d,
                                "tipo_mantenimiento": tipo_d,
                                "estado":            "Abierta",
                                "tecnico_asignado":  str(tech_opts_d[asig_d]),
                                "fecha_creacion":    datetime.now().isoformat()
                            }).execute()
                            if res_orden.data:
                                nuevo_id_ot = res_orden.data[0]['id']
                                st.toast(f"✅ Orden #{nuevo_id_ot} creada correctamente.")
                                if archivo_inicial:
                                    with st.spinner("Subiendo archivo adjunto..."):
                                        url_doc = subir_archivo_generico(archivo_inicial)
                                        if url_doc:
                                            supabase.table("bitacora").insert({
                                                "orden_id":     nuevo_id_ot,
                                                "usuario_text": usuario,
                                                "mensaje":      "📎 Documento inicial adjunto al crear la orden.",
                                                "archivo_url":  url_doc,
                                                "fecha":        datetime.now().isoformat()
                                            }).execute()
                                            st.toast("Documento vinculado a la bitácora")
                                        else:
                                            st.error("La orden se creó, pero falló la subida del archivo.")
                                time.sleep(1.5)
                                st.rerun()
                            else:
                                st.error("No se pudo obtener el ID de la nueva orden.")
                        except Exception as e:
                            st.error(f"Error al crear: {e}")
        else:
            st.warning("No hay activos registrados.")

    with tab_preventivos:
        render_tab_preventivos(df_act, df_users)

# ==============================================================================
# 🔩 REPUESTOS
# ==============================================================================
elif choice == "Repuestos":
    st.title("🔩 GESTIÓN DE REPUESTOS")
    mostrar_notificaciones()

    categorias_rep = sorted([
        "Eléctrico","Mecánico","Hidráulico","Neumático","Lubricantes","Filtros",
        "Correas y Cadenas","Rodamientos","Electrónico","Herramientas","Otros"
    ])

    df_rep = run_query("repuestos")
    df_ord = run_query("ordenes")
    df_mov = run_query("movimientos_repuestos")
    df_users = run_query("usuarios")

    tab_stock, tab_nuevo, tab_movimientos, tab_alertas = st.tabs([
        "📋 STOCK ACTUAL", "➕ NUEVO REPUESTO", "🔄 MOVIMIENTOS", "🚨 ALERTAS DE STOCK"
    ])

    with tab_stock:
        if df_rep.empty:
            st.info("No hay repuestos registrados aún.")
        else:
            total_rep  = len(df_rep)
            bajo_stock = len(df_rep[df_rep['stock_actual'] <= df_rep['stock_minimo']])
            sin_stock  = len(df_rep[df_rep['stock_actual'] == 0])
            valor_items = df_rep['stock_actual'].sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("🔩 Total Repuestos",   total_rep)
            k2.metric("📦 Unidades Totales",  int(valor_items))
            k3.metric("⚠️ Bajo Stock",         bajo_stock, delta_color="inverse")
            k4.metric("🚨 Sin Stock",           sin_stock,  delta_color="inverse")

            st.markdown("---")
            cf1, cf2 = st.columns(2)
            filtro_cat_r = cf1.selectbox("Filtrar Categoría", ["Todas"] + categorias_rep)
            filtro_stock = cf2.selectbox("Filtrar Estado Stock", ["Todos","OK","Bajo Stock","Sin Stock"])

            df_rep_f = df_rep.copy()
            if filtro_cat_r != "Todas":
                df_rep_f = df_rep_f[df_rep_f['categoria'] == filtro_cat_r]
            if filtro_stock == "OK":
                df_rep_f = df_rep_f[df_rep_f['stock_actual'] > df_rep_f['stock_minimo']]
            elif filtro_stock == "Bajo Stock":
                df_rep_f = df_rep_f[(df_rep_f['stock_actual'] <= df_rep_f['stock_minimo']) & (df_rep_f['stock_actual'] > 0)]
            elif filtro_stock == "Sin Stock":
                df_rep_f = df_rep_f[df_rep_f['stock_actual'] == 0]

            def estado_stock(row):
                if row['stock_actual'] == 0:              return "🔴 Sin Stock"
                elif row['stock_actual'] <= row['stock_minimo']: return "🟡 Bajo Stock"
                else:                                     return "🟢 OK"

            df_rep_f['Estado'] = df_rep_f.apply(estado_stock, axis=1)
            st.dataframe(
                df_rep_f[['id','foto_url','nombre','referencia','categoria',
                           'stock_actual','stock_minimo','unidad','ubicacion','Estado']],
                column_config={
                    "foto_url":     st.column_config.ImageColumn("Foto",       width="small"),
                    "id":           st.column_config.NumberColumn("ID",         format="%d", width="small"),
                    "nombre":       st.column_config.TextColumn("Nombre",       width="medium"),
                    "referencia":   st.column_config.TextColumn("Referencia"),
                    "categoria":    st.column_config.TextColumn("Categoría"),
                    "stock_actual": st.column_config.NumberColumn("Stock",      format="%d"),
                    "stock_minimo": st.column_config.NumberColumn("Mínimo",     format="%d"),
                    "unidad":       st.column_config.TextColumn("Unidad"),
                    "ubicacion":    st.column_config.TextColumn("Ubicación"),
                    "Estado":       st.column_config.TextColumn("Estado")
                },
                hide_index=True, use_container_width=True, height=400
            )

            st.markdown("---")
            st.markdown("#### 📊 Nivel de Stock por Repuesto")
            df_grafica = df_rep_f.sort_values('stock_actual', ascending=True).tail(15)
            fig_stock  = go.Figure()
            fig_stock.add_trace(go.Bar(name='Stock Actual', y=df_grafica['nombre'], x=df_grafica['stock_actual'],
                                       orientation='h', marker=dict(color='#10B981'),
                                       text=df_grafica['stock_actual'], textposition='inside'))
            fig_stock.add_trace(go.Bar(name='Stock Mínimo', y=df_grafica['nombre'], x=df_grafica['stock_minimo'],
                                       orientation='h', marker=dict(color='#F59E0B', opacity=0.5),
                                       text=df_grafica['stock_minimo'], textposition='inside'))
            fig_stock.update_layout(barmode='overlay', paper_bgcolor='rgba(0,0,0,0)',
                                     plot_bgcolor='rgba(0,0,0,0)', font=dict(color='white'), height=400,
                                     margin=dict(l=0,r=0,t=10,b=0), legend=dict(orientation="h", y=-0.15),
                                     xaxis=dict(title="Unidades"), yaxis=dict(title=None))
            st.plotly_chart(fig_stock, use_container_width=True)

    with tab_nuevo:
        st.markdown("### Registrar Nuevo Repuesto")
        with st.form("form_nuevo_repuesto", clear_on_submit=True):
            c1, c2  = st.columns(2)
            nom_r   = c1.text_input("Nombre del Repuesto")
            ref_r   = c2.text_input("Referencia / Código", placeholder="Ej: SKF-6205")
            cat_r   = c1.selectbox("Categoría", categorias_rep)
            ubic_r  = c2.text_input("Ubicación en bodega", placeholder="Ej: Estante A, Gaveta 3")
            c3, c4, c5 = st.columns(3)
            stock_i = c3.number_input("Stock Inicial",  min_value=0, value=0)
            stock_m = c4.number_input("Stock Mínimo",   min_value=0, value=1)
            unidad  = c5.selectbox("Unidad", ["Unidad","Par","Caja","Litro","Galón","Metro","Kilogramo","Rollo"])
            foto_r  = st.file_uploader("Foto del repuesto (Opcional)", type=["jpg","png","jpeg"])

            if st.form_submit_button("💾 GUARDAR REPUESTO", type="primary", use_container_width=True):
                if not nom_r:
                    agregar_notificacion('error', 'El nombre es obligatorio.')
                else:
                    try:
                        url_foto_r = None
                        if foto_r:
                            with st.spinner("Subiendo foto..."):
                                url_foto_r = subir_imagen(foto_r, "orion_repuestos")
                        supabase.table("repuestos").insert({
                            "nombre":       nom_r, "referencia": ref_r,
                            "categoria":    cat_r, "ubicacion":  ubic_r,
                            "stock_actual": int(stock_i), "stock_minimo": int(stock_m),
                            "unidad":       unidad, "foto_url": url_foto_r
                        }).execute()
                        st.cache_data.clear()
                        agregar_notificacion('success', f'Repuesto {nom_r} registrado correctamente.')
                        st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error: {e}')

    with tab_movimientos:
        st.markdown("### 🔄 Registrar Entrada o Salida")
        if df_rep.empty:
            st.warning("Primero registra repuestos en la pestaña anterior.")
        else:
            rep_dict = dict(zip(df_rep['nombre'], df_rep['id']))
            ord_dict = {}
            if not df_ord.empty:
                df_ord_ab = df_ord[df_ord['estado'] == 'Abierta']
                ord_dict  = {f"OT #{r['id']} — {r['descripcion'][:40]}": r['id']
                             for _, r in df_ord_ab.iterrows()}

            with st.form("form_movimiento", clear_on_submit=True):
                c1, c2   = st.columns(2)
                rep_sel  = c1.selectbox("Repuesto", list(rep_dict.keys()))
                tipo_mov = c2.selectbox("Tipo", ["Salida","Entrada"])
                cantidad = c1.number_input("Cantidad", min_value=1, value=1)
                orden_sel = None
                if tipo_mov == "Salida" and ord_dict:
                    orden_sel = c2.selectbox("Vincular a Orden (Opcional)",
                                              ["Sin vincular"] + list(ord_dict.keys()))
                observacion = st.text_input("Observación", placeholder="Ej: Cambio por desgaste en línea 1")

                if st.form_submit_button("✅ REGISTRAR MOVIMIENTO", type="primary", use_container_width=True):
                    try:
                        rep_id    = int(rep_dict[rep_sel])
                        rep_actual = df_rep[df_rep['id'] == rep_id].iloc[0]
                        stock_hoy  = int(rep_actual['stock_actual'])
                        if tipo_mov == "Salida" and cantidad > stock_hoy:
                            agregar_notificacion('error', f'Stock insuficiente. Disponible: {stock_hoy} {rep_actual["unidad"]}')
                        else:
                            nuevo_stock  = stock_hoy - cantidad if tipo_mov == "Salida" else stock_hoy + cantidad
                            id_orden_mov = None
                            if tipo_mov == "Salida" and orden_sel and orden_sel != "Sin vincular":
                                id_orden_mov = int(ord_dict[orden_sel])
                            supabase.table("movimientos_repuestos").insert({
                                "repuesto_id":  rep_id,
                                "orden_id":     id_orden_mov,
                                "tipo":         tipo_mov,
                                "cantidad":     int(cantidad),
                                "usuario_text": usuario,
                                "observacion":  observacion,
                                "fecha":        datetime.now().isoformat()
                            }).execute()
                            supabase.table("repuestos").update({"stock_actual": nuevo_stock}).eq("id", rep_id).execute()
                            stock_min = int(rep_actual['stock_minimo'])
                            if nuevo_stock <= stock_min:
                                mensaje_tel = (
                                    f"⚠️ *ALERTA STOCK BAJO*\n\n"
                                    f"🔩 *Repuesto:* {rep_sel}\n"
                                    f"📦 *Stock actual:* {nuevo_stock} {rep_actual['unidad']}\n"
                                    f"🔻 *Stock mínimo:* {stock_min}"
                                )
                                df_admins = df_users[df_users['rol'] == 'Admin'] if not df_users.empty else pd.DataFrame()
                                for _, adm in df_admins.iterrows():
                                    if adm.get('chat_id'):
                                        notificar_telegram(adm['chat_id'], mensaje_tel)
                            st.cache_data.clear()
                            agregar_notificacion('success', f'{tipo_mov} de {cantidad} {rep_actual["unidad"]} de {rep_sel} registrada.')
                            st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error: {e}')

            st.markdown("---")
            st.markdown("#### 📜 Historial de Movimientos")
            if not df_mov.empty:
                df_mov_vis = df_mov.copy()
                rep_map    = dict(zip(df_rep['id'], df_rep['nombre']))
                df_mov_vis['Repuesto'] = df_mov_vis['repuesto_id'].map(rep_map).fillna('N/A')
                df_mov_vis = df_mov_vis.sort_values('fecha', ascending=False).head(50)
                st.dataframe(
                    df_mov_vis[['fecha','tipo','Repuesto','cantidad','orden_id','usuario_text','observacion']],
                    column_config={
                        "fecha":        st.column_config.DatetimeColumn("Fecha", format="DD/MM/YY HH:mm"),
                        "tipo":         st.column_config.TextColumn("Tipo"),
                        "Repuesto":     st.column_config.TextColumn("Repuesto"),
                        "cantidad":     st.column_config.NumberColumn("Cant.", format="%d"),
                        "orden_id":     st.column_config.NumberColumn("OT #",  format="%d"),
                        "usuario_text": st.column_config.TextColumn("Usuario"),
                        "observacion":  st.column_config.TextColumn("Observación")
                    },
                    hide_index=True, use_container_width=True, height=350
                )
            else:
                st.info("No hay movimientos registrados aún.")

    with tab_alertas:
        st.markdown("### 🚨 Repuestos que Requieren Atención")
        if df_rep.empty:
            st.info("No hay repuestos registrados.")
        else:
            df_alertas_r = df_rep[df_rep['stock_actual'] <= df_rep['stock_minimo']].copy()
            if df_alertas_r.empty:
                st.toast("✅ Todo el inventario está en niveles óptimos.")
            else:
                df_alertas_r['Déficit'] = (df_alertas_r['stock_minimo'] - df_alertas_r['stock_actual']).clip(lower=0)
                df_sin  = df_alertas_r[df_alertas_r['stock_actual'] == 0]
                df_bajo = df_alertas_r[df_alertas_r['stock_actual'] > 0]

                if not df_sin.empty:
                    st.error(f"🔴 {len(df_sin)} repuestos SIN STOCK")
                    st.dataframe(df_sin[['nombre','referencia','categoria','stock_actual','stock_minimo','Déficit','ubicacion']],
                                 hide_index=True, use_container_width=True)
                if not df_bajo.empty:
                    st.warning(f"🟡 {len(df_bajo)} repuestos con STOCK BAJO")
                    st.dataframe(df_bajo[['nombre','referencia','categoria','stock_actual','stock_minimo','Déficit','ubicacion']],
                                 hide_index=True, use_container_width=True)

                st.markdown("---")
                if st.button("📲 ENVIAR RESUMEN DE ALERTAS POR TELEGRAM", type="primary", use_container_width=True):
                    resumen  = f"🚨 *RESUMEN DE STOCK — ORIÓN*\n\n"
                    resumen += f"🔴 Sin stock: {len(df_sin)} repuestos\n"
                    resumen += f"🟡 Bajo stock: {len(df_bajo)} repuestos\n\n"
                    for _, r in df_alertas_r.iterrows():
                        icono    = "🔴" if r['stock_actual'] == 0 else "🟡"
                        resumen += f"{icono} {r['nombre']} — Stock: {r['stock_actual']}/{r['stock_minimo']}\n"
                    df_admins = df_users[df_users['rol'] == 'Admin'] if not df_users.empty else pd.DataFrame()
                    enviados  = 0
                    for _, adm in df_admins.iterrows():
                        if adm.get('chat_id'):
                            notificar_telegram(adm['chat_id'], resumen)
                            enviados += 1
                    if enviados > 0:
                        agregar_notificacion('success', f'Resumen enviado a {enviados} administrador(es).')
                    else:
                        agregar_notificacion('warning', 'No hay admins con chat_id configurado.')
                    st.rerun()

# ==============================================================================
# 👤 USUARIOS
# ==============================================================================
elif choice == "Usuarios":
    st.title("USUARIOS")
    mostrar_notificaciones()

    tab_crear, tab_gestionar = st.tabs(["CREAR USUARIO", "GESTIONAR USUARIOS"])

    with tab_crear:
        st.subheader("Registrar Nuevo Usuario")
        with st.form("new_user_form"):
            c1, c2    = st.columns(2)
            documento = c1.text_input("Documento/ID",      key="new_user_doc")
            nombre    = c2.text_input("Nombre Completo",   key="new_user_name")
            password  = c1.text_input("Contraseña",        type="password", key="new_user_pass")
            rol       = c2.selectbox("Rol", ["Tecnico","Programador","Admin"], key="new_user_rol")
            submitted = st.form_submit_button("REGISTRAR USUARIO", type="primary")

            if submitted:
                if documento and nombre and password and rol:
                    if not validar_usuario_unico(documento):
                        agregar_notificacion('error', 'El documento ya existe en el sistema.')
                    elif len(password) < 4:
                        agregar_notificacion('error', 'La contraseña debe tener al menos 4 caracteres.')
                    else:
                        try:
                            res = supabase.table("usuarios").insert({
                                "documento": documento,
                                "nombre":    nombre,
                                "password":  hashear_password(password),
                                "rol":       rol
                            }).execute()
                            if res.data:
                                st.cache_data.clear()
                                agregar_notificacion('success', f'Usuario {nombre} registrado con éxito.')
                                st.rerun()
                            else:
                                agregar_notificacion('error', 'Error al registrar el usuario.')
                        except Exception as e:
                            agregar_notificacion('error', f'Error de base de datos: {e}')
                else:
                    agregar_notificacion('warning', 'Por favor, complete todos los campos.')

    with tab_gestionar:
        df_users = run_query("usuarios")
        if not df_users.empty:
            st.subheader("Seleccionar Usuario para Gestionar")
            user_options      = {f"{row['nombre']} (ID: {row['id']})": row['id'] for _, row in df_users.iterrows()}
            user_options_list = ["-- Seleccione un usuario --"] + list(user_options.keys())
            selected_option   = st.selectbox("Usuario:", user_options_list, key="user_selector")

            st.markdown("### Lista Completa de Usuarios")
            st.dataframe(df_users[['id','documento','nombre','rol']], hide_index=True, use_container_width=True)

            if selected_option != "-- Seleccione un usuario --":
                user_id       = user_options[selected_option]
                selected_user = df_users[df_users['id'] == user_id].iloc[0]

                st.markdown("---")
                st.markdown(f"### Editando: **{selected_user['nombre']}** (ID: {user_id})")

                with st.form(key=f"edit_user_form_{user_id}"):
                    c1, c2       = st.columns(2)
                    edit_doc     = c1.text_input("Documento/ID",    value=selected_user['documento'])
                    edit_name    = c2.text_input("Nombre Completo", value=selected_user['nombre'])
                    rol_options  = ["Tecnico","Programador","Admin"]
                    current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                    new_rol      = st.selectbox("Rol", rol_options, index=current_rol_index)
                    new_password = st.text_input("Nueva Contraseña (Dejar vacío para no cambiar)", type="password")
                    st.markdown("<br>", unsafe_allow_html=True)
                    update_submitted = st.form_submit_button("✅ ACTUALIZAR USUARIO", type="primary", use_container_width=True)

                    if update_submitted:
                        if new_rol != selected_user['rol']:
                            if check_open_orders(user_id):
                                agregar_notificacion('error',
                                    f'El usuario **{selected_user["nombre"]}** tiene Órdenes pendientes. Debe cerrarlas antes de cambiar su rol.')
                                st.stop()
                        if not validar_usuario_unico(edit_doc, user_id):
                            agregar_notificacion('error', 'El documento ya está en uso por otro usuario.')
                        else:
                            update_data = {"documento": edit_doc, "nombre": edit_name, "rol": new_rol}
                            if new_password:
                                if len(new_password) < 4:
                                    agregar_notificacion('error', 'La contraseña debe tener al menos 4 caracteres.')
                                else:
                                    update_data["password"] = hashear_password(new_password)
                            try:
                                supabase.table("usuarios").update(update_data).eq("id", user_id).execute()
                                st.cache_data.clear()
                                agregar_notificacion('success', f'Usuario {edit_name} actualizado.')
                                st.rerun()
                            except Exception as e:
                                agregar_notificacion('error', f'Error al actualizar: {e}')

                st.markdown("---")
                st.markdown("### 🗑️ Zona de Eliminación")
                has_open_orders = check_open_orders(user_id)
                if has_open_orders:
                    st.markdown(f"""
                        <div style='background:rgba(239,68,68,0.15);border:2px solid #EF4444;border-radius:8px;padding:20px;text-align:center;'>
                            <p style='color:#FCA5A5;margin:0;font-size:1.1rem;'>⚠️ <strong>ELIMINACIÓN BLOQUEADA</strong></p>
                            <p style='color:#FEE2E2;margin-top:10px;font-size:0.95rem;'>El usuario <strong>{selected_user['nombre']}</strong> tiene Órdenes de Trabajo pendientes.</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ Esta acción eliminará permanentemente al usuario **{selected_user['nombre']}**")
                    if st.button("🗑️ ELIMINAR USUARIO PERMANENTEMENTE", type="secondary",
                                 use_container_width=True, key=f"delete_btn_{user_id}"):
                        try:
                            supabase.table("usuarios").delete().eq("id", user_id).execute()
                            st.cache_data.clear()
                            agregar_notificacion('delete', f'Usuario {selected_user["nombre"]} eliminado.')
                            st.rerun()
                        except Exception as e:
                            agregar_notificacion('error', f'Error al eliminar: {e}')
        else:
            st.info("No se encontraron usuarios. Use la pestaña 'CREAR USUARIO'.")
