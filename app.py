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
import plotly.graph_objects as go # Para gráficos avanzados

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="wide", initial_sidebar_state="collapsed")

# ==============================================================================
# 🎨 TEMA: "BIO-HAZARD AMBER" (Profesional, Alto Contraste y Volumen)
# ==============================================================================

COLOR_ACCION = "#F59E0B" # Naranja Ámbar (Principal)
COLOR_EXITO = "#10B981"  # Verde Esmeralda (Secundario)
COLOR_FONDO_OSCURO = "#0F172A" 
COLOR_TEXTO = "#F8FAFC"

st.markdown(f"""
    <style>
    /* 1. FONDO LIMPIO Y PROFESIONAL */
    .stApp {{
        background: radial-gradient(circle at top, #1E293B, {COLOR_FONDO_OSCURO});
        color: {COLOR_TEXTO};
    }}

    /* 2. BARRA LATERAL */
    [data-testid="stSidebar"] {{
        background-color: rgba(15, 23, 42, 0.98);
        border-right: 1px solid rgba(245, 158, 11, 0.2);
    }}

    /* 3. TÍTULOS CON DEGRADADO NARANJA-VERDE */
    h1, h2, h3 {{
        background: linear-gradient(90deg, {COLOR_ACCION}, {COLOR_EXITO});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800 !important;
    }}
    
    /* 4. TARJETAS DE VIDRIO (GLASS) */
    .card-style {{
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border-radius: 16px;
        padding: 24px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        box-shadow: 0 4px 20px rgba(0,0,0,0.4);
        margin-bottom: 20px;
    }}

    /* 5. CORRECCIÓN MENÚS DESPLEGABLES (TEXTO VISIBLE) */
    .stSelectbox > div > div {{
        background-color: rgba(15, 23, 42, 0.8) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
    }}
    /* Popover (La lista que se abre) */
    div[data-baseweb="popover"] {{ background-color: #1E293B !important; }}
    div[data-baseweb="menu"] li {{ color: white !important; }}
    div[data-baseweb="menu"] li:hover {{ background-color: {COLOR_ACCION} !important; }}
    
    /* 6. INPUTS */
    .stTextInput input, .stTextArea textarea {{
        background-color: rgba(0,0,0,0.3) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 8px;
    }}
    
    /* 7. BOTONES */
    div.stButton > button:first-child {{
        background: linear-gradient(135deg, {COLOR_ACCION}, #D97706) !important;
        color: white !important;
        border: none;
        font-weight: bold;
        border-radius: 8px;
        padding: 0.6rem 1.2rem;
        transition: transform 0.2s;
    }}
    div.stButton > button:first-child:hover {{
        transform: scale(1.02);
        box-shadow: 0 0 15px rgba(245, 158, 11, 0.5);
    }}

    /* 8. MÉTRICAS */
    [data-testid="stMetric"] {{
        background: rgba(255,255,255,0.03);
        padding: 15px;
        border-radius: 12px;
        border-left: 4px solid {COLOR_ACCION};
    }}
    [data-testid="stMetricLabel"] {{ color: #94A3B8 !important; }}
    [data-testid="stMetricValue"] {{ color: white !important; }}
    
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
    # 🔗 URL REAL
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

# --- GRÁFICOS AVANZADOS (PLOTLY) ---

def graficar_criticidad(df):
    if df.empty: return
    conteo = df['criticidad'].value_counts().reset_index()
    conteo.columns = ['Nivel', 'Cantidad']
    
    # Orden lógico de criticidad
    orden = ["Baja", "Media", "Alta", "Crítica"]
    conteo['Nivel'] = pd.Categorical(conteo['Nivel'], categories=orden, ordered=True)
    conteo = conteo.sort_values('Nivel')

    # Mapa de colores semántico (Verde -> Rojo)
    colores = {
        "Baja": "#10B981",    # Verde
        "Media": "#F59E0B",   # Amarillo/Naranja
        "Alta": "#EA580C",    # Naranja Oscuro
        "Crítica": "#EF4444"  # Rojo
    }

    fig = px.bar(conteo, x='Nivel', y='Cantidad', title="<b>Gravedad de las Fallas</b>",
                 color='Nivel', color_discrete_map=colores, text='Cantidad')
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=False,
        height=300
    )
    fig.update_traces(textposition='outside', marker_line_width=0)
    st.plotly_chart(fig, use_container_width=True)

def graficar_torta_tipo(df):
    if df.empty: return
    if 'tipo_mantenimiento' not in df.columns: return

    conteo = df['tipo_mantenimiento'].value_counts().reset_index()
    conteo.columns = ['Tipo', 'Cantidad']
    
    # Colores elegantes
    colores_torta = ["#3B82F6", "#8B5CF6", "#EC4899"] # Azul, Violeta, Rosa

    fig = go.Figure(data=[go.Pie(
        labels=conteo['Tipo'], 
        values=conteo['Cantidad'], 
        hole=.5, # Hace que sea una DONA
        marker=dict(colors=colores_torta, line=dict(color='#0F172A', width=2))
    )])
    
    fig.update_layout(
        title="<b>Tipos de Mantenimiento</b>",
        paper_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        height=300,
        showlegend=True,
        legend=dict(orientation="h", y=-0.1)
    )
    st.plotly_chart(fig, use_container_width=True)

def graficar_estado_barras(df):
    if df.empty: return
    conteo = df['estado'].value_counts().reset_index()
    conteo.columns = ['Estado', 'Cantidad']
    
    colores = {"Abierta": "#0EA5E9", "Concluida": "#10B981"} # Azul cielo, Verde

    fig = px.bar(conteo, x='Cantidad', y='Estado', orientation='h', 
                 color='Estado', color_discrete_map=colores, text='Cantidad',
                 title="<b>Progreso de Órdenes</b>")
    
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        showlegend=False,
        height=300
    )
    st.plotly_chart(fig, use_container_width=True)


# --- NOTIFICACIONES ---
def mostrar_notificaciones():
    if 'notification' in st.session_state:
        notif = st.session_state['notification']
        if notif:
            tipo = notif.get('type')
            msg = notif.get('message')
            
            if tipo == 'success':
                st.balloons()
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 12px; background: rgba(16, 185, 129, 0.1); border: 1px solid {COLOR_EXITO}; text-align: center; margin-bottom: 20px;">
                    <h3 style="margin:0; color: {COLOR_EXITO};">✅ EXCELENTE</h3>
                    <p style="margin:5px 0 0 0; color: #E2E8F0;">{msg}</p>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1) 
            
            elif tipo == 'delete':
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid #EF4444; text-align: center; margin-bottom: 20px;">
                    <h3 style="margin:0; color: #EF4444;">♻️ ELIMINADO</h3>
                    <p style="color:#E2E8F0;">{msg}</p>
                </div>
                """, unsafe_allow_html=True)
        del st.session_state['notification']

