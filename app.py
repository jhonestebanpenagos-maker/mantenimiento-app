import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="wide")

# Inicializar conexión a Supabase
# Usamos st.cache_resource para no reconectar cada vez que algo cambia
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- FUNCIONES AUXILIARES ---

def run_query(table_name):
    """Trae todos los datos de una tabla con manejo de errores"""
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        # AQUÍ ESTÁ EL TRUCO: Mostramos el error en la pantalla si algo falla
        st.error(f"⚠️ Error crítico consultando la tabla '{table_name}'")
        st.code(str(e)) 
        st.stop()
        return pd.DataFrame()

def subir_imagen(archivo):
    """Sube imagen al Bucket 'evidencias' y devuelve la URL pública"""
    if archivo:
        try:
            # Crear nombre único: timestamp_nombrearchivo
            file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
            bucket_name = "evidencias"
            
            # Leer el archivo en bytes
            file_bytes = archivo.getvalue()
            
            # Subir a Supabase Storage
            supabase.storage.from_(bucket_name).upload(
                path=file_name,
                file=file_bytes,
                file_options={"content-type": archivo.type}
            )
            
            # Obtener URL pública
            public_url = supabase.storage.from_(bucket_name).get_public_url(file_name)
            return public_url
        except Exception as e:
            st.error(f"Error subiendo imagen: {e}")
            return None
    return None

# --- INTERFAZ (MENÚ MODERNO) ---
st.title("🛠️ Sistema CMMS (Supabase)")

with st.sidebar:
    choice = option_menu(
        menu_title="Navegación",
        options=["Dashboard", "Gestión de Activos", "Crear Orden", "Cierre de OTs"],
        icons=["speedometer2", "box-seam", "plus-circle", "check2-circle"],
        menu_icon="cast",
        default_index=0,
        styles={
            # 1. ESTILO DEL TÍTULO
            "menu-title": {"color": "white", "font-weight": "bold", "font-size": "20px"},
            # 2. Fondo del contenedor
            "container": {"padding": "5!important", "background-color": "#262730"},
            # 3. Iconos
            "icon": {"color": "#ff8c00", "font-size": "25px"},
            # 4. Letra de las opciones
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "--hover-color": "#444",
                "color": "white"
            },
            # 5. Opción seleccionada
            "nav-link-selected": {"background-color": "#02ab21"},
        }
    )

# --- LÓGICA DE PANTALLAS ---

# 1. DASHBOARD
if choice == "Dashboard":
    st.subheader("Tablero de Control")
    
    # CORRECCIÓN AQUÍ: "ordenes" sin tilde
    df_ordenes = run_query("ordenes") 
    
    if not df_ordenes.empty:
        col1, col2, col3 = st.columns(3)
        col1.metric("Total OTs", len(df_ordenes))
        col2.metric("Abiertas", len(df_ordenes[df_ordenes['estado']=='Abierta']))
        col3.metric("Concluidas", len(df_ordenes[df_ordenes['estado']=='Concluida']))
        
        st.divider()
        c1, c2 = st.columns(2)
        
        with c1:
            st.write("### Estado de Órdenes")
            st.bar_chart(df_ordenes['estado'].value_counts())
        
        with c2:
            st.write("### Criticidad")
            st.bar_chart(df_ordenes['criticidad'].value_counts())
    else:
        st.info("Aún no hay datos para mostrar en el Dashboard.")

# 2. ACTIVOS
elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    
    with st.form("form_activo"):
        c1, c2 = st.columns(2)
        nombre = c1.text_input("Nombre")
        ubicacion = c2.text_input("Ubicación")
        categoria = st.selectbox("Categoría", ["Mecánico", "Eléctrico", "Infraestructura", "HVAC"])
        
        if st.form_submit_button("Guardar Activo"):
            datos = {"nombre": nombre, "ubicacion": ubicacion, "categoria": categoria}
            supabase.table("activos").insert(datos).execute()
            st.success("Activo creado!")
            st.rerun()
            
    st.dataframe(run_query("activos"))

