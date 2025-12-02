# ==============================================================================
# PROYECTO: ORIÓN - Mantenimiento Inteligente
# AUTOR: [JHON ESTEBN PENAGOS Jhonestebanpenagos@gmail.com +57 3184705862]
# FECHA DE CREACIÓN: Noviembre 2025
# DERECHOS: Todos los derechos reservados. Prohibida su copia o distribución.
# ==============================================================================
import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io
import urllib.parse
import json
import qrcode
import cv2 
import numpy as np
import time
import plotly.express as px
import plotly.graph_objects as go 

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Orión | Mantenimiento", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# 🎨 TEMA: "ORIÓN COMFORT UI" (Mejorado para la vista)
# ==============================================================================

PRO_ORANGE = "#F59E0B" 
PRO_GREEN = "#10B981"  
BG_DARK_CLEAN = "#0e1117"  # Fondo principal más profundo (Gris casi negro)
BG_SIDEBAR = "#161b22"     # Barra lateral: Gris azulado oscuro (tipo GitHub Dark)
BG_CARD = "rgba(30, 41, 59, 0.7)" # Tarjetas semitransparentes
TEXT_WHITE = "#E5E7EB"     # Blanco humo (menos agresivo que #FFFFFF)

st.markdown(f"""
    <style>
    /* 1. FONDO GENERAL */
    .stApp {{
        background-color: {BG_DARK_CLEAN};
        color: {TEXT_WHITE};
    }}

    /* 2. BARRA LATERAL AJUSTADA */
    [data-testid="stSidebar"] {{
        background-color: {BG_SIDEBAR};
        border-right: 1px solid #30363d;
    }}
    
    /* Texto de navegación más legible */
    [data-testid="stSidebarNav"] span {{
        color: #9CA3AF !important;
        font-weight: 500;
    }}
    
    /* Elemento seleccionado en el menú */
    [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background-color: rgba(245, 158, 11, 0.1);
        border-left: 3px solid {PRO_ORANGE};
    }}

    /* 3. TÍTULOS */
    h1, h2, h3 {{
        background: linear-gradient(90deg, {PRO_ORANGE}, {PRO_GREEN});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }}

    /* 4. TARJETAS */
    .card-style {{
        background: {BG_CARD};
        backdrop-filter: blur(12px);
        border-radius: 12px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }}
    .login-container {{
        border-radius: 12px;
        padding: 30px;
        margin-top: 20px;
    }}

    /* 5. TÍTULOS DE GRÁFICAS */
    .chart-header {{
        font-size: 1.1rem;
        font-weight: 700;
        color: {PRO_ORANGE};
        margin-bottom: 15px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 8px;
        display: block;
    }}

    /* 6. INPUTS Y MENÚS (Estilo unificado) */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
        background-color: #0d1117 !important; 
        color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        border-radius: 6px;
    }}
    
    /* Focus en inputs */
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {PRO_ORANGE} !important;
        box-shadow: 0 0 0 1px {PRO_ORANGE} !important;
    }}

    div[data-baseweb="popover"], div[data-baseweb="menu"] {{
        background-color: #161b22 !important;
        border: 1px solid #30363d;
    }}
    div[data-baseweb="menu"] li:hover {{
        background-color: {PRO_ORANGE} !important;
        color: white !important;
    }}
    
    /* Etiquetas de inputs */
    .stTextInput label, .stSelectbox label, .stTextArea label {{
        color: #E5E7EB !important;
        font-weight: 600 !important;
    }}
    
    /* 7. BOTONES */
    div.stButton > button:first-child {{
        background: linear-gradient(90deg, {PRO_ORANGE} 0%, {PRO_GREEN} 100%) !important;
        color: white !important;
        border: none;
        font-weight: 600;
        border-radius: 6px;
        padding: 0.6rem 1.2rem;
        transition: transform 0.2s;
    }}
    div.stButton > button:first-child:hover {{
        transform: translateY(-2px);
        opacity: 0.9;
    }}

    /* 8. MÉTRICAS */
    [data-testid="stMetric"] {{
        background: rgba(30, 41, 59, 0.5);
        padding: 15px;
        border-radius: 8px;
        border-left: 4px solid {PRO_GREEN};
        border-top: 1px solid rgba(255,255,255,0.05);
        border-right: 1px solid rgba(255,255,255,0.05);
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }}
    [data-testid="stMetricLabel"] {{ color: #9CA3AF !important; }}
    [data-testid="stMetricValue"] {{ color: #F3F4F6 !important; }}

    /* 9. PESTAÑAS (TABS) */
    .stTabs [data-baseweb="tab"] {{ color: #9CA3AF; font-weight: 600; }}
    .stTabs [aria-selected="true"] {{ color: {PRO_ORANGE} !important; background-color: transparent !important; border-bottom-color: {PRO_ORANGE} !important; }}
    
    /* 10. ZONA PELIGRO */
    .danger-zone {{
        background: rgba(220, 38, 38, 0.1);
        border: 1px solid rgba(220, 38, 38, 0.3);
        color: #f87171;
        padding: 15px;
        border-radius: 8px;
        text-align: center;
    }}

    /* 11. BOTÓN SECUNDARIO (ROJO/BORRAR) */
    div.stButton > button[kind="secondary"] {{
        background: rgba(220, 38, 38, 0.15) !important;
        color: #fca5a5 !important;
        border: 1px solid #ef4444 !important;
        font-weight: 600 !important;
    }}
    div.stButton > button[kind="secondary"]:hover {{
        background: rgba(220, 38, 38, 0.3) !important;
        border-color: #f87171 !important;
    }}

    /* 12. HACK: OCULTAR CONTENEDORES VACÍOS */
    div[data-testid="stVerticalBlock"] > div:empty {{
        height: 0 !important;
        margin: 0 !important;
    }}
    
    /* 13. MEJORAS NAVEGACIÓN COLAPSADA */
    [data-testid="stSidebarNav"] {{
        padding-top: 10px !important;
    }}
    
    /* Tooltip personalizado en CSS para menú colapsado */
    @media (max-width: 768px) {{
        [data-testid="stSidebarNavItems"] .nav-link span {{ display: none; }}
    }}
    
    </style>
""", unsafe_allow_html=True)

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key) 
    except KeyError as e:
        st.error(f"❌ ERROR CRÍTICO: La clave {e} no se encuentra en la configuración de Streamlit Secrets (secrets.toml).")
        return None
    except Exception as e:
        st.error(f"❌ Error desconocido al conectar a Supabase. Verifique URL y clave. Detalles: {e}")
        return None

supabase = init_supabase()
if not supabase:
    st.stop()

# --- 3. FUNCIONES AUXILIARES MEJORADAS ---

@st.cache_data(ttl=1)  # Cache de 1 segundo para datos en tiempo real
def run_query(table_name, filters=None, order_by="id"):
    """Función optimizada para consultas con cache de 1 segundo"""
    try:
        query = supabase.table(table_name).select("*")
        
        if filters:
            for key, value in filters.items():
                if value is not None:
                    query = query.eq(key, value)
        
        query = query.order(order_by)
        response = query.execute()
        return pd.DataFrame(response.data) if response.data else pd.DataFrame()
    except Exception as e:
        st.error(f"Error en consulta {table_name}: {e}")
        return pd.DataFrame()

