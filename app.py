# ==============================================================================
# PROYECTO: ORIÓN - Mantenimiento Inteligente
# AUTOR: [JHON ESTEBN PENAGOS]
# VERSIÓN: INTEGRACIÓN CLOUDINARY + ORIÓN UI (CORREGIDO)
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
import plotly.express as px
import plotly.graph_objects as go
from fpdf import FPDF
import tempfile

# --- NUEVOS IMPORTS PARA CLOUDINARY ---
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Orión | Mantenimiento", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# ☁️ CONFIGURACIÓN DE CLOUDINARY
# ==============================================================================
try:
    cloudinary.config(
        cloud_name = st.secrets["cloudinary"]["cloud_name"],
        api_key = st.secrets["cloudinary"]["api_key"],
        api_secret = st.secrets["cloudinary"]["api_secret"],
        secure = True
    )
except KeyError:
    st.warning("⚠️ ADVERTENCIA: No se encontraron las credenciales de Cloudinary en secrets.toml. La subida de imágenes fallará.")
except Exception as e:
    st.error(f"Error configurando Cloudinary: {e}")
# ==============================================================================
# 🎨 TEMA: "ORIÓN COMFORT UI" (SOLUCIÓN FINAL POR UBICACIÓN)
# ==============================================================================

PRO_ORANGE = "#F59E0B" 
PRO_GREEN = "#10B981"  
BG_DARK_CLEAN = "#0e1117"  
BG_SIDEBAR = "#161b22"     
BG_CARD = "rgba(30, 41, 59, 0.7)" 
TEXT_WHITE = "#E5E7EB"     

st.markdown(f"""
    <style>
    /* =========================================
       1. ESTILOS GENERALES
       ========================================= */
    .stApp {{
        background-color: {BG_DARK_CLEAN};
        color: {TEXT_WHITE};
    }}

    /* =========================================
       2. BARRA LATERAL (SIDEBAR)
       ========================================= */
    [data-testid="stSidebar"] {{
        background-color: {BG_SIDEBAR};
        border-right: 1px solid #30363d;
    }}
    
    /* A) TEXTO DEL MENÚ DE NAVEGACIÓN -> BLANCO (Como te gustó) */
    [data-testid="stSidebarNav"] span {{
        color: #E5E7EB !important;
        font-weight: 500;
    }}
    
    /* Elemento seleccionado en el menú */
    [data-testid="stSidebarNav"] a[aria-current="page"] {{
        background-color: rgba(245, 158, 11, 0.1);
        border-left: 3px solid {PRO_ORANGE};
    }}

    /* B) BOTÓN 'SALIR' (Solo los botones secundarios DENTRO del Sidebar) */
    section[data-testid="stSidebar"] button[kind="secondary"] {{
        background-color: transparent !important;
        border: 1px solid #fca5a5 !important;
    }}
    
    /* Texto del botón Salir -> ROSA */
    section[data-testid="stSidebar"] button[kind="secondary"] p {{
        color: #fca5a5 !important;
    }}

    /* Hover del botón Salir */
    section[data-testid="stSidebar"] button[kind="secondary"]:hover {{
        background-color: rgba(239, 68, 68, 0.15) !important;
    }}

    /* =========================================
       3. ÁREA PRINCIPAL (MAIN)
       ========================================= */
    
    /* C) BOTÓN 'RECHAZAR' / 'ELIMINAR' (Cualquier botón secundario en el centro) */
    section[data-testid="stMain"] button[kind="secondary"] {{
        background-color: #fca5a5 !important; /* FONDO ROSADO SÓLIDO */
        border: 1px solid #ef4444 !important;
        transition: transform 0.1s;
    }}

    /* Texto del botón Rechazar -> NEGRO (Forzado con fuerza bruta) */
    section[data-testid="stMain"] button[kind="secondary"] * {{
        color: #000000 !important; /* NEGRO PURO */
        font-weight: 800 !important; /* NEGRITA */
    }}
    
    /* Aseguramos que el párrafo interno también sea negro */
    section[data-testid="stMain"] button[kind="secondary"] p {{
        color: #000000 !important;
    }}

    /* Hover del botón Rechazar */
    section[data-testid="stMain"] button[kind="secondary"]:hover {{
        background-color: #f87171 !important; /* Rojo un poco más intenso */
        transform: scale(1.02);
        border-color: #b91c1c !important;
    }}

    /* =========================================
       4. RESTO DE ESTILOS (Títulos, Inputs, etc)
       ========================================= */
    h1, h2, h3 {{
        background: linear-gradient(90deg, {PRO_ORANGE}, {PRO_GREEN});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        text-transform: uppercase;
    }}

    .card-style {{
        background: {BG_CARD};
        backdrop-filter: blur(12px);
        border-radius: 12px;
        padding: 25px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.2);
        margin-bottom: 20px;
    }}

    .chart-header {{
        font-size: 1.1rem;
        font-weight: 700;
        color: {PRO_ORANGE};
        margin-bottom: 15px;
        border-bottom: 1px solid #30363d;
        padding-bottom: 8px;
        display: block;
    }}

    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
        background-color: #0d1117 !important; 
        color: #e6edf3 !important;
        border: 1px solid #30363d !important;
        border-radius: 6px;
    }}
    
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {PRO_ORANGE} !important;
        box-shadow: 0 0 0 1px {PRO_ORANGE} !important;
    }}
    
    .stTextInput label, .stSelectbox label, .stTextArea label {{
        color: #E5E7EB !important;
        font-weight: 600 !important;
    }}

    div.stButton > button:first-child {{
        background: linear-gradient(90deg, {PRO_ORANGE} 0%, {PRO_GREEN} 100%) !important;
        color: white !important;
        border: none;
        font-weight: 600;
        border-radius: 6px;
    }}
    div.stButton > button:first-child:hover {{
        transform: translateY(-2px);
        opacity: 0.9;
    }}

    [data-testid="stMetric"] {{
        background: rgba(30, 41, 59, 0.5);
        border-left: 4px solid {PRO_GREEN};
        border-radius: 8px;
        padding: 15px;
    }}
    [data-testid="stMetricLabel"] {{ color: #9CA3AF !important; }}
    [data-testid="stMetricValue"] {{ color: #F3F4F6 !important; }}

    .stTabs [data-baseweb="tab"] {{ color: #9CA3AF; font-weight: 600; }}
    .stTabs [aria-selected="true"] {{ color: {PRO_ORANGE} !important; background-color: transparent !important; border-bottom-color: {PRO_ORANGE} !important; }}

    div[data-testid="stVerticalBlock"] > div:empty {{ height: 0 !important; margin: 0 !important; }}
    [data-testid="stSidebarNav"] {{ padding-top: 10px !important; }}
    
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
# ==============================================================================
# 🔔 SISTEMA DE NOTIFICACIONES (FALTABA ESTO)
# ==============================================================================
def agregar_notificacion(tipo, mensaje):
    """Guarda una notificación en el estado de la sesión"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    st.session_state.notifications.append({'type': tipo, 'message': mensaje})

def mostrar_notificaciones():
    """Muestra y limpia las notificaciones pendientes"""
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    
    # Copiamos la lista para iterar y luego la limpiamos
    for notif in st.session_state.notifications[:]:
        if notif['type'] == 'success':
            st.success(f"✅ {notif['message']}")
        elif notif['type'] == 'error':
            st.error(f"❌ {notif['message']}")
        elif notif['type'] == 'warning':
            st.warning(f"⚠️ {notif['message']}")
        elif notif['type'] == 'delete':
            st.error(f"🗑️ {notif['message']}") # Usamos rojo de error para borrado
            
    # Limpiar notificaciones ya mostradas
    st.session_state.notifications = []
    
# --- 3. FUNCIONES AUXILIARES MEJORADAS ---

def subir_archivo_generico(archivo):
    """
    Sube archivos forzando acceso PÚBLICO para evitar el error 401.
    """
    if archivo:
        try:
            nombre_original = archivo.name.lower()
            
            # 1. Detectar si es Imagen (Para visor) o Documento (Para descarga)
            ext_imagenes = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
            es_imagen_visual = nombre_original.endswith(ext_imagenes)
            
            if es_imagen_visual:
                tipo_recurso = "image"
                carpeta = "orion_evidencias"
                public_id_manual = None 
                use_unique = True
            else:
                # 2. DOCUMENTOS (PDF, MSG, DOCX) - MODO RAW
                tipo_recurso = "raw"
                carpeta = "orion_documentos"
                
                # Limpieza de nombre
                nombre_base, extension = os.path.splitext(archivo.name)
                # Quitamos caracteres raros y espacios
                nombre_limpio = "".join(c for c in nombre_base if c.isalnum() or c in ('_', '-')).strip()
                timestamp = int(time.time())
                
                # Forzamos nombre único manual
                public_id_manual = f"{nombre_limpio}_{timestamp}{extension}"
                use_unique = False 

            # 3. Subir con permisos EXPLÍCITOS
            respuesta = cloudinary.uploader.upload(
                archivo.getvalue(),
                folder=carpeta,
                resource_type=tipo_recurso,
                public_id=public_id_manual,
                use_filename=True,
                unique_filename=use_unique,
                
                # --- ESTAS DOS LÍNEAS SOLUCIONAN EL 401 EN CÓDIGO ---
                type="upload",        # Tipo 'upload' significa PÚBLICO (vs 'private' o 'authenticated')
                access_mode="public"  # Refuerzo para asegurar que sea accesible
                # ---------------------------------------------------
            )
            return respuesta.get("secure_url")
        except Exception as e:
            st.error(f"Error subiendo archivo: {e}")
            return None
    return None

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

# 🔥 FUNCIÓN MODIFICADA PARA CLOUDINARY 🔥
def subir_imagen(archivo, carpeta="orion_evidencias"):
    """
    Sube imágenes a Cloudinary con optimización automática.
    Retorna la URL segura (https).
    Reemplaza la lógica anterior de Supabase Storage.
    """
    if archivo:
        try:
            # 1. Preparar el archivo (Bytes o UploadedFile)
            file_to_upload = archivo
            
            # Si es bytes (QR generado por código)
            if isinstance(archivo, bytes):
                file_to_upload = archivo
            # Si es un UploadedFile de Streamlit
            elif hasattr(archivo, 'getvalue'):
                file_to_upload = archivo.getvalue()
            
            # 2. Subir a Cloudinary
            # Usamos transformaciones para que la imagen no pese tanto (ahorro de datos)
            respuesta = cloudinary.uploader.upload(
                file_to_upload,
                folder=carpeta,
                resource_type="image",
                transformation=[
                    {'width': 1000, 'crop': "limit"}, # Limitar ancho a 1000px
                    {'quality': "auto"},              # Calidad automática
                    {'fetch_format': "auto"}          # Formato moderno (WebP/AVIF)
                ]
            )
            
            # 3. Retornar la URL segura
            return respuesta.get("secure_url")
            
        except Exception as e:
            # Imprimimos el error en consola para depuración
            print(f"Error Cloudinary: {e}")
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
    img_byte_arr = img_byte_arr.getvalue()
    # Usamos la carpeta específica para QRs
    return subir_imagen(img_byte_arr, "orion_codigos_qr")

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
# ==============================================================================
# 🛡️ FUNCIONES DE VALIDACIÓN DE USUARIOS (FALTABAN ESTAS)
# ==============================================================================

def validar_usuario_unico(nuevo_documento, id_ignorar=None):
    """
    Verifica si el documento ya existe en la base de datos.
    Si id_ignorar se pasa (al editar), permite que el documento sea el mismo del usuario actual.
    Retorna True si es único (válido), False si ya existe (inválido).
    """
    try:
        # Buscamos si existe alguien con ese documento
        res = supabase.table("usuarios").select("*").eq("documento", nuevo_documento).execute()
        
        if res.data:
            usuario_existente = res.data[0]
            # Si estamos editando y el ID encontrado es el mismo que estamos editando, todo bien.
            if id_ignorar and str(usuario_existente['id']) == str(id_ignorar):
                return True
            
            # Si encontramos a alguien y no somos nosotros mismos, es un duplicado.
            return False
            
        # Si no hay datos, el documento está libre.
        return True
    except Exception as e:
        st.error(f"Error validando usuario: {e}")
        return False

def check_open_orders(user_id):
    """
    Revisa si un usuario (técnico) tiene órdenes pendientes (Abierta o Por Validar).
    Retorna True si tiene pendientes (Bloquea borrado), False si está libre.
    """
    try:
        # Buscamos órdenes activas asignadas a este ID
        res = supabase.table("ordenes").select("id")\
            .eq("tecnico_asignado", user_id)\
            .in_("estado", ["Abierta", "Por Validar"])\
            .execute()
            
        if res.data and len(res.data) > 0:
            return True # Tiene órdenes pendientes
        return False # Está libre
    except Exception as e:
        print(f"Error checking orders: {e}")
        return False

# ==========================================
# 🔔 FUNCIÓN CORREGIDA (SOLO 1 ENVÍO)
# ==========================================
def notificar_telegram(chat_id, mensaje, foto_url=None):
    """Envía notificaciones a Telegram (Versión Limpia)"""

# --- 🖨️ GENERADOR DE REPORTES PDF ---
class PDFReport(FPDF):
    def header(self):
        # Título
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, 'REPORTE DE SERVICIO TÉCNICO', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, 'Sistema de Mantenimiento Orión', 0, 1, 'C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
        
# --- FUNCIÓN NUEVA: GENERAR HOJA DE VIDA (HISTORIAL) ---
def generar_hoja_vida_pdf(activo, lista_ordenes, df_users):
    """Genera un reporte histórico completo del activo antes de borrarlo"""
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # 1. ENCABEZADO
    pdf.set_fill_color(245, 158, 11) # Naranja
    pdf.set_text_color(255, 255, 255)
    pdf.set_font('Arial', 'B', 14)
    pdf.cell(0, 10, f"HOJA DE VIDA: {activo['nombre']}".encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'C', fill=True)
    pdf.ln(5)
    
    # 2. DATOS DEL EQUIPO
    pdf.set_text_color(0, 0, 0)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 6, "Ubicacion:", 0, 0)
    pdf.set_font('Arial', '', 10); pdf.cell(0, 6, f"{activo['area']} - {activo['ubicacion']}".encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.set_font('Arial', 'B', 10); pdf.cell(40, 6, "Categoria:", 0, 0)
    pdf.set_font('Arial', '', 10); pdf.cell(0, 6, f"{activo['categoria']}".encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    pdf.ln(5)
    
    # 3. LISTADO DE MANTENIMIENTOS
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font('Arial', 'B', 10)
    pdf.cell(0, 8, f"HISTORIAL ({len(lista_ordenes)} Registros)", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    # Mapa de usuarios para saber nombres
    user_map = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}

    for orden in lista_ordenes:
        # Fecha y Estado
        fecha = orden['fecha_creacion'][:10]
        tecnico = user_map.get(str(orden['tecnico_asignado']), "N/A")
        
        pdf.set_font('Arial', 'B', 9)
        pdf.cell(30, 5, f"{fecha}", 0, 0)
        pdf.set_text_color(0, 128, 0) # Verde
        pdf.cell(30, 5, f"OT #{orden['id']}", 0, 0)
        pdf.set_text_color(0,0,0)
        pdf.set_font('Arial', 'I', 8)
        pdf.cell(0, 5, f"Tec: {tecnico}".encode('latin-1', 'replace').decode('latin-1'), 0, 1, 'R')
        
        # Falla y Solución
        pdf.set_font('Arial', '', 9)
        pdf.multi_cell(0, 5, f"Falla: {orden['descripcion']}".encode('latin-1', 'replace').decode('latin-1'))
        if orden.get('comentarios_cierre'):
            pdf.set_font('Arial', 'I', 8)
            pdf.multi_cell(0, 5, f"Solucion: {orden['comentarios_cierre']}".encode('latin-1', 'replace').decode('latin-1'))
        
        pdf.line(10, pdf.get_y(), 200, pdf.get_y()) # Línea separadora
        pdf.ln(2)

    return pdf.output(dest='S').encode('latin-1') # <--- AQUÍ ESTABA EL ERROR (Faltaba paréntesis de cierre)

# --- FUNCIÓN ORIGINAL (YA EXISTENTE) ---
def generar_pdf_orden(orden, activo_nombre, tecnico_nombre):
    """Genera un PDF con los detalles de la orden y las fotos"""
    pdf = PDFReport()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # --- 1. INFORMACIÓN GENERAL ---
    pdf.set_fill_color(240, 240, 240) # Gris claro
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, f"Orden de Trabajo #{orden['id']}", 0, 1, 'L', fill=True)
    pdf.ln(2)
    
    pdf.set_font('Arial', '', 10)
    # Fila 1
    pdf.cell(50, 8, "Fecha Creación:", 0, 0, 'B')
    pdf.cell(50, 8, f"{orden['fecha_creacion'][:10]}", 0, 0)
    pdf.cell(40, 8, "Estado Final:", 0, 0, 'B')
    pdf.set_text_color(0, 128, 0) # Verde
    pdf.cell(50, 8, f"{orden['estado']}", 0, 1)
    pdf.set_text_color(0, 0, 0) # Negro
    
    # Fila 2
    pdf.cell(50, 8, "Activo:", 0, 0, 'B')
    # encode/decode para evitar errores de tildes en FPDF básico
    pdf.cell(50, 8, f"{activo_nombre}".encode('latin-1', 'replace').decode('latin-1'), 0, 0)
    pdf.cell(40, 8, "Técnico:", 0, 0, 'B')
    pdf.cell(50, 8, f"{tecnico_nombre}".encode('latin-1', 'replace').decode('latin-1'), 0, 1)
    
    # Fila 3
    pdf.cell(50, 8, "Tipo:", 0, 0, 'B')
    pdf.cell(50, 8, f"{orden.get('tipo_mantenimiento', 'N/A')}", 0, 0)
    pdf.cell(40, 8, "Criticidad:", 0, 0, 'B')
    pdf.cell(50, 8, f"{orden['criticidad']}", 0, 1)
    pdf.ln(5)

    # --- 2. DETALLE DEL PROBLEMA ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "1. Reporte de Falla / Solicitud", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10)
    pdf.multi_cell(0, 6, f"{orden['descripcion']}".encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)

    # --- 3. SOLUCIÓN TÉCNICA ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "2. Informe de Reparación", 0, 1, 'L', fill=True)
    pdf.set_font('Arial', '', 10)
    reporte = orden.get('comentarios_cierre') or "Sin reporte registrado."
    pdf.multi_cell(0, 6, f"{reporte}".encode('latin-1', 'replace').decode('latin-1'))
    pdf.ln(5)

    # --- 4. EVIDENCIA FOTOGRÁFICA ---
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 10, "3. Evidencia Fotográfica", 0, 1, 'L', fill=True)
    pdf.ln(2)

    y_pos = pdf.get_y()
    
    # Función interna para descargar y poner imagen
    def poner_imagen_desde_url(url, x, y, w, titulo):
        try:
            if url:
                response = requests.get(url)
                if response.status_code == 200:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(response.content)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=x, y=y, w=w)
                    pdf.set_xy(x, y + 45) # Bajamos para el título
                    pdf.set_font('Arial', 'I', 8)
                    pdf.cell(w, 5, titulo, 0, 0, 'C')
                    os.remove(tmp_path) # Limpiar
        except Exception as e:
            print(f"Error img pdf: {e}")

    # Foto de cierre
    if orden.get('foto_cierre_url'):
        poner_imagen_desde_url(orden['foto_cierre_url'], 10, y_pos, 60, "Trabajo Terminado (Evidencia)")
    else:
        pdf.set_font('Arial', 'I', 10)
        pdf.cell(0, 10, "Sin evidencia fotográfica de cierre.", 0, 1)

    # Retornar bytes
    return pdf.output(dest='S').encode('latin-1')
    # ---------------------------------------------------------
    # TOKEN CONFIGURADO DIRECTAMENTE
    # ---------------------------------------------------------
    token_raw = "8382805163:AAEfkue6AMQu6qvqyRdTmh05kIOZUOxCdwM" 
    token = token_raw.strip().replace("bot", "") 
    # ---------------------------------------------------------

    with st.expander("🕵️ DIAGNÓSTICO TELEGRAM (Clic para ver)", expanded=False):
        st.write(f"🔹 **1. Chat ID:** `{chat_id}`")
        
        try:
            base_url = f"https://api.telegram.org/bot{token}"
            payload = {
                "chat_id": chat_id,
                "parse_mode": "Markdown"
            }
            
            url_envio = ""
            if foto_url:
                st.write("🔹 **Modo:** FOTO")
                payload["caption"] = mensaje
                payload["photo"] = foto_url
                url_envio = f"{base_url}/sendPhoto"
            else:
                st.write("🔹 **Modo:** TEXTO")
                payload["text"] = mensaje
                url_envio = f"{base_url}/sendMessage"

            st.write("⏳ Enviando una sola vez...")
            
            # --- AQUÍ OCURRE EL ENVÍO (SOLO UNA VEZ) ---
            response = requests.post(url_envio, data=payload)
            # -------------------------------------------
            
            if response.status_code == 200:
                st.success("✅ Mensaje entregado a Telegram")
            else:
                st.error(f"❌ Error {response.status_code}: {response.text}")

        except Exception as e:
            st.error(f"❌ Error de Conexión Python: {e}")