# 3. CREAR ORDEN
elif choice == "Crear Orden":
    st.subheader("Reportar Falla")
    
    df_activos = run_query("activos")
    
    if not df_activos.empty:
        # Diccionario para el Selectbox: "Nombre (ID)" -> ID
        activos_dict = {f"{row['nombre']} - {row['ubicacion']}": row['id'] for i, row in df_activos.iterrows()}
        
        seleccion = st.selectbox("Seleccionar Equipo", list(activos_dict.keys()))
        activo_id = activos_dict[seleccion]
        
        descripcion = st.text_area("Descripción del problema")
        criticidad = st.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        
        if st.button("Crear Orden de Trabajo"):
            try:
                # Preparamos los datos
                datos = {
                    "activo_id": int(activo_id),
                    "descripcion": descripcion,
                    "criticidad": criticidad,
                    "estado": "Abierta",
                    "fecha_creacion": datetime.now().isoformat()
                }
                
                # Intentamos guardar
                supabase.table("ordenes").insert(datos).execute()
                
                st.success("Orden Generada Correctamente")
                st.rerun()
                
            except Exception as e:
                # AQUÍ CAPTURAMOS EL ERROR REAL
                st.error("⚠️ Error al guardar la orden:")
                # Mostramos los detalles técnicos del error
                if hasattr(e, 'message'):
                    st.write(f"Mensaje: {e.message}")
                if hasattr(e, 'details'):
                    st.write(f"Detalles: {e.details}")
                if hasattr(e, 'hint'):
                    st.write(f"Pista: {e.hint}")
                # Mostramos el error crudo por si acaso
                st.code(str(e))
    else:
        st.warning("Crea activos primero.")

# 4. CIERRE Y EVIDENCIAS
elif choice == "Cierre de OTs":
    st.subheader("Cierre Técnico y Evidencias")
    
    df_ots = run_query("ordenes")
    
    if not df_ots.empty:
        # Filtros
        pendientes = df_ots[df_ots['estado'] != 'Concluida']
        
        if not pendientes.empty:
            st.write("### Órdenes Pendientes")
            st.dataframe(pendientes[['id', 'descripcion', 'criticidad', 'fecha_creacion']])
            
            ot_id = st.selectbox("Selecciona ID para cerrar", pendientes['id'].values)
            
            st.markdown("---")
            st.write(f"Gestionando OT ID: **{ot_id}**")
            
            with st.form("form_cierre"):
                comentarios = st.text_area("Informe de Reparación")
                archivo = st.file_uploader("Foto de Evidencia (Antes/Después)", type=['jpg', 'png', 'jpeg'])
                
                if st.form_submit_button("Cerrar Orden"):
                    with st.spinner("Subiendo evidencia..."):
                        url_imagen = subir_imagen(archivo)
                        
                        update_data = {
                            "estado": "Concluida",
                            "comentarios_cierre": comentarios,
                            "evidencia_url": url_imagen if url_imagen else "Sin evidencia"
                        }
                        
                        supabase.table("ordenes").update(update_data).eq("id", int(ot_id)).execute()
                        st.balloons()
                        st.success("OT Cerrada y Guardada en la Nube")
                        st.rerun()
        else:
            st.info("¡Todo al día! No hay órdenes abiertas.")
            
        # Opcional: Ver historial de evidencias
        if st.checkbox("Ver Historial de Evidencias"):
            concluidas = df_ots[df_ots['estado'] == 'Concluida']
            for i, row in concluidas.iterrows():
                with st.expander(f"OT #{row['id']} - {row['descripcion']}"):
                    st.write(f"**Cierre:** {row['comentarios_cierre']}")
                    if row['evidencia_url'] and row['evidencia_url'] != "Sin evidencia":
                        st.image(row['evidencia_url'], caption="Evidencia", width=300)
    else:
        st.info("No hay órdenes en el sistema.")
