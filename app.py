import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Gestión de Mantenimiento", layout="wide")

# Inicializar conexión a Supabase
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

# --- FUNCIONES AUXILIARES ---

def run_query(table_name):
    """Trae todos los datos de una tabla con manejo de errores"""
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        st.error(f"⚠️ Error crítico consultando la tabla '{table_name}'")
        st.code(str(e)) 
        st.stop()
        return pd.DataFrame()

def subir_imagen(archivo):
    """Sube imagen al Bucket 'evidencias' y devuelve la URL pública"""
    if archivo:
        try:
            file_name = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{archivo.name}"
            bucket_name = "evidencias"
            file_bytes = archivo.getvalue()
            
            supabase.storage.from_(bucket_name).upload(
                path=file_name,
                file=file_bytes,
                file_options={"content-type": archivo.type}
            )
            return supabase.storage.from_(bucket_name).get_public_url(file_name)
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
            "menu-title": {"color": "white", "font-weight": "bold", "font-size": "20px"},
            "container": {"padding": "5!important", "background-color": "#262730"},
            "icon": {"color": "#ff8c00", "font-size": "25px"},
            "nav-link": {
                "font-size": "16px",
                "text-align": "left",
                "margin": "0px",
                "--hover-color": "#444",
                "color": "white"
            },
            "nav-link-selected": {"background-color": "#02ab21"},
        }
    )

# --- LÓGICA DE PANTALLAS ---

# 1. DASHBOARD
if choice == "Dashboard":
    st.subheader("Tablero de Control")
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
            try:
                datos = {"nombre": nombre, "ubicacion": ubicacion, "categoria": categoria}
                supabase.table("activos").insert(datos).execute()
                st.success("Activo creado!")
                st.rerun()
            except Exception as e:
                st.error(f"Error al guardar activo: {e}")
            
    st.dataframe(run_query("activos"), use_container_width=True)

# 3. CREAR ORDEN (AQUÍ ESTÁ LA INTEGRACIÓN VISTOSA)
elif choice == "Crear Orden":
    st.subheader("Reportar Falla")
    
    df_activos = run_query("activos")
    
    if not df_activos.empty:
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
                
                # Intentamos guardar y CAPTURAMOS la respuesta en la variable 'response'
                response = supabase.table("ordenes").insert(datos).execute()
                
                # Verificamos si Supabase nos devolvió los datos creados
                if response.data:
                    # Obtenemos el ID de la nueva orden (está en la primera posición de la lista)
                    new_id = response.data[0]['id']
                    
                    # --- INICIO DEL CUADRO VISTOSO ---
                    st.balloons() # Lluvia de globos
                    
                    st.markdown(f"""
                        <div style="
                            background-color: #d4edda; 
                            color: #155724; 
                            padding: 20px; 
                            border-radius: 10px; 
                            border: 2px solid #c3e6cb; 
                            text-align: center; 
                            margin-top: 10px;
                            box-shadow: 2px 2px 10px rgba(0,0,0,0.1);">
                            <h2 style="margin:0;">✅ Orden Generada Exitosamente</h2>
                            <hr style="border-top: 1px solid #155724; margin: 10px 0;">
                            <p style="font-size: 18px;">Número de Control:</p>
                            <h1 style="font-size: 60px; margin: 0; font-weight: bold;">OT #{new_id}</h1>
                            <p style="font-size: 14px; font-style: italic; margin-top: 10px;">
                                El equipo ha sido notificado y la orden está en estado 'Abierta'.
                            </p>
                        </div>
                    """, unsafe_allow_html=True)
                    # --- FIN DEL CUADRO VISTOSO ---
                    
                else:
                    st.warning("La orden se guardó, pero no se pudo recuperar el número de ID.")
                
            except Exception as e:
                # Manejo de errores detallado
                st.error("⚠️ Error al guardar la orden:")
                if hasattr(e, 'message'):
                    st.write(f"Mensaje: {e.message}")
                if hasattr(e, 'details'):
                    st.write(f"Detalles: {e.details}")
                st.code(str(e))
    else:
        st.warning("Primero debes crear activos en la sección 'Gestión de Activos'.")

# 4. CIERRE Y EVIDENCIAS
elif choice == "Cierre de OTs":
    st.subheader("Cierre Técnico y Evidencias")
    
    df_ots = run_query("ordenes")
    
    if not df_ots.empty:
        pendientes = df_ots[df_ots['estado'] != 'Concluida']
        
        if not pendientes.empty:
            st.write("### Órdenes Pendientes")
            st.dataframe(pendientes[['id', 'descripcion', 'criticidad', 'fecha_creacion']], use_container_width=True)
            
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
            
        if st.checkbox("Ver Historial de Evidencias"):
            concluidas = df_ots[df_ots['estado'] == 'Concluida']
            for i, row in concluidas.iterrows():
                with st.expander(f"OT #{row['id']} - {row['descripcion']}"):
                    st.write(f"**Cierre:** {row['comentarios_cierre']}")
                    if row['evidencia_url'] and row['evidencia_url'] != "Sin evidencia":
                        st.image(row['evidencia_url'], caption="Evidencia", width=300)
    else:
        st.info("No hay órdenes en el sistema.")