# --- MÉTRICAS INTELIGENTES (VERSIÓN BLINDADA) ---
# --- MÉTRICAS INTELIGENTES (AHORA CON SOLICITUDES) ---
def mostrar_metricas_inteligentes(df_ordenes, df_users, df_solicitudes):
    """Muestra métricas incluyendo el Buzón de Solicitudes"""
    
    # 1. Contar Solicitudes Nuevas (Buzón)
    n_solicitudes = 0
    if not df_solicitudes.empty:
        # Aseguramos limpieza de texto
        df_solicitudes['estado'] = df_solicitudes['estado'].astype(str).str.strip()
        n_solicitudes = len(df_solicitudes[df_solicitudes['estado'] == 'Pendiente'])

    # 2. Contar Órdenes (Trabajos)
    total = len(df_ordenes)
    pendientes = 0
    por_validar = 0
    concluidas = 0
    devueltas_calidad = 0
    porcentaje_concluidas = 0

    if not df_ordenes.empty:
        df_ordenes['estado'] = df_ordenes['estado'].astype(str).str.strip()
        pendientes = len(df_ordenes[df_ordenes['estado'] == 'Abierta'])
        por_validar = len(df_ordenes[df_ordenes['estado'] == 'Por Validar'])
        concluidas = len(df_ordenes[df_ordenes['estado'] == 'Concluida'])
        
        # Devoluciones
        devueltas_calidad = len(df_ordenes[
            (df_ordenes['estado'] == 'Abierta') & 
            (df_ordenes['comentarios_validacion'].notnull()) &
            (df_ordenes['comentarios_validacion'] != "")
        ])
        
        porcentaje_concluidas = (concluidas / total * 100) if total > 0 else 0

    # 3. Visualización en 5 Columnas
    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        # AQUÍ ESTÁ EL CAMBIO: Mostramos las Solicitudes Pendientes
        color_sol = "normal" if n_solicitudes == 0 else "inverse"
        st.metric("📬 Solicitudes", n_solicitudes, "Nuevas en Buzón", delta_color=color_sol)
    
    with c2: 
        st.metric("🔨 En Ejecución", pendientes, f"{devueltas_calidad} Devueltas" if devueltas_calidad > 0 else None, delta_color="inverse")
    
    with c3:
        # Esto es Calidad (Técnico terminó -> Admin revisa)
        st.metric("🧐 Calidad", por_validar, "Por Aprobar")
    
    with c4: 
        st.metric("✅ Finalizadas", concluidas, f"{porcentaje_concluidas:.0f}%")
        
    with c5:
        st.metric("📦 Total OTs", total)
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
    
