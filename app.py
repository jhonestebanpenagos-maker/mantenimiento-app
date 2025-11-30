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
# 🎨 ZONA DE PERSONALIZACIÓN: TEMA "NEON DATA FLOW" (Estilo Orion)
# ==============================================================================

# COLORES BASADOS EN TUS IMÁGENES (Morados, Rosas, Fondo Oscuro)
NEON_PURPLE = "#7d12ff"
NEON_PINK = "#e6007e"
NEON_CYAN = "#00f2ea"
BG_DARK = "#080a12"  # Casi negro
CARD_BG = "rgba(20, 24, 40, 0.7)" # Semitransparente

# Inyección de CSS para replicar el estilo de las fotos
st.markdown(f"""
    <style>
    /* 1. FONDO GENERAL CON DEGRADADO SUTIL (Como la imagen 1) */
    .stApp {{
        background: radial-gradient(circle at 50% 0%, #1a0b2e 0%, #080a12 70%);
        background-attachment: fixed;
        color: #ffffff;
    }}

    /* 2. BARRA LATERAL (SIDEBAR) */
    [data-testid="stSidebar"] {{
        background-color: #050505;
        border-right: 1px solid #333;
    }}
    
    /* 3. TÍTULOS CON DEGRADADO (Estilo moderno) */
    h1, h2, h3 {{
        background: -webkit-linear-gradient(0deg, {NEON_CYAN}, {NEON_PURPLE});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
        letter-spacing: 1px;
    }}
    
    /* 4. TARJETAS GLOW (Efecto de las burbujas/paneles) */
    .card-style {{
        background: {CARD_BG};
        backdrop-filter: blur(10px); /* Efecto vidrio */
        border-radius: 20px;
        padding: 25px;
        border: 1px solid rgba(125, 18, 255, 0.2); /* Borde morado sutil */
        box-shadow: 0 0 20px rgba(125, 18, 255, 0.1); /* Resplandor suave */
        margin-bottom: 25px;
    }}
    
    /* 5. INPUTS Y SELECTORES (Oscuros y redondeados) */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
        background-color: #0f111a !important;
        color: white !important;
        border-radius: 12px;
        border: 1px solid #333 !important;
    }}
    .stTextInput input:focus, .stSelectbox > div > div:focus-within {{
        border-color: {NEON_PINK} !important;
        box-shadow: 0 0 10px rgba(230, 0, 126, 0.5);
    }}
    
    /* 6. BOTONES (Gradiente Morado -> Rosa como en la imagen 1) */
    div.stButton > button:first-child {{
        background: linear-gradient(90deg, {NEON_PURPLE} 0%, {NEON_PINK} 100%) !important;
        color: white !important;
        border: none;
        border-radius: 50px; /* Botones redondos */
        font-weight: bold;
        padding: 0.5rem 1.5rem;
        transition: transform 0.2s;
        box-shadow: 0 4px 15px rgba(230, 0, 126, 0.4);
    }}
    div.stButton > button:first-child:hover {{
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(230, 0, 126, 0.6);
    }}

    /* 7. MÉTRICAS (Estilo Panel Flotante) */
    [data-testid="stMetric"] {{
        background: linear-gradient(145deg, rgba(255,255,255,0.05), rgba(255,255,255,0.01));
        border-radius: 15px;
        padding: 15px;
        border-top: 3px solid {NEON_CYAN}; /* Detalle de color arriba */
        box-shadow: 0 4px 10px rgba(0,0,0,0.3);
    }}
    [data-testid="stMetricLabel"] {{ color: #a0a0a0 !important; font-size: 14px; }}
    [data-testid="stMetricValue"] {{ color: white !important; font-size: 30px !important; font-weight: bold; }}

    /* 8. TABLAS */
    [data-testid="stTable"] {{
        background: transparent;
    }}
    
    /* 9. ALERTA DE PELIGRO (Roja Brillante) */
    .danger-zone {{
        background: rgba(50, 0, 0, 0.8);
        border: 2px solid #ff2a2a;
        box-shadow: 0 0 15px #ff2a2a;
        color: #ff2a2a;
        padding: 20px;
        border-radius: 15px;
        text-align: center;
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
                # Notificación estilo Neon
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 15px; background: rgba(0, 242, 234, 0.1); border: 1px solid {NEON_CYAN}; text-align: center; margin-bottom: 20px; box-shadow: 0 0 15px {NEON_CYAN};">
                    <h2 style="margin:0; color: {NEON_CYAN}; text-shadow: 0 0 5px {NEON_CYAN};">⚡ ÉXITO ⚡</h2>
                    <p style="font-size: 18px; margin:5px 0 0 0; color: white;">{msg}</p>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1) 
            
            elif tipo == 'delete':
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 15px; background: rgba(255, 42, 42, 0.1); border: 1px solid #ff2a2a; text-align: center; margin-bottom: 20px; box-shadow: 0 0 15px #ff2a2a;">
                    <h3 style="margin:0; color: #ff2a2a;">🗑️ ELIMINADO</h3>
                    <p style="color:white;">{msg}</p>
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
                <h3 style="margin-top:0; color: {NEON_CYAN};">Detalles del Equipo</h3>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
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
    st.markdown("<h1 style='text-align: center;'>ORION CMMS</h1>", unsafe_allow_html=True)
    
    # Estilo personalizado para Tabs
    st.markdown(f"""
        <style>
            .stTabs [data-baseweb="tab-list"] {{
                background-color: transparent;
                border-bottom: 2px solid #333;
            }}
            .stTabs [data-baseweb="tab"] {{
                color: #a0a0a0;
            }}
            .stTabs [aria-selected="true"] {{
                color: {NEON_CYAN} !important;
                border-bottom: 2px solid {NEON_CYAN};
            }}
        </style>
    """, unsafe_allow_html=True)

    tab_login, tab_scan = st.tabs(["🔐 ACCESO", "📷 ESCÁNER"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            st.markdown("<div class='card-style' style='text-align:center;'><h3>Identificación</h3>", unsafe_allow_html=True)
            with st.form("login_form"):
                documento = st.text_input("Usuario / Documento")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("INGRESAR", type="primary", use_container_width=True)
                
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
        st.info("📷 Escanea el QR del activo para ver su ficha.")
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
        <div style="background: linear-gradient(135deg, #1a0b2e, #000); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; border: 1px solid {NEON_PURPLE};">
            <h2 style="margin:0;">👤</h2>
            <h3 style="margin:10px 0; font-size: 18px; color: white;">{usuario_actual}</h3>
            <span style="background: {NEON_PINK}; padding: 3px 10px; border-radius: 20px; font-size: 12px; font-weight: bold;">{rol_actual}</span>
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
    
    # MENÚ ADAPTADO AL TEMA NEON
    choice = option_menu(
        menu_title="NAVEGACIÓN",
        options=options_menu,
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
        default_index=0,
        styles={
            "container": {"padding": "5px!important", "background-color": "transparent"},
            "icon": {"color": NEON_CYAN, "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "color": "#fff"},
            "nav-link-selected": {"background": f"linear-gradient(90deg, {NEON_PURPLE}, {NEON_PINK})", "color": "white", "border-radius": "10px"},
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
        # Métricas "flotantes"
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        
        st.divider()
        
        # Gráficos
        c1, c2, c3 = st.columns(3)
        with c1: 
            st.markdown(f"<h4 style='color:{NEON_CYAN}'>Estado</h4>", unsafe_allow_html=True)
            st.bar_chart(df_ordenes['estado'].value_counts(), color="#00f2ea") 
        with c2: 
            st.markdown(f"<h4 style='color:{NEON_PINK}'>Criticidad</h4>", unsafe_allow_html=True)
            st.bar_chart(df_ordenes['criticidad'].value_counts(), color="#e6007e")
        with c3: 
            st.markdown(f"<h4 style='color:{NEON_PURPLE}'>Tipo</h4>", unsafe_allow_html=True)
            if 'tipo_mantenimiento' in df_ordenes.columns: 
                st.bar_chart(df_ordenes['tipo_mantenimiento'].value_counts(), color="#7d12ff")
    else: st.info("Sin datos para analizar.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    
    if 'tab_index_activos' not in st.session_state: st.session_state['tab_index_activos'] = 0
    
    # Tabs estilo minimalista
    st.markdown(f"""<style> .stTabs [data-baseweb="tab-list"] {{ border-bottom: 1px solid {NEON_PURPLE}; }} </style>""", unsafe_allow_html=True)

    selected_tab = option_menu(
        menu_title=None, 
        options=["Registrar Nuevo", "Editar / Imprimir QR"], 
        icons=["plus-square", "qr-code"], 
        orientation="horizontal", 
        default_index=st.session_state['tab_index_activos'],
        styles={
            "container": {"background-color": "transparent"},
            "nav-link": {"color": "white"},
            "nav-link-selected": {"background-color": NEON_PURPLE, "color": "white", "border-radius":"20px"}
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
                            <p>Esta acción eliminará el activo y todas sus órdenes asociadas de forma permanente.</p>
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
