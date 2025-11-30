import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io
import urllib.parse
import json
import qrcode # NUEVA LIBRERÍA

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="wide")

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
    """Trae todos los datos de una tabla"""
    try:
        response = supabase.table(table_name).select("*").order("id").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        return pd.DataFrame()

def subir_imagen(archivo, carpeta="evidencias"):
    """Sube imagen al Bucket"""
    if archivo:
        try:
            # Si es bytes (como el QR generado)
            if isinstance(archivo, bytes):
                file_bytes = archivo
                file_name = f"qr_{datetime.now().strftime('%Y%m%d%H%M%S')}.png"
                mime_type = "image/png"
            else:
                # Si es archivo subido por usuario
                file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
                file_bytes = archivo.getvalue()
                mime_type = archivo.type

            supabase.storage.from_(carpeta).upload(path=file_name, file=file_bytes, file_options={"content-type": mime_type})
            return supabase.storage.from_(carpeta).get_public_url(file_name)
        except Exception as e:
            st.error(f"Error subiendo imagen: {e}")
            return None
    return None

def generar_qr_activo(id_activo, nombre_activo):
    """Genera un QR que apunta a la APP con el ID del activo"""
    # URL BASE DE TU APP (Cámbiala por la URL real de tu deploy en Streamlit Cloud)
    # Por ahora usamos localhost o la detección automática si fuera posible, 
    # pero mejor pon tu URL fija aquí.
    base_url = "https://tu-app-mantenimiento.streamlit.app" 
    
    # El link mágico
    link = f"{base_url}/?id_activo_qr={id_activo}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    # Convertir a bytes para subir a Supabase
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    return subir_imagen(img_byte_arr, "evidencias") # Usamos la misma carpeta evidencias

# --- 4. SISTEMA DE LOGIN Y SESIÓN ---

if 'usuario' not in st.session_state: st.session_state['usuario'] = None
if 'rol' not in st.session_state: st.session_state['rol'] = None
if 'doc_sesion' not in st.session_state: st.session_state['doc_sesion'] = None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Iniciar Sesión CMMS</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            documento = st.text_input("Número de Documento")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
            
            if submitted:
                try:
                    response = supabase.table("usuarios").select("*").eq("documento", documento).eq("password", password).execute()
                    if response.data:
                        user_data = response.data[0]
                        st.session_state['usuario'] = user_data['nombre']
                        st.session_state['rol'] = user_data['rol']
                        st.session_state['doc_sesion'] = user_data['documento']
                        st.success(f"Bienvenido {user_data['nombre']}")
                        st.rerun()
                    else:
                        st.error("Credenciales incorrectas")
                except Exception as e:
                    st.error(f"Error: {e}")

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.session_state['doc_sesion'] = None
    st.rerun()

