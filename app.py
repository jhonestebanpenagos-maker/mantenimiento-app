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

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="centered", initial_sidebar_state="collapsed")

# ==============================================================================
# 🎨 ZONA DE PERSONALIZACIÓN: TEMA "INDUSTRIAL PRIME" (ROBOT/ENGRANAJES)
# ==============================================================================
# ¡HEMOS CAMBIADO TOTALMENTE EL CSS AQUÍ!

# URL del GIF de fondo (Engranajes oscuros).
# Puedes cambiar este enlace por otro GIF que te guste más.
URL_FONDO_ENGRANAJES = "https://i.gifer.com/origin/e4/e467ab52993afdd8a9dd9ab9f2a589d4_w200.gif"

# Colores principales del tema
COLOR_ACERO_OSCURO = "#0a192f"
COLOR_AZUL_ELECTRICO = "#64ffda"
COLOR_OCRE_DORADO = "#d4af37"
COLOR_BRONCE = "#b4941f"
COLOR_ALERTA = "#ff5555"

# Inyección de CSS AVANZADO para el efecto Robot
st.markdown(f"""
    <style>
    /* --- 1. FONDO ANIMADO Y ESTRUCTURA PRINCIPAL --- */
    .stApp {{
        /* Capa de fondo con el GIF animado */
        background-image: linear-gradient(rgba(10, 25, 47, 0.85), rgba(10, 25, 47, 0.95)), url('{URL_FONDO_ENGRANAJES}');
        background-size: cover;
        background-attachment: fixed;
        background-position: center;
        color: #e6f1ff; /* Color de texto general (blanco azulado) */
    }}
    
    /* Títulos en Ocre Dorado */
    h1, h2, h3 {{
        color: {COLOR_OCRE_DORADO} !important;
        text-transform: uppercase;
        letter-spacing: 1px;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
    }}

    /* --- 2. BARRA LATERAL (SIDEBAR) --- */
    [data-testid="stSidebar"] {{
        background-color: #020c1b; /* Metal muy oscuro */
        border-right: 3px solid {COLOR_BRONCE};
        box-shadow: 5px 0 15px rgba(0,0,0,0.5);
    }}
    [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
         color: {COLOR_AZUL_ELECTRICO} !important;
    }}

    /* --- 3. INPUTS Y SELECTORES (Estilo Panel de Control) --- */
    /* El fondo de los inputs */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
        background-color: rgba(23, 42, 69, 0.8) !important; /* Azul oscuro semitransparente */
        border: 2px solid {COLOR_BRONCE} !important; /* Borde metálico ocre */
        color: {COLOR_OCRE_DORADO} !important; /* Texto dorado */
        border-radius: 4px;
    }}
    /* Cuando haces foco en un input */
    .stTextInput input:focus, .stTextArea textarea:focus, .stSelectbox > div > div:focus-within {{
        border-color: {COLOR_AZUL_ELECTRICO} !important; /* Brillo azul al seleccionar */
        box-shadow: 0 0 10px {COLOR_AZUL_ELECTRICO};
    }}
    /* El texto de las etiquetas de los inputs */
    .stTextInput label, .stSelectbox label, .stTextArea label {{
        color: {COLOR_AZUL_ELECTRICO} !important;
        font-weight: bold;
    }}

    /* --- 4. BOTONES (Estilo Placa Metálica) --- */
    div.stButton > button:first-child {{
        background: linear-gradient(180deg, {COLOR_OCRE_DORADO} 0%, {COLOR_BRONCE} 100%) !important;
        color: #0a192f !important; /* Texto oscuro sobre dorado */
        border: 2px solid #8c7012 !important;
        font-weight: bold;
        text-transform: uppercase;
        box-shadow: 0 4px 0px #5e4b0d; /* Efecto 3D de botón físico */
        transition: all 0.1s ease;
    }}
    div.stButton > button:first-child:hover {{
        background: linear-gradient(180deg, #ffe066 0%, {COLOR_OCRE_DORADO} 100%) !important;
        transform: translateY(2px);
        box-shadow: 0 2px 0px #5e4b0d;
    }}
    div.stButton > button:first-child:active {{
        transform: translateY(4px);
        box-shadow: none;
    }}

    /* --- 5. TARJETAS Y CONTENEDORES PERSONALIZADOS --- */
    .card-style {{
        background: linear-gradient(135deg, #112240, #0a192f); /* Degradado metálico oscuro */
        padding: 25px;
        border-radius: 8px;
        /* Borde doble para parecer atornillado */
        border: 3px solid {COLOR_BRONCE};
        box-shadow: inset 0 0 20px rgba(0,0,0,0.8), 0 10px 20px rgba(0,0,0,0.3);
        margin-bottom: 25px;
        position: relative;
    }}
    /* Pequeños detalles como tornillos en las esquinas (simulados) */
    .card-style::before {{
        content: ''; position: absolute; top: 5px; left: 5px; width: 10px; height: 10px; 
        background: {COLOR_OCRE_DORADO}; border-radius: 50%; box-shadow: 2px 2px 2px black;
    }}
    .card-style::after {{
        content: ''; position: absolute; top: 5px; right: 5px; width: 10px; height: 10px; 
        background: {COLOR_OCRE_DORADO}; border-radius: 50%; box-shadow: -2px 2px 2px black;
    }}
    
    /* --- 6. ALERTAS Y ZONAS DE PELIGRO --- */
    .stAlert {{
        background-color: rgba(23, 42, 69, 0.9) !important;
        border: 2px solid {COLOR_AZUL_ELECTRICO};
    }}
    .danger-zone {{
        background: repeating-linear-gradient(
          45deg,
          #3b1717,
          #3b1717 10px,
          #290f0f 10px,
          #290f0f 20px
        );
        border: 3px dashed {COLOR_ALERTA};
        padding: 20px;
        text-align: center;
        color: {COLOR_ALERTA};
        text-shadow: 1px 1px 2px black;
    }}

    /* Estilo para las tablas */
    [data-testid="stTable"] {{
        background-color: #112240;
        border: 1px solid {COLOR_BRONCE};
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
    except:
        return None

supabase = init_supabase()
if not supabase:
    st.error("Error conectando a Supabase. Revisa los Secrets.")
    st.stop()

# --- 3. FUNCIONES AUXILIARES ---

def run_query(table_name):
    try:
        response = supabase.table(table_name).select("*").order("id").execute()
        return pd.DataFrame(response.data)
    except:
        return pd.DataFrame()

def subir_imagen(archivo, carpeta="evidencias"):
    if archivo:
        try:
            if isinstance(archivo, bytes):
                file_bytes = archivo
                file_name = f"qr_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                mime_type = "image/png"
            else:
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
                file_bytes = archivo.getvalue()
                mime_type = archivo.type

            supabase.storage.from_(carpeta).upload(path=file_name, file=file_bytes, file_options={"content-type": mime_type})
            return supabase.storage.from_(carpeta).get_public_url(file_name)
        except:
            return None
    return None

def generar_qr_activo(id_activo, nombre_activo):
    # ==============================================================================
    # 🔗 TU URL REAL INTEGRADA AQUÍ
    # ==============================================================================
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

# --- FUNCION PARA MOSTRAR MENSAJES GUARDADOS (ANIMACIONES) ---
def mostrar_notificaciones():
    if 'notification' in st.session_state:
        notif = st.session_state['notification']
        if notif:
            tipo = notif.get('type')
            msg = notif.get('message')
            
            if tipo == 'success':
                st.balloons()
                # Notificación estilo "Panel de Control Exitoso"
                st.markdown(f"""
                <div style="padding: 20px; border-radius: 10px; background: linear-gradient(135deg, #0f3d2a, #0a1f16); color: #64ffda; border: 3px solid #64ffda; margin-bottom: 20px; text-align: center; box-shadow: 0 0 15px #64ffda;">
                    <h2 style="margin:0; text-transform: uppercase;">⚡ Operación Exitosa ⚡</h2>
                    <p style="font-size: 18px; margin:10px 0 0 0;">{msg}</p>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1) 
            
            elif tipo == 'delete':
                # Notificación estilo "Alerta Roja"
                st.markdown(f"""
                <div style="padding: 20px; border-radius: 10px; background: linear-gradient(135deg, #3d0f0f, #1f0a0a); color: #ff5555; border: 3px solid #ff5555; margin-bottom: 20px; text-align: center; box-shadow: 0 0 15px #ff5555;">
                    <h3 style="margin:0; text-transform: uppercase;">🗑️ PROTOCOLO DE ELIMINACIÓN COMPLETADO</h3>
                    <p>{msg}</p>
                </div>
                """, unsafe_allow_html=True)
        
        del st.session_state['notification']

