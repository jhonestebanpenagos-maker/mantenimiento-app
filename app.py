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

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="centered", initial_sidebar_state="collapsed")

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
    # ⚠️ CAMBIA ESTO POR LA URL REAL DE TU APP EN STREAMLIT CLOUD ⚠️
    # ==============================================================================
    base_url = "https://mantenimiento-app-esw6r3vpeqxngz3ifyp5ey.streamlit.app/" 
    
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
    """Lee QR desde una imagen subida o de cámara"""
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
# 🚀 ZONA 1: INTERCEPTOR PÚBLICO (ACCESO SIN LOGIN)
# ==============================================================================
# Esta sección se ejecuta SIEMPRE que haya un QR en la URL, sin importar el usuario.

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
        
        # --- VISTA PÚBLICA / VISITANTE ---
        st.markdown(f"<h1 style='text-align: center;'>📋 Ficha Técnica: {activo['nombre']}</h1>", unsafe_allow_html=True)
        
        st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 5px solid #28a745;">
                <h3 style="margin-top:0;">Detalles del Equipo</h3>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
                <p style="font-size: 12px; color: #666;">ID Sistema: {activo['id']}</p>
            </div>
        """, unsafe_allow_html=True)

        st.subheader("🛠️ Últimos Mantenimientos")
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).limit(5).execute()
            if ots.data:
                df_qr = pd.DataFrame(ots.data)
                # Mostramos tabla limpia
                st.table(df_qr[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Este equipo no tiene historial registrado.")
        except:
            pass
            
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🏠 Ir al Inicio"):
                st.query_params.clear()
                st.rerun()
        with c2:
            if st.session_state.get('usuario') is None:
                if st.button("🔐 Login Técnico"):
                    st.query_params.clear()
                    st.rerun()
            
    else:
        st.error("❌ El activo escaneado no existe o fue eliminado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
            
    # 🛑 DETENER EJECUCIÓN: El visitante no ve nada más.
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

# Si NO está logueado, mostramos el Hub de Entrada
if st.session_state['usuario'] is None:
    
    st.markdown("<h1 style='text-align: center;'>🏭 CMMS Industrial</h1>", unsafe_allow_html=True)
    
    tab_login, tab_scan = st.tabs(["🔐 Ingreso Personal", "📷 Escáner Visitante"])
    
    # PESTAÑA LOGIN
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

    # PESTAÑA ESCÁNER PÚBLICO
    with tab_scan:
        st.info("📷 Toma una foto al código QR del equipo para ver su ficha técnica.")
        img_file = st.camera_input("Escanear", label_visibility="collapsed")
        
        if img_file is not None:
            id_detectado = leer_qr_imagen(img_file)
            if id_detectado:
                # TRUCO: Recargamos poniendo el ID en la URL para activar la ZONA 1
                st.query_params["id_activo_qr"] = id_detectado
                st.rerun()
            else:
                st.warning("⚠️ No se detectó QR. Intenta acercarte más.")
    
    # 🛑 DETENER EJECUCIÓN: No mostrar dashboard si no hay login
    st.stop()


# ==============================================================================
# 🚀 ZONA 3: DASHBOARD PRIVADO (SOLO USUARIOS LOGUEADOS)
# ==============================================================================

# Si el código llega aquí, es porque el usuario YA inició sesión.

rol_actual = st.session_state['rol']
usuario_actual = st.session_state['usuario']

# --- BARRA LATERAL ---
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
        default_index=0
    )

# --- DICCIONARIOS MAESTROS (Para Listas Desplegables) ---
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
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes))
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        st.divider()
        c1, c2, c3 = st.columns(3)
        with c1: st.bar_chart(df_ordenes['estado'].value_counts(), color="#00b09b") 
        with c2: st.bar_chart(df_ordenes['criticidad'].value_counts(), color="#ff6b6b")
        with c3: 
            if 'tipo_mantenimiento' in df_ordenes.columns: 
                st.bar_chart(df_ordenes['tipo_mantenimiento'].value_counts(), color="#ffaa00")
    else: st.info("Sin datos.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    
    # Mensajes de Feedback
    if 'asset_msg' in st.session_state:
        msg = st.session_state['asset_msg']
        if msg['tipo'] == 'create': st.success(f"✅ Activo Creado: {msg['nombre']}")
        elif msg['tipo'] == 'update': st.info(f"🔄 Activo Actualizado: {msg['nombre']}")
        del st.session_state['asset_msg']

    df_activos = run_query("activos")
    
    if 'tab_index_activos' not in st.session_state: st.session_state['tab_index_activos'] = 0
    
    selected_tab = option_menu(
        menu_title=None, 
        options=["Registrar Nuevo", "Editar / Imprimir QR"], 
        icons=["plus-square", "qr-code"], 
        orientation="horizontal", 
        default_index=st.session_state['tab_index_activos']
    )
    
    # VISTA 1: CREAR
    if selected_tab == "Registrar Nuevo":
        if 'asset_reset_key' not in st.session_state: st.session_state.asset_reset_key = 0
        
        st.write("#### Ubicación")
        # Selector Área
        area_selec = st.selectbox("Área", [""] + list(ESTRUCTURA_AREAS.keys()), key=f"area_create_{st.session_state.asset_reset_key}")
        # Selector Sub-Área (Dependiente)
        sub_areas = [""] + ESTRUCTURA_AREAS.get(area_selec, []) if area_selec else [""]
        
        st.write("#### Datos Técnicos")
        with st.form("form_activo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre del Equipo")
            ubicacion = c2.selectbox("Sub-Área / Ubicación", sub_areas)
            categoria = st.selectbox("Categoría Técnica", [""] + LISTA_CATEGORIAS)
            
            if st.form_submit_button("Guardar Activo y Generar QR"):
                if nombre and area_selec and ubicacion and categoria:
                    try:
                        # 1. Insertar
                        res = supabase.table("activos").insert({
                            "nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria
                        }).execute()
                        
                        if res.data:
                            new_id = res.data[0]['id']
                            # 2. Generar QR
                            url_qr = generar_qr_activo(new_id, nombre)
                            # 3. Actualizar con QR
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                            
                            st.session_state['asset_msg'] = {'tipo': 'create', 'nombre': nombre}
                            st.session_state.asset_reset_key += 1
                            st.session_state['tab_index_activos'] = 0
                            st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")
                else:
                    st.warning("Faltan campos obligatorios.")

    # VISTA 2: EDITAR
    elif selected_tab == "Editar / Imprimir QR":
        st.session_state['tab_index_activos'] = 1 
        
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("Buscar Activo", [""] + list(activos_dict.keys()))
            
            if seleccion:
                id_sel = activos_dict[seleccion]
                dato = df_activos[df_activos['id'] == id_sel].iloc[0]
                
                st.markdown("---")
                c1, c2 = st.columns([1,3])
                with c1:
                    if dato.get('qr_url'): st.image(dato['qr_url'], caption="QR")
                    else: 
                        if st.button("Generar QR Faltante"):
                            url_qr = generar_qr_activo(id_sel, dato['nombre'])
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_sel)).execute()
                            st.rerun()
                with c2:
                    st.info(f"Ficha de: {dato['nombre']}")
                    st.caption("Imprime este QR para el equipo.")
                
                st.markdown("---")
                
                # Edición con Listas Dependientes
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

                    if st.form_submit_button("Actualizar"):
                        supabase.table("activos").update({
                            "nombre": new_nombre, "ubicacion": new_ubic, "area": new_area, "categoria": new_cat
                        }).eq("id", int(id_sel)).execute()
                        st.session_state['asset_msg'] = {'tipo': 'update', 'nombre': new_nombre}
                        st.rerun()

                with st.expander("Borrar Activo"):
                    if st.button("Eliminar Definitivamente"):
                        supabase.table("activos").delete().eq("id", int(id_sel)).execute()
                        st.rerun()
        else:
            st.info("No hay activos.")

elif choice == "Crear Orden":
    st.subheader("Crear OT")
    df_activos = run_query("activos")
    df_users = run_query("usuarios")
    tecnicos = df_users[df_users['rol'].isin(['Tecnico','Admin'])]['nombre'].tolist() if not df_users.empty else []
    
    if not df_activos.empty:
        activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
        sel = st.selectbox("Equipo", list(activos_dict.keys()))
        col_a, col_b = st.columns(2)
        tipo = col_a.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo"])
        crit = col_b.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        desc = st.text_area("Descripción")
        asig = st.selectbox("Asignar", tecnicos)
        
        if st.button("Crear OT"):
            supabase.table("ordenes").insert({
                "activo_id": activos_dict[sel], "descripcion": desc, "criticidad": crit, 
                "tipo_mantenimiento": tipo, "estado": "Abierta", 
                "fecha_creacion": datetime.now().isoformat(), "tecnico_asignado": asig
            }).execute()
            st.success("OT Creada")
            st.rerun()
    else: st.warning("Crea activos primero.")

elif choice == "Usuarios":
    # CRUD Usuarios simplificado (ya lo tienes completo en versiones anteriores)
    st.info("Gestión de Usuarios Activa") 

elif choice == "Cierre de OTs":
    st.subheader("Mis Órdenes")
    df_ots = run_query("ordenes")
    if not df_ots.empty:
        mis_ots = df_ots if rol_actual != "Tecnico" else df_ots[df_ots['tecnico_asignado'] == usuario_actual]
        mis_ots = mis_ots[mis_ots['estado'] != 'Concluida']
        
        if not mis_ots.empty:
            st.dataframe(mis_ots[['id','descripcion','estado']])
            sel_id = st.selectbox("Seleccionar ID", mis_ots['id'].values)
            with st.form("close_form"):
                coment = st.text_area("Informe")
                foto = st.file_uploader("Evidencia")
                if st.form_submit_button("Cerrar"):
                    url = subir_imagen(foto)
                    supabase.table("ordenes").update({"estado":"Concluida", "comentarios_cierre": coment, "evidencia_url": url}).eq("id", int(sel_id)).execute()
                    st.success("Cerrada")
                    st.rerun()
        else: st.info("Nada pendiente.")
