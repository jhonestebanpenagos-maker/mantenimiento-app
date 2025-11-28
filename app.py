import streamlit as st
import pandas as pd
from supabase import create_client
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
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        if "auditoria_eliminados" in table_name or "usuarios" in table_name:
            return pd.DataFrame()
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

# --- 4. SISTEMA DE LOGIN ---

if 'usuario' not in st.session_state:
    st.session_state['usuario'] = None
if 'rol' not in st.session_state:
    st.session_state['rol'] = None

def login():
    st.markdown("<h1 style='text-align: center;'>🔐 Iniciar Sesión CMMS</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,2,1])
    with c2:
        with st.form("login_form"):
            email = st.text_input("Correo Electrónico")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
            
            if submitted:
                # Buscar usuario en base de datos
                response = supabase.table("usuarios").select("*").eq("email", email).eq("password", password).execute()
                if response.data:
                    user_data = response.data[0]
                    st.session_state['usuario'] = user_data['nombre']
                    st.session_state['rol'] = user_data['rol']
                    st.success(f"Bienvenido {user_data['nombre']}")
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos")

def logout():
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.rerun()

# --- 5. LÓGICA PRINCIPAL (SI ESTÁ LOGUEADO) ---

if st.session_state['usuario'] is None:
    login() # Si no hay usuario, mostrar login
else:
    # --- BARRA LATERAL CON ROLES ---
    rol_actual = st.session_state['rol']
    
    with st.sidebar:
        st.write(f"👤 **{st.session_state['usuario']}**")
        st.caption(f"Rol: {rol_actual}")
        if st.button("Cerrar Sesión"):
            logout()
        
        # DEFINIR MENÚ SEGÚN ROL 

[Image of maintenance dashboard UI]

        options_menu = []
        
        if rol_actual == "Admin":
            options_menu = ["Dashboard", "Gestión de Activos", "Crear Orden", "Cierre de OTs", "Usuarios"]
        elif rol_actual == "Programador":
            options_menu = ["Dashboard", "Crear Orden", "Usuarios"] # Puede ver dashboard, asignar y ver usuarios
        elif rol_actual == "Tecnico":
            options_menu = ["Cierre de OTs"] # Solo cierra ordenes
        
        choice = option_menu(
            menu_title="Menú",
            options=options_menu,
            icons=["speedometer2", "box-seam", "plus-circle", "check2-circle", "people"],
            default_index=0,
            styles={
                "container": {"padding": "5!important", "background-color": "#262730"},
                "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "color": "white"},
                "nav-link-selected": {"background-color": "#02ab21"},
            }
        )

    # --- PANTALLAS ---

    # 1. DASHBOARD
    if choice == "Dashboard":
        st.subheader("Tablero de Control")
        df_ordenes = run_query("ordenes")
        if not df_ordenes.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("Total OTs", len(df_ordenes))
            c2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
            c3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
            st.bar_chart(df_ordenes['estado'].value_counts())
        else:
            st.info("Sin datos.")

    # 2. GESTIÓN DE ACTIVOS (Solo Admin)
    elif choice == "Gestión de Activos":
        st.subheader("Inventario de Equipos")
        # ... (Tu código de activos va aquí, lo resumí por espacio pero usa el que ya tenías) ...
        # Copia aquí tu código completo de activos anterior o úsalo tal cual estaba.
        # Para el ejemplo, pondré algo básico para que no de error:
        df_activos = run_query("activos")
        st.dataframe(df_activos)
        with st.form("nuevo_activo"):
            nombre = st.text_input("Nombre")
            ubicacion = st.text_input("Ubicación")
            if st.form_submit_button("Guardar"):
                supabase.table("activos").insert({"nombre": nombre, "ubicacion": ubicacion}).execute()
                st.rerun()

    # 3. CREAR ORDEN Y ASIGNAR (Admin y Programador)
    elif choice == "Crear Orden":
        st.subheader("Planificación y Asignación de OTs")
        
        df_activos = run_query("activos")
        # TRAEMOS LOS TÉCNICOS PARA ASIGNARLES TRABAJO
        df_usuarios = run_query("usuarios")
        lista_tecnicos = []
        if not df_usuarios.empty:
            # Filtramos solo los que tengan rol Tecnico o sean el mismo usuario
            tecnicos = df_usuarios[df_usuarios['rol'].isin(['Tecnico', 'Admin', 'Programador'])]
            lista_tecnicos = tecnicos['nombre'].tolist()

        if not df_activos.empty:
            activos_dict = {f"{row['nombre']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("Equipo", list(activos_dict.keys()))
            activo_id = activos_dict[seleccion]
            
            c1, c2 = st.columns(2)
            descripcion = c1.text_area("Descripción")
            # AQUÍ ESTÁ LA MAGIA: ASIGNAR A UN TÉCNICO ESPECÍFICO
            asignado_a = c2.selectbox("Asignar Técnico Responsable", lista_tecnicos)
            
            criticidad = st.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
            
            if st.button("Generar y Asignar"):
                datos = {
                    "activo_id": int(activo_id),
                    "descripcion": descripcion,
                    "criticidad": criticidad,
                    "estado": "Abierta",
                    "fecha_creacion": datetime.now().isoformat(),
                    "tecnico_asignado": asignado_a # Guardamos a quién se le asignó
                }
                res = supabase.table("ordenes").insert(datos).execute()
                if res.data:
                    new_id = res.data[0]['id']
                    st.success(f"OT #{new_id} creada y asignada a {asignado_a}")
                    
                    # Generar Link WhatsApp para el técnico
                    # Buscamos el telefono (si tuvieras esa columna) o enviamos al general
                    texto = f"*NUEVA ASIGNACIÓN OT #{new_id}*\nResp: {asignado_a}\nEquipo: {seleccion}\nFalla: {descripcion}"
                    texto_enc = urllib.parse.quote(texto)
                    st.link_button("📲 Enviar WhatsApp al Técnico", f"https://wa.me/?text={texto_enc}")
        else:
            st.warning("No hay activos.")

    # 4. USUARIOS (Creación de perfiles - Solo Admin y Programador)
    elif choice == "Usuarios":
        st.subheader("Gestión de Personal")
        
        tab1, tab2 = st.tabs(["Nuevo Usuario", "Lista de Usuarios"])
        
        with tab1:
            with st.form("crear_user"):
                c1, c2 = st.columns(2)
                nombre_u = c1.text_input("Nombre Completo")
                email_u = c2.text_input("Email (Login)")
                pass_u = c1.text_input("Contraseña", type="password")
                rol_u = c2.selectbox("Rol", ["Admin", "Programador", "Tecnico"])
                especialidad = st.text_input("Especialidad (Ej: Electricista)")
                
                if st.form_submit_button("Crear Usuario"):
                    try:
                        supabase.table("usuarios").insert({
                            "email": email_u,
                            "password": pass_u,
                            "nombre": nombre_u,
                            "rol": rol_u,
                            "especialidad": especialidad
                        }).execute()
                        st.success("Usuario creado correctamente")
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with tab2:
            st.dataframe(run_query("usuarios"))

    # 5. CIERRE (Técnicos)
    elif choice == "Cierre de OTs":
        st.subheader("Mis Órdenes Pendientes")
        df_ots = run_query("ordenes")
        
        if not df_ots.empty:
            # FILTRO INTELIGENTE:
            # Si soy Admin, veo todo. Si soy Tecnico, solo veo las mías.
            if rol_actual == "Tecnico":
                mis_ots = df_ots[(df_ots['tecnico_asignado'] == st.session_state['usuario']) & (df_ots['estado'] != 'Concluida')]
            else:
                mis_ots = df_ots[df_ots['estado'] != 'Concluida']
            
            if not mis_ots.empty:
                st.dataframe(mis_ots)
                # ... (Aquí va tu lógica de cierre con foto que ya tenías) ...
                ot_id = st.selectbox("Seleccionar OT para cerrar", mis_ots['id'].values)
                with st.form("cierre_form"):
                    coments = st.text_area("Informe")
                    foto = st.file_uploader("Evidencia")
                    if st.form_submit_button("Cerrar"):
                        url = subir_imagen(foto)
                        supabase.table("ordenes").update({"estado":"Concluida", "evidencia_url": url, "comentarios_cierre": coments}).eq("id", int(ot_id)).execute()
                        st.success("Cerrada")
                        st.rerun()
            else:
                st.info("No tienes órdenes asignadas pendientes.")