def subir_imagen(archivo, carpeta="evidencias"):
    if archivo:
        try:
            # 1. Caso: Imagen generada por código (bytes / QR)
            if isinstance(archivo, bytes):
                file_bytes = archivo
                file_name = f"qr_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                mime_type = "image/png"
            
            # 2. Caso: Archivo subido por el usuario (UploadedFile)
            else:
                file_bytes = archivo.getvalue()
                mime_type = archivo.type
                
                # --- CORRECCIÓN AQUÍ ---
                # Ignoramos el nombre original 'archivo.name' porque puede tener espacios o ser muy largo.
                # Generamos un nombre seguro usando solo la fecha y hora.
                extension = ".png" # Por defecto
                if archivo.name:
                    # Intentamos obtener la extensión original si existe (ej: .jpg)
                    if "." in archivo.name:
                        extension = f".{archivo.name.split('.')[-1]}"
                
                # Nombre final limpio: 202512012350_evidencia.jpg
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_evidencia{extension}"

            # 3. Subida a Supabase
            supabase.storage.from_(carpeta).upload(
                path=file_name, 
                file=file_bytes, 
                file_options={"content-type": mime_type}
            )
            return supabase.storage.from_(carpeta).get_public_url(file_name)
            
        except Exception as e:
            # Imprimimos el error en consola para depuración, pero no rompemos la app
            print(f"Error subida: {e}")
            st.error(f"Error al subir imagen: Verifique que el archivo no esté corrupto.")
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
    img_byte_arr = img_byte_arr.getvalue()
    return subir_imagen(img_byte_arr, "evidencias")

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
    """
    Convierte los valores de un diccionario a tipos nativos de Python
    para evitar errores de serialización JSON
    """
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

# --- SISTEMA DE NOTIFICACIONES MEJORADO ---
def mostrar_notificaciones():
    """Sistema de notificaciones más robusto"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    for notif in st.session_state.notifications[:]:
        tipo = notif.get('type')
        mensaje = notif.get('message')
        
        if tipo == 'success':
            st.success(f"✅ {mensaje}")
        elif tipo == 'error':
            st.error(f"❌ {mensaje}")
        elif tipo == 'warning':
            st.warning(f"⚠️ {mensaje}")
        elif tipo == 'info':
            st.info(f"ℹ️ {mensaje}")
        
        st.session_state.notifications.remove(notif)

def agregar_notificacion(tipo, mensaje):
    """Agrega una notificación al sistema"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    st.session_state.notifications.append({
        'type': tipo,
        'message': mensaje
    })

# --- VALIDACIONES MEJORADAS ---
def validar_usuario_unico(documento, usuario_id=None):
    """Valida que el documento sea único en el sistema"""
    try:
        query = supabase.table("usuarios").select("id").eq("documento", documento)
        if usuario_id:
            query = query.neq("id", usuario_id)
        
        response = query.execute()
        return len(response.data) == 0
    except:
        return False

def check_open_orders(user_id):
    """Verifica si el usuario tiene órdenes de trabajo activas"""
    try:
        user_id_str = str(user_id)
        response = supabase.table("ordenes") \
            .select("id, descripcion, fecha_creacion, estado") \
            .eq("tecnico_asignado", user_id_str) \
            .neq("estado", "Concluida") \
            .execute()
        
        if response.data and len(response.data) > 0:
            return True
        return False
    except Exception as e:
        return True

def get_open_orders_details(user_id):
    """Obtiene los detalles de las órdenes pendientes de un usuario"""
    try:
        user_id_str = str(user_id)
        response = supabase.table("ordenes") \
            .select("id, descripcion, criticidad, tipo_mantenimiento, fecha_creacion, estado") \
            .eq("tecnico_asignado", user_id_str) \
            .neq("estado", "Concluida") \
            .execute()
        return response.data if response.data else []
    except:
        return []

# --- MÉTRICAS INTELIGENTES MEJORADAS ---
def mostrar_metricas_inteligentes(df_ordenes, df_users):
    """Muestra métricas con análisis contextual mejorado"""
    if df_ordenes.empty:
        st.info("No hay datos para mostrar métricas")
        return
    
    total = len(df_ordenes)
    pendientes = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
    concluidas = len(df_ordenes[df_ordenes['estado'] == 'Concluida'])
    
    # Calcular porcentajes
    porcentaje_concluidas = (concluidas / total * 100) if total > 0 else 0
    
    # Cálculo de eficiencia
    if total == 0:
        eficiencia_valor = "Sin datos"
        eficiencia_color = "⚪"
    elif porcentaje_concluidas >= 90:
        eficiencia_valor = "Excelente"
        eficiencia_color = "🟢"
    elif porcentaje_concluidas >= 70:
        eficiencia_valor = "Buena"
        eficiencia_color = "🟡"
    elif porcentaje_concluidas >= 50:
        eficiencia_valor = "Regular"
        eficiencia_color = "🟠"
    else:
        eficiencia_valor = "Crítica"
        eficiencia_color = "🔴"
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Órdenes", total)
    
    with col2:
        st.metric("Pendientes", pendientes)
    
    with col3:
        st.metric("Finalizadas", concluidas, f"{porcentaje_concluidas:.1f}%")
    
    with col4:
        st.metric(
            f"{eficiencia_color} Eficiencia", 
            eficiencia_valor,
            help="Excelente: ≥90% | Buena: ≥70% | Regular: ≥50% | Crítica: <50%"
        )

# --- GRÁFICOS (PLOTLY) ---
def graficar_ordenes_por_tecnico(df_ordenes, df_users):
    """Muestra gráfico compacto de órdenes por técnico"""
    if df_ordenes.empty or df_users.empty:
        st.info("No hay datos de técnicos")
        return
    
    # Crear mapeo de IDs a nombres de técnicos
    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre']))
    
    # Preparar datos
    df_tecnicos = df_ordenes.copy()
    df_tecnicos['tecnico_nombre'] = df_tecnicos['tecnico_asignado'].astype(str).map(user_map).fillna('Sin asignar')
    
    # Contar órdenes por técnico y estado
    conteo_tecnicos = df_tecnicos.groupby(['tecnico_nombre', 'estado']).size().reset_index(name='cantidad')
    
    # Separar en abiertas y concluidas
    abiertas = conteo_tecnicos[conteo_tecnicos['estado'] == 'Abierta']
    concluidas = conteo_tecnicos[conteo_tecnicos['estado'] == 'Concluida']
    
    # Crear DataFrame unificado
    tecnicos_unicos = df_tecnicos['tecnico_nombre'].unique()
    datos_final = []
    
    for tecnico in tecnicos_unicos:
        abierta_count = abiertas[abiertas['tecnico_nombre'] == tecnico]['cantidad'].sum()
        concluida_count = concluidas[concluidas['tecnico_nombre'] == tecnico]['cantidad'].sum()
        total_tecnico = abierta_count + concluida_count
        
        datos_final.append({
            'Técnico': tecnico,
            'Abiertas': abierta_count,
            'Concluidas': concluida_count,
            'Total': total_tecnico
        })
    
    df_final = pd.DataFrame(datos_final).sort_values('Total', ascending=True)
    
    # Crear gráfico de barras apiladas
    fig = go.Figure()
    
    # Concluidas
    fig.add_trace(go.Bar(
        name='Concluidas',
        y=df_final['Técnico'],
        x=df_final['Concluidas'],
        orientation='h',
        marker=dict(color=PRO_GREEN, line=dict(width=0)),
        text=df_final['Concluidas'],
        textposition='inside',
        textfont=dict(color='white', size=12, weight='bold'),
        hovertemplate='<b>%{y}</b><br>Concluidas: %{x}<extra></extra>'
    ))
    
    # Abiertas
    fig.add_trace(go.Bar(
        name='Abiertas',
        y=df_final['Técnico'],
        x=df_final['Abiertas'],
        orientation='h',
        marker=dict(color=PRO_ORANGE, line=dict(width=0)),
        text=df_final['Abiertas'],
        textposition='inside',
        textfont=dict(color='white', size=12, weight='bold'),
        hovertemplate='<b>%{y}</b><br>Abiertas: %{x}<extra></extra>'
    ))
    
    fig.update_layout(
        barmode='stack',
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white', size=12),
        height=250,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=True,
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=-0.25,
            xanchor="center",
            x=0.5,
            font=dict(color='white', size=12),
            bgcolor='rgba(0,0,0,0)'
        ),
        xaxis=dict(
            showgrid=True, 
            gridcolor='rgba(255,255,255,0.1)',
            title=None,
            showticklabels=True
        ),
        yaxis=dict(title=None, tickfont=dict(size=11))
    )
    
    fig.update_layout(dragmode=False, hovermode='y unified')
    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})

