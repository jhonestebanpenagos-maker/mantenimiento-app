import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io
import urllib.parse
import json

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

def subir_imagen(archivo):
    """Sube imagen al Bucket"""
    if archivo:
        try:
            file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
            bucket_name = "evidencias"
            file_bytes = archivo.getvalue()
            supabase.storage.from_(bucket_name).upload(path=file_name, file=file_bytes, file_options={"content-type": archivo.type})
            return supabase.storage.from_(bucket_name).get_public_url(file_name)
        except Exception:
            return None
    return None

# --- 4. SISTEMA DE LOGIN Y SESIÓN ---

if 'usuario' not in st.session_state:
    st.session_state['usuario'] = None
if 'rol' not in st.session_state:
    st.session_state['rol'] = None
if 'email_sesion' not in st.session_state:
    st.session_state['email_sesion'] = None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Iniciar Sesión CMMS</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            email = st.text_input("Correo Electrónico")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
            
            if submitted:
                try:
                    response = supabase.table("usuarios").select("*").eq("email", email).eq("password", password).execute()
                    if response.data:
                        user_data = response.data[0]
                        st.session_state['usuario'] = user_data['nombre']
                        st.session_state['rol'] = user_data['rol']
                        st.session_state['email_sesion'] = user_data['email']
                        st.success(f"Bienvenido {user_data['nombre']}")
                        st.rerun()
                    else:
                        st.error("Usuario o contraseña incorrectos")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.session_state['email_sesion'] = None
    st.rerun()