# --- 0. INTERCEPTOR DE CÓDIGO QR (LÓGICA NUEVA) ---
# Esto revisa si la URL tiene ?id_activo_qr=123 antes de mostrar nada más
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    
    # Verificamos Login Rápido (Opcional: podrías dejarlo público si quisieras)
    if st.session_state['usuario'] is None:
        st.warning("🔒 Por favor inicia sesión para ver la ficha del equipo.")
        login()
        st.stop() # Detiene la ejecución aquí hasta que se loguee
    
    # --- MOSTRAR HOJA DE VIDA DEL EQUIPO ---
    st.title("📋 Hoja de Vida del Equipo (QR Scan)")
    
    # Datos del activo
    datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    
    if datos_activo.data:
        activo = datos_activo.data[0]
        
        # Cabecera
        c1, c2 = st.columns([3, 1])
        with c1:
            st.markdown(f"## {activo['nombre']}")
            st.markdown(f"**Área:** {activo.get('area')} | **Ubicación:** {activo['ubicacion']}")
            st.markdown(f"**Categoría:** {activo.get('categoria')}")
            st.info(f"ID Sistema: {activo['id']}")
        with c2:
            if activo.get('qr_url'):
                st.image(activo['qr_url'], caption="Código QR", width=150)

        st.divider()
        
        # Órdenes de Trabajo Asociadas
        st.subheader("🛠️ Historial de Mantenimiento")
        ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).execute()
        
        if ots.data:
            df_ots_qr = pd.DataFrame(ots.data)
            
            # Métricas rápidas
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Órdenes", len(df_ots_qr))
            m2.metric("Pendientes", len(df_ots_qr[df_ots_qr['estado'] == 'Abierta']))
            m3.metric("Preventivos", len(df_ots_qr[df_ots_qr['tipo_mantenimiento'] == 'Preventivo']))
            
            # Tabla detallada
            st.dataframe(
                df_ots_qr[['id', 'fecha_creacion', 'tipo_mantenimiento', 'descripcion', 'estado', 'tecnico_asignado']],
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("Este equipo aún no tiene órdenes de trabajo registradas.")
            
        if st.button("⬅️ Volver al Inicio"):
            # Limpiar query params para volver a la app normal
            st.query_params.clear()
            st.rerun()
            
    else:
        st.error("Equipo no encontrado o eliminado.")
    
    st.stop() # Detenemos la ejecución normal de la app aquí


# --- 5. LÓGICA PRINCIPAL NORMAL ---

if st.session_state['usuario'] is None:
    login()
else:
    # --- BARRA LATERAL ---
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

    # --- PANTALLAS ---
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
        st.subheader("Inventario de Equipos & QR")
        
        if 'asset_msg' in st.session_state:
            msg = st.session_state['asset_msg']
            if msg['tipo'] == 'create': 
                st.balloons()
                st.success(f"✅ Activo {msg['nombre']} creado con Código QR.")
            del st.session_state['asset_msg']

        df_activos = run_query("activos")
        
        # Estructura Áreas
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
                            # 1. Insertar para obtener ID
                            data_insert = {"nombre": nombre, "ubicacion": ubicacion, "area": area_selec, "categoria": categoria}
                            res = supabase.table("activos").insert(data_insert).execute()
                            
                            if res.data:
                                new_id = res.data[0]['id']
                                # 2. Generar QR con el ID
                                url_qr = generar_qr_activo(new_id, nombre)
                                # 3. Actualizar activo con la URL del QR
                                supabase.table("activos").update({"qr_url": url_qr}).eq("id", new_id).execute()
                                
                                st.session_state['asset_msg'] = {'tipo': 'create', 'nombre': nombre}
                                st.session_state.asset_reset_key += 1
                                st.session_state['tab_index_activos'] = 0
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
                    else:
                        st.warning("Complete todos los campos.")

        elif selected_tab == "Editar / Imprimir QR":
            st.session_state['tab_index_activos'] = 1 
            
            if not df_activos.empty:
                activos_dict = {f"{row['nombre']} - {row.get('ubicacion','?')}": row['id'] for i, row in df_activos.iterrows()}
                seleccion = st.selectbox("Seleccionar Activo", [""] + list(activos_dict.keys()))
                
                if seleccion:
                    id_seleccionado = activos_dict[seleccion]
                    datos_actuales = df_activos[df_activos['id'] == id_seleccionado].iloc[0]
                    
                    # --- SECCIÓN DE TARJETA QR ---
                    st.markdown("---")
                    col_qr1, col_qr2 = st.columns([1, 3])
                    
                    with col_qr1:
                        if datos_actuales.get('qr_url'):
                            st.image(datos_actuales['qr_url'], caption="Escanea para ver Hoja de Vida")
                        else:
                            st.warning("Sin QR generado")
                            if st.button("Generar QR Ahora"):
                                url_qr = generar_qr_activo(id_seleccionado, datos_actuales['nombre'])
                                supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_seleccionado)).execute()
                                st.rerun()

                    with col_qr2:
                        st.markdown(f"### 🏷️ Ficha: {datos_actuales['nombre']}")
                        st.info("Imprime esta sección para pegar en el equipo.")
                        st.markdown(f"**Área:** {datos_actuales.get('area')} / {datos_actuales.get('ubicacion')}")
                        st.markdown(f"**Categoría:** {datos_actuales.get('categoria')}")
                        st.caption(f"ID Sistema: {datos_actuales['id']}")
                        
                        # Botón simulado de imprimir (En web real se usa JS, aquí mostramos la vista limpia)
                        st.success("☝️ Haz clic derecho en la imagen del QR y selecciona 'Guardar imagen' o 'Imprimir' para etiquetar el equipo.")

                    st.markdown("---")
                    st.write("### ✏️ Editar Datos")
                    
                    # Logica de edición normal (igual a la anterior)
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
                            st.success("Eliminado")
                            st.rerun()

    # RESTO DE OPCIONES (Crear Orden, etc) SE MANTIENEN IGUAL...
    elif choice == "Crear Orden":
        # ... (Mantén tu código de Crear Orden aquí, no cambia)
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
        # ... (Tu código de usuarios se mantiene igual)
        st.write("Gestion de Usuarios (Código existente)")
        pass
    
    elif choice == "Cierre de OTs":
         # ... (Tu código de cierre se mantiene igual)
        st.write("Cierre de OTs (Código existente)")
        pass