def graficar_criticidad(df):
    if df.empty: return
    conteo = df['criticidad'].value_counts().reset_index()
    conteo.columns = ['Nivel', 'Cantidad']
    orden = ["Baja", "Media", "Alta", "Crítica"]
    conteo['Nivel'] = pd.Categorical(conteo['Nivel'], categories=orden, ordered=True)
    conteo = conteo.sort_values('Nivel')
    colores = {"Baja": "#10B981", "Media": "#F59E0B", "Alta": "#EA580C", "Crítica": "#EF4444"}
    fig = px.bar(conteo, x='Nivel', y='Cantidad', color='Nivel', 
                 color_discrete_map=colores, text='Cantidad')
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'), showlegend=False,
        margin=dict(l=0, r=0, t=10, b=0), height=250,
        xaxis=dict(title=None),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    fig.update_traces(textfont_size=14, textposition='outside', marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

def graficar_torta_tipo(df):
    if df.empty: return
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
    if df.empty: return
    conteo = df['estado'].value_counts().reset_index()
    conteo.columns = ['Estado', 'Cantidad']
    colores = {"Abierta": PRO_ORANGE, "Concluida": PRO_GREEN}
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

# --- FUNCIÓN AISLADA PARA EL SVG ---
def render_orion_svg(PRO_ORANGE):
    ORION_SVG = f"""
        <svg width="250" height="250" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
            <style>
                .star {{ fill: white; filter: drop-shadow(0 0 2px white); }}
                .belt {{ stroke: {PRO_ORANGE}; filter: drop-shadow(0 0 5px {PRO_ORANGE}); stroke-width: 2; opacity: 0.8; }}
                .line {{ stroke: {PRO_ORANGE}; stroke-width: 1; opacity: 0.4; }}
            </style>
            <path class="line" d="M100 150 L200 50 L300 150 L250 250 L150 250 L100 150 Z"/>
            <line class="belt" x1="160" y1="180" x2="200" y2="200"/>
            <line class="belt" x1="200" y1="200" x2="240" y2="220"/>
            <circle class="star" cx="200" cy="50" r="5"/> 
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
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).limit(5).execute()
            if ots.data:
                st.table(pd.DataFrame(ots.data)[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Sin registros.")
        except: pass

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
# 🚀 LOGIN
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        render_orion_svg(PRO_ORANGE)

        st.markdown(f"""
            <h1 style='text-align: center; font-size: 3.5rem; margin-bottom: -15px; text-shadow: 0 0 10px {PRO_ORANGE};'>ORIÓN</h1>
            <p style='text-align: center; color: #E5E7EB; font-size: 1.2rem; letter-spacing: 2px; margin-top: 5px; margin-bottom: 20px; font-weight: 300;'>
                PLATAFORMA INTEGRAL DE MANTENIMIENTO
            </p>
        """, unsafe_allow_html=True)

        st.markdown(f"""
            <div class='card-style' style='padding: 10px; margin-top: 0px; margin-bottom: 30px; text-align: center; font-size: 0.85em; color: {PRO_ORANGE}; border: none; box-shadow: none; background: transparent;'>
                <p style='margin: 0;'>Desarrollado por: <b>Jhonestebanpenagos@gmail.com</b></p>
            </div>
            <hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, {PRO_ORANGE}, transparent); margin-bottom: 30px;">
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>ACCESO DE USUARIOS</h3>", unsafe_allow_html=True)

        with st.form("login_form"):
            documento = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("ACCEDER AL SISTEMA", type="primary", use_container_width=True)
            if submitted:
                with st.spinner("Conectando y validando credenciales..."):
                    time.sleep(1) 

                try:
                    response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()

                    if response.data:
                        user = response.data[0]
                        st.session_state['usuario'] = user['nombre']
                        st.session_state['rol'] = user['rol']
                        st.rerun()
                    else: 
                        st.error("Acceso denegado. Usuario o contraseña incorrectos.")
                except Exception as e: 
                    st.error(f"Error de conexión. Intente nuevamente. Detalles: {e}")

    st.stop()

# ==============================================================================
# 🚀 DASHBOARD PRIVADO
# ==============================================================================

rol = st.session_state['rol']
usuario = st.session_state['usuario']

with st.sidebar:
    # Encabezado limpio
    st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <p style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">👋 {usuario}</p>
            <p style="color: #F59E0B; margin: 5px 0 0 0; font-size: 0.9rem;">{rol.upper()}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Botón de cerrar sesión
    if st.button("🔓 Salir", use_container_width=True, type="secondary"):
        logout()
    
    st.divider()
    
    # Inicializar navegación
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Tablero de Mando"
    
    # Menú simple
    if rol == "Admin":
        menu = [
            ("📊", "Tablero"),
            ("📦", "Inventario De Activos"), 
            ("➕", "Nueva OT"),
            ("📋", "Gestionar"),
            ("✅", "Cerrar"),
            ("👤", "Usuarios")
        ]
        valores = [
            "Tablero de Mando",
            "Inventario Activos", 
            "Crear Orden",
            "Gestionar Órdenes",
            "Cerrar Orden",
            "Usuarios"
        ]
    elif rol == "Programador":
        menu = [
            ("📊", "Tablero"),
            ("➕", "Nueva OT"),
            ("📋", "Gestionar"),
            ("👤", "Usuarios")
        ]
        valores = [
            "Tablero de Mando",
            "Crear Orden",
            "Gestionar Órdenes",
            "Usuarios"
        ]
    elif rol == "Tecnico":
        menu = [("✅", "Cerrar OT")]
        valores = ["Cerrar Orden"]
    
    # Navegación
    for (icono, texto), valor in zip(menu, valores):
        activo = st.session_state.current_page == valor
        tipo = "primary" if activo else "secondary"
        
        # CSS inline simple para botón activo
        if activo:
            st.markdown("""
            <style>
            .boton-activo {
                border: 2px solid #F59E0B !important;
            }
            </style>
            """, unsafe_allow_html=True)
        
        if st.button(
            f"{icono} {texto}",
            key=f"menu_{valor}",
            use_container_width=True,
            type=tipo
        ):
            st.session_state.current_page = valor
            st.rerun()
    
    choice = st.session_state.current_page
# ==============================================================================
# 📊 PANTALLAS
# ==============================================================================

if choice == "Tablero de Mando":
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()
    
    df = run_query("ordenes")
    df_users = run_query("usuarios")
    
    if not df.empty:
        # Métricas inteligentes MEJORADAS
        mostrar_metricas_inteligentes(df, df_users)

        st.write("") 

        # PRIMERA FILA: 3 GRÁFICOS PRINCIPALES
        st.markdown("### 📈 Métricas Visuales")
        c_left, c_mid, c_right = st.columns(3)

        with c_left:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Progreso de Órdenes</span>", unsafe_allow_html=True)
            graficar_estado_barras(df)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_mid:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Gravedad de las Fallas</span>", unsafe_allow_html=True)
            graficar_criticidad(df) 
            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Tipos de Mantenimiento</span>", unsafe_allow_html=True)
            graficar_torta_tipo(df) 
            st.markdown("</div>", unsafe_allow_html=True)

        # SEGUNDA FILA: GRÁFICO DE TÉCNICOS (MÁS ANCHO)
        st.markdown("### 👥 Órdenes de Trabajo por Técnico")
        with st.container():
            graficar_ordenes_por_tecnico(df, df_users)

    else: 
        st.info("No hay datos para mostrar.")
