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
import plotly.express as px # NUEVO: Para gráficos transparentes y animados

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="centered", initial_sidebar_state="collapsed")

# ==============================================================================
# 🎨 TEMA: "KINETIC GLASS" (Limpio, Atrevido, Animado)
# ==============================================================================

# PALETA ATREVIDA PERO LIMPIA
ACCENT_1 = "#00F5D4" # Turquesa Neón (Energía)
ACCENT_2 = "#F15BB5" # Magenta (Acción/Alerta)
BG_GRADIENT_1 = "#0F172A" # Azul Noche Profundo
BG_GRADIENT_2 = "#312E81" # Indigo
TEXT_MAIN = "#F8FAFC"
GLASS_BG = "rgba(255, 255, 255, 0.05)" # Vidrio semitransparente

st.markdown(f"""
    <style>
    /* --- ANIMACIONES --- */
    @keyframes fadeIn {{
        from {{ opacity: 0; transform: translateY(20px); }}
        to {{ opacity: 1; transform: translateY(0); }}
    }}
    
    @keyframes pulseGlow {{
        0% {{ box-shadow: 0 0 10px rgba(0, 245, 212, 0.1); }}
        50% {{ box-shadow: 0 0 20px rgba(0, 245, 212, 0.3); }}
        100% {{ box-shadow: 0 0 10px rgba(0, 245, 212, 0.1); }}
    }}

    /* 1. FONDO LIMPIO PERO PROFUNDO */
    .stApp {{
        background: linear-gradient(135deg, {BG_GRADIENT_1} 0%, {BG_GRADIENT_2} 100%);
        background-attachment: fixed;
        color: {TEXT_MAIN};
    }}

    /* 2. BARRA LATERAL */
    [data-testid="stSidebar"] {{
        background-color: rgba(15, 23, 42, 0.95);
        border-right: 1px solid rgba(255,255,255,0.1);
    }}

    /* 3. EFECTO VIDRIO (GLASSMORPHISM) PARA TARJETAS */
    .card-style {{
        background: {GLASS_BG};
        backdrop-filter: blur(16px); /* El truco del vidrio */
        -webkit-backdrop-filter: blur(16px);
        border-radius: 20px;
        padding: 30px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 25px;
        animation: fadeIn 0.6s ease-out; /* Animación de entrada */
    }}
    
    /* 4. TÍTULOS ATREVIDOS */
    h1, h2, h3 {{
        background: linear-gradient(90deg, {ACCENT_1}, {ACCENT_2});
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 900 !important;
        letter-spacing: -0.5px;
    }}

    /* 5. CORRECCIÓN DE MENÚS DESPLEGABLES (CRÍTICO) */
    /* Fondo del input select */
    .stSelectbox > div > div {{
        background-color: rgba(15, 23, 42, 0.6) !important;
        color: white !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        border-radius: 12px;
    }}
    /* Fondo de la lista desplegable (Popover) */
    div[data-baseweb="popover"] {{
        background-color: #0F172A !important;
        border: 1px solid {ACCENT_1};
    }}
    /* Opciones individuales */
    div[data-baseweb="menu"] li {{
        background-color: #0F172A !important;
        color: white !important;
    }}
    div[data-baseweb="menu"] li:hover {{
        background-color: {ACCENT_2} !important; /* Color al pasar el mouse */
        color: white !important;
    }}
    /* Texto seleccionado */
    div[data-baseweb="select"] span {{
        color: white !important;
    }}
    
    /* 6. INPUTS DE TEXTO */
    .stTextInput input, .stTextArea textarea {{
        background-color: rgba(0,0,0,0.3) !important;
        color: white !important;
        border-radius: 12px;
        border: 1px solid rgba(255,255,255,0.1) !important;
    }}
    .stTextInput input:focus, .stTextArea textarea:focus {{
        border-color: {ACCENT_1} !important;
        box-shadow: 0 0 15px rgba(0, 245, 212, 0.2);
    }}

    /* 7. BOTONES ANIMADOS */
    div.stButton > button:first-child {{
        background: linear-gradient(45deg, {ACCENT_1}, #4361ee) !important;
        color: #0F172A !important;
        border: none;
        border-radius: 12px;
        font-weight: 800;
        padding: 0.7rem 2rem;
        transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275); /* Efecto rebote */
        text-transform: uppercase;
        letter-spacing: 1px;
    }}
    div.stButton > button:first-child:hover {{
        transform: scale(1.05) translateY(-3px);
        box-shadow: 0 10px 25px rgba(0, 245, 212, 0.4);
    }}
    
    /* 8. MÉTRICAS FLOTANTES */
    [data-testid="stMetric"] {{
        background: rgba(255,255,255,0.03);
        border-radius: 15px;
        padding: 20px;
        border: 1px solid rgba(255,255,255,0.05);
        transition: transform 0.3s;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-5px);
        background: rgba(255,255,255,0.06);
        border-color: {ACCENT_1};
    }}
    [data-testid="stMetricLabel"] {{ color: rgba(255,255,255,0.7) !important; }}
    [data-testid="stMetricValue"] {{ 
        background: linear-gradient(90deg, {ACCENT_1}, white);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 800;
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

# --- GRAFICOS PLOTLY (FONDO TRANSPARENTE) ---
def plot_bar_chart(df, col_x, color_hex, title):
    if df.empty: return
    # Contamos valores
    conteo = df[col_x].value_counts().reset_index()
    conteo.columns = [col_x, 'Cantidad']
    
    fig = px.bar(conteo, x=col_x, y='Cantidad', title=title, 
                 text='Cantidad', color_discrete_sequence=[color_hex])
    
    # Hacemos transparente el fondo para que se integre
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='white'),
        title_font_size=18,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='rgba(255,255,255,0.1)')
    )
    fig.update_traces(textposition='outside')
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
                <div style="padding: 15px; border-radius: 15px; background: rgba(0, 245, 212, 0.15); border: 1px solid {ACCENT_1}; text-align: center; margin-bottom: 20px; box-shadow: 0 0 20px rgba(0, 245, 212, 0.2);">
                    <h2 style="margin:0; color: {ACCENT_1};">🚀 ÉXITO</h2>
                    <p style="font-size: 16px; margin:5px 0 0 0; color: white;">{msg}</p>
                </div>
                """, unsafe_allow_html=True)
                time.sleep(1) 
            
            elif tipo == 'delete':
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 15px; background: rgba(241, 91, 181, 0.15); border: 1px solid {ACCENT_2}; text-align: center; margin-bottom: 20px;">
                    <h3 style="margin:0; color: {ACCENT_2};">♻️ ELIMINADO</h3>
                    <p style="color:white;">{msg}</p>
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
        st.markdown(f"<h1 style='text-align: center;'>{activo['nombre']}</h1>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div class="card-style">
                <h3 style="margin-top:0; color: {ACCENT_1};">Detalles</h3>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)

        st.subheader("🛠️ Últimos Eventos")
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).limit(5).execute()
            if ots.data:
                df_qr = pd.DataFrame(ots.data)
                st.markdown("<style>th{color: #00F5D4 !important;}</style>", unsafe_allow_html=True)
                st.table(df_qr[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Sin historial.")
        except: pass
            
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 Inicio"):
                st.query_params.clear()
                st.rerun()
        with c2:
            if st.session_state.get('usuario') is None:
                if st.button("🔐 Login"):
                    st.query_params.clear()
                    st.rerun()
    else:
        st.error("❌ Activo no encontrado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    st.stop() 


# ==============================================================================
# 🚀 ZONA 2: LOGIN / SCANNER
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear()
    st.rerun()

if st.session_state['usuario'] is None:
    st.markdown("<h1 style='text-align: center; font-size: 3rem;'>CMMS <span style='color:#00F5D4'>KINETIC</span></h1>", unsafe_allow_html=True)
    
    st.markdown(f"""
        <style>
            .stTabs [data-baseweb="tab-list"] {{ border-bottom: none; }}
            .stTabs [aria-selected="true"] {{ color: {ACCENT_1} !important; border-bottom: 3px solid {ACCENT_1}; }}
        </style>
    """, unsafe_allow_html=True)

    tab_login, tab_scan = st.tabs(["🔐 ACCESO", "📷 ESCÁNER"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            st.markdown("<div class='card-style' style='text-align:center;'><h3>Bienvenido</h3>", unsafe_allow_html=True)
            with st.form("login_form"):
                documento = st.text_input("Usuario")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("ENTRAR AL SISTEMA", type="primary", use_container_width=True)
                
                if submitted:
                    try:
                        response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()
                        if response.data:
                            user_data = response.data[0]
                            st.session_state['usuario'] = user_data['nombre']
                            st.session_state['rol'] = user_data['rol']
                            st.rerun()
                        else:
                            st.error("Credenciales incorrectas.")
                    except:
                        st.error("Error de conexión.")
            st.markdown("</div>", unsafe_allow_html=True)

    with tab_scan:
        st.markdown("<div class='card-style' style='text-align:center;'>", unsafe_allow_html=True)
        st.info("Escanea el QR del equipo")
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        if img_file is not None:
            id_detectado = leer_qr_imagen(img_file)
            if id_detectado:
                st.query_params["id_activo_qr"] = id_detectado
                st.rerun()
            else:
                st.warning("QR no válido.")
        st.markdown("</div>", unsafe_allow_html=True)
    st.stop()


# ==============================================================================
# 🚀 ZONA 3: DASHBOARD PRIVADO
# ==============================================================================

rol_actual = st.session_state['rol']
usuario_actual = st.session_state['usuario']

with st.sidebar:
    st.markdown(f"""
        <div style="background: rgba(255,255,255,0.05); padding: 20px; border-radius: 15px; text-align: center; margin-bottom: 20px; border: 1px solid rgba(255,255,255,0.1);">
            <div style="width: 60px; height: 60px; background: linear-gradient(135deg, {ACCENT_1}, {ACCENT_2}); border-radius: 50%; margin: 0 auto 10px auto; display: flex; align-items: center; justify-content: center; font-size: 24px;">👤</div>
            <h3 style="margin:10px 0; font-size: 18px; color: white;">{usuario_actual}</h3>
            <span style="background: {ACCENT_1}; color: #0F172A; padding: 4px 12px; border-radius: 20px; font-size: 11px; font-weight: 900; letter-spacing: 1px;">{rol_actual.upper()}</span>
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
        menu_title="MENÚ",
        options=options_menu,
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": ACCENT_1, "font-size": "18px"}, 
            "nav-link": {"font-size": "15px", "text-align": "left", "margin": "5px", "color": "#cbd5e1"},
            "nav-link-selected": {"background": f"linear-gradient(90deg, {ACCENT_1}, #4361ee)", "color": "#0F172A", "border-radius": "10px", "font-weight":"bold"},
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
    st.subheader("Panel de Control")
    mostrar_notificaciones()
    
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        
        st.divider()
        
        # --- USAMOS PLOTLY PARA GRÁFICOS INTEGRADOS Y ATREVIDOS ---
        c1, c2, c3 = st.columns(3)
        with c1: 
            plot_bar_chart(df_ordenes, 'estado', ACCENT_1, "Estado")
        with c2: 
            plot_bar_chart(df_ordenes, 'criticidad', ACCENT_2, "Criticidad")
        with c3: 
            if 'tipo_mantenimiento' in df_ordenes.columns: 
                plot_bar_chart(df_ordenes, 'tipo_mantenimiento', '#4361ee', "Tipo")
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
            "nav-link-selected": {"background-color": ACCENT_1, "color": "#0F172A", "border-radius":"10px", "font-weight":"bold"}
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
            
            if st.form_submit_button("💾 Guardar"):
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
                with c2: st.info("Usa este QR para el equipo.")
                
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
                    confirmar_borrado = st.checkbox("Confirmar eliminación irreversible.")
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
