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
# 🎨 ZONA DE PERSONALIZACIÓN: TEMA "PROFESSIONAL AMBER & EMERALD"
# ==============================================================================

# COLORES PROFESIONALES (Naranja Ámbar y Verde Esmeralda)
PRO_ORANGE = "#F59E0B" # Ámbar brillante para acción
PRO_GREEN = "#10B981"  # Esmeralda para datos/éxito
BG_DARK_CLEAN = "#111827" # Gris carbón muy oscuro (fondo principal)
BG_CARD_CLEAN = "rgba(31, 41, 55, 0.7)" # Gris azulado semitransparente para tarjetas
TEXT_HIGH_CONTRAST = "#F9FAFB" # Blanco hueso para máximo contraste

# Inyección de CSS Profesional
st.markdown(f"""
    <style>
    /* 1. FONDO GENERAL LIMPIO Y PROFESIONAL */
    .stApp {{
        /* Degradado sutil de gris carbón, menos fatigante que el negro puro */
        background: radial-gradient(circle at 50% 0%, #374151 0%, {BG_DARK_CLEAN} 80%);
        background-attachment: fixed;
        color: {TEXT_HIGH_CONTRAST}; /* Texto de alto contraste */
    }}

    /* 2. BARRA LATERAL (SIDEBAR) */
    [data-testid="stSidebar"] {{
        background-color: {BG_DARK_CLEAN};
        border-right: 1px solid #374151;
    }}
    
    /* 3. TÍTULOS MODERNOS (Degradado Naranja -> Verde) */
    h1, h2, h3 {{
        background: linear-gradient(90deg, {PRO_ORANGE}, {PRO_GREEN});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: 0.5px;
    }}
    
    /* Texto normal dentro de la app para asegurar contraste */
    p, label, span, div {{
        color: {TEXT_HIGH_CONTRAST};
    }}
    
    /* 4. TARJETAS "ORION" MEJORADAS */
    .card-style {{
        background: {BG_CARD_CLEAN};
        backdrop-filter: blur(12px); /* Efecto vidrio esmerilado */
        border-radius: 16px;
        padding: 25px;
        /* Borde sutil naranja */
        border: 1px solid rgba(245, 158, 11, 0.3); 
        /* Sombra suave para profundidad */
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2); 
        margin-bottom: 25px;
    }}
    
    /* 5. INPUTS Y SELECTORES (Limpios y alto contraste) */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
        background-color: rgba(17, 24, 39, 0.8) !important;
        color: {TEXT_HIGH_CONTRAST} !important;
        border-radius: 8px;
        border: 1px solid #4B5563 !important; /* Borde gris medio */
    }}
    .stTextInput input:focus, .stSelectbox > div > div:focus-within {{
        border-color: {PRO_ORANGE} !important;
        box-shadow: 0 0 8px rgba(245, 158, 11, 0.4);
    }}
    
    /* 6. BOTONES (Gradiente Naranja -> Verde Profesional) */
    div.stButton > button:first-child {{
        background: linear-gradient(90deg, {PRO_ORANGE} 0%, {PRO_GREEN} 100%) !important;
        color: white !important;
        border: none;
        border-radius: 8px; /* Un poco menos redondeados para look pro */
        font-weight: 600;
        padding: 0.6rem 1.5rem;
        transition: all 0.2s ease-in-out;
        box-shadow: 0 4px 12px rgba(245, 158, 11, 0.3);
    }}
    div.stButton > button:first-child:hover {{
        transform: translateY(-2px);
        box-shadow: 0 6px 15px rgba(16, 185, 129, 0.4);
    }}

    /* 7. MÉTRICAS (Estilo Panel Limpio) */
    [data-testid="stMetric"] {{
        background: {BG_CARD_CLEAN};
        border-radius: 12px;
        padding: 20px;
        border-left: 4px solid {PRO_GREEN}; /* Barra de acento verde a la izquierda */
        box-shadow: 0 2px 10px rgba(0,0,0,0.2);
    }}
    [data-testid="stMetricLabel"] {{ color: #9CA3AF !important; font-size: 15px; font-weight: 500; }}
    [data-testid="stMetricValue"] {{ color: {TEXT_HIGH_CONTRAST} !important; font-size: 32px !important; font-weight: 700; }}

    /* 8. TABLAS (Hacerlas legibles) */
    [data-testid="stTable"] {{
        background: transparent;
        color: {TEXT_HIGH_CONTRAST};
    }}
    /* Encabezados de tabla */
    th {{
        color: {PRO_ORANGE} !important;
        border-bottom: 2px solid #374151 !important;
    }}
    td {{
        border-bottom: 1px solid #374151 !important;
    }}
    
    /* 9. ZONA DE PELIGRO */
    .danger-zone {{
        background: rgba(127, 29, 29, 0.2); /* Rojo oscuro transparente */
        border: 2px solid #EF4444;
        color: #EF4444;
        padding: 20px;
        border-radius: 12px;
        text-align: center;
    }}
    /* Asegurar que los textos dentro de danger zone se vean */
    .danger-zone p, .danger-zone h3 {{
         color: #EF4444 !important;
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
                # Notificación estilo Verde Profesional
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 12px; background: rgba(16, 185, 129, 0.15); border: 1px solid {PRO_GREEN}; text-align: center; margin-bottom: 20px; box-shadow: 0 4px 15px rgba(16, 185, 129, 0.2);">
                    <h2 style="margin:0; color: {PRO_GREEN};">✅ Operación Exitosa</h2>
                    <p style="font-size: 18px; margin:5px 0 0 0; color: {TEXT_HIGH_CONTRAST};">{msg}</p>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1) 
            
            elif tipo == 'delete':
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 12px; background: rgba(239, 68, 68, 0.15); border: 1px solid #EF4444; text-align: center; margin-bottom: 20px;">
                    <h3 style="margin:0; color: #EF4444;">🗑️ Registro Eliminado</h3>
                    <p style="color:{TEXT_HIGH_CONTRAST};">{msg}</p>
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
        st.markdown(f"<h1 style='text-align: center;'>{activo['nombre']}</h1>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="card-style">
                <h3 style="margin-top:0; color: {PRO_ORANGE};">Ficha Técnica del Equipo</h3>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)

        st.subheader("🛠️ Historial Reciente")
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
# 🚀 ZONA 2: PORTAL DE ACCESO
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    st.markdown("<h1 style='text-align: center;'>SISTEMA CMMS</h1>", unsafe_allow_html=True)
    
    # Estilo personalizado para Tabs (Naranja activo)
    st.markdown(f"""
        <style>
            .stTabs [data-baseweb="tab-list"] {{
                background-color: transparent;
                border-bottom: 2px solid #374151;
            }}
            .stTabs [data-baseweb="tab"] {{
                color: #9CA3AF; /* Gris claro inactivo */
            }}
            .stTabs [aria-selected="true"] {{
                color: {PRO_ORANGE} !important;
                border-bottom: 3px solid {PRO_ORANGE};
                font-weight: bold;
            }}
        </style>
    """, unsafe_allow_html=True)

    tab_login, tab_scan = st.tabs(["🔐 ACCESO PERSONAL", "📷 ESCÁNER QR"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            st.markdown("<div class='card-style' style='text-align:center;'><h3>Credenciales</h3>", unsafe_allow_html=True)
            with st.form("login_form"):
                documento = st.text_input("Usuario / Documento")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("INICIAR SESIÓN", type="primary", use_container_width=True)
                
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
                        st.error("Error de conexión.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_scan:
        st.markdown("<div class='card-style' style='text-align:center;'>", unsafe_allow_html=True)
        st.info("📷 Escanea el QR del activo para acceso rápido.")
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        if img_file is not None:
            id_detectado = leer_qr_imagen(img_file)
            if id_detectado:
                st.query_params["id_activo_qr"] = id_detectado
                st.rerun()
            else:
                st.warning("⚠️ QR no detectado.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# 🚀 ZONA 3: DASHBOARD PRIVADO
# ==============================================================================

rol_actual = st.session_state['rol']
usuario_actual = st.session_state['usuario']

# --- BARRA LATERAL ---
with st.sidebar:
    st.markdown(f"""
        <div style="background: {BG_CARD_CLEAN}; padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; border: 1px solid {PRO_ORANGE};">
            <h2 style="margin:0;">👤</h2>
            <h3 style="margin:10px 0; font-size: 18px; color: white;">{usuario_actual}</h3>
            <span style="background: {PRO_GREEN}; color: #064E3B; padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 700;">{rol_actual.upper()}</span>
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
    
    # MENÚ ADAPTADO AL TEMA PROFESIONAL
    choice = option_menu(
        menu_title="NAVEGACIÓN",
        options=options_menu,
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
        default_index=0,
        styles={
            "container": {"padding": "5px!important", "background-color": "transparent"},
            "icon": {"color": PRO_ORANGE, "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "color": "#D1D5DB"},
            "nav-link-selected": {"background": f"linear-gradient(90deg, {PRO_ORANGE}, {PRO_GREEN})", "color": "white", "border-radius": "8px", "font-weight":"600"},
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
    st.subheader("Resumen de Operaciones")
    mostrar_notificaciones()
    
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        # Métricas limpias
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        
        st.divider()
        
        # Gráficos con títulos de color
        c1, c2, c3 = st.columns(3)
        with c1: 
            st.markdown(f"<h4 style='color:{PRO_ORANGE}'>Estado de OTs</h4>", unsafe_allow_html=True)
            st.bar_chart(df_ordenes['estado'].value_counts(), color=PRO_ORANGE) 
        with c2: 
            st.markdown(f"<h4 style='color:{PRO_GREEN}'>Criticidad</h4>", unsafe_allow_html=True)
            st.bar_chart(df_ordenes['criticidad'].value_counts(), color=PRO_GREEN)
        with c3: 
            st.markdown(f"<h4 style='color:#A78BFA'>Tipo Mto.</h4>", unsafe_allow_html=True)
            if 'tipo_mantenimiento' in df_ordenes.columns: 
                st.bar_chart(df_ordenes['tipo_mantenimiento'].value_counts(), color="#A78BFA") # Un morado suave para contraste
    else: st.info("Sin datos para analizar.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    
    if 'tab_index_activos' not in st.session_state: st.session_state['tab_index_activos'] = 0
    
    # Tabs internos estilo minimalista naranja
    st.markdown(f"""<style> .stTabs [data-baseweb="tab-list"] {{ border-bottom: 2px solid {PRO_ORANGE}; }} </style>""", unsafe_allow_html=True)

    selected_tab = option_menu(
        menu_title=None, 
        options=["Registrar Nuevo", "Editar / Imprimir QR"], 
        icons=["plus-square", "qr-code"], 
        orientation="horizontal", 
        default_index=st.session_state['tab_index_activos'],
        styles={
            "container": {"background-color": "transparent"},
            "nav-link": {"color": "#D1D5DB"},
            "nav-link-selected": {"background-color": PRO_ORANGE, "color": "white", "border-radius":"8px"}
        }
    )
    
    if selected_tab == "Registrar Nuevo":
        if 'asset_reset_key' not in st.session_state: st.session_state.asset_reset_key = 0
        
        st.markdown(f"<div class='card-style'><h4>📍 Paso 1: Ubicación</h4>", unsafe_allow_html=True)
        area_selec = st.selectbox("Área Principal", [""] + list(ESTRUCTURA_AREAS.keys()), key=f"area_create_{st.session_state.asset_reset_key}")
        sub_areas = [""] + ESTRUCTURA_AREAS.get(area_selec, []) if area_selec else [""]
        st.markdown("</div>", unsafe_allow_html=True)
        
        st.markdown(f"<div class='card-style'><h4>⚙️ Paso 2: Datos Técnicos</h4>", unsafe_allow_html=True)
        with st.form("form_activo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("ID / Nombre del Equipo")
            ubicacion = c2.selectbox("Sub-Área / Ubicación", sub_areas)
            categoria = st.selectbox("Categoría Técnica", [""] + LISTA_CATEGORIAS)
            
            if st.form_submit_button("💾 Guardar y Generar QR"):
                if nombre and area_selec and ubicacion and categoria:
                    try:
                        res = supabase.table("activos").insert({
                            "nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria
                        }).execute()
                        
                        if res.data:
                            new_id = res.data[0]['id']
                            url_qr = generar_qr_activo(new_id, nombre)
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                            
                            st.session_state['notification'] = {'type': 'success', 'message': f"Activo '{nombre}' ingresado al sistema."}
                            st.session_state.asset_reset_key += 1
                            st.session_state['tab_index_activos'] = 0
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("⚠️ Faltan campos obligatorios.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected_tab == "Editar / Imprimir QR":
        st.session_state['tab_index_activos'] = 1 
        
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("🔍 Buscar Activo", [""] + list(activos_dict.keys()))
            
            if seleccion:
                id_sel = activos_dict[seleccion]
                dato = df_activos[df_activos['id'] == id_sel].iloc[0]
                
                st.markdown(f"""
                <div class="card-style">
                    <h2 style="margin-top:0; color:white;">{dato['nombre']}</h2>
                </div>
                """, unsafe_allow_html=True)

                c1, c2 = st.columns([1,3])
                with c1:
                    if dato.get('qr_url'): 
                        st.image(dato['qr_url'], caption="Matriz QR")
                    else: 
                        if st.button("Generar QR"):
                            url_qr = generar_qr_activo(id_sel, dato['nombre'])
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_sel)).execute()
                            st.rerun()
                with c2:
                    st.info("💡 Usa este QR para etiquetar el equipo físico.")
                
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

                    if st.form_submit_button("🔄 Actualizar"):
                        supabase.table("activos").update({
                            "nombre": new_nombre, "ubicacion": new_ubic, "area": new_area, "categoria": new_cat
                        }).eq("id", int(id_sel)).execute()
                        st.session_state['notification'] = {'type': 'success', 'message': f"Registro de '{new_nombre}' actualizado."}
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

                st.markdown("---")
                
                with st.expander("🚫 ZONA DE PELIGRO"):
                    st.markdown(f"""
                        <div class="danger-zone">
                            <h3>⚠️ ELIMINACIÓN DE ACTIVO</h3>
                            <p style="color:#EF4444;">Esta acción eliminará el activo y todas sus órdenes asociadas de forma permanente.</p>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    confirmar_borrado = st.checkbox("Entiendo que esto es irreversible.")
                    
                    if st.button("🔥 ELIMINAR AHORA", type="primary", disabled=not confirmar_borrado):
                        try:
                            supabase.table("ordenes").delete().eq("activo_id", int(id_sel)).execute()
                            supabase.table("activos").delete().eq("id", int(id_sel)).execute()
                            
                            st.session_state['notification'] = {'type': 'delete', 'message': f"Activo '{dato['nombre']}' eliminado."}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error crítico: {e}")

        else:
            st.info("Inventario vacío.")

elif choice == "Crear Orden":
    st.subheader("Nueva Orden de Trabajo")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin'])]['nombre'].tolist() if not df_users.empty else []
    
    if not df_activos.empty:
        activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
        
        st.markdown(f"<div class='card-style'>", unsafe_allow_html=True)
        sel = st.selectbox("Equipo Objetivo", list(activos_dict.keys()))
        
        col_a, col_b = st.columns(2)
        tipo = col_a.selectbox("Tipo Mantenimiento", ["Correctivo", "Preventivo", "Predictivo"])
        crit = col_b.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        desc = st.text_area("Descripción de la Tarea")
        asig = st.selectbox("Técnico Responsable", tecnicos)
        
        if st.button("🚀 Crear Orden", use_container_width=True):
            supabase.table("ordenes").insert({
                "activo_id": activos_dict[sel], "descripcion": desc, "criticidad": crit, 
                "tipo_mantenimiento": tipo, "estado": "Abierta", 
                "fecha_creacion": datetime.now().isoformat(), "tecnico_asignado": asig
            }).execute()
            st.session_state['notification'] = {'type': 'success', 'message': "Orden generada exitosamente."}
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else: st.warning("No hay activos registrados.")

elif choice == "Usuarios":
    st.subheader("Usuarios")
    mostrar_notificaciones()
    st.markdown("<div class='card-style'>Módulo de gestión de credenciales.</div>", unsafe_allow_html=True)

elif choice == "Cierre de OTs":
    st.subheader("Cierre de Órdenes")
    mostrar_notificaciones()
    
    df_ots = run_query("ordenes")
    if not df_ots.empty:
        mis_ots = df_ots if rol_actual != "Tecnico" else df_ots[df_ots['tecnico_asignado'] == usuario_actual]
        mis_ots = mis_ots[mis_ots['estado'] != 'Concluida']
        
        if not mis_ots.empty:
            st.markdown(f"<div class='card-style'>Seleccione la OT, complete informe y evidencia.</div>", unsafe_allow_html=True)
            st.dataframe(mis_ots[['id','descripcion','estado']], use_container_width=True)
            
            st.markdown(f"<div class='card-style'>", unsafe_allow_html=True)
            sel_id = st.selectbox("ID Orden a Cerrar", mis_ots['id'].values)
            
            with st.form("close_form"):
                coment = st.text_area("Informe de Cierre")
                foto = st.file_uploader("Evidencia (Foto)")
                if st.form_submit_button("✅ Finalizar Orden"):
                    url = subir_imagen(foto)
                    supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre": coment, "evidencia_url": url}).eq("id", int(sel_id)).execute()
                    st.session_state['notification'] = {'type': 'success', 'message': "Orden finalizada."}
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.info("No hay órdenes pendientes.")