# ==============================================================================
# 🚀 ZONA 1: INTERCEPTOR PÚBLICO
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
        # HEADER
        st.markdown(f"<h1 style='text-align: center;'>{activo['nombre']}</h1>", unsafe_allow_html=True)
        
        # CARD DETALLES
        st.markdown(f"""
            <div class="card-style">
                <h3 style="margin-top:0; color: {COLOR_ACCION};">Ficha Técnica</h3>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span>📍 Área:</span> <b style="color:white">{activo.get('area', 'N/A')}</b>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span>🏢 Ubicación:</span> <b style="color:white">{activo['ubicacion']}</b>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span>🔧 Categoría:</span> <b style="color:white">{activo.get('categoria', 'N/A')}</b>
                </div>
            </div>
        """, unsafe_allow_html=True)

        st.subheader("🛠️ Historial Reciente")
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).limit(5).execute()
            if ots.data:
                df_qr = pd.DataFrame(ots.data)
                # Estilo tabla transparente
                st.markdown("<style>th{color: #F59E0B !important;} td{border-bottom: 1px solid #334155 !important;}</style>", unsafe_allow_html=True)
                st.table(df_qr[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Sin registros históricos.")
        except: pass
            
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 Inicio"):
                st.query_params.clear()
                st.rerun()
        with c2:
            if st.session_state.get('usuario') is None:
                if st.button("🔐 Acceso Técnico"):
                    st.query_params.clear()
                    st.rerun()
    else:
        st.error("❌ Equipo no encontrado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    st.stop() 


# ==============================================================================
# 🚀 ZONA 2: LOGIN
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    st.markdown("<h1 style='text-align: center; font-size: 3rem;'>CMMS <span style='color:#F59E0B'>PRO</span></h1>", unsafe_allow_html=True)
    
    st.markdown(f"""
        <style>
            .stTabs [data-baseweb="tab-list"] {{ border-bottom: 1px solid rgba(255,255,255,0.1); }}
            .stTabs [aria-selected="true"] {{ color: {COLOR_ACCION} !important; border-bottom: 3px solid {COLOR_ACCION}; }}
        </style>
    """, unsafe_allow_html=True)

    tab_login, tab_scan = st.tabs(["🔐 INGRESAR", "📷 ESCANEAR"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            st.markdown("<div class='card-style' style='text-align:center;'><h3>Bienvenido</h3>", unsafe_allow_html=True)
            with st.form("login_form"):
                documento = st.text_input("Usuario")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("ACCEDER AL PANEL", type="primary", use_container_width=True)
                
                if submitted:
                    try:
                        response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()
                        if response.data:
                            user_data = response.data[0]
                            st.session_state['usuario'] = user_data['nombre']
                            st.session_state['rol'] = user_data['rol']
                            st.rerun()
                        else:
                            st.error("Datos incorrectos.")
                    except:
                        st.error("Sin conexión.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_scan:
        st.markdown("<div class='card-style' style='text-align:center;'>", unsafe_allow_html=True)
        st.info("Escanea el QR para ver la ficha técnica")
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        if img_file is not None:
            id_detectado = leer_qr_imagen(img_file)
            if id_detectado:
                st.query_params["id_activo_qr"] = id_detectado
                st.rerun()
            else:
                st.warning("No se detectó QR.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# 🚀 ZONA 3: DASHBOARD PRIVADO
# ==============================================================================

rol_actual = st.session_state['rol']
usuario_actual = st.session_state['usuario']

with st.sidebar:
    st.markdown(f"""
        <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px; text-align: center; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1);">
            <div style="width: 50px; height: 50px; background: linear-gradient(135deg, {COLOR_ACCION}, #D97706); border-radius: 50%; margin: 0 auto 10px auto; display: flex; align-items: center; justify-content: center; font-size: 20px; box-shadow: 0 0 10px {COLOR_ACCION};">👤</div>
            <h3 style="margin:5px 0; font-size: 16px; color: white;">{usuario_actual}</h3>
            <span style="background: {COLOR_EXITO}; color: #064E3B; padding: 2px 10px; border-radius: 10px; font-size: 11px; font-weight: bold;">{rol_actual.upper()}</span>
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
    
    choice = option_menu(
        menu_title="NAVEGACIÓN",
        options=options_menu,
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": COLOR_ACCION, "font-size": "18px"}, 
            "nav-link": {"font-size": "14px", "text-align": "left", "margin": "5px", "color": "#cbd5e1"},
            "nav-link-selected": {"background": f"linear-gradient(90deg, {COLOR_ACCION}, {COLOR_EXITO})", "color": "white", "border-radius": "8px", "font-weight":"bold"},
        }
    )

ESTRUCTURA_AREAS = {
    "Logística": ["Almacén Materia Prima", "Almacén Producto Terminado", "Distribución", "Taller Vehicular"],
    "Administración": ["Administración", "Servicios Generales"],
    "Técnica": ["Agua Cristal", "Linea 8", "Linea 2", "Linea 3", "Linea 1", "Linea 10", "Salas de Jarabe Terminado", "Sala de Jarabes Jugos", "Sala de Jarabe Simple", "Oficinas Técnicas", "Equipos Auxiliares", "Ptap", "Ptar"],
    "Ventas": ["Ventas", "Bodega de Publicidad"]
}
LISTA_CATEGORIAS = ["Mecánico", "Eléctrico", "Infraestructura", "HVAC", "Otros"]

# --- PANTALLAS ---

if choice == "Dashboard":
    st.subheader("Tablero de Mando")
    mostrar_notificaciones()
    
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        # Métricas
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        
        st.markdown("---")
        
        # --- GRÁFICOS INTERACTIVOS (PLOTLY) ---
        c1, c2, c3 = st.columns(3)
        
        with c1:
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            graficar_estado_barras(df_ordenes)
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c2:
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            graficar_criticidad(df_ordenes) # AQUÍ ESTÁ EL COLOR ROJO/NARANJA/VERDE
            st.markdown("</div>", unsafe_allow_html=True)
            
        with c3:
            st.markdown("<div class='card-style'>", unsafe_allow_html=True)
            graficar_torta_tipo(df_ordenes) # AQUÍ ESTÁ LA DONA
            st.markdown("</div>", unsafe_allow_html=True)

    else: st.info("Sin datos.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    
    if 'tab_index_activos' not in st.session_state: st.session_state['tab_index_activos'] = 0
    
    st.markdown(f"""<style> .stTabs [data-baseweb="tab-list"] {{ border-bottom: 1px solid rgba(255,255,255,0.1); }} </style>""", unsafe_allow_html=True)

    selected_tab = option_menu(
        menu_title=None, 
        options=["Registrar Nuevo", "Editar / Imprimir QR"], 
        icons=["plus-square", "qr-code"], 
        orientation="horizontal", 
        default_index=st.session_state['tab_index_activos'],
        styles={
            "container": {"background-color": "transparent"},
            "nav-link": {"color": "white"},
            "nav-link-selected": {"background-color": COLOR_ACCION, "color": "white", "border-radius":"8px", "font-weight":"bold"}
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
            nombre = c1.text_input("ID / Nombre")
            ubicacion = c2.selectbox("Sub-Área", sub_areas)
            categoria = st.selectbox("Categoría", [""] + LISTA_CATEGORIAS)
            
            if st.form_submit_button("💾 Guardar Activo"):
                if nombre and area_selec and ubicacion and categoria:
                    try:
                        res = supabase.table("activos").insert({
                            "nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria
                        }).execute()
                        if res.data:
                            new_id = res.data[0]['id']
                            url_qr = generar_qr_activo(new_id, nombre)
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                            
                            st.session_state['notification'] = {'type': 'success', 'message': f"Activo '{nombre}' creado."}
                            st.session_state.asset_reset_key += 1
                            st.session_state['tab_index_activos'] = 0
                            st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Faltan campos.")
        st.markdown("</div>", unsafe_allow_html=True)

    elif selected_tab == "Editar / Imprimir QR":
        st.session_state['tab_index_activos'] = 1 
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("🔍 Buscar Activo", [""] + list(activos_dict.keys()))
            
            if seleccion:
                id_sel = activos_dict[seleccion]
                dato = df_activos[df_activos['id'] == id_sel].iloc[0]
                
                st.markdown(f"<div class='card-style'><h2 style='margin:0;'>{dato['nombre']}</h2></div>", unsafe_allow_html=True)

                c1, c2 = st.columns([1,3])
                with c1:
                    if dato.get('qr_url'): st.image(dato['qr_url'], caption="QR")
                    else: 
                        if st.button("Generar QR"):
                            url_qr = generar_qr_activo(id_sel, dato['nombre'])
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_sel)).execute()
                            st.rerun()
                with c2: st.info("Usa este QR para identificar el equipo.")
                
                st.markdown(f"<div class='card-style'><h4>🛠️ Modificar</h4>", unsafe_allow_html=True)
                area_actual = dato.get('area', '')
                idx_area = 0
                if area_actual in ESTRUCTURA_AREAS: 
                    idx_area = ([""] + list(ESTRUCTURA_AREAS.keys())).index(area_actual)
                new_area = st.selectbox("Área", [""] + list(ESTRUCTURA_AREAS.keys()), index=idx_area, key=f"edit_area_{id_sel}")
                sub_areas_disp = [""] + ESTRUCTURA_AREAS.get(new_area, []) if new_area else [""]
                ubic_actual = dato.get('ubicacion', '')
                idx_ubic = 0
                if ubic_actual in sub_areas_disp: idx_ubic = sub_areas_disp.index(ubic_actual)
                
                with st.form("edit_form"):
                    c1, c2 = st.columns(2)
                    new_nombre = c1.text_input("Nombre", value=dato['nombre'])
                    new_ubic = c2.selectbox("Ubicación", sub_areas_disp, index=idx_ubic)
                    cat_actual = dato.get('categoria', '')
                    idx_cat = 0
                    if cat_actual in LISTA_CATEGORIAS: idx_cat = ([""] + LISTA_CATEGORIAS).index(cat_actual)
                    new_cat = st.selectbox("Categoría", [""] + LISTA_CATEGORIAS, index=idx_cat)

                    if st.form_submit_button("🔄 Actualizar"):
                        supabase.table("activos").update({
                            "nombre": new_nombre, "ubicacion": new_ubic, "area": new_area, "categoria": new_cat
                        }).eq("id", int(id_sel)).execute()
                        st.session_state['notification'] = {'type': 'success', 'message': "Actualizado."}
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
                
                with st.expander("🚫 ZONA DE PELIGRO"):
                    st.warning("Esto borrará el activo y su historial.")
                    confirmar_borrado = st.checkbox("Confirmar eliminación.")
                    if st.button("🔥 ELIMINAR", type="primary", disabled=not confirmar_borrado):
                        try:
                            supabase.table("ordenes").delete().eq("activo_id", int(id_sel)).execute()
                            supabase.table("activos").delete().eq("id", int(id_sel)).execute()
                            st.session_state['notification'] = {'type': 'delete', 'message': "Eliminado."}
                            st.rerun()
                        except Exception as e: st.error(f"Error: {e}")
        else: st.info("Sin activos.")

elif choice == "Crear Orden":
    st.subheader("Nueva Orden")
    mostrar_notificaciones()

    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin'])]['nombre'].tolist() if not df_users.empty else []
    
    if not df_activos.empty:
        activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
        st.markdown(f"<div class='card-style'>", unsafe_allow_html=True)
        sel = st.selectbox("Equipo", list(activos_dict.keys()))
        col_a, col_b = st.columns(2)
        tipo = col_a.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo"])
        crit = col_b.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        desc = st.text_area("Descripción")
        asig = st.selectbox("Técnico", tecnicos)
        
        if st.button("🚀 Crear Orden", use_container_width=True):
            supabase.table("ordenes").insert({
                "activo_id": activos_dict[sel], "descripcion": desc, "criticidad": crit, 
                "tipo_mantenimiento": tipo, "estado": "Abierta", 
                "fecha_creacion": datetime.now().isoformat(), "tecnico_asignado": asig
            }).execute()
            st.session_state['notification'] = {'type': 'success', 'message': "Orden creada."}
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else: st.warning("Sin activos.")

elif choice == "Usuarios":
    st.subheader("Usuarios")
    st.markdown("<div class='card-style'>Gestión de usuarios.</div>", unsafe_allow_html=True)

elif choice == "Cierre de OTs":
    st.subheader("Cierre")
    mostrar_notificaciones()
    
    df_ots = run_query("ordenes")
    if not df_ots.empty:
        mis_ots = df_ots if rol_actual != "Tecnico" else df_ots[df_ots['tecnico_asignado'] == usuario_actual]
        mis_ots = mis_ots[mis_ots['estado'] != 'Concluida']
        
        if not mis_ots.empty:
            st.markdown(f"<div class='card-style'>", unsafe_allow_html=True)
            st.dataframe(mis_ots[['id','descripcion','estado']], use_container_width=True)
            sel_id = st.selectbox("ID Orden", mis_ots['id'].values)
            with st.form("close_form"):
                coment = st.text_area("Informe")
                foto = st.file_uploader("Evidencia")
                if st.form_submit_button("✅ Finalizar"):
                    url = subir_imagen(foto)
                    supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre": coment, "evidencia_url": url}).eq("id", int(sel_id)).execute()
                    st.session_state['notification'] = {'type': 'success', 'message': "Orden cerrada."}
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        else: st.info("Nada pendiente.")
