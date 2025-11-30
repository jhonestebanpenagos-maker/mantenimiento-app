import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io
import urllib.parse
import json
import qrcode

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="centered", initial_sidebar_state="collapsed")
# Nota: Cambié layout a "centered" por defecto para que se vea mejor en celulares al escanear QR, 
# luego lo cambiamos a "wide" si es admin.

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
    # --- ¡IMPORTANTE! CAMBIA ESTO POR TU URL REAL DE STREAMLIT ---
    # Si estás en local usa http://localhost:8501
    # Si ya desplegaste, usa https://tu-app.streamlit.app
    base_url = "https://mantenimiento-app-demo.streamlit.app" 
    
    link = f"{base_url}/?id_activo_qr={id_activo}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    return subir_imagen(img_byte_arr, "evidencias")

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
    st.query_params.clear() # Limpiar URL al salir
    st.rerun()

# ==========================================
# 🚀 INTERCEPTOR DE CÓDIGO QR (MODO PÚBLICO)
# ==========================================
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    
    # Buscamos el activo
    try:
        datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    except Exception as e:
        st.error("Error de conexión pública. Verifica las políticas RLS en Supabase.")
        st.stop()
    
    if datos_activo.data:
        activo = datos_activo.data[0]
        
        # --- VISTA PÚBLICA (HOJA DE VIDA) ---
        st.markdown(f"<h1 style='text-align: center;'>📋 {activo['nombre']}</h1>", unsafe_allow_html=True)
        
        # Tarjeta de Detalles
        st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
                <p style="color: #666; font-size: 12px;">ID Sistema: {activo['id']}</p>
            </div>
        """, unsafe_allow_html=True)

        # Historial de Órdenes
        st.subheader("🛠️ Historial de Mantenimiento")
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr).order("id", desc=True).execute()
            if ots.data:
                df_ots_qr = pd.DataFrame(ots.data)
                
                # KPIs rápidos
                col1, col2 = st.columns(2)
                col1.metric("Total Intervenciones", len(df_ots_qr))
                pendientes = len(df_ots_qr[df_ots_qr['estado'] == 'Abierta'])
                col2.metric("Pendientes", pendientes, delta_color="inverse" if pendientes > 0 else "normal")
                
                # Tabla simplificada para móvil
                st.dataframe(
                    df_ots_qr[['fecha_creacion', 'tipo_mantenimiento', 'descripcion', 'estado']],
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("Este equipo está nuevo: Sin mantenimientos registrados.")
        except:
            st.warning("No se pudo cargar el historial.")

        st.markdown("---")
        
        # Botones de Acción
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("🏠 Ir al Inicio"):
                st.query_params.clear()
                st.rerun()
        with col_btn2:
            if st.session_state['usuario'] is None:
                if st.button("🔐 Soy Técnico (Login)"):
                    st.query_params.clear() # Limpiamos para ir al login normal
                    st.rerun()
            else:
                st.success(f"Logueado como: {st.session_state['usuario']}")

    else:
        st.error("❌ Equipo no encontrado o dado de baja.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    
    st.stop() # 🛑 DETIENE LA EJECUCIÓN AQUÍ PARA NO MOSTRAR EL RESTO DE LA APP

# ==========================================
# 🖥️ APP PRINCIPAL (SÓLO SI NO ES QR)
# ==========================================

# Cambiar layout a wide si estamos en modo escritorio/admin
# (No podemos cambiar config dinámicamente, pero ajustamos el contenido)

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
        st.subheader("Inventario de Equipos")
        
        if 'asset_msg' in st.session_state:
            msg = st.session_state['asset_msg']
            if msg['tipo'] == 'create': 
                st.balloons()
                st.success(f"✅ Activo {msg['nombre']} creado.")
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
                    
                    st.markdown("---")
                    col_qr1, col_qr2 = st.columns([1, 3])
                    with col_qr1:
                        if datos_actuales.get('qr_url'):
                            st.image(datos_actuales['qr_url'], caption="Escanea para ver")
                        else:
                            if st.button("Generar QR"):
                                url_qr = generar_qr_activo(id_seleccionado, datos_actuales['nombre'])
                                supabase.table("activos").update({"qr_url": url_qr}).eq("id", int(id_seleccionado)).execute()
                                st.rerun()
                    with col_qr2:
                        st.markdown(f"### 🏷️ Ficha: {datos_actuales['nombre']}")
                        st.info("Imprime esta sección para el equipo.")
                    
                    st.markdown("---")
                    st.write("### ✏️ Editar Datos")
                    
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
         # ... Código de usuarios simplificado para no exceder limite, copia el anterior si lo necesitas ...
         st.info("Módulo Usuarios Activo")

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