# --- 📅 CALENDARIO GANTT INTERACTIVO ---
def graficar_gantt_mantenimiento(df_ordenes, df_users):
    """Crea una línea de tiempo visual (Gantt) por Técnico"""
    if df_ordenes.empty:
        st.info("No hay datos para generar el calendario.")
        return

    # 1. Preparar datos
    df_gantt = df_ordenes.copy()
    
    # Mapear nombres de técnicos
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    df_gantt['Tecnico'] = df_gantt['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
    
    # Convertir fechas
    df_gantt['Inicio'] = pd.to_datetime(df_gantt['fecha_creacion'])
    
    # Para el final: si ya cerró, usa fecha_cierre. Si no, usa AHORA (para mostrar que sigue abierta)
    now = datetime.now()
    df_gantt['Final_Real'] = pd.to_datetime(df_gantt['fecha_cierre'])
    df_gantt['Final_Visual'] = df_gantt['Final_Real'].fillna(now)
    
    # Calcular duración en horas para el tooltip
    df_gantt['Duracion_Horas'] = (df_gantt['Final_Visual'] - df_gantt['Inicio']).dt.total_seconds() / 3600
    df_gantt['Duracion_Horas'] = df_gantt['Duracion_Horas'].round(1)

    # 2. Crear Gráfica Gantt con Plotly
    fig = px.timeline(
        df_gantt, 
        x_start="Inicio", 
        x_end="Final_Visual", 
        y="Tecnico",
        color="criticidad", # Colores según urgencia
        color_discrete_map={"Alta": "#EF4444", "Media": "#F59E0B", "Baja": "#10B981", "Crítica": "#7F1D1D"},
        hover_data=["id", "descripcion", "estado", "Duracion_Horas"],
        title="📅 Línea de Tiempo de Ejecución (Quién hace qué y cuándo)",
        height=400
    )
    
    # 3. Estilizado "Dark Mode Pro"
    fig.update_yaxes(categoryorder="total ascending", title=None) # Ordenar por quien tiene más trabajo
    fig.update_xaxes(title="Tiempo de Ejecución")
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(255,255,255,0.05)',
        font=dict(color='white'),
        legend=dict(orientation="h", y=1.1),
        margin=dict(l=10, r=10, t=40, b=10)
    )
    
    st.plotly_chart(fig, use_container_width=True)

# --- 🏆 TOP 10 LISTAS (ANTIGUAS Y CRÍTICAS) ---
def mostrar_tops_ordenes(df_ordenes):
    """Muestra tablas estilizadas con las órdenes más problemáticas"""
    if df_ordenes.empty: return

    # Calculamos días abierta
    now = datetime.now()
    df_ordenes['fecha_dt'] = pd.to_datetime(df_ordenes['fecha_creacion'])
    
    # Solo nos interesan las NO concluidas para el backlog
    df_abiertas = df_ordenes[df_ordenes['estado'] != 'Concluida'].copy()
    
    if df_abiertas.empty:
        st.success("¡Increíble! No hay órdenes pendientes antiguas.")
        return

    df_abiertas['dias_abierta'] = (now - df_abiertas['fecha_dt']).dt.days
    
    c1, c2 = st.columns(2)
    
    # --- TOP 10 ANTIGUAS ---
    with c1:
        st.markdown("### 🐢 Top 10 Más Antiguas")
        df_old = df_abiertas.sort_values('dias_abierta', ascending=False).head(10)
        
        st.dataframe(
            df_old[['id', 'descripcion', 'dias_abierta', 'tecnico_asignado']],
            column_config={
                "id": st.column_config.NumberColumn("ID", format="#%d", width="small"),
                "descripcion": st.column_config.TextColumn("Problema", width="medium"),
                "dias_abierta": st.column_config.ProgressColumn(
                    "Días Esperando", 
                    help="Días desde que se creó", 
                    format="%d días", 
                    min_value=0, 
                    max_value=30 # La barra se llena a los 30 días
                ),
                "tecnico_asignado": st.column_config.TextColumn("Técnico ID")
            },
            hide_index=True,
            use_container_width=True,
            height=300
        )

    # --- TOP 10 CRÍTICAS ---
    with c2:
        st.markdown("### 🔥 Top Críticas Pendientes")
        # Filtramos Alta o Crítica
        df_crit = df_abiertas[df_abiertas['criticidad'].isin(['Alta', 'Crítica'])].sort_values('fecha_dt').head(10)
        
        if df_crit.empty:
            st.info("No hay órdenes críticas pendientes.")
        else:
            st.dataframe(
                df_crit[['id', 'criticidad', 'descripcion', 'estado']],
                column_config={
                    "id": st.column_config.NumberColumn("ID", format="#%d", width="small"),
                    "criticidad": st.column_config.TextColumn("Nivel"),
                    "descripcion": st.column_config.TextColumn("Problema"),
                    "estado": st.column_config.TextColumn("Estado")
                },
                hide_index=True,
                use_container_width=True,
                height=300
            )

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

# ==============================================================================
# 🚀 NUEVAS GRÁFICAS: FLUJO & CARRERA
# ==============================================================================
def graficar_alternativas_visuales(df_ordenes, df_users):
    """Genera las gráficas de Flujo (Sankey/Parallel) y Carrera (Strip)"""
    if df_ordenes.empty: return

    # 1. Preparación de Datos
    df_vis = df_ordenes.copy()
    
    # Mapear nombres de técnicos
    map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
    df_vis['Tecnico'] = df_vis['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
    
    # Calcular Tiempos
    now = datetime.now()
    df_vis['Inicio'] = pd.to_datetime(df_vis['fecha_creacion'])
    # Si tiene fecha cierre, úsala. Si no, usa AHORA.
    df_vis['Cierre_Calc'] = pd.to_datetime(df_vis['fecha_cierre']).fillna(now)
    
    # Días transcurridos (para la gráfica de carrera)
    df_vis['Dias_Activa'] = (df_vis['Cierre_Calc'] - df_vis['Inicio']).dt.total_seconds() / 86400
    df_vis['Dias_Activa'] = df_vis['Dias_Activa'].round(1)

    # Definir mapa de colores para consistencia
    color_map_crit = {"Alta": "#EF4444", "Media": "#F59E0B", "Baja": "#10B981", "Crítica": "#7F1D1D"}

    # --- A. DIAGRAMA DE FLUJO (PARALLEL CATEGORIES) ---
    st.markdown("### 🌊 Flujo de Distribución")
    st.caption("Sigue las líneas: Técnico ➔ Criticidad ➔ Estado actual.")
    
    fig_flow = px.parallel_categories(
        df_vis, 
        dimensions=['Tecnico', 'criticidad', 'estado'],
        color="Dias_Activa", # El color indica antigüedad
        color_continuous_scale=px.colors.sequential.Inferno,
        labels={'Tecnico':'Personal', 'criticidad':'Urgencia', 'estado':'Situación'}
    )
    
    fig_flow.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        margin=dict(l=20, r=20, t=20, b=20),
        font=dict(color='white'),
        height=350
    )
    st.plotly_chart(fig_flow, use_container_width=True)

    st.markdown("---")

    # --- B. LA CARRERA (STRIP PLOT) ---
    st.markdown("### 🏎️ Tiempos de Respuesta (La Carrera)")
    st.caption("Cada punto es una Orden. Izquierda = Reciente/Rápido. Derecha = Antiguo/Lento.")
    
    fig_race = px.strip(
        df_vis, 
        x="Dias_Activa", 
        y="Tecnico", 
        color="criticidad",
        color_discrete_map=color_map_crit,
        orientation="h", 
        stripmode="overlay",
        hover_data=["id", "descripcion", "estado"]
    )
    
    fig_race.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(255,255,255,0.05)',
        font=dict(color='white'),
        height=300,
        xaxis=dict(title="Días desde creación", showgrid=True, gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(title=None)
    )
    
    # Línea de referencia (ej: 7 días es el límite aceptable)
    fig_race.add_vline(x=7, line_width=1, line_dash="dash", line_color="white", annotation_text="Límite 7 días")
    
    st.plotly_chart(fig_race, use_container_width=True)

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
    # --- NUEVO: LIMPIAR URL ---
    st.query_params.clear() 
    # --------------------------
    st.rerun()
# ==============================================================================
# 🔄 LÓGICA DE PERSISTENCIA (AUTO-LOGIN AL REFRESCAR)
# ==============================================================================
# Si no hay usuario en memoria, pero SÍ hay datos en la URL, intentamos recuperar la sesión
# ==============================================================================
# 🚀 LOGIN & GESTIÓN DE SESIÓN
# ==============================================================================

# 1. Inicializar variables de estado
if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

# 2. Función Logout (Limpiando URL también)
def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear() # Limpia la URL para que no se vuelva a loguear solo
    st.rerun()

# 3. LÓGICA DE PERSISTENCIA (AUTO-LOGIN AL REFRESCAR)
# Si no hay usuario logueado, miramos si la URL tiene el dato "session_id"
if st.session_state['usuario'] is None:
    query_params = st.query_params
    if "session_id" in query_params:
        user_doc_url = query_params["session_id"]
        try:
            # Buscamos al usuario automáticamente
            res = supabase.table("usuarios").select("*").eq("documento", user_doc_url).execute()
            if res.data:
                user = res.data[0]
                st.session_state['usuario'] = user['nombre']
                st.session_state['rol'] = user['rol']
                
                # Recuperar la página donde estaba (si existe)
                if "last_page" in query_params:
                    st.session_state.current_page = query_params["last_page"]
                
                st.rerun() # Recargamos para entrar directo
        except Exception as e:
            st.error(f"Error recuperando sesión: {e}")

# ==============================================================================
# 🔒 PANTALLA DE ACCESO (LOGIN)
# ==============================================================================
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
                        
                        # --- NUEVO: GUARDAR SESIÓN EN URL ---
                        st.query_params["session_id"] = documento
                        st.query_params["last_page"] = "Tablero de Mando"
                        # ------------------------------------
                        
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
    
    # --- MENÚ UNIFICADO ---
    if rol == "Admin":
        menu = [
            ("📊", "Tablero"),
            ("📦", "Inventario Activos"), 
            ("🛠️", "Órdenes de Trabajo"), 
            ("👤", "Usuarios")
        ]
        valores = [
            "Tablero de Mando",
            "Inventario Activos", 
            "Ordenes de Trabajo", 
            "Usuarios"
        ]
    elif rol == "Programador":
        menu = [
            ("📊", "Tablero"),
            ("🛠️", "Órdenes de Trabajo"),
            ("👤", "Usuarios")
        ]
        valores = [
            "Tablero de Mando",
            "Ordenes de Trabajo",
            "Usuarios"
        ]
    elif rol == "Tecnico":
        menu = [("🛠️", "Órdenes de Trabajo")]
        valores = ["Ordenes de Trabajo"]
    
    for (icono, texto), valor in zip(menu, valores):
        activo = st.session_state.current_page == valor
        tipo = "primary" if activo else "secondary"
        
        if activo:
            st.markdown("""
            <style>
            .boton-activo { border: 2px solid #F59E0B !important; }
            </style>
            """, unsafe_allow_html=True)
        
        if st.button(f"{icono} {texto}", key=f"menu_{valor}", use_container_width=True, type=tipo):
            st.session_state.current_page = valor
            
            # --- NUEVO: ACTUALIZAR PÁGINA EN URL ---
            # Mantenemos la sesión pero cambiamos la página
            doc_actual = st.query_params.get("session_id", "")
            st.query_params["session_id"] = doc_actual
            st.query_params["last_page"] = valor
            # ---------------------------------------
            
            st.rerun()
    
    choice = st.session_state.current_page

