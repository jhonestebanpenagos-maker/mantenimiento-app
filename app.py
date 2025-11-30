import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io
import urllib.parse
import json
import qrcode
import cv2 # Para leer QR
import numpy as np # Para procesar la imagen

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
    # Pega aquí tu URL real de la app desplegada
    base_url = "https://tu-app-mantenimiento.streamlit.app" 
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
    """Recibe una imagen de Streamlit, busca un QR y devuelve el ID del activo"""
    try:
        # Convertir la imagen subida a un formato que OpenCV entienda
        file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        
        # Detector de QR de OpenCV
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        
        if data:
            # El QR devuelve algo como: https://app.com/?id_activo_qr=5
            # Necesitamos extraer solo el número "5"
            parsed_url = urllib.parse.urlparse(data)
            params = urllib.parse.parse_qs(parsed_url.query)
            
            if 'id_activo_qr' in params:
                return params['id_activo_qr'][0] # Retorna el ID (ej: "5")
        return None
    except Exception as e:
        return None

# --- 4. GESTIÓN DE ESTADO ---

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.query_params.clear() 
    st.rerun()

# =======================================================
# 🚀 PANTALLA DE INICIO (LOGIN vs VISITANTE)
# =======================================================

# Si NO está logueado, mostramos el Hub de Acceso
if st.session_state['usuario'] is None:
    
    st.markdown("<h1 style='text-align: center;'>🏭 Gestión de Activos</h1>", unsafe_allow_html=True)
    
    # Creamos dos pestañas grandes
    tab_login, tab_scan = st.tabs(["🔐 Ingreso Personal", "📷 Escáner Visitante"])
    
    # --- PESTAÑA 1: LOGIN TÉCNICOS ---
    with tab_login:
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            st.write("")
            with st.form("login_form"):
                documento = st.text_input("Número de Documento")
                password = st.text_input("Contraseña", type="password")
                submitted = st.form_submit_button("Iniciar Sesión", type="primary", use_container_width=True)
                
                if submitted:
                    try:
                        response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()
                        if response.data:
                            user_data = response.data[0]
                            st.session_state['usuario'] = user_data['nombre']
                            st.session_state['rol'] = user_data['rol']
                            st.rerun()
                        else:
                            st.error("Acceso denegado.")
                    except:
                        st.error("Error de conexión.")

    # --- PESTAÑA 2: ESCÁNER VISITANTE (LO QUE PEDISTE) ---
    with tab_scan:
        st.markdown("<h3 style='text-align: center;'>Escanear Código QR del Equipo</h3>", unsafe_allow_html=True)
        st.info("Permite el uso de la cámara y toma una foto clara del código QR pegado en el activo.")
        
        # Widget de Cámara
        img_file = st.camera_input("📸 Tomar Foto del QR", label_visibility="collapsed")
        
        if img_file is not None:
            # Procesamos la imagen
            id_detectado = leer_qr_imagen(img_file)
            
            if id_detectado:
                st.success(f"✅ QR Detectado. Buscando Activo ID: {id_detectado}...")
                
                # Buscamos en BD
                try:
                    datos = supabase.table("activos").select("*").eq("id", id_detectado).execute()
                    if datos.data:
                        activo = datos.data[0]
                        st.divider()
                        st.markdown(f"<h2 style='text-align: center;'>{activo['nombre']}</h2>", unsafe_allow_html=True)
                        
                        st.markdown(f"""
                        <div style="background-color: #e8f5e9; padding: 20px; border-radius: 10px; border: 2px solid #4caf50;">
                            <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                            <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                            <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Historial
                        st.subheader("Historial Reciente")
                        ots = supabase.table("ordenes").select("*").eq("activo_id", id_detectado).order("id", desc=True).limit(5).execute()
                        if ots.data:
                            df = pd.DataFrame(ots.data)
                            st.dataframe(df[['fecha_creacion', 'tipo_mantenimiento', 'estado']], use_container_width=True, hide_index=True)
                        else:
                            st.info("Sin historial de mantenimiento.")
                            
                    else:
                        st.error("El QR es válido, pero el equipo no existe en la base de datos.")
                except Exception as e:
                    st.error(f"Error consultando datos: {e}")
            else:
                st.warning("⚠️ No se detectó ningún código QR en la imagen. Intenta acercarte más o enfocar mejor.")

    # IMPORTANTE: Detenemos la ejecución aquí si no hay usuario.
    # Así no carga el menú lateral ni nada más.
    st.stop()


# =======================================================
# 🖥️ APLICACIÓN PRINCIPAL (SOLO SI ESTÁ LOGUEADO)
# =======================================================

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
    
    choice = option_menu(menu_title="MENÚ PRINCIPAL", options=options_menu, icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"], default_index=0)

# --- PANTALLAS (El resto de tu código sigue igual) ---

if choice == "Dashboard":
    st.subheader("Tablero de Control")
    df_ordenes = run_query("ordenes")
    if not df_ordenes.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Total OTs", len(df_ordenes), delta="Global")
        c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']), delta="Pendientes", delta_color="inverse")
        c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']), delta="Finalizadas", delta_color="normal")
        st.divider()
        c1, c2, c3 = st.columns(3)
        with c1: st.bar_chart(df_ordenes['estado'].value_counts(), color="#00b09b") 
        with c2: st.bar_chart(df_ordenes['criticidad'].value_counts(), color="#ff6b6b")
        with c3: 
            if 'tipo_mantenimiento' in df_ordenes.columns: st.bar_chart(df_ordenes['tipo_mantenimiento'].value_counts(), color="#ffaa00")
    else: st.info("Sin datos.")

elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    if 'asset_msg' in st.session_state:
        msg = st.session_state['asset_msg']
        if msg['tipo'] == 'create': st.success(f"✅ Activo {msg['nombre']} creado.")
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
        st.write("#### Paso 1: Ubicación General")
        area_selec = st.selectbox("Seleccione el Área", [""] + list(ESTRUCTURA_AREAS.keys()), key=f"area_create_{st.session_state.asset_reset_key}")
        sub_areas_disponibles = [""] + ESTRUCTURA_AREAS.get(area_selec, []) if area_selec else [""]

        st.write("#### Paso 2: Detalles del Equipo")
        with st.form("form_activo", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre del Equipo")
            ubicacion = c2.selectbox("Ubicación Específica", sub_areas_disponibles)
            categoria = st.selectbox("Categoría Técnica", [""] + LISTA_CATEGORIAS_TECNICAS)
            
            if st.form_submit_button("Guardar Activo y Generar QR"):
                if nombre and area_selec and ubicacion and categoria:
                    try:
                        data_insert = {"nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria}
                        res = supabase.table("activos").insert(data_insert).execute()
                        if res.data:
                            new_id = res.data[0]['id']
                            url_qr = generar_qr_activo(new_id, nombre)
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                            st.session_state['asset_msg'] = {'tipo': 'create', 'nombre': nombre}
                            st.session_state.asset_reset_key += 1
                            st.session_state['tab_index_activos'] = 0
                            st.rerun()
                    except Exception as e: st.error(f"Error: {e}")
                else: st.warning("Complete todos los campos.")

    elif selected_tab == "Editar / Imprimir QR":
        st.session_state['tab_index_activos'] = 1 
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']} - {row.get('ubicacion','?')}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("Seleccionar Activo", [""] + list(activos_dict.keys()))
            if seleccion:
                id_seleccionado = activos_dict[seleccion]
                datos_actuales = df_activos[df_activos['id'] == id_seleccionado].iloc[0]
                
                st.markdown("---")
                col_qr1, col_qr2 = st.columns([1, 3])
                with col_qr1:
                    if datos_actuales.get('qr_url'): st.image(datos_actuales['qr_url'], caption="QR del Equipo")
                    else:
                        if st.button("Generar QR"):
                            url_qr = generar_qr_activo(id_seleccionado, datos_actuales['nombre'])
                            supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_seleccionado)).execute()
                            st.rerun()
                with col_qr2:
                    st.markdown(f"### 🏷️ Ficha: {datos_actuales['nombre']}")
                    st.info("Imprime esta sección.")
                
                st.markdown("---")
                area_actual_db = datos_actuales.get('area', '')
                idx_area = 0
                if area_actual_db in ESTRUCTURA_AREAS: idx_area = ([""] + list(ESTRUCTURA_AREAS.keys())).index(area_actual_db)
                nueva_area = st.selectbox("Área", [""] + list(ESTRUCTURA_AREAS.keys()), index=idx_area, key=f"edit_area_{id_seleccionado}")
                sub_areas_disp = [""] + ESTRUCTURA_AREAS.get(nueva_area, []) if nueva_area else [""]
                ubic_actual = datos_actuales.get('ubicacion', '')
                idx_ubic = 0
                if ubic_actual in sub_areas_disp: idx_ubic = sub_areas_disp.index(ubic_actual)
                
                with st.form("form_editar"):
                    c1, c2 = st.columns(2)
                    nuevo_nombre = c1.text_input("Nombre", value=datos_actuales['nombre'])
                    nueva_ubicacion = c2.selectbox("Ubicación", sub_areas_disp, index=idx_ubic)
                    cat_actual = datos_actuales.get('categoria', '')
                    idx_cat = 0
                    if cat_actual in LISTA_CATEGORIAS_TECNICAS: idx_cat = ([""] + LISTA_CATEGORIAS_TECNICAS).index(cat_actual)
                    nueva_categoria = st.selectbox("Categoría", [""] + LISTA_CATEGORIAS_TECNICAS, index=idx_cat)

                    if st.form_submit_button("Actualizar"):
                        supabase.table("activos").update({
                            "nombre": nuevo_nombre, "ubicacion": nueva_ubicacion, "area": nueva_area, "categoria": nueva_categoria
                        }).eq("id", int(id_seleccionado)).execute()
                        st.success("Actualizado")
                        st.rerun()

                with st.expander("🗑️ Eliminar Activo"):
                    if st.button("Eliminar Definitivamente"):
                        supabase.table("activos").delete().eq("id", int(id_seleccionado)).execute()
                        st.rerun()
        else: st.info("Sin activos.")

elif choice == "Crear Orden":
    st.subheader("Planificación y Asignación de OTs")
    df_activos = run_query("activos")
    df_usuarios = run_query("usuarios")
    lista_tecnicos = df_usuarios[df_usuarios['rol'].isin(['Tecnico', 'Admin', 'Programador'])]['nombre'].tolist() if not df_usuarios.empty else []

    if not df_activos.empty:
        activos_dict = {f"{row['nombre']} - {row.get('ubicacion','?')}": row['id'] for i, row in df_activos.iterrows()}
        seleccion = st.selectbox("Equipo", list(activos_dict.keys()))
        activo_id = activos_dict[seleccion]
        col_a, col_b = st.columns(2)
        tipo_mant = col_a.selectbox("Tipo", ["Correctivo", "Preventivo", "Predictivo"])
        criticidad = col_b.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        c1, c2 = st.columns(2)
        descripcion = c1.text_area("Descripción")
        asignado_a = c2.selectbox("Asignar a", lista_tecnicos)
        if st.button("Crear OT"):
            supabase.table("ordenes").insert({
                "activo_id": int(activo_id), "descripcion": descripcion, "criticidad": criticidad,
                "tipo_mantenimiento": tipo_mant, "estado": "Abierta", "fecha_creacion": datetime.now().isoformat(), "tecnico_asignado": asignado_a
            }).execute()
            st.success("OT Creada")
            st.rerun()
    else: st.warning("Sin activos")

elif choice == "Usuarios":
    st.info("Módulo de Usuarios activo.")
    
elif choice == "Cierre de OTs":
    st.subheader("Mis Órdenes Pendientes")
    df_ots = run_query("ordenes")
    if not df_ots.empty:
        if rol_actual == "Tecnico": mis_ots = df_ots[(df_ots['tecnico_asignado'] == usuario_actual) & (df_ots['estado'] != 'Concluida')]
        else: mis_ots = df_ots[df_ots['estado'] != 'Concluida']
        if not mis_ots.empty:
            st.dataframe(mis_ots[['id', 'descripcion', 'tipo_mantenimiento', 'tecnico_asignado', 'estado']], use_container_width=True)
            ot_id = st.selectbox("Seleccionar OT", mis_ots['id'].values)
            with st.form("cierre_form"):
                coments = st.text_area("Informe Técnico")
                foto = st.file_uploader("Evidencia Fotográfica")
                if st.form_submit_button("Cerrar Orden"):
                    url = subir_imagen(foto)
                    supabase.table("ordenes").update({"estado":"Concluida", "evidencia_url": url, "comentarios_cierre": coments}).eq("id", int(ot_id)).execute()
                    st.success("Orden Cerrada")
                    st.rerun()
        else: st.info("Sin órdenes pendientes.")