# ==============================================================================
# 🚀 ZONA 1: INTERCEPTOR PÚBLICO (ACCESO SIN LOGIN)
# ==============================================================================
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    try:
        datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    except:
        st.error("Error de conexión pública.")
        st.stop()
    
    if datos_activo.data:
        activo = datos_activo.data[0]
        # VISTA PÚBLICA
        st.markdown(f"<h1 style='text-align: center;'>🤖 FICHA TÉCNICA: {activo['nombre']}</h1>", unsafe_allow_html=True)
        
        # Usamos la nueva clase card-style
        st.markdown(f"""
            <div class="card-style">
                <h3 style="margin-top:0; color: {COLOR_AZUL_ELECTRICO} !important;">Detalles del Equipo</h3>
                <p><strong>📍 Área:</strong> <span style="color:{COLOR_OCRE_DORADO}">{activo.get('area', 'N/A')}</span></p>
                <p><strong>🏢 Ubicación:</strong> <span style="color:{COLOR_OCRE_DORADO}">{activo['ubicacion']}</span></p>
                <p><strong>🔧 Categoría:</strong> <span style="color:{COLOR_OCRE_DORADO}">{activo.get('categoria', 'N/A')}</span></p>
            </div>
        """, unsafe_allow_html=True)

        st.subheader("🛠️ Historial de Mantenimiento")
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).limit(5).execute()
            if ots.data:
                df_qr = pd.DataFrame(ots.data)
                st.table(df_qr[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Este equipo no tiene historial registrado.")
        except: pass
            
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 Inicio"):
                st.query_params.clear()
                st.rerun()
        with c2:
            if st.session_state.get('usuario') is None:
                if st.button("🔐 Soy Técnico"):
                    st.query_params.clear()
                    st.rerun()
    else:
        st.error("❌ El activo escaneado no existe o fue eliminado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    st.stop() 


# ==============================================================================
# 🚀 ZONA 2: PORTAL DE ACCESO (LOGIN O ESCÁNER VISITANTE)
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    st.markdown("<h1 style='text-align: center;'>⚙️ CMMS INDUSTRIAL PRIME ⚙️</h1>", unsafe_allow_html=True)
    
    # Estilo personalizado para los Tabs del login
    st.markdown(f"""
        <style>
            .stTabs [data-baseweb="tab-list"] {{
                background-color: #112240;
                border-radius: 10px;
                padding: 5px;
                border: 2px solid {COLOR_BRONCE};
            }}
            .stTabs [data-baseweb="tab"] {{
                color: {COLOR_OCRE_DORADO};
            }}
            .stTabs [aria-selected="true"] {{
                background-color: {COLOR_BRONCE} !important;
                color: #0a192f !important;
                font-weight: bold;
                border-radius: 5px;
            }}
        </style>
    """, unsafe_allow_html=True)

    tab_login, tab_scan = st.tabs(["🔐 ACCESO PERSONAL", "📷 ESCÁNER VISITANTE"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            # Wrap del login en una tarjeta metálica
            st.markdown("<div class='card-style' style='text-align:center;'><h3>Credenciales de Acceso</h3>", unsafe_allow_html=True)
            with st.form("login_form"):
                documento = st.text_input("Documento ID")
                password = st.text_input("Código de Acceso", type="password")
                submitted = st.form_submit_button("INICIAR SISTEMA", type="primary", use_container_width=True)
                
                if submitted:
                    try:
                        response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()
                        if response.data:
                            user_data = response.data[0]
                            st.session_state['usuario'] = user_data['nombre']
                            st.session_state['rol'] = user_data['rol']
                            st.rerun()
                        else:
                            st.error("Credenciales inválidas.")
                    except:
                        st.error("Fallo de conexión con el núcleo de datos.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_scan:
        st.markdown("<div class='card-style' style='text-align:center;'>", unsafe_allow_html=True)
        st.info("📷 Apunte la cámara al código QR del equipo.")
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        if img_file is not None:
            id_detectado = leer_qr_imagen(img_file)
            if id_detectado:
                st.query_params["id_activo_qr"] = id_detectado
                st.rerun()
            else:
                st.warning("⚠️ QR no detectado. Intente ajustar el enfoque.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# 🚀 ZONA 3: DASHBOARD PRIVADO (CON NUEVO TEMA)
# ==============================================================================

rol_actual = st.session_state['rol']
usuario_actual = st.session_state['usuario']

# --- BARRA LATERAL ---
with st.sidebar:
    # Tarjeta de usuario estilo metálico
    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #112240, #0a192f); padding: 15px; border-radius: 10px; text-align: center; margin-bottom: 20px; color: {COLOR_OCRE_DORADO}; border: 2px solid {COLOR_BRONCE}; box-shadow: inset 0 0 15px rgba(0,0,0,0.5);">
            <h2 style="margin:0; text-shadow: 0 0 10px {COLOR_OCRE_DORADO};">👤</h2>
            <h3 style="margin:10px 0; font-size: 18px; letter-spacing: 2px;">{usuario_actual.upper()}</h3>
            <div style="background-color: {COLOR_BRONCE}; color: #0a192f; padding: 2px 10px; border-radius: 4px; display: inline-block; font-weight: bold; font-size: 12px;">
                {rol_actual.upper()}
            </div>
        </div>
    """, unsafe_allow_html=True)
    
    if st.button("Cerrar Sesión", use_container_width=True): logout()
    st.write("") 

    options_menu = []
    if rol_actual == "Admin": 
        options_menu = ["Dashboard", "Gestión de Activos", "Crear Orden", "Cierre de OTs", "Usuarios"]
    elif rol_actual == "Programador": 
        options_menu = ["Dashboard", "Crear Orden", "Usuarios"] 
    elif rol_actual == "Tecnico": 
        options_menu = ["Cierre de OTs"] 
    
    # MENÚ CON ESTILO INDUSTRIAL
    choice = option_menu(
        menu_title="PANEL DE CONTROL",
        options=options_menu,
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
        default_index=0,
        styles={
            "container": {"padding": "5px!important", "background-color": "#020c1b", "border": f"2px solid {COLOR_BRONCE}", "border-radius": "8px"},
            "menu-title": {"color": COLOR_OCRE_DORADO, "font-weight": "bold"},
            "icon": {"color": COLOR_AZUL_ELECTRICO, "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "color": "#e6f1ff", "--hover-color": "#112240"},
            "nav-link-selected": {"background": f"linear-gradient(90deg, {COLOR_BRONCE}, {COLOR_OCRE_DORADO})", "color": "#0a192f", "font-weight": "bold", "border": f"1px solid {COLOR_OCRE_DORADO}"},
        }
    )

# --- DICCIONARIOS ---
ESTRUCTURA_AREAS = {
    "Logística": ["Almacén Materia Prima", "Almacén Producto Terminado", "Distribución", "Taller Vehicular"],
    "Administración": ["Administración", "Servicios Generales"],
    "Técnica": ["Agua Cristal", "Linea 8", "Linea 2", "Linea 3", "Linea 1", "Linea 10", "Salas de Jarabe Terminado", "Sala de Jarabes Jugos", "Sala de Jarabe Simple", "Oficinas Técnicas", "Equipos Auxiliares", "Ptap", "Ptar"],
    "Ventas": ["Ventas", "Bodega de Publicidad"]
}
LISTA_CATEGORIAS = ["Mecánico", "Eléctrico", "Infraestructura", "HVAC", "Otros"]

# --- PANTALLAS ---

if choice == "Dashboard":
    st.subheader("Tablero de Control")
    mostrar_notificaciones()
    
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        # Métricas con estilo de tarjeta
        c1, c2, c3 = st.columns(3)
        st.markdown(f"""
            <style>
                [data-testid="stMetric"] {{
                    background: linear-gradient(135deg, #112240, #0a192f);
                    border: 2px solid {COLOR_BRONCE};
                    padding: 15px;
                    border-radius: 10px;
                    box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                }}
                [data-testid="stMetricLabel"] {{ color: {COLOR_AZUL_ELECTRICO} !important; }}
                [data-testid="stMetricValue"] {{ color: {COLOR_OCRE_DORADO} !important; text-shadow: 0 0 10px {COLOR_BRONCE}; }}
            </style>
        """, unsafe_allow_html=True)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        
        st.divider()
        
        # Gráficos (Streamlit no permite estilar mucho los gráficos nativos, pero el fondo oscuro ayuda)
        c1, c2, c3 = st.columns(3)
        with c1: 
            st.markdown("#### Estado de OTs")
            st.bar_chart(df_ordenes['estado'].value_counts(), color="#00b09b") 
        with c2: 
            st.markdown("#### Criticidad")
            st.bar_chart(df_ordenes['criticidad'].value_counts(), color="#ff6b6b")
        with c3: 
            st.markdown("#### Tipo Mantenimiento")
            if 'tipo_mantenimiento' in df_ordenes.columns: 
                st.bar_chart(df_ordenes['tipo_mantenimiento'].value_counts(), color="#ffaa00")
    else: st.info("Sin datos para analizar.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    
    if 'tab_index_activos' not in st.session_state: st.session_state['tab_index_activos'] = 0
    
    # Estilo personalizado para los tabs internos
    st.markdown(f"""<style> .stTabs [data-baseweb="tab-list"] {{ background-color: #0a192f; border: 1px solid {COLOR_BRONCE}; }} </style>""", unsafe_allow_html=True)

    selected_tab = option_menu(
        menu_title=None, 
        options=["Registrar Nuevo", "Editar / Imprimir QR"], 
        icons=["plus-square", "qr-code"], 
        orientation="horizontal", 
        default_index=st.session_state['tab_index_activos'],
        styles={
            "container": {"background-color": "#0a192f"},
            "nav-link": {"color": COLOR_AZUL_ELECTRICO},
            "nav-link-selected": {"background-color": COLOR_BRONCE, "color": "#0a192f", "font-weight":"bold"}
        }
    )
    
    if selected_tab == "Registrar Nuevo":
        if 'asset_reset_key' not in st.session_state: st.session_state.asset_reset_key = 0
        
        st.markdown(f"<div class='card-style'><h4>📍 Paso 1: Ubicación del Activo</h4>", unsafe_allow_html=True)
        area_selec = st.selectbox("Área Principal", [""] + list(ESTRUCTURA_AREAS.keys()), key=f"area_create_{st.session_state.asset_reset_key}")
        sub_areas = [""] + ESTRUCTURA_AREAS.get(area_selec, []) if area_selec else [""]
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown(f"<div class='card-style'><h4>⚙️ Paso 2: Datos Técnicos</h4>", unsafe_allow_html=True)
        with st.form("form_activo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("ID / Nombre del Equipo")
            ubicacion = c2.selectbox("Sub-Área / Ubicación Específica", sub_areas)
            categoria = st.selectbox("Categoría Técnica", [""] + LISTA_CATEGORIAS)
            
            if st.form_submit_button("💾 Guardar Activo y Generar QR"):
                if nombre and area_selec and ubicacion and categoria:
                    try:
                        res = supabase.table("activos").insert({
                            "nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria
                        }).execute()
                        
                        if res.data:
                            new_id = res.data[0]['id']
                            url_qr = generar_qr_activo(new_id, nombre)
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                            
                            # GUARDAMOS EL MENSAJE EN SESSION Y RECARGAMOS
                            st.session_state['notification'] = {'type': 'success', 'message': f"Activo '{nombre}' ingresado al sistema con éxito."}
                            st.session_state.asset_reset_key += 1
                            st.session_state['tab_index_activos'] = 0
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("⚠️ Faltan campos obligatorios para el registro.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected_tab == "Editar / Imprimir QR":
        st.session_state['tab_index_activos'] = 1 
        
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("🔍 Buscar Activo en Inventario", [""] + list(activos_dict.keys()))
            
            if seleccion:
                id_sel = activos_dict[seleccion]
                dato = df_activos[df_activos['id'] == id_sel].iloc[0]
                
                # Tarjeta de QR y Datos
                st.markdown(f"""
                <div class="card-style">
                    <h3 style="margin-top:0; color: {COLOR_OCRE_DORADO} !important;">{dato['nombre']}</h3>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns([1,3])
                with c1:
                    if dato.get('qr_url'): 
                        st.image(dato['qr_url'], caption="Matriz QR")
                    else: 
                        if st.button("Generar Matriz QR"):
                            url_qr = generar_qr_activo(id_sel, dato['nombre'])
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_sel)).execute()
                            st.rerun()
                with c2:
                    st.info("💡 Imprima esta matriz QR para el etiquetado físico del equipo.")
                
                # Edición
                st.markdown(f"<div class='card-style'><h4>🛠️ Modificar Datos</h4>", unsafe_allow_html=True)
                area_actual = dato.get('area', '')
                idx_area = 0
                if area_actual in ESTRUCTURA_AREAS: 
                    idx_area = ([""] + list(ESTRUCTURA_AREAS.keys())).index(area_actual)
                
                new_area = st.selectbox("Área Principal", [""] + list(ESTRUCTURA_AREAS.keys()), index=idx_area, key=f"edit_area_{id_sel}")
                sub_areas_disp = [""] + ESTRUCTURA_AREAS.get(new_area, []) if new_area else [""]
                ubic_actual = dato.get('ubicacion', '')
                idx_ubic = 0
                if ubic_actual in sub_areas_disp: idx_ubic = sub_areas_disp.index(ubic_actual)
                
                with st.form("edit_form"):
                    c1, c2 = st.columns(2)
                    new_nombre = c1.text_input("ID / Nombre", value=dato['nombre'])
                    new_ubic = c2.selectbox("Ubicación", sub_areas_disp, index=idx_ubic)
                    cat_actual = dato.get('categoria', '')
                    idx_cat = 0
                    if cat_actual in LISTA_CATEGORIAS: idx_cat = ([""] + LISTA_CATEGORIAS).index(cat_actual)
                    new_cat = st.selectbox("Categoría", [""] + LISTA_CATEGORIAS, index=idx_cat)

                    if st.form_submit_button("🔄 Actualizar Registro"):
                        supabase.table("activos").update({
                            "nombre": new_nombre, "ubicacion": new_ubic, "area": new_area, "categoria": new_cat
                        }).eq("id", int(id_sel)).execute()
                        st.session_state['notification'] = {'type': 'success', 'message': f"Registro de '{new_nombre}' actualizado."}
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("---")
                
                # --- ZONA DE PELIGRO LLAMATIVA ---
                with st.expander("🚫 ZONA DE PELIGRO (Eliminación de Activo)"):
                    st.markdown(f"""
                        <div class="danger-zone">
                            <h2>⚠️ ADVERTENCIA DE SEGURIDAD</h2>
                            <p style="font-size: 18px; color: white;">Está a punto de purgar el activo <b>{dato['nombre']}</b> del sistema.</p>
                            <p style="color: white;">Esta acción eliminará irreversiblemente <b>TODAS las órdenes de trabajo</b> asociadas.</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    confirmar_borrado = st.checkbox("Confirmo que deseo proceder con la eliminación irreversible.")
                    
                    if st.button("🔥 EJECUTAR PURGA DE DATOS", type="primary", disabled=not confirmar_borrado):
                        try:
                            # Borrado en cascada
                            supabase.table("ordenes").delete().eq("activo_id", int(id_sel)).execute()
                            supabase.table("activos").delete().eq("id", int(id_sel)).execute()
                            
                            st.session_state['notification'] = {'type': 'delete', 'message': f"Activo '{dato['nombre']}' y sus registros han sido purgados."}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error crítico: {e}")

        else:
            st.info("Inventario vacío.")

elif choice == "Crear Orden":
    st.subheader("Crear Nueva Orden de Trabajo")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin'])]['nombre'].tolist() if not df_users.empty else []
    
    if not df_activos.empty:
        activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
        
        st.markdown(f"<div class='card-style'>", unsafe_allow_html=True)
        sel = st.selectbox("Seleccionar Equipo Objetivo", list(activos_dict.keys()))
        
        col_a, col_b = st.columns(2)
        tipo = col_a.selectbox("Tipo de Mantenimiento", ["Correctivo", "Preventivo", "Predictivo"])
        crit = col_b.select_slider("Nivel de Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        desc = st.text_area("Descripción Detallada de la Tarea")
        asig = st.selectbox("Asignar Técnico Responsable", tecnicos)
        
        if st.button("🚀 Generar Orden de Trabajo", use_container_width=True):
            supabase.table("ordenes").insert({
                "activo_id": activos_dict[sel], "descripcion": desc, "criticidad": crit, 
                "tipo_mantenimiento": tipo, "estado": "Abierta", 
                "fecha_creacion": datetime.now().isoformat(), "tecnico_asignado": asig
            }).execute()
            st.session_state['notification'] = {'type': 'success', 'message': "Orden de Trabajo generada y asignada."}
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else: st.warning("El inventario de activos está vacío.")

elif choice == "Usuarios":
    st.subheader("Gestión de Personal")
    mostrar_notificaciones()
    st.markdown("<div class='card-style'>Módulo de gestión de credenciales y roles.</div>", unsafe_allow_html=True)

elif choice == "Cierre de OTs":
    st.subheader("Cierre de Órdenes")
    mostrar_notificaciones()
    
    df_ots = run_query("ordenes")
    if not df_ots.empty:
        mis_ots = df_ots if rol_actual != "Tecnico" else df_ots[df_ots['tecnico_asignado'] == usuario_actual]
        mis_ots = mis_ots[mis_ots['estado'] != 'Concluida']
        
        if not mis_ots.empty:
            st.markdown(f"<div class='card-style'>Isntrucciones: Seleccione la OT, complete el informe y adjunte evidencia.</div>", unsafe_allow_html=True)
            st.dataframe(mis_ots[['id','descripcion','estado']], use_container_width=True)
            
            st.markdown(f"<div class='card-style'>", unsafe_allow_html=True)
            sel_id = st.selectbox("Seleccionar ID de Orden a Cerrar", mis_ots['id'].values)
            
            with st.form("close_form"):
                coment = st.text_area("Informe Técnico de Cierre")
                foto = st.file_uploader("Adjuntar Evidencia Fotográfica")
                if st.form_submit_button("✅ Finalizar Orden de Trabajo"):
                    url = subir_imagen(foto)
                    supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre": coment, "evidencia_url": url}).eq("id", int(sel_id)).execute()
                    st.session_state['notification'] = {'type': 'success', 'message': "Orden finalizada y archivada exitosamente."}
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.info("No hay órdenes pendientes de cierre.")