# ==============================================================================
# 📊 PANTALLAS
# ==============================================================================
# ==============================================================================
# 📅 MÓDULO DE MANTENIMIENTO PREVENTIVO
# ==============================================================================
def render_tab_preventivos(df_act, df_users):
    """Interfaz para gestionar y ejecutar planes de mantenimiento"""
    
    st.markdown("### 🗓️ Planes de Mantenimiento Recurrente")
       
    # --- 🔵 LÓGICA DE RECEPCIÓN DE SALTO (NUEVO) ---
    filtro_id_externo = None
    if st.session_state.get('jump_target') == 'preventivo' and st.session_state.get('jump_id'):
        filtro_id_externo = st.session_state.jump_id
        st.info(f"📍 Has sido redirigido al Plan #{filtro_id_externo}. Puedes editarlo o borrarlo abajo.")
        # Limpiamos para que no se quede pegado el filtro si recarga
        st.session_state.jump_target = None 
        st.session_state.jump_id = None
    st.info("Aquí configuras las tareas que se repiten (ej: Limpieza mensual).")

    # 1. FORMULARIO PARA CREAR NUEVO PLAN
    with st.expander("➕ Crear Nuevo Plan Preventivo"):
        with st.form("form_plan_prev"):
            c1, c2 = st.columns(2)
            
            # Selectores
            act_nombres = df_act['nombre'].values if not df_act.empty else []
            act_sel = c1.selectbox("Activo", act_nombres)
            
            users_dict = dict(zip(df_users['nombre'], df_users['id'])) if not df_users.empty else {}
            tec_sel = c2.selectbox("Técnico Sugerido", list(users_dict.keys()))
            
            desc = st.text_input("Tarea a realizar (Ej: Cambio de filtros)")
            
            c3, c4 = st.columns(2)
            dias = c3.number_input("Frecuencia (Días)", min_value=1, value=30, help="¿Cada cuánto se hace?")
            fecha_base = c4.date_input("Fecha de Inicio / Última vez hecho")
            
            if st.form_submit_button("GUARDAR PLAN"):
                # Buscar ID activo
                id_act = df_act[df_act['nombre'] == act_sel].iloc[0]['id']
                id_tec = users_dict[tec_sel]
                
                try:
                    supabase.table("planes_mantenimiento").insert({
                        "activo_id": int(id_act),
                        "descripcion": desc,
                        "frecuencia_dias": int(dias),
                        "ultima_ejecucion": fecha_base.isoformat(),
                        "tecnico_default": str(id_tec)
                    }).execute()
                    st.success("Plan guardado.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    st.divider()

    # 2. LISTADO Y EJECUCIÓN
    df_planes = run_query("planes_mantenimiento")
    
    # --- 🔵 APLICAR FILTRO SI VENIMOS DE UN SALTO ---
    if filtro_id_externo:
        # Convertimos a string por seguridad al comparar
        df_planes = df_planes[df_planes['id'].astype(str) == str(filtro_id_externo)]
        
    if df_planes.empty:
        st.warning("No hay planes configurados.")
        return

    # Cálculos de Próxima Fecha
    df_planes['ultima_ejecucion'] = pd.to_datetime(df_planes['ultima_ejecucion'])
    df_planes['proxima_fecha'] = df_planes['ultima_ejecucion'] + pd.to_timedelta(df_planes['frecuencia_dias'], unit='D')
    df_planes['dias_restantes'] = (df_planes['proxima_fecha'] - datetime.now()).dt.days
    
    # Visualización tipo Semáforo
    def color_estado(dias):
        if dias < 0: return "🔴 Vencido"
        elif dias <= 5: return "🟡 Próximo"
        else: return "🟢 A tiempo"
    
    df_planes['Estado'] = df_planes['dias_restantes'].apply(color_estado)
    
    # Enriquecer tabla con nombres
    map_act = dict(zip(df_act['id'], df_act['nombre']))
    df_planes['Activo'] = df_planes['activo_id'].map(map_act)
    
    # Mostrar tabla
    st.dataframe(
        df_planes[['id', 'Activo', 'descripcion', 'frecuencia_dias', 'ultima_ejecucion', 'proxima_fecha', 'Estado']],
        column_config={
            "ultima_ejecucion": st.column_config.DateColumn("Última vez"),
            "proxima_fecha": st.column_config.DateColumn("Próxima"),
            "frecuencia_dias": st.column_config.NumberColumn("Cada (días)"),
            "descripcion": "Tarea"
        },
        use_container_width=True,
        hide_index=True
    )

    # 3. EL BOTÓN MÁGICO (GENERADOR)
    st.markdown("### 🤖 Generador Automático")
    c_gen1, c_gen2 = st.columns([3, 1])
    c_gen1.caption("Este proceso buscará todos los planes 'Vencidos' o 'Próximos' (hoy o antes) y creará las Órdenes de Trabajo automáticamente.")
    
    if c_gen2.button("🚀 EJECUTAR RUTINA", type="primary"):
        contador = 0
        now = datetime.now()
        
        progress_bar = st.progress(0)
        
        for idx, plan in df_planes.iterrows():
            # Si la fecha próxima es HOY o YA PASÓ
            if plan['proxima_fecha'] <= now:
                try:
                    # 1. Crear la Orden
                    res = supabase.table("ordenes").insert({
                        "activo_id": int(plan['activo_id']),
                        "descripcion": f"[PREVENTIVO] {plan['descripcion']}",
                        "criticidad": "Media", # Preventivos suelen ser Media/Alta
                        "tipo_mantenimiento": "Preventivo",
                        "estado": "Abierta",
                        "tecnico_asignado": str(plan['tecnico_default']),
                        "fecha_creacion": now.isoformat()
                    }).execute()
                    
                    # 2. Actualizar la fecha de última ejecución en el plan para que no se repita mañana
                    # (Se asume que al generar la orden, se programa para hoy)
                    supabase.table("planes_mantenimiento").update({
                        "ultima_ejecucion": now.isoformat()
                    }).eq("id", plan['id']).execute()
                    
                    contador += 1
                except Exception as e:
                    st.error(f"Error en plan {plan['id']}: {e}")
            
            progress_bar.progress((idx + 1) / len(df_planes))
            
        if contador > 0:
            st.success(f"✅ Se generaron {contador} órdenes de mantenimiento preventivo.")
            time.sleep(2)
            st.rerun()
        else:
            st.info("👍 Todo al día. No hay mantenimientos pendientes para hoy.")
if choice == "Tablero de Mando":
    st.title("TABLERO DE MANDO")
    mostrar_notificaciones()
    
    # 1. Cargar datos
    df = run_query("ordenes")
    df_users = run_query("usuarios")
    df_solicitudes = run_query("solicitudes")
    
    # 2. Métricas KPI
    mostrar_metricas_inteligentes(df, df_users, df_solicitudes)
    
    st.write("") 

    if not df.empty:
        # 3. --- NUEVO: GRÁFICAS VISUALES (FLUJO Y CARRERA) ---
        st.markdown("---")
        # Aquí llamamos a la nueva función que acabas de pegar arriba
        graficar_alternativas_visuales(df, df_users)
        st.markdown("---")

        # 4. TOPS (Antiguas y Críticas)
        mostrar_tops_ordenes(df)
        st.markdown("---")

        # 5. GRÁFICAS CLÁSICAS DE DISTRIBUCIÓN
        st.markdown("### 📊 Análisis Global")
        c_left, c_mid, c_right = st.columns(3)

        with c_left:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Progreso Global</span>", unsafe_allow_html=True)
            graficar_estado_barras(df)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_mid:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Nivel de Riesgo</span>", unsafe_allow_html=True)
            graficar_criticidad(df) 
            st.markdown("</div>", unsafe_allow_html=True)

        with c_right:
            st.markdown(f"<div class='card-style'><span class='chart-header'>Por Categoría</span>", unsafe_allow_html=True)
            graficar_torta_tipo(df) 
            st.markdown("</div>", unsafe_allow_html=True)
        
        # 6. PRODUCTIVIDAD
        st.markdown("### 👥 Carga por Técnico")
        with st.container():
            graficar_ordenes_por_tecnico(df, df_users)

    else: 
        st.info("No hay órdenes registradas. El tablero se activará con datos.")
        
elif choice == "Inventario Activos":
    st.title("INVENTARIO DE ACTIVOS")
    mostrar_notificaciones()
    
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
    
    if 'specs_data' not in st.session_state:
        st.session_state.specs_data = pd.DataFrame(columns=["Componente/Dato", "Valor"])
    if 'draft_data' not in st.session_state:
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
                    if foto: st.image(foto, use_container_width=True)
                    else: st.warning("Sin foto")
                with c_zoom2:
                    st.markdown("**Código QR**")
                    if qr: st.image(qr, width=250)
                    else: st.warning("Sin QR")
                st.caption("Presione 'Esc' o la 'X' para cerrar.")

            col_kpi1, col_kpi2, col_kpi3, col_kpi4 = st.columns(4)
            col_kpi1.metric("Total Activos", len(df_act))
            col_kpi2.metric("Áreas Activas", df_act['area'].nunique())
            col_kpi3.metric("Categorías", df_act['categoria'].nunique())
            con_foto = df_act['foto_url'].notnull().sum()
            col_kpi4.metric("Con Fotografía", f"{con_foto}/{len(df_act)}")
            
            st.markdown("---")
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
            
            df_filtered = df_act.copy()
            if search_term:
                df_filtered = df_filtered[df_filtered['nombre'].str.contains(search_term, case=False, na=False)]
            if filtro_area != "Todas":
                df_filtered = df_filtered[df_filtered['area'] == filtro_area]
            if filtro_sub != "Todas":
                df_filtered = df_filtered[df_filtered['ubicacion'].str.contains(f"\[{filtro_sub}\]", regex=True, na=False)]
            if filtro_cat != "Todas":
                df_filtered = df_filtered[df_filtered['categoria'] == filtro_cat]

            @st.fragment
            def fragmento_tabla_estable(dataframe_filtrado):
                if not dataframe_filtrado.empty:
                    st.markdown(f"###### 🧬 Resultados: {len(dataframe_filtrado)}")
                    st.info("👆 **Haga clic en una fila** para ver Foto y QR.")

                    if 'last_viewed_id' not in st.session_state:
                        st.session_state.last_viewed_id = None

                    altura_tabla = (len(dataframe_filtrado) * 35) + 38
                    altura_final = min(max(altura_tabla, 100), 600)

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
                        on_select="rerun",
                        key="tabla_maestra_activos"
                    )

                    if len(event.selection.rows) > 0:
                        idx = event.selection.rows[0]
                        sel_data = dataframe_filtrado.iloc[idx]
                        sel_id = sel_data['id']
                        if st.session_state.last_viewed_id != sel_id:
                            st.session_state.last_viewed_id = sel_id
                            mostrar_visor(sel_data['nombre'], sel_data['foto_url'], sel_data['qr_url'])
                    elif len(event.selection.rows) == 0:
                         st.session_state.last_viewed_id = None
                else:
                    if search_term or filtro_area != "Todas" or filtro_cat != "Todas":
                        st.warning(f"⚠️ No se encontraron activos con estos filtros.")

            fragmento_tabla_estable(df_filtered)
        else:
            st.info("Aún no hay activos registrados para mostrar en la lista.")

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
                    agregar_notificacion('warning', 'Registro cancelado.')
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
                st.image(draft['foto_url'], width=100, caption="Foto actual")
            foto_archivo = st.file_uploader("Subir imagen", type=["jpg", "png", "jpeg"], key="uploader_new")
            
            st.markdown("---")
            st.markdown("#### ⚙️ Especificaciones")
            edited_df = st.data_editor(st.session_state.specs_data, num_rows="dynamic", use_container_width=True, key="editor_new")

            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 GUARDAR ACTIVO", type="primary", use_container_width=True):
                final_url = None
                if foto_archivo:
                    with st.spinner("Subiendo foto a Cloudinary..."):
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
                            # Generamos el QR (que ahora también se guarda en Cloudinary)
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
                if dat.get('foto_url'): st.image(dat['foto_url'], use_container_width=True)
                else: st.warning("Sin imagen")
            
            with col_f2:
                st.markdown("#### 🔄 Cambiar Foto (Opcional)")
                edit_foto_file = st.file_uploader("Subir nueva foto", type=["jpg", "png"], key=f"edit_uploader_{id_suffix}")
            
            st.markdown("---")
            st.markdown("#### ⚙️ Editar Especificaciones")
            
            current_specs_df = pd.DataFrame(columns=["Componente/Dato", "Valor"])
            if dat.get('detalles') and isinstance(dat['detalles'], dict):
                current_specs_df = pd.DataFrame(list(dat['detalles'].items()), columns=["Componente/Dato", "Valor"])
            
            edited_specs = st.data_editor(
                current_specs_df, num_rows="dynamic", use_container_width=True,
                column_config={"Componente/Dato": st.column_config.TextColumn("Característica"), "Valor": st.column_config.TextColumn("Valor")},
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
                                agregar_notificacion("success", f"Activo '{edit_nom}' actualizado correctamente")
                                time.sleep(1.5)
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
            with bc2:
                with st.expander("🗑️ Zona de Peligro", expanded=True):
                    st.warning("Acciones críticas.")
                    
                    # 1. CLASIFICACIÓN INTELIGENTE (Separamos lo activo de lo viejo)
                    ids_planes = []     # Bloqueante
                    ids_solic = []      # Bloqueante
                    ids_activas = []    # Bloqueante (Abiertas/Por Validar)
                    ids_historial = []  # NO Bloqueante (Concluidas/Canceladas) - Solo advertencia
                    
                    if dat.get('id'):
                        # Planes (Siempre bloquean si existen)
                        res = supabase.table("planes_mantenimiento").select("id").eq("activo_id", dat['id']).execute()
                        ids_planes = [str(x['id']) for x in res.data]
                        
                        # Solicitudes (Siempre bloquean si existen)
                        res = supabase.table("solicitudes").select("id").eq("activo_id", dat['id']).execute()
                        ids_solic = [str(x['id']) for x in res.data]
                        
                        # Órdenes (Aquí está la clave: separamos vivas de muertas)
                        res = supabase.table("ordenes").select("id, estado").eq("activo_id", dat['id']).execute()
                        for o in res.data:
                            if o['estado'] in ['Abierta', 'Por Validar']:
                                ids_activas.append(str(o['id']))
                            else:
                                ids_historial.append(str(o['id']))

                    # 2. LÓGICA DE BLOQUEO (ROJO) - SOLO SI HAY TAREAS PENDIENTES
                    # Si hay Planes, Solicitudes u Órdenes ABIERTAS, no dejamos borrar.
                    bloqueo_total = ids_planes or ids_activas or ids_solic

                    if bloqueo_total:
                        st.markdown(f"""
                        <div style="background-color: rgba(239, 68, 68, 0.1); border-left: 4px solid #EF4444; padding: 10px; margin-bottom: 10px;">
                            <strong style="color: #EF4444;">🛑 NO SE PUEDE BORRAR</strong>
                            <p style="font-size: 0.85em; margin:0;">Hay tareas pendientes activas. Debes gestionarlas primero.</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Mostramos qué estorba y permitimos ir a arreglarlo
                        if ids_planes:
                            st.caption(f"📅 Planes ({len(ids_planes)}) - ID: {', '.join(ids_planes)}")
                            df_l = pd.DataFrame({'ID': ids_planes, 'Ir': ['Ver Plan' for _ in ids_planes]})
                            sel = st.dataframe(df_l, selection_mode='single-row', on_select='rerun', use_container_width=True, hide_index=True, key=f"lk_p_{id_suffix}")
                            if len(sel.selection.rows) > 0:
                                st.session_state.current_page = "Ordenes de Trabajo"
                                st.session_state.jump_target = "preventivo"
                                st.session_state.jump_id = df_l.iloc[sel.selection.rows[0]]['ID']
                                st.rerun()

                        if ids_activas:
                            st.caption(f"🛠️ Órdenes Activas ({len(ids_activas)})")
                            df_l = pd.DataFrame({'ID': ids_activas, 'Ir': ['Ver Orden' for _ in ids_activas]})
                            sel = st.dataframe(df_l, selection_mode='single-row', on_select='rerun', use_container_width=True, hide_index=True, key=f"lk_o_{id_suffix}")
                            if len(sel.selection.rows) > 0:
                                st.session_state.current_page = "Ordenes de Trabajo"
                                st.session_state.jump_target = "orden"
                                st.session_state.jump_id = df_l.iloc[sel.selection.rows[0]]['ID']
                                st.rerun()
                        
                        if ids_solic:
                             st.caption(f"📬 Solicitudes ({len(ids_solic)}) - Gestionar en Buzón")

                    # 3. LÓGICA DE ADVERTENCIA (NARANJA/VERDE) - AQUÍ APARECE EL PDF
                    else:
                        # Si llegamos aquí, NO hay pendientes. Pero puede haber historial viejo.
                        if ids_historial:
                            st.markdown(f"""
                            <div style="background-color: rgba(245, 158, 11, 0.1); border-left: 4px solid #F59E0B; padding: 10px; margin-bottom: 10px;">
                                <strong style="color: #F59E0B;">⚠️ TIENE HISTORIAL</strong>
                                <p style="font-size: 0.85em; margin:0;">
                                    Este equipo tiene <b>{len(ids_historial)}</b> órdenes cerradas.<br>
                                    Se recomienda descargar la Hoja de Vida antes de borrar.
                                </p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            # --- GENERAR PDF DE RESPALDO ---
                            try:
                                if 'df_users_cache' not in st.session_state: st.session_state.df_users_cache = run_query("usuarios")
                                # Traemos los datos completos del historial
                                data_hist = supabase.table("ordenes").select("*").in_("id", ids_historial).order("fecha_creacion", desc=True).execute()
                                
                                if data_hist.data:
                                    # Llamamos a la función que ya definiste arriba
                                    pdf_bytes = generar_hoja_vida_pdf(dat, data_hist.data, st.session_state.df_users_cache)
                                    
                                    st.download_button(
                                        label="📄 DESCARGAR HOJA DE VIDA (PDF)", 
                                        data=pdf_bytes, 
                                        file_name=f"Hoja_Vida_{dat['nombre']}.pdf", 
                                        mime="application/pdf", 
                                        use_container_width=True
                                    )
                            except Exception as e:
                                st.error(f"Error generando PDF: {e}")
                        
                        else:
                            st.success("✅ Equipo limpio (Sin historial).")

                        st.markdown("---")
                        
                        # BOTÓN FINAL DE BORRADO
                        if st.button("🗑️ CONFIRMAR ELIMINACIÓN", type="secondary", use_container_width=True, key=f"fin_del_{id_suffix}"):
                            try:
                                # 1. Borrar historial viejo (silenciosamente) para evitar error de Foreign Key
                                if ids_historial:
                                    supabase.table("ordenes").delete().in_("id", ids_historial).execute()
                                
                                # 2. Borrar activo
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

elif choice == "Ordenes de Trabajo":
    st.title("GESTIÓN DE MANTENIMIENTO")
    mostrar_notificaciones()
    
    # ---------------------------------------------------------
    # 1. CARGA DE DATOS (CRÍTICO: HACERLO ANTES DEL INTERCEPTOR)
    # ---------------------------------------------------------
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")

    # ==============================================================================
    # 🚀 INTERCEPTOR 3.0: GESTIÓN TOTAL (CON DATOS DISPONIBLES)
    # ==============================================================================
    if 'jump_target' in st.session_state and st.session_state.jump_target:
        target_type = st.session_state.jump_target
        target_id = st.session_state.jump_id

        # Encabezado
        st.markdown(f"""
        <div style="background-color: #1F2937; padding: 15px; border-radius: 8px; border-left: 5px solid #3B82F6; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between;">
            <div>
                <h3 style="color: #60A5FA; margin: 0;">🛠️ Gestión de Dependencia #{target_id}</h3>
                <p style="margin: 0; color: #9CA3AF; font-size: 0.9em;">Edita o reasigna este registro para liberar el activo original.</p>
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("⬅️ VOLVER A EDICIÓN DE ACTIVO", use_container_width=True):
            st.session_state.current_page = "Inventario Activos"
            st.session_state.jump_target = None
            st.session_state.jump_id = None
            st.rerun()

        st.markdown("---")

        # --- CASO 1: ORDEN DE TRABAJO ---
        if target_type == "orden":
            try:
                res = supabase.table("ordenes").select("*").eq("id", target_id).execute()
                if res.data:
                    orden_actual = res.data[0]
                    
                    with st.form(key=f"form_focus_orden_{target_id}"):
                        c_edit1, c_edit2, c_edit3 = st.columns(3)
                        
                        est_opts = ["Abierta", "Por Validar", "Concluida", "Cancelada"]
                        idx_est = est_opts.index(orden_actual['estado']) if orden_actual['estado'] in est_opts else 0
                        nuevo_estado = c_edit1.selectbox("Estado", est_opts, index=idx_est)
                        
                        # Selectores de Técnicos
                        lista_tecnicos = df_users[df_users['rol'].isin(['Tecnico', 'Admin', 'Programador'])]
                        tech_dict = dict(zip(lista_tecnicos['nombre'], lista_tecnicos['id']))
                        tech_actual_id = str(orden_actual['tecnico_asignado'])
                        nombre_tech = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), "Seleccionar...")
                        
                        # Selector de Activo (Para reasignar si es necesario)
                        act_dict = dict(zip(df_act['nombre'], df_act['id']))
                        act_actual_id = orden_actual['activo_id']
                        nombre_act = next((k for k, v in act_dict.items() if v == act_actual_id), list(act_dict.keys())[0])
                        
                        nuevo_act_nom = c_edit2.selectbox("Reasignar Activo", list(act_dict.keys()), index=list(act_dict.keys()).index(nombre_act))
                        nuevo_tec_nom = c_edit3.selectbox("Técnico", list(tech_dict.keys()), index=list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0)
                        
                        nueva_desc = st.text_area("Descripción / Reporte", value=orden_actual['descripcion'])
                        nueva_crit = st.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], value=orden_actual['criticidad'])
                        
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                        if st.form_submit_button("💾 GUARDAR CAMBIOS Y REASIGNAR", type="primary", use_container_width=True):
                            supabase.table("ordenes").update({
                                "estado": nuevo_estado, 
                                "tecnico_asignado": str(tech_dict[nuevo_tec_nom]),
                                "activo_id": int(act_dict[nuevo_act_nom]), # Aquí guardamos el cambio de activo
                                "criticidad": nueva_crit, 
                                "descripcion": nueva_desc
                            }).eq("id", target_id).execute()
                            
                            st.success("✅ Orden actualizada. Si cambiaste el activo, ahora podrás borrar el original.")
                            time.sleep(1.5)
                            st.rerun()

                    # Botón de borrar fuera del form
                    st.markdown("### 🗑️ Opciones Críticas")
                    if st.button("ELIMINAR ORDEN DEFINITIVAMENTE", type="secondary", use_container_width=True, key="btn_focus_del"):
                        supabase.table("ordenes").delete().eq("id", target_id).execute()
                        st.success("🗑️ Orden eliminada.")
                        st.session_state.current_page = "Inventario Activos"
                        st.session_state.jump_target = None
                        time.sleep(1.5)
                        st.rerun()
                else:
                    st.error("Orden no encontrada.")
            except Exception as e:
                st.error(f"Error: {e}")

        # --- CASO 2: PLAN PREVENTIVO (MEJORADO) ---
        elif target_type == "preventivo":
            try:
                res = supabase.table("planes_mantenimiento").select("*").eq("id", target_id).execute()
                if res.data:
                    plan_focus = res.data[0]
                    
                    st.info(f"Editando Plan Preventivo #{target_id}")
                    
                    with st.form("form_focus_prev"):
                        c1, c2 = st.columns(2)
                        
                        # 1. Selector de Activo (Crucial para reasignar)
                        act_dict = dict(zip(df_act['nombre'], df_act['id']))
                        act_actual_id = plan_focus['activo_id']
                        # Buscar nombre del activo actual
                        nombre_act_actual = next((k for k, v in act_dict.items() if v == act_actual_id), list(act_dict.keys())[0])
                        idx_act = list(act_dict.keys()).index(nombre_act_actual) if nombre_act_actual in act_dict else 0
                        
                        nuevo_act_nom = c1.selectbox("Reasignar a Activo", list(act_dict.keys()), index=idx_act)
                        
                        # 2. Selector de Técnico
                        tech_dict = dict(zip(df_users['nombre'], df_users['id']))
                        tech_actual_id = str(plan_focus['tecnico_default'])
                        nombre_tech = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), list(tech_dict.keys())[0])
                        idx_tech = list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0
                        
                        nuevo_tec_nom = c2.selectbox("Técnico Encargado", list(tech_dict.keys()), index=idx_tech)
                        
                        desc_p = st.text_input("Tarea", value=plan_focus['descripcion'])
                        dias_p = st.number_input("Frecuencia (Días)", value=plan_focus['frecuencia_dias'])
                        
                        st.markdown("<br>", unsafe_allow_html=True)

                        if st.form_submit_button("💾 GUARDAR Y REASIGNAR", type="primary", use_container_width=True):
                             supabase.table("planes_mantenimiento").update({
                                 "activo_id": int(act_dict[nuevo_act_nom]), # Guardar cambio activo
                                 "tecnico_default": str(tech_dict[nuevo_tec_nom]), # Guardar cambio técnico
                                 "descripcion": desc_p,
                                 "frecuencia_dias": dias_p
                             }).eq("id", target_id).execute()
                             
                             st.success(f"✅ Plan reasignado a '{nuevo_act_nom}'.")
                             time.sleep(1.5)
                             st.rerun()
                    
                    st.markdown("---")
                    if st.button("🗑️ ELIMINAR PLAN DEFINITIVAMENTE", type="secondary", use_container_width=True):
                        supabase.table("planes_mantenimiento").delete().eq("id", target_id).execute()
                        st.success("🗑️ Plan eliminado.")
                        st.session_state.current_page = "Inventario Activos"
                        st.session_state.jump_target = None
                        time.sleep(1.5)
                        st.rerun()
            except Exception as e:
                st.error(f"Error cargando plan: {e}")

        # 🛑 DETENER LA EJECUCIÓN (IMPORTANTE)
        st.stop()
        
    # Cargar datos necesarios
    df_act = run_query("activos")
    df_users = run_query("usuarios")
    df_ordenes = run_query("ordenes")
    
    # --- LÓGICA DE PESTAÑAS SEGÚN ROL ---
    
    # 👷 TÉCNICO: Solo ve sus órdenes y puede pedir cosas nuevas
    if rol == "Tecnico":
        tab_mis_ordenes, tab_solicitar = st.tabs(["👷 MIS ÓRDENES", "📢 SOLICITAR MANTENIMIENTO"])
        
        # PESTAÑA 1: MIS ÓRDENES (Técnico)
        with tab_mis_ordenes:
            mi_id = None
            if not df_users.empty:
                usuario_data = df_users[df_users['nombre'] == usuario]
                if not usuario_data.empty:
                    mi_id = usuario_data.iloc[0]['id']
            
            if mi_id:
                mis_ots = df_ordenes[(df_ordenes['tecnico_asignado'] == str(mi_id)) & (df_ordenes['estado'] == 'Abierta')]
                
                if mis_ots.empty:
                    st.info("🎉 No tienes órdenes pendientes.")
                else:
                    st.write(f"Tienes {len(mis_ots)} órdenes pendientes.")
                    for index, row in mis_ots.iterrows():
                        nombre_activo = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "Activo"
                        
                        with st.expander(f"🔧 {nombre_activo} | {row['criticidad']} (ID: {row['id']})"):
                            st.markdown(f"**Falla:** {row['descripcion']}")
                            st.caption(f"📅 Asignada: {row['fecha_creacion'][:10]}")
                            
                            if row.get('comentarios_validacion'):
                                st.error(f"⚠️ **Devolución:** {row['comentarios_validacion']}")
                            
                            st.divider()

                            with st.form(f"cierre_riguroso_{row['id']}"):
                                st.markdown("#### 📝 Reporte Técnico")
                                reporte = st.text_area("Descripción del trabajo realizado:", height=100, placeholder="Describa qué reparó y qué repuestos usó...")
                                st.markdown("#### 📸 Evidencia (Obligatoria)")
                                foto_cierre = st.file_uploader("Subir foto del trabajo terminado", type=["jpg", "png", "jpeg"], key=f"up_cierre_{row['id']}")
                                
                                if st.form_submit_button("✅ TERMINAR Y ENVIAR A REVISIÓN", type="primary", use_container_width=True):
                                    if not reporte or not foto_cierre:
                                        st.error("⚠️ Faltan datos: Es obligatorio escribir el reporte Y subir la foto de evidencia.")
                                    else:
                                        try:
                                            url_final = None
                                            with st.spinner("Subiendo evidencia a la nube..."):
                                                url_final = subir_imagen(foto_cierre, "orion_evidencias_cierre")
                                            
                                            if not url_final:
                                                st.error("Error al subir la imagen. Intenta de nuevo.")
                                            else:
                                                supabase.table("ordenes").update({
                                                    "estado": "Por Validar",
                                                    "comentarios_cierre": reporte,
                                                    "fecha_cierre": datetime.now().isoformat(),
                                                    "foto_cierre_url": url_final,
                                                    "comentarios_validacion": None
                                                }).eq("id", row['id']).execute()
                                                
                                                st.success("🚀 ¡Excelente! Orden enviada a control de calidad.")
                                                time.sleep(1.5)
                                                st.rerun()
                                        except Exception as e:
                                            st.error(f"Error al guardar: {e}")
            else:
                st.error("No se pudo identificar tu usuario técnico en la base de datos.")

        # PESTAÑA 2: SOLICITAR (Técnico)
        with tab_solicitar:
            st.markdown("### Reportar una Falla o Necesidad")
            if not df_act.empty:
                act_nombres = df_act['nombre'].values
                with st.form("form_solicitud"):
                    act_sol = st.selectbox("Activo que presenta fallas", act_nombres)
                    desc_sol = st.text_area("Describa el problema detalladamente")
                    prio_sol = st.select_slider("¿Qué tan urgente parece?", ["Baja", "Media", "Alta"], value="Media")
                    foto_sol = st.file_uploader("Foto del daño (Opcional)", type=["jpg", "png"])
                    
                    if st.form_submit_button("ENVIAR SOLICITUD", type="primary", use_container_width=True):
                        if not desc_sol:
                            st.error("La descripción es obligatoria.")
                        else:
                            act_id = df_act[df_act['nombre'] == act_sol].iloc[0]['id']
                            url_foto = subir_imagen(foto_sol) if foto_sol else None
                            
                            supabase.table("solicitudes").insert({
                                "activo_id": int(act_id),
                                "solicitante_id": usuario,
                                "descripcion": desc_sol,
                                "prioridad_sugerida": prio_sol,
                                "foto_url": url_foto,
                                "estado": "Pendiente"
                            }).execute()
                            
                            agregar_notificacion("success", "Solicitud enviada al planificador.")
                            st.rerun()
            else:
                st.warning("No hay activos registrados.")

    # 👮 ADMIN / PROGRAMADOR: Gestión Completa
    else:
        # Consultamos solicitudes pendientes
        df_solicitudes = run_query("solicitudes", {"estado": "Pendiente"})
        n_pendientes = len(df_solicitudes)
        titulo_buzon = f"👮 VALIDAR ({n_pendientes})" if n_pendientes > 0 else "👮 VALIDAR"
        
        # ==============================================================================
        # 🟢 AQUI EMPIEZA LA PARTE 3 (MODIFICADA)
        # Reemplazamos la definición anterior de st.tabs por esta nueva lista de 6 pestañas
        # ==============================================================================
        
        tab_mis_gestiones, tab_buzon, tab_calidad, tab_gestion, tab_crear_directa, tab_preventivos = st.tabs([
            "📂 MIS GESTIONES",  # <--- NUEVA PESTAÑA
            titulo_buzon, 
            "💎 CALIDAD", 
            "📊 GESTIÓN GLOBAL", 
            "⚡ CREAR DIRECTA", 
            "📅 PREVENTIVOS"
        ])
        
        # ------------------------------------------------------------------
        # 1. PESTAÑA DE GESTIÓN ADMINISTRATIVA (NUEVA LÓGICA)
        # ------------------------------------------------------------------
        with tab_mis_gestiones:
            st.info("Aquí administras las órdenes asignadas a ti (Cotizaciones, Compras, Trámites).")
            
            # 1. Buscar mi ID de usuario
            mi_id_admin = None
            if not df_users.empty:
                user_match = df_users[df_users['nombre'] == usuario]
                if not user_match.empty:
                    mi_id_admin = user_match.iloc[0]['id']
            
            if mi_id_admin:
                # 2. Filtrar órdenes asignadas a MÍ y que NO estén concluidas
                mis_gestiones = df_ordenes[
                    (df_ordenes['tecnico_asignado'] == str(mi_id_admin)) & 
                    (df_ordenes['estado'] != 'Concluida')
                ]
                
                if mis_gestiones.empty:
                    st.success("🎉 No tienes gestiones administrativas pendientes.")
                else:
                    for idx, row in mis_gestiones.iterrows():
                        nombre_activo = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "Activo"
                        
                        # Usamos un expander para cada orden
                        with st.expander(f"📂 {nombre_activo} | {row['descripcion'][:50]}... (ID: {row['id']})", expanded=False):
                            
                            # A) Mostrar Bitácora (Historial de avances)
# ... Dentro de tab_mis_gestiones ...
                            # ... Dentro de with st.expander(...): ...

                           # ==========================================
                            # 1. DEFINICIÓN DEL DIÁLOGO DE EDICIÓN (MEJORADO)
                            # ==========================================
                            @st.dialog("✏️ Editar Avance")
                            def editar_avance_dialog(item_id, texto_actual, url_actual):
                                st.write(f"Editando registro #{item_id}")
                                
                                # A) Editar Texto
                                nuevo_texto = st.text_area("Corrección", value=texto_actual, height=100)
                                
                                st.markdown("---")
                                st.caption("📎 Gestión de Archivos")

                                # B) Lógica de Archivo
                                borrar_archivo = False
                                
                                # Si ya existe un archivo, mostramos opción de borrar
                                if url_actual:
                                    st.markdown(f"**Archivo actual:** [Ver documento]({url_actual})")
                                    borrar_archivo = st.checkbox("🗑️ Borrar archivo actual", value=False)
                                
                                # Opción para reemplazar (o agregar si no había)
                                archivo_nuevo = st.file_uploader("Cambiar archivo (Opcional)", type=["pdf", "docx", "xlsx", "jpg", "png", "msg"])
                                
                                if st.button("💾 GUARDAR CAMBIOS", type="primary"):
                                    with st.spinner("Procesando..."):
                                        try:
                                            # Preparar datos a actualizar
                                            datos_update = {"mensaje": nuevo_texto}
                                            
                                            # 1. Si marcó borrar, ponemos NULL en la base de datos
                                            if borrar_archivo:
                                                datos_update["archivo_url"] = None
                                            
                                            # 2. Si subió uno nuevo, lo procesamos (esto sobreescribe el borrado si marcó ambos)
                                            if archivo_nuevo:
                                                url_subida = subir_archivo_generico(archivo_nuevo)
                                                if url_subida:
                                                    datos_update["archivo_url"] = url_subida
                                            
                                            # Ejecutar actualización
                                            supabase.table("bitacora").update(datos_update).eq("id", item_id).execute()
                                            
                                            st.success("Registro actualizado.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error al guardar: {e}")

                           # ... (Código anterior del diálogo de edición se mantiene igual) ...

                            # ==========================================
                            # 2. LISTADO INTERACTIVO (MEJORADO)
                            # ==========================================
                            st.markdown("##### 📜 Historial de Gestión")
                            
                            try:
                                bitacora = supabase.table("bitacora").select("*").eq("orden_id", row['id']).order("fecha", desc=True).execute()
                                
                                if bitacora.data:
                                    for b in bitacora.data:
                                        with st.container():
                                            c_info, c_actions = st.columns([5, 1])
                                            
                                            # --- COLUMNA IZQUIERDA: INFORMACIÓN ---
                                            with c_info:
                                                fecha_fmt = b['fecha'][:10] + " " + b['fecha'][11:16]
                                                url = b['archivo_url']
                                                
                                                # Lógica de Iconos y Formatos
                                                adjunto_html = ""
                                                if url:
                                                    url_lower = url.lower()
                                                    nombre_archivo = "Ver Adjunto"
                                                    
                                                    # Detectar tipo de archivo por extensión
                                                    if url_lower.endswith(('.jpg', '.jpeg', '.png', '.webp')):
                                                        adjunto_html = f"""<br><a href="{url}" target="_blank" style="text-decoration:none; color: #10B981;">🖼️ <b>Ver Imagen</b></a>"""
                                                    elif url_lower.endswith('.pdf'):
                                                        adjunto_html = f"""<br><a href="{url}" target="_blank" style="text-decoration:none; color: #EF4444;">📄 <b>Descargar PDF</b></a>"""
                                                    elif url_lower.endswith('.msg'):
                                                        adjunto_html = f"""<br><a href="{url}" target="_blank" style="text-decoration:none; color: #3B82F6;">📧 <b>Descargar Correo (.msg)</b></a>"""
                                                    elif url_lower.endswith(('.doc', '.docx')):
                                                        adjunto_html = f"""<br><a href="{url}" target="_blank" style="text-decoration:none; color: #2563EB;">📝 <b>Descargar Word</b></a>"""
                                                    elif url_lower.endswith(('.xls', '.xlsx')):
                                                        adjunto_html = f"""<br><a href="{url}" target="_blank" style="text-decoration:none; color: #16A34A;">📊 <b>Descargar Excel</b></a>"""
                                                    else:
                                                        # Archivo genérico
                                                        adjunto_html = f"""<br><a href="{url}" target="_blank" style="text-decoration:none; color: #F59E0B;">📎 <b>Descargar Archivo</b></a>"""

                                                # Renderizar tarjeta
                                                st.markdown(f"""
                                                <div style="background-color: rgba(255,255,255,0.05); border-left: 3px solid #F59E0B; padding: 10px; border-radius: 0 5px 5px 0; margin-bottom: 5px;">
                                                    <div style="display:flex; justify-content:space-between; color: #9CA3AF; font-size: 0.85em;">
                                                        <span>📅 {fecha_fmt}</span>
                                                        <span>👤 <b>{b['usuario_text']}</b></span>
                                                    </div>
                                                    <div style="margin-top: 5px; color: #E5E7EB; white-space: pre-wrap;">{b['mensaje']}</div>
                                                    {adjunto_html}
                                                </div>
                                                """, unsafe_allow_html=True)

                                            # --- COLUMNA DERECHA: BOTONES ---
                                            with c_actions:
                                                if st.button("✏️", key=f"btn_edit_{b['id']}", help="Editar"):
                                                    editar_avance_dialog(b['id'], b['mensaje'], b['archivo_url'])
                                                
                                                if st.button("🗑️", key=f"btn_del_{b['id']}", help="Eliminar"):
                                                    supabase.table("bitacora").delete().eq("id", b['id']).execute()
                                                    st.toast("Eliminado")
                                                    time.sleep(0.5)
                                                    st.rerun()
                                            
                                            st.write("") 
                                else:
                                    st.caption("No hay avances registrados aún.")
                                    
                            except Exception as e:
                                st.error(f"Error cargando historial: {e}")
                            # ==========================================
                            # FIN DEL LISTADO
                            # ==========================================

                            st.divider() # Aquí sigue tu código del formulario de "Registrar Nuevo Avance"...

                            # B) Formulario para NUEVO AVANCE
                            # Importante: clear_on_submit=True limpia el texto después de enviar
                            with st.form(key=f"form_bitacora_{row['id']}", clear_on_submit=True):
                                st.markdown("##### ➕ Registrar Nuevo Avance")
                                c_msg, c_file = st.columns([2, 1])
                                nuevo_mensaje = c_msg.text_area("Detalle de la gestión", placeholder="Ej: Recibí la cotización del proveedor X...", height=100)

                                archivo_gestion = c_file.file_uploader("Adjuntar (PDF, Word, Foto, Email .msg)", type=["pdf", "docx", "xlsx", "jpg", "png", "msg"])
                                
                                col_btns = st.columns([1, 1])
                                btn_avanzar = col_btns[0].form_submit_button("💾 REGISTRAR AVANCE", type="primary")
                                btn_cerrar_admin = col_btns[1].form_submit_button("✅ FINALIZAR GESTIÓN (CERRAR ORDEN)")

                                if btn_avanzar:
                                    if not nuevo_mensaje:
                                        st.error("Escribe un detalle.")
                                    else:
                                        url_doc = None
                                        if archivo_gestion:
                                            with st.spinner("Subiendo documento..."):
                                                # Usamos la función nueva que creamos en el PASO 2
                                                url_doc = subir_archivo_generico(archivo_gestion)
                                        
                                        try:
                                            supabase.table("bitacora").insert({
                                                "orden_id": row['id'],
                                                "usuario_text": usuario,
                                                "mensaje": nuevo_mensaje,
                                                "archivo_url": url_doc
                                            }).execute()
                                            st.success("Avance registrado.")
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error guardando bitácora: {e}")

                                if btn_cerrar_admin:
                                    try:
                                        supabase.table("ordenes").update({
                                            "estado": "Concluida",
                                            "comentarios_cierre": f"[CIERRE ADMINISTRATIVO] {nuevo_mensaje if nuevo_mensaje else 'Gestión finalizada.'}",
                                            "fecha_cierre": datetime.now().isoformat()
                                        }).eq("id", row['id']).execute()
                                        st.success("Gestión finalizada y orden cerrada.")
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"Error cerrando orden: {e}")
            else:
                st.warning("No se pudo identificar tu usuario Admin en la base de datos.")

# 1. BUZÓN DE VALIDACIÓN
        with tab_buzon:
            if df_solicitudes.empty:
                st.markdown("<div style='text-align: center; padding: 40px; color: #6B7280;'><h3>✨ Todo limpio</h3><p>No hay solicitudes pendientes.</p></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"### 📥 Solicitudes Pendientes ({len(df_solicitudes)})")
                if not df_act.empty:
                    act_map_nombre_id = dict(zip(df_act['nombre'], df_act['id']))
                    lista_nombres_activos = sorted(list(act_map_nombre_id.keys()))
                    
                    for idx, sol in df_solicitudes.iterrows():
                        # --- INICIO DEL FORMULARIO (Evita el refresco al mover el slider) ---
                        with st.form(key=f"form_sol_{sol['id']}"):
                            st.markdown(f"""
                            <div style="border: 1px solid #374151; border-radius: 8px; padding: 15px; margin-bottom: 15px; background-color: #1F2937;">
                                <div style="display:flex; justify-content:space-between;"><h4 style="color: #F59E0B; margin: 0;">Solicitud #{sol['id']}</h4><span style="color: #6B7280; font-size: 0.8em;">📅 {sol['fecha_solicitud'][:10]}</span></div>
                                <p style="margin: 5px 0; color: #D1D5DB;">👤 <b>Solicita:</b> {sol['solicitante_id']}</p>
                                <p style="margin: 5px 0; color: #E5E7EB; background: rgba(255,255,255,0.05); padding: 8px; border-radius: 4px;">📝 <i>"{sol['descripcion']}"</i></p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            cols_val = st.columns([1, 2, 2, 1])
                            with cols_val[0]:
                                if sol['foto_url']: st.image(sol['foto_url'], width=80)
                                else: st.caption("Sin foto")
                            
                            with cols_val[1]:
                                activo_final_nombre = st.selectbox(
                                    "Vincular Activo", 
                                    lista_nombres_activos, 
                                    index=None, 
                                    placeholder="🔍 Buscar activo..."
                                )
                                
                                tipo_ot = st.selectbox(
                                    "Tipo Mant.", 
                                    ["Correctivo", "Preventivo", "Predictivo", "Mejora"], 
                                    index=None,
                                    placeholder="Seleccionar tipo..."
                                )
                            
                            with cols_val[2]:
                                tech_options = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
                                
                                asignar_a = st.selectbox(
                                    "Asignar a", 
                                    list(tech_options.keys()), 
                                    index=None,
                                    placeholder="Seleccionar técnico..."
                                )
                                
                                sug = sol['prioridad_sugerida']
                                val_defecto = sug if sug in ["Baja", "Media", "Alta", "Crítica"] else "Media"
                                # Al estar dentro de st.form, este slider YA NO refrescará la página
                                criticidad_final = st.select_slider("Definir Criticidad", options=["Baja", "Media", "Alta", "Crítica"], value=val_defecto)
                            
                            with cols_val[3]:
                                st.markdown("<br>", unsafe_allow_html=True)
                                # Usamos form_submit_button para ambos casos
                                btn_crear = st.form_submit_button("✅ CREAR", type="primary", use_container_width=True)
                                btn_rechazar = st.form_submit_button("❌ RECHAZAR", type="secondary", use_container_width=True)

                            # --- LÓGICA DE BOTONES ---
                            if btn_crear:
                                # Validación: Solo exigimos datos si se va a CREAR
                                if not activo_final_nombre or not tipo_ot or not asignar_a:
                                    st.error("⚠️ Falta seleccionar: Activo, Tipo o Técnico.")
                                else:
                                    try:
                                        res_orden = supabase.table("ordenes").insert({
                                                "activo_id": int(act_map_nombre_id[activo_final_nombre]),
                                                "chat_id": sol.get('chat_id'),
                                                "descripcion": f"[Solicitud #{sol['id']}] {sol['descripcion']}",
                                                "criticidad": criticidad_final,
                                                "tipo_mantenimiento": tipo_ot,
                                                "estado": "Abierta",
                                                "tecnico_asignado": str(tech_options[asignar_a]),
                                                "fecha_creacion": datetime.now().isoformat(),
                                        }).execute()
                                        
                                        nuevo_id = res_orden.data[0]['id'] if res_orden.data else "##"
                                        msj_ok = f"✅ **¡Solicitud Aprobada!**\n\nOrden **#{nuevo_id}** ({tipo_ot}). Prioridad: {criticidad_final}."
                                        notificar_telegram(sol.get('chat_id'), msj_ok)
                                        supabase.table("solicitudes").update({"estado": "Aprobada"}).eq("id", sol['id']).execute()
                                        st.success("Orden creada.")
                                        st.rerun()
                                    except Exception as e: st.error(f"Error: {e}")
                            
                            if btn_rechazar:
                                # Si rechaza, no importan los selectboxes vacíos
                                supabase.table("solicitudes").update({"estado": "Rechazada"}).eq("id", sol['id']).execute()
                                notificar_telegram(sol.get('chat_id'), "🚫 Solicitud Rechazada.")
                                st.warning("Rechazada.")
                                st.rerun()

        # 2. CONTROL DE CALIDAD
        with tab_calidad:
            df_revision = run_query("ordenes", {"estado": "Por Validar"})
            if df_revision.empty:
                st.markdown("<div style='text-align: center; padding: 40px; color: #10B981;'><h3>✨ Todo revisado</h3><p>No hay trabajos pendientes.</p></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"### 🧐 Auditoría de Trabajos ({len(df_revision)})")
                for idx, row in df_revision.iterrows():
                    nombre_activo = df_act[df_act['id'] == row['activo_id']].iloc[0]['nombre'] if not df_act.empty else "N/A"
                    tecnico_nombre = "Desconocido"
                    if not df_users.empty:
                        t_data = df_users[df_users['id'].astype(str) == row['tecnico_asignado']]
                        if not t_data.empty: tecnico_nombre = t_data.iloc[0]['nombre']
                    
                    with st.container():
                        st.markdown(f"""<div style="border: 1px solid #4B5563; border-radius: 8px; padding: 20px; margin-bottom: 20px; background-color: #1F2937;">
                            <h3 style="color: #60A5FA; margin:0;">OT #{row['id']} | {nombre_activo}</h3>
                            <p style="color: #9CA3AF;">👷 Realizado por: <b>{tecnico_nombre}</b></p><hr style="border-color: #374151;">""", unsafe_allow_html=True)
                        
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
                                    notificar_telegram(row.get('chat_id'), f"🎉 **¡Solucionado!**\n\nOrden **#{row['id']}** cerrada.\n📝 Solución: {row.get('comentarios_cierre')}", row.get('foto_cierre_url'))
                                st.success("Orden cerrada.")
                                st.rerun()
                            
                            st.markdown("<br>", unsafe_allow_html=True)
                            with st.expander("↩️ Devolver (Rechazar)"):
                                motivo = st.text_input("Motivo", key=f"mot_{row['id']}")
                                if st.button("CONFIRMAR DEVOLUCIÓN", key=f"dev_{row['id']}", type="secondary", use_container_width=True):
                                    if motivo:
                                        supabase.table("ordenes").update({"estado": "Abierta", "comentarios_validacion": f"DEVUELTA: {motivo}"}).eq("id", row['id']).execute()
                                        st.warning("Devuelta.")
                                        st.rerun()
                                    else: st.error("Falta motivo.")
                        st.markdown("</div>", unsafe_allow_html=True)

        # 3. GESTIÓN GLOBAL (CON PDF)
        with tab_gestion:
            st.markdown("### 🎛️ Control Central de Órdenes")
            # --- 🔵 LÓGICA DE RECEPCIÓN (Órdenes) ---
            filtro_ot_externo = None
            if st.session_state.get('jump_target') == 'orden' and st.session_state.get('jump_id'):
                filtro_ot_externo = st.session_state.jump_id
                st.toast(f"📍 Filtrando Orden #{filtro_ot_externo}", icon="🔍")
                # Limpiamos variables de sesión
                st.session_state.jump_target = None
                st.session_state.jump_id = None
            col_filtros = st.columns(3)
            filtro_estado = col_filtros[0].selectbox("Filtrar Estado", ["Todas", "Abierta", "Por Validar", "Concluida"], index=0)
            
            df_display = df_ordenes.copy()
            if filtro_estado != "Todas":
                df_display = df_display[df_display['estado'] == filtro_estado]
            
            # --- 🔵 APLICAR FILTRO ID EXTERNO ---
            if filtro_ot_externo:
                df_display = df_display[df_display['id'].astype(str) == str(filtro_ot_externo)]
            if filtro_estado != "Todas": df_display = df_display[df_display['estado'] == filtro_estado]
            
            if not df_display.empty:
                map_act = dict(zip(df_act['id'], df_act['nombre'])) if not df_act.empty else {}
                map_user = dict(zip(df_users['id'].astype(str), df_users['nombre'])) if not df_users.empty else {}
                df_display['Activo Nombre'] = df_display['activo_id'].map(map_act).fillna("Desconocido")
                df_display['Técnico Nombre'] = df_display['tecnico_asignado'].map(map_user).fillna("Sin Asignar")
                df_display = df_display.sort_values('id', ascending=False)
                
                event = st.dataframe(df_display[['id', 'estado', 'Activo Nombre', 'descripcion', 'Técnico Nombre', 'criticidad', 'fecha_creacion']], use_container_width=True, hide_index=True, selection_mode="single-row", on_select="rerun", height=300)
                
                if len(event.selection.rows) > 0:
                    idx_tabla = event.selection.rows[0]
                    id_orden_selec = df_display.iloc[idx_tabla]['id']
                    orden_actual = df_ordenes[df_ordenes['id'] == id_orden_selec].iloc[0]
                    
                    st.divider()
                    c_head1, c_head2 = st.columns([3, 1])
                    with c_head1: st.markdown(f"#### ✏️ Editando Orden #{id_orden_selec}")
                    with c_head2:
                        if orden_actual['estado'] in ['Concluida', 'Por Validar']:
                            try:
                                pdf_data = generar_pdf_orden(orden_actual, df_display.iloc[idx_tabla]['Activo Nombre'], df_display.iloc[idx_tabla]['Técnico Nombre'])
                                st.download_button("📄 Descargar PDF", data=pdf_data, file_name=f"Reporte_OT_{id_orden_selec}.pdf", mime="application/pdf", key=f"btn_pdf_{id_orden_selec}")
                            except: st.error("Error PDF")

                    with st.form(key=f"form_edit_orden_{id_orden_selec}"):
                        c_edit1, c_edit2, c_edit3 = st.columns(3)
                        est_opts = ["Abierta", "Por Validar", "Concluida", "Cancelada"]
                        nuevo_estado = c_edit1.selectbox("Estado", est_opts, index=est_opts.index(orden_actual['estado']) if orden_actual['estado'] in est_opts else 0)
                        
                        lista_tecnicos = df_users[df_users['rol'].isin(['Tecnico', 'Admin', 'Programador'])]
                        tech_dict = dict(zip(lista_tecnicos['nombre'], lista_tecnicos['id']))
                        tech_actual_id = str(orden_actual['tecnico_asignado'])
                        nombre_tech = next((k for k, v in tech_dict.items() if str(v) == tech_actual_id), "Seleccionar...")
                        nuevo_tec_nom = c_edit2.selectbox("Reasignar", list(tech_dict.keys()), index=list(tech_dict.keys()).index(nombre_tech) if nombre_tech in tech_dict else 0)
                        
                        nueva_crit = c_edit3.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"], value=orden_actual['criticidad'])
                        nueva_desc = st.text_area("Descripción", value=orden_actual['descripcion'])
                        
                        if st.form_submit_button("💾 GUARDAR CAMBIOS", type="primary"):
                            supabase.table("ordenes").update({"estado": nuevo_estado, "tecnico_asignado": str(tech_dict[nuevo_tec_nom]), "criticidad": nueva_crit, "descripcion": nueva_desc}).eq("id", id_orden_selec).execute()
                            st.success("Actualizado."); st.rerun()

                    with st.expander("🗑️ Zona de Peligro"):
                        if st.button("ELIMINAR DEFINITIVAMENTE", key=f"del_{id_orden_selec}", type="secondary"):
                            supabase.table("ordenes").delete().eq("id", id_orden_selec).execute()
                            st.success("Eliminado."); st.rerun()
            else: st.info("Sin datos.")

        # 4. CREAR DIRECTA
        
        # 4. CREAR DIRECTA
        with tab_crear_directa:
            st.info("Creación rápida: Los campos se limpiarán automáticamente al guardar.")
            
            if not df_act.empty:
                act_dict = dict(zip(df_act['nombre'], df_act['id']))
                
                # Usamos clear_on_submit=True para limpiar todo al terminar
                with st.form("ot_directa", clear_on_submit=True):
                    
                    sel_act_dir = st.selectbox("Activo", sorted(act_dict.keys())) 
                    
                    c1, c2 = st.columns(2)
                    tipo_d = c1.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo", "Mejora"])
                    crit_d = c2.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
                    
                    desc_d = st.text_area("Descripción")
                    
                    tech_opts_d = {u['nombre']: u['id'] for i, u in df_users.iterrows()}
                    asig_d = st.selectbox("Asignar", list(tech_opts_d.keys()))
                    
                    st.markdown("---")
                    st.markdown("##### 📎 Adjuntos Iniciales")
                    archivo_inicial = st.file_uploader("Soporte (PDF, Excel, Foto, Correo)", 
                                                     type=["pdf", "docx", "xlsx", "jpg", "png", "msg"],
                                                     help="Este archivo se guardará automáticamente en la bitácora de la orden.")

                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if st.form_submit_button("CREAR ORDEN", type="primary", use_container_width=True):
                        if not desc_d:
                            st.error("La descripción es obligatoria.")
                        else:
                            try:
                                # 1. CREAR LA ORDEN PRIMERO
                                res_orden = supabase.table("ordenes").insert({
                                    "activo_id": int(act_dict[sel_act_dir]), 
                                    "descripcion": desc_d, 
                                    "criticidad": crit_d, 
                                    "tipo_mantenimiento": tipo_d,
                                    "estado": "Abierta", 
                                    "tecnico_asignado": str(tech_opts_d[asig_d]), 
                                    "fecha_creacion": datetime.now().isoformat()
                                }).execute()
                                
                                if res_orden.data:
                                    nuevo_id_ot = res_orden.data[0]['id']
                                    st.success(f"✅ Orden #{nuevo_id_ot} creada correctamente.")
                                    
                                    # 2. SI HAY ARCHIVO, SUBIRLO A LA BITÁCORA DE ESA ORDEN
                                    if archivo_inicial:
                                        with st.spinner("Subiendo archivo adjunto..."):
                                            url_doc = subir_archivo_generico(archivo_inicial)
                                            
                                            if url_doc:
                                                supabase.table("bitacora").insert({
                                                    "orden_id": nuevo_id_ot,
                                                    "usuario_text": usuario, # Variable global del usuario logueado
                                                    "mensaje": "📎 Documento inicial adjunto al crear la orden.",
                                                    "archivo_url": url_doc,
                                                    "fecha": datetime.now().isoformat()
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

        # 5. ✅ MÓDULO NUEVO: MANTENIMIENTO PREVENTIVO
        with tab_preventivos:
            # Llamamos a la función que pegaste anteriormente
            # (Asegúrate de haber copiado la función render_tab_preventivos en el PASO 2)
            render_tab_preventivos(df_act, df_users)
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
                                "documento": documento, "nombre": nombre, "password": password, "rol": rol
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
            user_options = {f"{row['nombre']} (ID: {row['id']})": row['id'] for _, row in df_users.iterrows()}
            user_options_list = ["-- Seleccione un usuario --"] + list(user_options.keys())
            
            selected_option = st.selectbox("Usuario:", user_options_list, key="user_selector")

            st.markdown("### Lista Completa de Usuarios")
            st.dataframe(df_users[['id', 'documento', 'nombre', 'rol']], hide_index=True, use_container_width=True)

            if selected_option != "-- Seleccione un usuario --":
                user_id = user_options[selected_option]
                selected_user = df_users[df_users['id'] == user_id].iloc[0]

                st.markdown("---")
                st.markdown(f"### Editando: **{selected_user['nombre']}** (ID: {user_id})")

                with st.form(key=f"edit_user_form_{user_id}"):
                    c1, c2 = st.columns(2)
                    edit_doc = c1.text_input("Documento/ID", value=selected_user['documento'])
                    edit_name = c2.text_input("Nombre Completo", value=selected_user['nombre'])
                    rol_options = ["Tecnico", "Programador", "Admin"]
                    current_rol_index = rol_options.index(selected_user['rol']) if selected_user['rol'] in rol_options else 0
                    new_rol = st.selectbox("Rol", rol_options, index=current_rol_index)
                    new_password = st.text_input("Nueva Contraseña (Dejar vacío para no cambiar)", type="password")

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
                            update_data = {"documento": edit_doc, "nombre": edit_name, "rol": new_rol}
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
                        <div style='background: rgba(239, 68, 68, 0.15); border: 2px solid #EF4444; border-radius: 8px; padding: 20px; text-align: center;'>
                            <p style='color: #FCA5A5; margin: 0; font-size: 1.1rem;'>⚠️ <strong>ELIMINACIÓN BLOQUEADA</strong></p>
                            <p style='color: #FEE2E2; margin-top: 10px; font-size: 0.95rem;'>El usuario <strong>{selected_user['nombre']}</strong> tiene Órdenes de Trabajo pendientes.<br>Debe cerrarlas o reasignarlas antes de eliminar este usuario.</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning(f"⚠️ Esta acción eliminará permanentemente al usuario **{selected_user['nombre']}**")
                    if st.button("🗑️ ELIMINAR USUARIO PERMANENTEMENTE", type="secondary", use_container_width=True, key=f"delete_btn_{user_id}"):
                        try:
                            supabase.table("usuarios").delete().eq("id", user_id).execute()
                            st.cache_data.clear()
                            agregar_notificacion('delete', f'Usuario {selected_user["nombre"]} eliminado.')
                            st.rerun()
                        except Exception as e:
                            agregar_notificacion('error', f'Error al eliminar: {e}')
        else:
            st.info("No se encontraron usuarios en la base de datos. Use la pestaña 'CREAR USUARIO'.")