# --- 5. LÓGICA PRINCIPAL (SI ESTÁ LOGUEADO) ---

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
        
        if st.button("Cerrar Sesión", use_container_width=True):
            logout()
        
        st.write("") 

        # DEFINIR MENÚ
        options_menu = []
        if rol_actual == "Admin":
            options_menu = ["Dashboard", "Gestión de Activos", "Crear Orden", "Cierre de OTs", "Usuarios"]
        elif rol_actual == "Programador":
            options_menu = ["Dashboard", "Crear Orden", "Usuarios"] 
        elif rol_actual == "Tecnico":
            options_menu = ["Cierre de OTs"] 
        
        choice = option_menu(
            menu_title="MENÚ PRINCIPAL",
            options=options_menu,
            icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
            default_index=0,
            styles={
                "container": {"padding": "0!important", "background-color": "#151515", "border-radius": "5px"},
                "menu-title": {"color": "#ffffff", "font-weight": "bold", "font-size": "18px", "text-align": "center", "padding": "15px", "letter-spacing": "2px"},
                "icon": {"color": "#00d4ff", "font-size": "20px"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "5px", "--hover-color": "#2b2b2b", "color": "white"},
                "nav-link-selected": {"background-image": "linear-gradient(to right, #00b09b, #96c93d)", "color": "white", "font-weight": "bold", "box-shadow": "0px 4px 15px rgba(0,0,0,0.3)"},
            }
        )

    # --- PANTALLAS ---

    # 1. DASHBOARD
    if choice == "Dashboard":
        st.subheader("Tablero de Control")
        df_ordenes = run_query("ordenes")
        if not df_ordenes.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total OTs", len(df_ordenes), delta="Global")
            c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']), delta="Pendientes", delta_color="inverse")
            c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']), delta="Finalizadas", delta_color="normal")
            
            st.divider()
            col_a, col_b = st.columns(2)
            col_a.write("### Estado de Órdenes")
            col_a.bar_chart(df_ordenes['estado'].value_counts(), color="#00b09b") 
            col_b.write("### Criticidad")
            col_b.bar_chart(df_ordenes['criticidad'].value_counts(), color="#ff6b6b") 
        else:
            st.info("Sin datos para mostrar.")

    # 2. GESTIÓN DE ACTIVOS
    elif choice == "Gestión de Activos":
        st.subheader("Inventario de Equipos")
        df_activos = run_query("activos")
        
        tab1, tab2 = st.tabs(["➕ Registrar Nuevo", "✏️ Editar / Dar de Baja"])
        
        with tab1:
            with st.form("form_activo", clear_on_submit=True):
                c1, c2 = st.columns(2)
                nombre = c1.text_input("Nombre del Equipo")
                ubicacion = c2.text_input("Ubicación")
                categoria = st.selectbox("Categoría", ["Mecánico", "Eléctrico", "Infraestructura", "HVAC", "Otros"])
                if st.form_submit_button("Guardar Activo"):
                    if nombre and ubicacion:
                        supabase.table("activos").insert({"nombre": nombre, "ubicacion": ubicacion, "categoria": categoria}).execute()
                        st.success("Activo creado!")
                        st.rerun()
                    else:
                        st.warning("Faltan datos.")

        with tab2:
            if not df_activos.empty:
                activos_dict = {f"{row['nombre']} - {row['ubicacion']}": row['id'] for i, row in df_activos.iterrows()}
                seleccion = st.selectbox("Seleccionar Activo", list(activos_dict.keys()))
                id_seleccionado = activos_dict[seleccion]
                datos_actuales = df_activos[df_activos['id'] == id_seleccionado].iloc[0]
                
                with st.form("form_editar"):
                    nuevo_nombre = st.text_input("Nombre", value=datos_actuales['nombre'])
                    nueva_ubicacion = st.text_input("Ubicación", value=datos_actuales['ubicacion'])
                    if st.form_submit_button("Actualizar"):
                        supabase.table("activos").update({"nombre": nuevo_nombre, "ubicacion": nueva_ubicacion}).eq("id", int(id_seleccionado)).execute()
                        st.success("Actualizado.")
                        st.rerun()
                
                st.markdown("---")
                with st.expander("🗑️ Zona de Peligro (Baja)"):
                    usuario_baja = st.text_input("👤 Responsable de la Baja:")
                    motivo = st.text_area("Motivo:")
                    if st.button("Dar de Baja", type="primary", disabled=(not motivo or not usuario_baja)):
                        backup = {
                            "id_original": int(id_seleccionado),
                            "nombre": datos_actuales['nombre'],
                            "ubicacion": datos_actuales['ubicacion'],
                            "categoria": datos_actuales['categoria'],
                            "motivo_baja": motivo
                        }
                        supabase.table("auditoria_eliminados").insert({
                            "tipo_registro": "Activo",
                            "nombre_referencia": datos_actuales['nombre'],
                            "datos_respaldo": backup,
                            "usuario_responsable": usuario_baja
                        }).execute()
                        
                        supabase.table("ordenes").delete().eq("activo_id", int(id_seleccionado)).execute()
                        supabase.table("activos").delete().eq("id", int(id_seleccionado)).execute()
                        st.success("Eliminado")
                        st.rerun()
    
    # 3. CREAR ORDEN Y ASIGNAR
    elif choice == "Crear Orden":
        st.subheader("Planificación y Asignación de OTs")
        
        df_activos = run_query("activos")
        df_usuarios = run_query("usuarios")
        
        lista_tecnicos = []
        if not df_usuarios.empty:
            tecnicos = df_usuarios[df_usuarios['rol'].isin(['Tecnico', 'Admin', 'Programador'])]
            lista_tecnicos = tecnicos['nombre'].tolist()

        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("Equipo", list(activos_dict.keys()))
            activo_id = activos_dict[seleccion]
            
            c1, c2 = st.columns(2)
            descripcion = c1.text_area("Descripción")
            asignado_a = c2.selectbox("Asignar Técnico Responsable", lista_tecnicos)
            
            criticidad = st.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
            
            if st.button("Generar y Asignar"):
                datos = {
                    "activo_id": int(activo_id),
                    "descripcion": descripcion,
                    "criticidad": criticidad,
                    "estado": "Abierta",
                    "fecha_creacion": datetime.now().isoformat(),
                    "tecnico_asignado": asignado_a
                }
                res = supabase.table("ordenes").insert(datos).execute()
                if res.data:
                    new_id = res.data[0]['id']
                    texto = f"*NUEVA ASIGNACIÓN OT #{new_id}*\nResp: {asignado_a}\nEquipo: {seleccion}\nFalla: {descripcion}"
                    texto_enc = urllib.parse.quote(texto)
                    
                    st.balloons()
                    st.markdown(f"""
                        <div style="background-color:#d4edda; color:#155724; padding:20px; border-radius:10px; text-align:center;">
                            <h2 style="margin:0;">✅ OT #{new_id} Creada</h2>
                            <p>Asignada a: <strong>{asignado_a}</strong></p>
                        </div>
                    """, unsafe_allow_html=True)
                    st.link_button("📲 Enviar WhatsApp al Técnico", f"https://wa.me/?text={texto_enc}")
        else:
            st.warning("No hay activos registrados.")

    # 4. USUARIOS (SISTEMA DE MENSAJES UNIFICADO)
    elif choice == "Usuarios":
        st.subheader("Gestión de Personal")
        
        # --- LÓGICA DE MENSAJES (CREAR / EDITAR / ELIMINAR) ---
        if 'user_msg' in st.session_state:
            msg = st.session_state['user_msg']
            tipo = msg['tipo'] # create, update, delete
            
            # 1. CASO CREACIÓN (Verde)
            if tipo == 'create':
                st.balloons()
                st.markdown(f"""
                    <div style="background-color: #d1e7dd; border: 2px solid #28a745; border-radius: 15px; padding: 20px; 
                    text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px; max-width: 600px; margin: 0 auto;">
                        <h3 style="color: #28a745; margin: 0;">✅ ¡Usuario Creado con Éxito!</h3>
                        <hr style="border-top: 1px solid #a3cfbb; margin: 15px 0;">
                        <h2 style="margin: 0; color: #0f5132;">{msg['nombre']}</h2>
                        <p style="margin: 0; color: #146c43;">{msg['rol']} - {msg['especialidad']}</p>
                    </div>
                    <br>
                """, unsafe_allow_html=True)
            
            # 2. CASO EDICIÓN (Azul)
            elif tipo == 'update':
                st.balloons()
                st.markdown(f"""
                    <div style="background-color: #cff4fc; border: 2px solid #0dcaf0; border-radius: 15px; padding: 20px; 
                    text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px; max-width: 600px; margin: 0 auto;">
                        <h3 style="color: #055160; margin: 0;">🔄 Datos Actualizados</h3>
                        <hr style="border-top: 1px solid #9eeaf9; margin: 15px 0;">
                        <h2 style="margin: 0; color: #055160;">{msg['nombre']}</h2>
                        <p style="margin: 0; color: #055160;">Nuevos datos guardados correctamente.</p>
                    </div>
                    <br>
                """, unsafe_allow_html=True)
            
            # 3. CASO ELIMINACIÓN (Rojo/Naranja)
            elif tipo == 'delete':
                st.markdown(f"""
                    <div style="background-color: #f8d7da; border: 2px solid #dc3545; border-radius: 15px; padding: 20px; 
                    text-align: center; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 20px; max-width: 600px; margin: 0 auto;">
                        <h3 style="color: #842029; margin: 0;">🗑️ Usuario Eliminado</h3>
                        <hr style="border-top: 1px solid #f1aeb5; margin: 15px 0;">
                        <h2 style="margin: 0; color: #842029;">{msg['nombre']}</h2>
                        <p style="margin: 0; color: #842029;">Este usuario ya no tiene acceso al sistema.</p>
                    </div>
                    <br>
                """, unsafe_allow_html=True)
                
            del st.session_state['user_msg']

        df_usuarios = run_query("usuarios")

        tab1, tab2 = st.tabs(["➕ Nuevo Usuario", "✏️ Editar / Eliminar"])
        
        # --- TAB 1: CREAR ---
        with tab1:
            st.write("#### Paso 1: Definir Perfil")
            if 'reset_key' not in st.session_state: st.session_state.reset_key = 0
            
            rol_u = st.selectbox("Seleccione el Rol", ["", "Admin", "Programador", "Tecnico"], key=f"rol_{st.session_state.reset_key}")
            
            especialidad_selec = "Gestión/Admin"
            if rol_u == "Tecnico":
                especialidad_selec = st.selectbox("Especialidad Técnica", ["", "Técnico Infraestructura", "Tecnico Soldadura", "Tecnico Electricista", "Tecnico Aire Acondicionado", "Otros"], key=f"esp_{st.session_state.reset_key}")
            
            st.write("#### Paso 2: Credenciales")
            with st.form("crear_user", clear_on_submit=True):
                c1, c2 = st.columns(2)
                nombre_u = c1.text_input("Nombre Completo")
                email_u = c2.text_input("Email (Login)")
                pass_u = c1.text_input("Contraseña", type="password")
                
                if st.form_submit_button("Crear Usuario"):
                    if nombre_u and email_u and pass_u and rol_u and (rol_u != ""):
                        if rol_u == "Tecnico" and especialidad_selec == "":
                            st.warning("Debes seleccionar una especialidad.")
                        else:
                            try:
                                supabase.table("usuarios").insert({
                                    "email": email_u, "password": pass_u, "nombre": nombre_u, "rol": rol_u, "especialidad": especialidad_selec
                                }).execute()
                                
                                st.session_state['user_msg'] = {
                                    'tipo': 'create', 
                                    'nombre': nombre_u, 
                                    'rol': rol_u, 
                                    'especialidad': especialidad_selec
                                }
                                st.session_state.reset_key += 1
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al crear: {e}")
                    else:
                        st.warning("Completa todos los campos.")
        
        # --- TAB 2: EDITAR / ELIMINAR ---
        with tab2:
            if not df_usuarios.empty:
                user_map = {f"{row['nombre']} ({row['email']})": row['id'] for i, row in df_usuarios.iterrows()}
                seleccion_user = st.selectbox("🔍 Buscar Usuario a Modificar", list(user_map.keys()))
                
                id_user_edit = user_map[seleccion_user]
                data_edit = df_usuarios[df_usuarios['id'] == id_user_edit].iloc[0]
                
                st.markdown("---")
                st.write(f"### Editando a: **{data_edit['nombre']}**")
                
                # Campos dinámicos de edición
                new_rol = st.selectbox("Rol", ["Admin", "Programador", "Tecnico"], index=["Admin", "Programador", "Tecnico"].index(data_edit['rol']), key="edit_rol")
                
                new_esp = "Gestión/Admin"
                if new_rol == "Tecnico":
                    opciones_esp = ["Técnico Infraestructura", "Tecnico Soldadura", "Tecnico Electricista", "Tecnico Aire Acondicionado", "Otros"]
                    idx_esp = 0
                    if data_edit['especialidad'] in opciones_esp:
                        idx_esp = opciones_esp.index(data_edit['especialidad'])
                    new_esp = st.selectbox("Especialidad", opciones_esp, index=idx_esp, key="edit_esp")

                with st.form("editar_usuario_form"):
                    c1, c2 = st.columns(2)
                    new_nombre = c1.text_input("Nombre", value=data_edit['nombre'])
                    new_email = c2.text_input("Email", value=data_edit['email'])
                    new_pass = st.text_input("Contraseña", value=data_edit['password'], type="password")
                    
                    if st.form_submit_button("💾 Guardar Cambios"):
                        try:
                            supabase.table("usuarios").update({
                                "nombre": new_nombre, "email": new_email, "password": new_pass, "rol": new_rol, "especialidad": new_esp
                            }).eq("id", int(id_user_edit)).execute()
                            
                            st.session_state['user_msg'] = {'tipo': 'update', 'nombre': new_nombre}
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error al actualizar: {e}")
                
                st.markdown("---")
                with st.expander("🗑️ Zona de Peligro (Eliminar Usuario)"):
                    st.warning(f"¿Estás seguro de que quieres eliminar a **{data_edit['nombre']}**?")
                    if data_edit['email'] == st.session_state['email_sesion']:
                        st.error("⛔ No puedes eliminar tu propio usuario.")
                    else:
                        if st.button("Sí, Eliminar", type="primary"):
                            try:
                                supabase.table("usuarios").delete().eq("id", int(id_user_edit)).execute()
                                st.session_state['user_msg'] = {'tipo': 'delete', 'nombre': data_edit['nombre']}
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error al eliminar: {e}")
            else:
                st.info("No hay usuarios registrados.")
            
            st.markdown("---")
            st.write("#### 📋 Listado Completo")
            st.dataframe(df_usuarios[['nombre', 'email', 'rol', 'especialidad']], use_container_width=True)

    # 5. CIERRE
    elif choice == "Cierre de OTs":
        st.subheader("Mis Órdenes Pendientes")
        df_ots = run_query("ordenes")
        
        if not df_ots.empty:
            if rol_actual == "Tecnico":
                mis_ots = df_ots[(df_ots['tecnico_asignado'] == usuario_actual) & (df_ots['estado'] != 'Concluida')]
            else:
                mis_ots = df_ots[df_ots['estado'] != 'Concluida']
            
            if not mis_ots.empty:
                st.dataframe(mis_ots[['id', 'descripcion', 'tecnico_asignado', 'estado']], use_container_width=True)
                ot_id = st.selectbox("Seleccionar OT", mis_ots['id'].values)
                with st.form("cierre_form"):
                    coments = st.text_area("Informe")
                    foto = st.file_uploader("Evidencia")
                    if st.form_submit_button("Cerrar Orden"):
                        with st.spinner("Procesando..."):
                            url = subir_imagen(foto)
                            supabase.table("ordenes").update({"estado":"Concluida", "evidencia_url": url, "comentarios_cierre": coments}).eq("id", int(ot_id)).execute()
                            st.success("Cerrada Correctamente")
                            st.rerun()
            else:
                st.info("No tienes órdenes asignadas pendientes.")
        else:
            st.info("Sin registros.")