elif choice == "Inventario Activos":
    st.title("INVENTARIO DE ACTIVOS")
    mostrar_notificaciones()
    
    # --- 1. DATOS MAESTROS ---
    areas_data = {
        "Producción": [
            "Agua Cristal", "B&B", "Calderas", "Cuarto de Lubricación", 
            "Equipos Auxiliares", "Laboratorio Fisico Quimico", 
            "Laboratorio Microbiológico", "Linea 1", "Linea 10", 
            "Linea 8 Jugos", "Oficinas Técnicas", "Pasillo Técnico", 
            "Ptap", "Ptar", "Sala de Jarabe Simple", 
            "Sala de Jarabe Terminado", "Sala de Jarabes Jugos", 
            "Sub Estación Eléctrica", "Taller de Mantenimiento"
        ],
        "Administración": [
            "Administración", "Auditorio", "Casino", 
            "Portería Vehicular", "Servicios Generales"
        ],
        "Ventas": [
            "Bodega Carrera 8va", "Bodega Publicidad", 
            "Dispensadores", "Ventas"
        ],
        "Logística": [
            "Almacen Materia Prima", "Almacén Producto Terminado", 
            "Lavadero de Vehiculos", "Punto de Canje", 
            "Taller de Reparación de Estibas", "Taller Vehicular"
        ]
    }

    categorias_list = sorted([
        "Aire Acondicionado", "CCTV", "Control de Acceso", "Eléctrico", 
        "Estanterías", "Extraccion", "Hidrosanitario", "Infraestructura", 
        "Mecánico", "Muelles", "Red Contra Incendio", 
        "Refrigeración Industrial", "Ventilacion"
    ])

    df_act = run_query("activos")
    
    # --- ESTADOS DE SESIÓN ---
    if 'specs_data' not in st.session_state:
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
    
    if 'draft_data' not in st.session_state:
        st.session_state.draft_data = {}

    # --- DEFINICIÓN DE PESTAÑAS (AHORA SON 3) ---
    tab_lista, tab_nuevo, tab_edit = st.tabs(["📋 LISTA DE ACTIVOS", "➕ NUEVO ACTIVO", "✏️ EDITAR / QR"])

 # ==============================================================================
    # 📋 PESTAÑA 1: LISTA MAESTRA (ESTABLE - SIN CIERRE AUTOMÁTICO)
    # ==============================================================================
    with tab_lista:
        if not df_act.empty:
            
            # --- 1. DEFINICIÓN DEL VISOR (VENTANA FLOTANTE) ---
            @st.dialog("📸 Detalle Visual del Activo")
            def mostrar_visor(nombre, foto, qr):
                st.subheader(nombre)
                st.markdown("---")
                c_zoom1, c_zoom2 = st.columns(2)
                with c_zoom1:
                    st.markdown("**Fotografía Real**")
                    if foto: st.image(foto, use_container_width=True)
                    else: st.warning("Sin foto")
                with c_zoom2:
                    st.markdown("**Código QR**")
                    if qr: st.image(qr, width=250)
                    else: st.warning("Sin QR")
                st.caption("Presione 'Esc' o la 'X' para cerrar.")

            # --- 2. MÉTRICAS (ESTÁTICAS) ---
            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            col_kpi1.metric("Total Activos", len(df_act))
            col_kpi2.metric("Áreas Activas", df_act['area'].nunique())
            col_kpi3.metric("Categorías", df_act['categoria'].nunique())
            con_foto = df_act['foto_url'].notnull().sum()
            col_kpi4.metric("Con Fotografía", f"{con_foto}/{len(df_act)}")
            
            st.markdown("---")
            
            # --- 3. FILTROS ---
            st.markdown("#### 🔍 Explorador de Activos")
            c_fil1, c_fil2, c_fil3, c_fil4 = st.columns([2, 1, 1, 1])
            
            search_term = c_fil1.text_input("Buscar por nombre", placeholder="Escribe y presiona Enter...", help="Busca coincidencias.")
            area_opts = ["Todas"] + sorted(areas_data.keys())
            filtro_area = c_fil2.selectbox("Filtrar Área", area_opts)
            
            sub_opts = ["Todas"]
            if filtro_area != "Todas":
                sub_opts += sorted(areas_data[filtro_area])
            filtro_sub = c_fil3.selectbox("Filtrar Sub-área", sub_opts)
            
            cat_opts = ["Todas"] + categorias_list
            filtro_cat = c_fil4.selectbox("Filtrar Categoría", cat_opts)
            
            # --- 4. PREPARAR DATOS (FUERA DEL FRAGMENTO) ---
            df_filtered = df_act.copy()
            if search_term:
                df_filtered = df_filtered[df_filtered['nombre'].str.contains(search_term, case=False, na=False)]
            if filtro_area != "Todas":
                df_filtered = df_filtered[df_filtered['area'] == filtro_area]
            if filtro_sub != "Todas":
                df_filtered = df_filtered[df_filtered['ubicacion'].str.contains(f"\[{filtro_sub}\]", regex=True, na=False)]
            if filtro_cat != "Todas":
                df_filtered = df_filtered[df_filtered['categoria'] == filtro_cat]

            # --- 5. FRAGMENTO DE TABLA (LÓGICA CORREGIDA) ---
            @st.fragment
            def fragmento_tabla_estable(dataframe_filtrado):
                if not dataframe_filtrado.empty:
                    st.markdown(f"###### 🧬 Resultados: {len(dataframe_filtrado)}")
                    st.info("👆 **Haga clic en una fila** para ver Foto y QR.")

                    # Inicializar variable para controlar qué activo ya vimos
                    # Esto evita que la ventana se abra sola repetidamente
                    if 'last_viewed_id' not in st.session_state:
                        st.session_state.last_viewed_id = None

                    altura_tabla = (len(dataframe_filtrado) * 35) + 38
                    altura_final = min(max(altura_tabla, 100), 600)

                    # Tabla
                    event = st.dataframe(
                        dataframe_filtrado[['id', 'foto_url', 'nombre', 'categoria', 'area', 'ubicacion', 'qr_url']],
                        column_config={
                            "foto_url": st.column_config.ImageColumn("Foto", width="small"),
                            "qr_url": st.column_config.ImageColumn("QR", width="small"),
                            "id": st.column_config.NumberColumn("ID", format="%d", width="small"),
                            "nombre": st.column_config.TextColumn("Nombre", width="medium"),
                            "categoria": st.column_config.TextColumn("Categoría", width="small"),
                            "area": st.column_config.TextColumn("Área", width="small"),
                            "ubicacion": st.column_config.TextColumn("Ubicación", width="medium"),
                        },
                        use_container_width=True,
                        hide_index=True,
                        height=altura_final,
                        selection_mode="single-row",
                        on_select="rerun", # Recarga el fragmento suavemente
                        key="tabla_maestra_activos" # Key fija para estabilidad
                    )

                    # LÓGICA DE APERTURA SEGURA
                    if len(event.selection.rows) > 0:
                        idx = event.selection.rows[0]
                        sel_data = dataframe_filtrado.iloc[idx]
                        sel_id = sel_data['id']
                        
                        # SOLO abrimos la ventana si el ID seleccionado es DIFERENTE al último que vimos.
                        # Esto permite cerrar la ventana y que no se vuelva a abrir sola aunque la fila siga seleccionada.
                        if st.session_state.last_viewed_id != sel_id:
                            st.session_state.last_viewed_id = sel_id # Actualizamos el "visto"
                            mostrar_visor(sel_data['nombre'], sel_data['foto_url'], sel_data['qr_url'])
                    
                    # Si el usuario deselecciona (clic afuera), reseteamos el control para permitir re-seleccionar el mismo.
                    elif len(event.selection.rows) == 0:
                         st.session_state.last_viewed_id = None

                else:
                    if search_term or filtro_area != "Todas" or filtro_cat != "Todas":
                        st.warning(f"⚠️ No se encontraron activos con estos filtros.")

            # --- 6. EJECUTAR FRAGMENTO ---
            fragmento_tabla_estable(df_filtered)
                
        else:
            st.info("Aún no hay activos registrados para mostrar en la lista.")
    # ==============================================================================
    # 🆕 PESTAÑA 2: CREAR NUEVO (Código anterior)
    # ==============================================================================
    with tab_nuevo:
        if 'activo_creado_info' in st.session_state and st.session_state.activo_creado_info is not None:
            info = st.session_state.activo_creado_info
            
            st.markdown(f"""
                <div style="background-color: rgba(6, 78, 59, 0.5); border: 1px solid #10B981; border-radius: 10px; padding: 20px; margin-bottom: 20px;">
                    <h2 style="color: #10B981; text-align: center; margin:0;">✨ ACTIVO REGISTRADO</h2>
                    <p style="text-align: center; color: #D1FAE5;">Verifique los datos a continuación</p>
                </div>
            """, unsafe_allow_html=True)
            
            c_foto, c_datos, c_qr = st.columns([1, 1.5, 1])
            with c_foto:
                if info['foto_url']: st.image(info['foto_url'], use_container_width=True)
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
                    st.toast("✅ Proceso finalizado", icon="🎉")
                    del st.session_state['activo_creado_info']
                    st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
                    st.session_state.draft_data = {}
                    time.sleep(1)
                    st.rerun()
            with b2:
                if st.button("✏️ EDITAR (CORREGIR)", use_container_width=True):
                    supabase.table("activos").delete().eq("id", info['id']).execute()
                    st.cache_data.clear()
                    st.session_state.draft_data = info
                    if info['detalles']:
                         st.session_state.specs_data = pd.DataFrame(list(info['detalles'].items()), columns=["Componente/Dato", "Valor"])
                    del st.session_state['activo_creado_info']
                    st.rerun()
            with b3:
                if st.button("🗑️ DESHACER", type="secondary", use_container_width=True):
                    supabase.table("activos").delete().eq("id", info['id']).execute()
                    st.cache_data.clear()
                    del st.session_state['activo_creado_info']
                    st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
                    st.session_state.draft_data = {}
                    st.toast("Registro cancelado", icon="🗑️")
                    time.sleep(1)
                    st.rerun()

        else:
            st.markdown("### Registrar Nuevo Activo")
            draft = st.session_state.get('draft_data', {})
            c1, c2 = st.columns(2)
            
            def get_idx(opts, val): 
                try: return list(opts).index(val) 
                except: return 0
            
            keys_areas = sorted(areas_data.keys())
            area_principal = c1.selectbox("Área Principal", keys_areas, index=get_idx(keys_areas, draft.get('area')))
            sub_areas = sorted(areas_data[area_principal])
            
            d_sub, d_det = "", ""
            if draft.get('ubicacion'):
                parts = draft['ubicacion'].split('] ', 1)
                d_sub = parts[0].replace('[', '')
                d_det = parts[1] if len(parts) > 1 else ""
                
            sub_area = c2.selectbox("Sub-área", sub_areas, index=get_idx(sub_areas, d_sub))
            nom = c1.text_input("Nombre del Activo", value=draft.get('nombre', ''))
            ubic_detalle = c2.text_input("Ubicación Exacta / Detalle", value=d_det)
            cat = c1.selectbox("Categoría", categorias_list, index=get_idx(categorias_list, draft.get('categoria')))
            
            st.markdown("---")
            st.markdown("#### 📸 Fotografía (Obligatorio)")
            if draft.get('foto_url'):
                st.image(draft['foto_url'], width=100, caption="Foto actual (se mantendrá si no subes otra)")
            foto_archivo = st.file_uploader("Subir imagen", type=["jpg", "png", "jpeg"], key="uploader_new")
            
            st.markdown("---")
            st.markdown("#### ⚙️ Especificaciones")
            edited_df = st.data_editor(st.session_state.specs_data, num_rows="dynamic", use_container_width=True, key="editor_new")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 GUARDAR ACTIVO", type="primary", use_container_width=True):
                final_url = None
                if foto_archivo:
                    with st.spinner("Subiendo foto..."):
                        final_url = subir_imagen(foto_archivo)
                elif draft.get('foto_url'):
                    final_url = draft['foto_url']
                
                if not nom or not final_url:
                    agregar_notificacion('error', 'Nombre y Foto son obligatorios.')
                else:
                    try:
                        detalles_json = {row["Componente/Dato"]: row["Valor"] for i, row in edited_df.iterrows() if row["Componente/Dato"] and row["Valor"]}
                        ubic_final = f"[{sub_area}] {ubic_detalle}" if ubic_detalle else f"[{sub_area}]"
                        
                        res = supabase.table("activos").insert({
                            "nombre": nom, "area": area_principal, "ubicacion": ubic_final,
                            "categoria": cat, "foto_url": final_url, "detalles": detalles_json
                        }).execute()
                        
                        if res.data:
                            nid = res.data[0]['id']
                            qr = generar_qr_activo(nid, nom)
                            supabase.table("activos").update({"qr_url":qr}).eq("id", nid).execute()
                            st.cache_data.clear()
                            st.session_state.draft_data = {}
                            st.session_state.activo_creado_info = {
                                "id": nid, "nombre": nom, "area": area_principal, "ubicacion": ubic_final,
                                "categoria": cat, "foto_url": final_url, "detalles": detalles_json, "qr_url": qr
                            }
                            st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error: {e}')

    # ==============================================================================
    # ✏️ PESTAÑA 3: EDITAR / QR (Código anterior)
    # ==============================================================================
    with tab_edit:
        if not df_act.empty:
            all_assets = df_act['nombre'].values
            sel_asset = st.selectbox("🔍 Buscar Activo para Ver o Editar", all_assets)
            
            dat = df_act[df_act['nombre']==sel_asset].iloc[0]
            id_suffix = dat['id'] 
            
            st.markdown("---")
            st.subheader(f"Editando: {dat['nombre']}")
            
            c1, c2 = st.columns(2)
            current_area_idx = list(sorted(areas_data.keys())).index(dat['area']) if dat['area'] in areas_data else 0
            edit_area = c1.selectbox("Área", sorted(areas_data.keys()), index=current_area_idx, key=f"edit_area_{id_suffix}")
            
            curr_sub, curr_det = "", ""
            if dat['ubicacion']:
                parts = dat['ubicacion'].split('] ', 1)
                curr_sub = parts[0].replace('[', '')
                curr_det = parts[1] if len(parts) > 1 else ""
            
            sub_areas_edit = sorted(areas_data[edit_area])
            curr_sub_idx = sub_areas_edit.index(curr_sub) if curr_sub in sub_areas_edit else 0
            edit_sub = c2.selectbox("Sub-área", sub_areas_edit, index=curr_sub_idx, key=f"edit_sub_{id_suffix}")
            
            edit_nom = c1.text_input("Nombre", value=dat['nombre'], key=f"edit_nom_{id_suffix}")
            edit_det = c2.text_input("Ubicación Detalle", value=curr_det, key=f"edit_det_{id_suffix}")
            curr_cat_idx = categorias_list.index(dat['categoria']) if dat['categoria'] in categorias_list else 0
            edit_cat = c1.selectbox("Categoría", categorias_list, index=curr_cat_idx, key=f"edit_cat_{id_suffix}")
            
            st.markdown("---")
            col_f1, col_f2 = st.columns([1, 2])
            with col_f1:
                st.markdown("#### 🖼️ Foto Actual")
                if dat.get('foto_url'):
                    st.image(dat['foto_url'], use_container_width=True)
                else:
                    st.warning("Sin imagen")
            
            with col_f2:
                st.markdown("#### 🔄 Cambiar Foto (Opcional)")
                st.info("Si no subes nada, se mantiene la foto actual.")
                edit_foto_file = st.file_uploader("Subir nueva foto", type=["jpg", "png"], key=f"edit_uploader_{id_suffix}")
            
            st.markdown("---")
            st.markdown("#### ⚙️ Editar Especificaciones")
            
            current_specs_df = pd.DataFrame(columns=["Componente/Dato", "Valor"])
            if dat.get('detalles') and isinstance(dat['detalles'], dict):
                current_specs_df = pd.DataFrame(list(dat['detalles'].items()), columns=["Componente/Dato", "Valor"])
            
            edited_specs = st.data_editor(
                current_specs_df,
                num_rows="dynamic",
                use_container_width=True,
                column_config={
                    "Componente/Dato": st.column_config.TextColumn("Característica"),
                    "Valor": st.column_config.TextColumn("Valor")
                },
                key=f"editor_edit_{id_suffix}"
            )
            
            st.markdown("<br>", unsafe_allow_html=True)
            bc1, bc2 = st.columns([2, 1])
            with bc1:
                if st.button("💾 GUARDAR CAMBIOS", type="primary", use_container_width=True, key=f"btn_save_{id_suffix}"):
                    if not edit_nom:
                        st.toast("❌ El nombre no puede estar vacío", icon="Error")
                    else:
                        try:
                            with st.spinner("Actualizando activo..."):
                                final_edit_url = dat['foto_url']
                                if edit_foto_file:
                                    final_edit_url = subir_imagen(edit_foto_file)
                                
                                final_edit_ubic = f"[{edit_sub}] {edit_det}" if edit_det else f"[{edit_sub}]"
                                final_specs_json = {row["Componente/Dato"]: row["Valor"] for i, row in edited_specs.iterrows() if row["Componente/Dato"] and row["Valor"]}
                                
                                supabase.table("activos").update({
                                    "nombre": edit_nom, "area": edit_area, "ubicacion": final_edit_ubic,
                                    "categoria": edit_cat, "foto_url": final_edit_url, "detalles": final_specs_json
                                }).eq("id", dat['id']).execute()
                                
                                st.cache_data.clear()
                                st.toast(f"✅ Activo '{edit_nom}' actualizado correctamente", icon="💾")
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
            with bc2:
                with st.expander("🗑️ Borrar Activo"):
                    st.warning("Acción irreversible.")
                    if st.button("CONFIRMAR BORRADO", type="secondary", use_container_width=True, key=f"btn_del_{id_suffix}"):
                        try:
                            supabase.table("ordenes").delete().eq("activo_id", dat['id']).execute()
                            supabase.table("activos").delete().eq("id", dat['id']).execute()
                            st.cache_data.clear()
                            st.toast("🗑️ Activo eliminado permanentemente", icon="👋")
                            time.sleep(1.5)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al borrar: {e}")
            st.markdown("---")
            if dat.get('qr_url'):
                st.caption("Código QR del Activo")
                st.image(dat['qr_url'], width=150)
        else:
            st.info("No hay activos registrados para editar.")
