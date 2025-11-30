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

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="centered", initial_sidebar_state="collapsed")

# --- 2. CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_supabase()
except Exception as e:
    st.error("Error conectando a Supabase. Revisa los Secrets.")
    st.stop()

# --- 3. FUNCIONES AUXILIARES ---

def run_query(table_name):
    try:
        response = supabase.table(table_name).select("*").order("id").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
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
        except Exception as e:
            return None
    return None

def generar_qr_activo(id_activo, nombre_activo):
    # ================================================================
    # ⚠️ RECUERDA: PON AQUÍ TU URL REAL DE DEPLOY (NO LOCALHOST) ⚠️
    # ================================================================
    base_url = "https://tu-app-en-internet.streamlit.app" 
    
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

# ==============================================================================
# 🚀 INTERCEPTOR PRIORITARIO (ESTO SE EJECUTA ANTES DE CUALQUIER LOGIN)
# ==============================================================================
query_params = st.query_params

# Si la URL tiene ?id_activo_qr=..., ignoramos el login y mostramos la info
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    
    # 1. Buscamos el activo
    try:
        datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    except:
        st.error("Error conectando a la base de datos.")
        st.stop()
    
    if datos_activo.data:
        activo = datos_activo.data[0]
        
        # MOSTRAR FICHA TÉCNICA PUBLICA
        st.markdown(f"<h1 style='text-align: center;'>📋 {activo['nombre']}</h1>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #007bff;">
                <p style="font-size: 18px;"><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p style="font-size: 18px;"><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p style="font-size: 18px;"><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)

        st.subheader("🛠️ Historial de Mantenimiento")
        ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).execute()
        
        if ots.data:
            df_ots_qr = pd.DataFrame(ots.data)
            col1, col2 = st.columns(2)
            col1.metric("Total Intervenciones", len(df_ots_qr))
            pendientes = len(df_ots_qr[df_ots_qr['estado'] == 'Abierta'])
            col2.metric("Pendientes", pendientes, delta_color="inverse" if pendientes > 0 else "normal")
            
            st.dataframe(df_ots_qr[['fecha_creacion', 'tipo_mantenimiento', 'descripcion', 'estado']], use_container_width=True, hide_index=True)
        else:
            st.info("Equipo nuevo o sin registros históricos.")

        st.markdown("---")
        if st.button("🏠 Ir al Inicio (Salir de Ficha)"):
            st.query_params.clear()
            st.rerun()

    else:
        st.error("❌ El equipo que intentas buscar no existe.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    
    # IMPORTANTE: Esto detiene la app aquí para que NO pida login
    st.stop()


# ==============================================================================
# 🚪 ZONA DE ACCESO (SI NO HAY QR EN LA URL)
# ==============================================================================

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.rerun()

# Si no está logueado, mostramos Pestañas (Login / Escáner)
if st.session_state['usuario'] is None:
    
    st.markdown("<h1 style='text-align: center;'>🏭 Mantenimiento App</h1>", unsafe_allow_html=True)
    
    tab_login, tab_scan = st.tabs(["🔐 Ingreso Personal", "📷 Escáner Visitante"])
    
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            with st.form("login_form"):
                documento = st.text_input("Documento")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
                
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
                        st.error("Error de conexión.")

    with tab_scan:
        st.info("Toma una foto al código QR del equipo.")
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        
        if img_file is not None:
            id_detectado = leer_qr_imagen(img_file)
            if id_detectado:
                # TRUCO: Si detectamos QR, recargamos la página poniendo el ID en la URL
                # Esto activará el "Interceptor Prioritario" de arriba.
                st.query_params["id_activo_qr"] = id_detectado
                st.rerun()
            else:
                st.warning("No se detectó QR. Intenta acercarte más.")
    
    # Detenemos para no mostrar el dashboard
    st.stop()


# ==============================================================================
# 🖥️ DASHBOARD PRIVADO (SOLO LOGUEADOS)
# ==============================================================================

# Si llegamos aquí, es porque NO hay QR en la URL Y el usuario SÍ está logueado
rol_actual = st.session_state['rol']
usuario_actual = st.session_state['usuario']

with st.sidebar:
    st.markdown(f"""
        <div style="background-color: #333; padding: 10px; border-radius: 10px; text-align: center; margin-bottom: 20px;">
            <h3 style="margin:0; color: white;">👤 {usuario_actual}</h3>
            <p style="margin:0; color: #aaa; font-size: 14px;">Rol: {rol_actual}</p>
        </div>
    """, unsafe_allow_html=True)
    if st.button("Cerrar Sesión", use_container_width=True): logout()
    st.write("") 

    options_menu = []
    if rol_actual == "Admin": options_menu = ["Dashboard", "Gestión de Activos", "Crear Orden", "Cierre de OTs", "Usuarios"]
    elif rol_actual == "Programador": options_menu = ["Dashboard", "Crear Orden", "Usuarios"] 
    elif rol_actual == "Tecnico": options_menu = ["Cierre de OTs"] 
    
    choice = option_menu(menu_title="MENÚ", options=options_menu, icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"], default_index=0)

if choice == "Dashboard":
    st.subheader("Tablero de Control")
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        st.bar_chart(df_ordenes['estado'].value_counts(), color="#00b09b") 
    else: st.info("Sin datos.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    if 'asset_msg' in st.session_state:
        msg = st.session_state['asset_msg']
        if msg['tipo'] == 'create': st.success(f"✅ Creado: {msg['nombre']}")
        del st.session_state['asset_msg']

    df_activos = run_query("activos")
    
    ESTRUCTURA_AREAS = {
        "Logística": ["Almacén Materia Prima", "Almacén Producto Terminado", "Distribución", "Taller Vehicular"],
        "Administración": ["Administración", "Servicios Generales"],
        "Técnica": ["Agua Cristal", "Linea 8", "Linea 2", "Linea 3", "Linea 1", "Linea 10", "Salas de Jarabe Terminado", "Sala de Jarabes Jugos", "Sala de Jarabe Simple", "Oficinas Técnicas", "Equipos Auxiliares", "Ptap", "Ptar"],
        "Ventas": ["Ventas", "Bodega de Publicidad"]
    }
    LISTA_CATEGORIAS_TECNICAS = ["Mecánico", "Eléctrico", "Infraestructura", "HVAC", "Otros"]

    if 'tab_index_activos' not in st.session_state: st.session_state['tab_index_activos'] = 0
    selected_tab = option_menu(menu_title=None, options=["Registrar Nuevo", "Editar / Imprimir QR"], icons=["plus-square", "qr-code"], orientation="horizontal", default_index=st.session_state['tab_index_activos'])
    
    if selected_tab == "Registrar Nuevo":
        if 'asset_reset_key' not in st.session_state: st.session_state.asset_reset_key = 0
        area_selec = st.selectbox("Área", [""] + list(ESTRUCTURA_AREAS.keys()), key=f"area_create_{st.session_state.asset_reset_key}")
        sub_areas = [""] + ESTRUCTURA_AREAS.get(area_selec, []) if area_selec else [""]
        
        with st.form("form_activo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre")
            ubicacion = c2.selectbox("Ubicación", sub_areas)
            categoria = st.selectbox("Categoría", [""] + LISTA_CATEGORIAS_TECNICAS)
            
            if st.form_submit_button("Guardar"):
                if nombre and area_selec and ubicacion:
                    res = supabase.table("activos").insert({"nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria}).execute()
                    if res.data:
                        new_id = res.data[0]['id']
                        url_qr = generar_qr_activo(new_id, nombre)
                        supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                        st.session_state['asset_msg'] = {'tipo': 'create', 'nombre': nombre}
                        st.session_state.asset_reset_key += 1
                        st.rerun()
                else: st.warning("Datos incompletos.")

    elif selected_tab == "Editar / Imprimir QR":
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("Seleccionar Activo", [""] + list(activos_dict.keys()))
            if seleccion:
                id_sel = activos_dict[seleccion]
                dato = df_activos[df_activos['id'] == id_sel].iloc[0]
                
                c1, c2 = st.columns([1,3])
                with c1:
                    if dato.get('qr_url'): st.image(dato['qr_url'])
                    else: 
                        if st.button("Generar QR"):
                            url_qr = generar_qr_activo(id_sel, dato['nombre'])
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_sel)).execute()
                            st.rerun()
                with c2:
                    st.info(f"Ficha de: {dato['nombre']}")
                
                # Formulario simple de edición
                with st.form("edit_form"):
                    nuevo_nombre = st.text_input("Nombre", value=dato['nombre'])
                    if st.form_submit_button("Actualizar Nombre"):
                        supabase.table("activos").update({"nombre": nuevo_nombre}).eq("id", int(id_sel)).execute()
                        st.rerun()
                
                if st.button("Eliminar Activo"):
                    supabase.table("activos").delete().eq("id", int(id_sel)).execute()
                    st.rerun()

elif choice == "Crear Orden":
    st.subheader("Crear OT")
    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin'])]['nombre'].tolist() if not df_users.empty else []
    
    if not df_activos.empty:
        activos_dict = {row['nombre']: row['id'] for i, row in df_activos.iterrows()}
        sel = st.selectbox("Equipo", list(activos_dict.keys()))
        desc = st.text_area("Descripción")
        asig = st.selectbox("Asignar", tecnicos)
        if st.button("Crear"):
            supabase.table("ordenes").insert({"activo_id": activos_dict[sel], "descripcion": desc, "estado": "Abierta", "tecnico_asignado": asig, "fecha_creacion": datetime.now().isoformat()}).execute()
            st.success("Creada")
            st.rerun()
    else: st.warning("No hay activos.")

elif choice == "Usuarios":
    st.info("Gestión de Usuarios")

elif choice == "Cierre de OTs":
    st.subheader("Cerrar OT")
    df_ots = run_query("ordenes")
    if not df_ots.empty:
        mis_ots = df_ots if rol_actual != "Tecnico" else df_ots[df_ots['tecnico_asignado'] == usuario_actual]
        mis_ots = mis_ots[mis_ots['estado'] != 'Concluida']
        
        if not mis_ots.empty:
            st.dataframe(mis_ots)
            sel_id = st.selectbox("ID Orden", mis_ots['id'])
            comentario = st.text_area("Informe")
            foto = st.file_uploader("Evidencia")
            if st.button("Cerrar"):
                url = subir_imagen(foto)
                supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre": comentario, "evidencia_url": url}).eq("id", int(sel_id)).execute()
                st.success("Cerrada")
                st.rerun()
        else: st.info("Nada pendiente.")