elif choice == "Crear Orden":
    st.title("GENERAR ORDEN DE TRABAJO")
    mostrar_notificaciones()
    
    # Cargar datos frescos
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes_activas = run_query("ordenes", filters={"estado": "Abierta"})
    
    if not df_act.empty:
        # Crear diccionario para búsqueda rápida: "Nombre Activo" -> ID
        act_dict = dict(zip(df_act['nombre'], df_act['id']))
        lista_nombres = sorted(list(act_dict.keys()))
        
        st.markdown("<div class='card-style'>", unsafe_allow_html=True)
        st.subheader("1. Seleccionar Equipo")
        
        # Selector del activo con búsqueda
        sel_activo_nombre = st.selectbox("Buscar Activo", lista_nombres, help="Escriba para buscar...")
        id_activo_seleccionado = act_dict[sel_activo_nombre]
        
        # Recuperar datos completos del activo seleccionado
        activo_info = df_act[df_act['id'] == id_activo_seleccionado].iloc[0]
        
        # --- VISUALIZACIÓN INTELIGENTE DEL ACTIVO ---
        st.markdown("---")
        c_visual, c_datos = st.columns([1, 2])
        
        with c_visual:
            if activo_info.get('foto_url'):
                st.image(activo_info['foto_url'], caption="Referencia Visual", use_container_width=True)
            else:
                st.info("🖼️ Sin fotografía disponible")
                
        with c_datos:
            st.markdown(f"### {activo_info['nombre']}")
            st.caption(f"ID: {activo_info['id']} | Ubicación: {activo_info['ubicacion']}")
            
            # Mostrar alerta si ya tiene órdenes abiertas
            ordenes_pendientes = df_ordenes_activas[df_ordenes_activas['activo_id'] == id_activo_seleccionado]
            cantidad_pendientes = len(ordenes_pendientes)
            
            if cantidad_pendientes > 0:
                st.warning(f"⚠️ ¡ATENCIÓN! Este activo ya tiene {cantidad_pendientes} orden(es) abierta(s).")
                with st.expander("Ver órdenes pendientes"):
                    st.dataframe(ordenes_pendientes[['id', 'descripcion', 'tecnico_asignado', 'fecha_creacion']], hide_index=True)
            else:
                st.success("✅ El equipo está disponible (Sin órdenes pendientes).")

            # Mostrar especificaciones técnicas (JSON)
            detalles = activo_info.get('detalles')
            if detalles and isinstance(detalles, dict) and len(detalles) > 0:
                with st.expander("Ver Ficha Técnica"):
                    # Convertimos el JSON a tabla para que se vea bonito
                    df_detalles = pd.DataFrame(list(detalles.items()), columns=["Dato", "Valor"])
                    st.table(df_detalles)

        # --- FORMULARIO DE LA ORDEN ---
        st.markdown("---")
        st.subheader("2. Detalles del Mantenimiento")
        
        with st.form("crear_orden_form"):
            c1, c2 = st.columns(2)
            
            tipo = c1.selectbox("Tipo de Mantenimiento", ["Correctivo", "Preventivo", "Mejora", "Instalación"])
            crit = c2.select_slider("Criticidad / Urgencia", ["Baja", "Media", "Alta", "Crítica"], value="Media")
            
            desc = st.text_area("Descripción de la Falla o Trabajo a realizar", height=100, placeholder="Describa el problema detalladamente...")
            
            # Selector de Técnicos
            if not df_users.empty:
                # Muestra Nombre y Rol en la lista
                tech_options = {f"{u['nombre']} ({u['rol']})": u['id'] for _, u in df_users.iterrows()}
                tech_list = ["-- Seleccionar Técnico --"] + list(tech_options.keys())
                
                sel_tech = st.selectbox("Asignar a:", tech_list)
            else:
                st.error("No hay usuarios registrados para asignar.")
                sel_tech = "-- Seleccionar Técnico --"

            st.markdown("<br>", unsafe_allow_html=True)
            btn_crear = st.form_submit_button("🚀 GENERAR ORDEN DE TRABAJO", type="primary", use_container_width=True)
            
            if btn_crear:
                # Validaciones
                if sel_tech == "-- Seleccionar Técnico --":
                    agregar_notificacion('error', 'Debe asignar un técnico responsable.')
                elif not desc.strip():
                    agregar_notificacion('error', 'La descripción es obligatoria.')
                else:
                    try:
                        tecnico_id = tech_options[sel_tech]
                        
                        # Insertar orden
                        new_ot = {
                            "activo_id": int(id_activo_seleccionado),
                            "descripcion": desc,
                            "criticidad": crit,
                            "tipo_mantenimiento": tipo,
                            "estado": "Abierta",
                            "tecnico_asignado": str(tecnico_id),
                            "fecha_creacion": datetime.now().isoformat()
                        }
                        
                        res = supabase.table("ordenes").insert(new_ot).execute()
                        
                        if res.data:
                            new_id = res.data[0]['id']
                            st.cache_data.clear()
                            agregar_notificacion('success', f'Orden OT-{new_id} creada exitosamente para {sel_activo_nombre}.')
                            time.sleep(1)
                            st.rerun()
                    except Exception as e:
                        agregar_notificacion('error', f'Error al crear la orden: {e}')

        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.warning("⚠️ No hay activos registrados. Vaya a 'Inventario' para crear uno primero.")

elif choice == "Gestionar Órdenes":
    st.title("GESTIONAR ÓRDENES DE TRABAJO")
    mostrar_notificaciones()
    
    df_ordenes = run_query("ordenes")
    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    
    if not df_ordenes.empty:
        
        # Filtros en la parte superior
        st.markdown("### 🔍 Filtros")
        col_f1, col_f2, col_f3 = st.columns(3)
        
        with col_f1:
            filter_estado = st.selectbox(
                "Estado:",
                ["Todas", "Abierta", "Concluida"],
                key="filter_estado"
            )
        
        with col_f2:
            filter_criticidad = st.selectbox(
                "Criticidad:",
                ["Todas", "Baja", "Media", "Alta", "Crítica"],
                key="filter_criticidad"
            )
        
        with col_f3:
            filter_tipo = st.selectbox(
                "Tipo:",
                ["Todos", "Correctivo", "Preventivo"],
                key="filter_tipo"
            )
        
        # Aplicar filtros
        df_filtered = df_ordenes.copy()
        
        if filter_estado != "Todas":
            df_filtered = df_filtered[df_filtered['estado'] == filter_estado]
        
        if filter_criticidad != "Todas":
            df_filtered = df_filtered[df_filtered['criticidad'] == filter_criticidad]
        
        if filter_tipo != "Todos":
            df_filtered = df_filtered[df_filtered['tipo_mantenimiento'] == filter_tipo]
        
        # Mostrar tabla con las órdenes filtradas
        st.markdown("---")
        st.markdown(f"### 📋 Órdenes Encontradas: **{len(df_filtered)}**")
        
        if not df_filtered.empty:
            # Crear DataFrame mejorado con información de activo y técnico
            df_display = df_filtered.copy()
            
            # Mapear nombres de activos
            if not df_activos.empty:
                activo_map = dict(zip(df_activos['id'], df_activos['nombre']))
                df_display['activo_nombre'] = df_display['activo_id'].map(activo_map)
            
            # Mapear nombres de técnicos - ACTUALIZADO PARA USAR DATOS EN TIEMPO REAL
            if not df_users.empty:
                user_map = dict(zip(df_users['id'].astype(str), df_users['nombre']))
                df_display['tecnico_nombre'] = df_display['tecnico_asignado'].astype(str).map(user_map).fillna('Sin asignar')
            
            # Mostrar tabla con clave única para forzar actualización
            st.dataframe(
                df_display[['id', 'activo_nombre', 'tipo_mantenimiento', 'criticidad', 
                           'estado', 'tecnico_nombre', 'fecha_creacion']].rename(columns={
                    'id': 'ID',
                    'activo_nombre': 'Activo',
                    'tipo_mantenimiento': 'Tipo',
                    'criticidad': 'Criticidad',
                    'estado': 'Estado',
                    'tecnico_nombre': 'Asignado a',
                    'fecha_creacion': 'Fecha Creación'
                }),
                hide_index=True,
                use_container_width=True,
                key=f"tabla_ordenes_{datetime.now().timestamp()}"  # Clave única para forzar actualización
            )
            
            # Selector de orden para editar
            st.markdown("---")
            st.markdown("### ✏️ Editar / Reasignar Orden")
            
            # Crear opciones para el selectbox
            orden_options = {
                f"OT-{row['id']} | {activo_map.get(row['activo_id'], 'N/A')} | {row['estado']}": row['id']
                for _, row in df_filtered.iterrows()
            }
            
            orden_options_list = ["-- Seleccione una orden --"] + list(orden_options.keys())
            
            selected_orden_option = st.selectbox(
                "Orden de Trabajo:",
                orden_options_list,
                key="orden_selector"
            )
            
            if selected_orden_option != "-- Seleccione una orden --":
                orden_id = orden_options[selected_orden_option]
                orden_actual = df_ordenes[df_ordenes['id'] == orden_id].iloc[0]
                
                st.markdown(f"""
                    <div class='card-style' style='border-left: 4px solid {PRO_ORANGE}; background: rgba(245, 158, 11, 0.05);'>
                        <p><strong>📌 Orden Seleccionada:</strong> OT-{orden_actual['id']}</p>
                        <p><strong>🔧 Activo:</strong> {activo_map.get(orden_actual['activo_id'], 'N/A')}</p>
                        <p><strong>📅 Creada:</strong> {orden_actual['fecha_creacion']}</p>
                    </div>
                """, unsafe_allow_html=True)
                
                # Formulario de edición
                with st.form(key=f"edit_orden_form_{orden_id}"):
                    st.markdown("#### Información de la Orden")
                    
                    col1, col2 = st.columns(2)
                    
                    # Campo Activo
                    activo_actual = activo_map.get(orden_actual['activo_id'], 'N/A')
                    activo_index = list(df_activos['nombre']).index(activo_actual) if activo_actual in df_activos['nombre'].values else 0
                    nuevo_activo = col1.selectbox(
                        "Activo",
                        df_activos['nombre'].values,
                        index=activo_index
                    )
                    
                    # Campo Tipo
                    tipo_options = ["Correctivo", "Preventivo"]
                    tipo_index = tipo_options.index(orden_actual['tipo_mantenimiento']) if orden_actual['tipo_mantenimiento'] in tipo_options else 0
                    nuevo_tipo = col2.selectbox(
                        "Tipo de Mantenimiento",
                        tipo_options,
                        index=tipo_index
                    )
                    
                    # Campo Criticidad
                    crit_options = ["Baja", "Media", "Alta", "Crítica"]
                    crit_index = crit_options.index(orden_actual['criticidad']) if orden_actual['criticidad'] in crit_options else 0
                    nueva_crit = col1.select_slider(
                        "Criticidad",
                        crit_options,
                        value=crit_options[crit_index]
                    )
                    
                    # Campo Estado
                    estado_options = ["Abierta", "Concluida"]
                    estado_index = estado_options.index(orden_actual['estado']) if orden_actual['estado'] in estado_options else 0
                    nuevo_estado = col2.selectbox(
                        "Estado",
                        estado_options,
                        index=estado_index
                    )
                    
                    # Campo Descripción
                    nueva_desc = st.text_area(
                        "Descripción",
                        value=orden_actual.get('descripcion', ''),
                        height=100
                    )
                    
                    # Campo Reasignar Técnico
                    st.markdown("#### 👤 Reasignación de Técnico")
                    
                    if not df_users.empty:
                        user_options = {
                            f"{row['nombre']} - {row['rol']}": str(row['id'])
                            for _, row in df_users.iterrows()
                        }
                        
                        # Encontrar el índice del técnico actual
                        tecnico_actual_id = str(orden_actual.get('tecnico_asignado', ''))
                        tecnico_actual_nombre = user_map.get(tecnico_actual_id, 'Sin asignar')
                        
                        # Buscar la opción que corresponde al técnico actual
                        current_tech_option = None
                        for option, uid in user_options.items():
                            if uid == tecnico_actual_id:
                                current_tech_option = option
                                break
                        
                        user_options_list = list(user_options.keys())
                        current_index = user_options_list.index(current_tech_option) if current_tech_option else 0
                        
                        nuevo_tecnico_option = st.selectbox(
                            "Asignar a:",
                            user_options_list,
                            index=current_index,
                            help=f"Actualmente asignado a: {tecnico_actual_nombre}"
                        )
                        
                        nuevo_tecnico_id = user_options[nuevo_tecnico_option]
                    else:
                        st.warning("No hay usuarios disponibles")
                        nuevo_tecnico_id = tecnico_actual_id
                    
                    # Comentarios adicionales
                    comentarios = st.text_area(
                        "Comentarios de cierre (Opcional)",
                        value=orden_actual.get('comentarios_cierre', ''),
                        height=80
                    )
                    
                    # Botones de acción
                    st.markdown("<br>", unsafe_allow_html=True)
                    col_btn1, col_btn2 = st.columns(2)
                    
                    with col_btn1:
                        actualizar_btn = st.form_submit_button(
                            "✅ ACTUALIZAR ORDEN",
                            type="primary",
                            use_container_width=True
                        )
                    
                    with col_btn2:
                        cancelar_btn = st.form_submit_button(
                            "🗑️ ELIMINAR ORDEN",
                            type="secondary",
                            use_container_width=True
                        )
                    
                    # PROCESAR ACTUALIZACIÓN
                    if actualizar_btn:
                        try:
                            # Obtener el ID del activo seleccionado
                            nuevo_activo_id = int(df_activos[df_activos['nombre'] == nuevo_activo].iloc[0]['id'])
                            
                            # Preparar los datos actualizados con conversión explícita
                            update_data = {
                                "activo_id": nuevo_activo_id,
                                "tipo_mantenimiento": str(nuevo_tipo),
                                "criticidad": str(nueva_crit),
                                "estado": str(nuevo_estado),
                                "descripcion": str(nueva_desc),
                                "tecnico_asignado": str(nuevo_tecnico_id),
                                "comentarios_cierre": str(comentarios) if comentarios else None
                            }
                            
                            # Validar datos requeridos
                            if not update_data["descripcion"].strip():
                                agregar_notificacion('error', 'La descripción no puede estar vacía.')
                            else:
                                # Ejecutar actualización
                                supabase.table("ordenes").update(update_data).eq("id", int(orden_id)).execute()
                                
                                # LIMPIAR CACHE Y ACTUALIZAR INMEDIATAMENTE
                                st.cache_data.clear()
                                agregar_notificacion('success', f'Orden OT-{orden_id} actualizada correctamente.')
                                st.rerun()
                                
                        except Exception as e:
                            agregar_notificacion('error', f'Error al actualizar la orden: {str(e)}')
                    
                    # PROCESAR ELIMINACIÓN
                    if cancelar_btn:
                        try:
                            # Confirmación adicional para eliminar
                            st.warning(f"⚠️ Está a punto de eliminar permanentemente la orden OT-{orden_id}")
                            confirmar = st.checkbox("Confirmar eliminación")
                            
                            if confirmar:
                                supabase.table("ordenes").delete().eq("id", int(orden_id)).execute()
                                
                                # LIMPIAR CACHE Y FORZAR ACTUALIZACIÓN
                                st.cache_data.clear()
                                agregar_notificacion('delete', f'Orden OT-{orden_id} eliminada permanentemente.')
                                st.rerun()
                                
                        except Exception as e:
                            agregar_notificacion('error', f'Error al eliminar la orden: {str(e)}')
        
        else:
            st.info("No se encontraron órdenes con los filtros seleccionados.")
    
    else:
        st.info("📭 No hay órdenes de trabajo registradas en el sistema.")
        
elif choice == "Cerrar Orden":
    st.title("CERRAR ORDEN")
    mostrar_notificaciones()
    
    df_ot = run_query("ordenes")
        
    if not df_ot.empty:
        my_ots = df_ot[(df_ot['estado']!='Concluida')]
        if not my_ots.empty:
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            st.dataframe(my_ots[['id','descripcion','criticidad']], use_container_width=True)
            sid = st.selectbox("ID Orden", my_ots['id'].values)
            with st.form("close"):
                rep = st.text_area("Reporte Técnico")
                img = st.file_uploader("Foto")
                if st.form_submit_button("FINALIZAR"):
                    url = subir_imagen(img)
                    supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre":rep, "evidencia_url":url}).eq("id",sid).execute()
                    st.cache_data.clear()
                    agregar_notificacion('success', 'Orden cerrada exitosamente.')
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else: 
            st.info("No hay órdenes pendientes para cerrar.")

elif choice == "Usuarios":
    st.title("USUARIOS")
    mostrar_notificaciones()

    tab_crear, tab_gestionar = st.tabs(["CREAR USUARIO", "GESTIONAR USUARIOS"])

    with tab_crear:
        st.subheader("Registrar Nuevo Usuario")

        with st.form("new_user_form"):
            c1, c2 = st.columns(2)
            documento = c1.text_input("Documento/ID", key="new_user_doc")
            nombre = c2.text_input("Nombre Completo", key="new_user_name")
            password = c1.text_input("Contraseña", type="password", key="new_user_pass")
            rol = c2.selectbox("Rol", ["Tecnico", "Programador", "Admin"], key="new_user_rol")

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
                                "nombre": nombre, 
                                "password": password, 
                                "rol": rol
                            }).execute()

                            if res.data:
                                st.cache_data.clear()
                                agregar_notificacion('success', f'Usuario {nombre} registrado con éxito.')
                                st.rerun()
                            else:
                                agregar_notificacion('error', 'Error al registrar el usuario en la base de datos.')
                        except Exception as e:
                            agregar_notificacion('error', f'Error de base de datos: {e}')
                else:
                    agregar_notificacion('warning', 'Por favor, complete todos los campos.')

    with tab_gestionar:
        df_users = run_query("usuarios")

        if not df_users.empty:
            st.subheader("Seleccionar Usuario para Gestionar")

            user_options = {f"{row['nombre']} (ID: {row['id']})": row['id'] 
                           for _, row in df_users.iterrows()}
            
            user_options_list = ["-- Seleccione un usuario --"] + list(user_options.keys())
            
            selected_option = st.selectbox(
                "Usuario:",
                user_options_list,
                key="user_selector"
            )

            st.markdown("### Lista Completa de Usuarios")
            st.dataframe(
                df_users[['id', 'documento', 'nombre', 'rol']],
                hide_index=True,
                use_container_width=True
            )

            if selected_option != "-- Seleccione un usuario --":
                user_id = user_options[selected_option]
                selected_user = df_users[df_users['id'] == user_id].iloc[0]

                st.markdown("---")
                st.markdown(f"### Editando: **{selected_user['nombre']}** (ID: {user_id})")

                with st.form(key=f"edit_user_form_{user_id}"):
                    st.subheader("Información del Usuario")

                    c1, c2 = st.columns(2)

                    edit_doc = c1.text_input(
                        "Documento/ID", 
                        value=selected_user['documento']
                    )
                    edit_name = c2.text_input(
                        "Nombre Completo", 
                        value=selected_user['nombre']
                    )

                    rol_options = ["Tecnico", "Programador", "Admin"]
                    current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                    new_rol = st.selectbox("Rol", rol_options, index=current_rol_index)

                    new_password = st.text_input(
                        "Nueva Contraseña (Dejar vacío para no cambiar)", 
                        type="password"
                    )

                    st.markdown("<br>", unsafe_allow_html=True)
                    update_submitted = st.form_submit_button("✅ ACTUALIZAR USUARIO", type="primary", use_container_width=True)

                    if update_submitted:
                        if new_rol != selected_user['rol']:
                            if check_open_orders(user_id):
                                agregar_notificacion('error', f'El usuario **{selected_user["nombre"]}** tiene Órdenes de Trabajo pendientes. Debe cerrarlas antes de cambiar su rol.')
                                st.stop()

                        if not validar_usuario_unico(edit_doc, user_id):
                            agregar_notificacion('error', 'El documento ya está en uso por otro usuario.')
                        else:
                            update_data = {
                                "documento": edit_doc,
                                "nombre": edit_name,
                                "rol": new_rol
                            }
                            if new_password:
                                if len(new_password) < 4:
                                    agregar_notificacion('error', 'La contraseña debe tener al menos 4 caracteres.')
                                else:
                                    update_data["password"] = new_password

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
                        <div style='background: rgba(239, 68, 68, 0.15); 
                                    border: 2px solid #EF4444; 
                                    border-radius: 8px; 
                                    padding: 20px; 
                                    text-align: center;'>
                            <p style='color: #FCA5A5; margin: 0; font-size: 1.1rem;'>
                                ⚠️ <strong>ELIMINACIÓN BLOQUEADA</strong>
                            </p>
                            <p style='color: #FEE2E2; margin-top: 10px; font-size: 0.95rem;'>
                                El usuario <strong>{selected_user['nombre']}</strong> tiene Órdenes de Trabajo pendientes.<br>
                                Debe cerrarlas o reasignarlas antes de eliminar este usuario.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ Esta acción eliminará permanentemente al usuario **{selected_user['nombre']}**")
                    
                    if st.button(
                        "🗑️ ELIMINAR USUARIO PERMANENTEMENTE",
                        type="secondary",
                        use_container_width=True,
                        key=f"delete_btn_{user_id}"
                    ):
                        try:
                            supabase.table("usuarios").delete().eq("id", user_id).execute()
                            st.cache_data.clear()
                            agregar_notificacion('delete', f'Usuario {selected_user["nombre"]} eliminado.')
                            st.rerun()
                        except Exception as e:
                            agregar_notificacion('error', f'Error al eliminar: {e}')

        else:
            st.info("No se encontraron usuarios en la base de datos. Use la pestaña 'CREAR USUARIO'.")
