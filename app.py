import streamlit as st
import pandas as pd
from supabase import create_client, Client
from datetime import datetime
from streamlit_option_menu import option_menu
import io

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
    """Trae todos los datos de una tabla con manejo de errores"""
    try:
        response = supabase.table(table_name).select("*").execute()
        return pd.DataFrame(response.data)
    except Exception as e:
        # Si la tabla de auditoría no existe aún, devolvemos vacío sin romper la app
        if "auditoria_eliminados" in table_name:
            return pd.DataFrame()
        
        st.error(f"⚠️ Error consultando tabla '{table_name}'")
        st.code(str(e))
        return pd.DataFrame()

def subir_imagen(archivo):
    """Sube imagen al Bucket 'evidencias' y devuelve la URL"""
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

# --- 4. INTERFAZ Y MENÚ ---
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
            "nav-link": {"font-size": "16px", "text-align": "left", "margin": "0px", "--hover-color": "#444", "color": "white"},
            "nav-link-selected": {"background-color": "#02ab21"},
        }
    )

# --- 5. LÓGICA DE PANTALLAS ---

# === A. DASHBOARD ===
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
        st.info("Aún no hay datos para mostrar.")

# === B. GESTIÓN DE ACTIVOS (CON AUDITORÍA INTEGRADA) ===
elif choice == "Gestión de Activos":
    st.subheader("Inventario de Equipos")
    
    df_activos = run_query("activos")
    
    # Pestañas
    tab1, tab2 = st.tabs(["➕ Registrar Nuevo", "✏️ Editar / Dar de Baja"])
    
    # --- PESTAÑA 1: CREAR ---
    with tab1:
        with st.form("form_activo"):
            c1, c2 = st.columns(2)
            nombre = c1.text_input("Nombre del Equipo")
            ubicacion = c2.text_input("Ubicación")
            categoria = st.selectbox("Categoría", ["Mecánico", "Eléctrico", "Infraestructura", "HVAC", "Otros"])
            
            if st.form_submit_button("Guardar Activo"):
                if nombre and ubicacion:
                    datos = {"nombre": nombre, "ubicacion": ubicacion, "categoria": categoria}
                    supabase.table("activos").insert(datos).execute()
                    st.success(f"Activo '{nombre}' creado correctamente!")
                    st.rerun()
                else:
                    st.warning("Nombre y Ubicación son obligatorios.")

    # --- PESTAÑA 2: EDITAR / ELIMINAR ---
    with tab2:
        if not df_activos.empty:
            activos_dict = {f"{row['nombre']} - {row['ubicacion']}": row['id'] for i, row in df_activos.iterrows()}
            seleccion = st.selectbox("Seleccionar Activo", list(activos_dict.keys()))
            id_seleccionado = activos_dict[seleccion]
            
            datos_actuales = df_activos[df_activos['id'] == id_seleccionado].iloc[0]
            
            st.markdown("---")
            st.write("### Modificar Datos")
            
            with st.form("form_editar"):
                c1, c2 = st.columns(2)
                nuevo_nombre = c1.text_input("Nombre", value=datos_actuales['nombre'])
                nueva_ubicacion = c2.text_input("Ubicación", value=datos_actuales['ubicacion'])
                
                opciones = ["Mecánico", "Eléctrico", "Infraestructura", "HVAC", "Otros"]
                idx = opciones.index(datos_actuales['categoria']) if datos_actuales['categoria'] in opciones else 0
                nueva_cat = st.selectbox("Categoría", opciones, index=idx)
                
                if st.form_submit_button("💾 Actualizar Datos"):
                    update_data = {"nombre": nuevo_nombre, "ubicacion": nueva_ubicacion, "categoria": nueva_cat}
                    supabase.table("activos").update(update_data).eq("id", int(id_seleccionado)).execute()
                    st.success("Datos actualizados.")
                    st.rerun()
            
            # ZONA DE PELIGRO
            st.markdown("---")
            with st.expander("🗑️ Zona de Peligro (Dar de Baja)"):
                st.warning(f"Estás gestionando la baja de: **{datos_actuales['nombre']}**")
                
                # --- NUEVOS CAMPOS DE TRAZABILIDAD ---
                usuario_baja = st.text_input("👤 Persona Responsable de la Baja:")
                motivo = st.text_area("Motivo de la baja (Obligatorio):", placeholder="Ej: Equipo vendido, dañado, obsoleto...")
                
                if st.button("Confirmar Baja Definitiva", type="primary", disabled=(not motivo or not usuario_baja)):
                    # 1. Verificar si hay OTs abiertas
                    ots_abiertas = supabase.table("ordenes").select("*").eq("activo_id", int(id_seleccionado)).eq("estado", "Abierta").execute()
                    
                    if len(ots_abiertas.data) > 0:
                        st.error(f"⛔ NO SE PUEDE ELIMINAR. Tiene {len(ots_abiertas.data)} órdenes ABIERTAS. Ciérralas primero.")
                    else:
                        try:
                            with st.spinner("Procesando baja y auditoría..."):
                                # A. Auditoría
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
                                    "usuario_responsable": usuario_baja # <--- NUEVO CAMPO AQUI
                                }).execute()
                                
                                # B. Eliminar
                                supabase.table("ordenes").delete().eq("activo_id", int(id_seleccionado)).execute()
                                supabase.table("activos").delete().eq("id", int(id_seleccionado)).execute()
                                
                                st.success("✅ Activo dado de baja correctamente.")
                                st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        else:
            st.info("No hay activos para editar.")

    # Tabla general y Auditoría
    st.markdown("---")
    st.markdown("### 📋 Inventario Activo")
    st.dataframe(df_activos, use_container_width=True)
    
    # --- VISUALIZACIÓN ORDENADA DEL HISTORIAL ---
    with st.expander("📂 Ver Historial de Eliminados (Auditoría)"):
        df_audit = run_query("auditoria_eliminados")
        
        if not df_audit.empty:
            st.markdown("#### Registros de Baja:")
            # Iteramos sobre cada fila del historial
            for i, row in df_audit.iterrows():
                # Accedemos al diccionario guardado
                datos = row['datos_respaldo']
                
                # Usamos un expander para cada registro borrado
                with st.expander(f"❌ BAJA #{datos.get('id_original')} - {datos.get('nombre_referencia', 'Activo Desconocido')} ({row['fecha_eliminacion'][:10]})"):
                    st.markdown(f"""
                        - **Tipo de Registro:** `{row['tipo_registro']}`
                        - **Responsable de Baja:** **`{row['usuario_responsable']}`**
                        - **Motivo Detallado:** *{datos.get('motivo_baja')}*
                        - **ID Original:** `{datos.get('id_original')}`
                        - **Ubicación Original:** `{datos.get('ubicacion')}`
                        - **Categoría:** `{datos.get('categoria')}`
                        ---
                        <small>Fecha de Eliminación: {row['fecha_eliminacion']}</small>
                    """, unsafe_allow_html=True)
        else:
            st.info("La bitácora de auditoría está vacía.")

# === C. CREAR ORDEN ===
elif choice == "Crear Orden":
    st.subheader("Reportar Falla")
    
    df_activos = run_query("activos")
    
    if not df_activos.empty:
        activos_dict = {f"{row['nombre']} - {row['ubicacion']}": row['id'] for i, row in df_activos.iterrows()}
        seleccion = st.selectbox("Seleccionar Equipo", list(activos_dict.keys()))
        activo_id = activos_dict[seleccion]
        
        descripcion = st.text_area("Descripción del problema")
        criticidad = st.select_slider("Criticidad", ["Baja", "Media", "Alta", "Crítica"])
        
        if st.button("Generar Orden de Trabajo"):
            try:
                datos = {
                    "activo_id": int(activo_id),
                    "descripcion": descripcion,
                    "criticidad": criticidad,
                    "estado": "Abierta",
                    "fecha_creacion": datetime.now().isoformat()
                }
                response = supabase.table("ordenes").insert(datos).execute()
                
                if response.data:
                    new_id = response.data[0]['id']
                    st.balloons()
                    st.markdown(f"""
                        <div style="background-color:#d4edda; color:#155724; padding:20px; border-radius:10px; text-align:center; margin-top:10px;">
                            <h2 style="margin:0;">✅ Orden Generada</h2>
                            <h1 style="font-size:60px; margin:0; font-weight:bold;">OT #{new_id}</h1>
                            <p>El equipo ha sido notificado.</p>
                        </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Orden guardada, pero no se recuperó el ID.")
            except Exception as e:
                st.error(f"Error: {e}")
    else:
        st.warning("Primero crea activos en la sección 'Gestión de Activos'.")

# === D. CIERRE Y EVIDENCIAS ===
elif choice == "Cierre de OTs":
    st.subheader("Cierre Técnico")
    df_ots = run_query("ordenes")
    
    if not df_ots.empty:
        pendientes = df_ots[df_ots['estado'] != 'Concluida']
        if not pendientes.empty:
            st.dataframe(pendientes[['id', 'descripcion', 'estado']], use_container_width=True)
            ot_id = st.selectbox("ID a Cerrar", pendientes['id'].values)
            
            with st.form("cierre"):
                comentarios = st.text_area("Informe Técnico")
                archivo = st.file_uploader("Evidencia", type=['jpg','png'])
                if st.form_submit_button("Cerrar Orden"):
                    with st.spinner("Guardando..."):
                        url_img = subir_imagen(archivo)
                        update_data = {
                            "estado": "Concluida",
                            "comentarios_cierre": comentarios,
                            "evidencia_url": url_img if url_img else "Sin evidencia"
                        }
                        supabase.table("ordenes").update(update_data).eq("id", int(ot_id)).execute()
                        st.success("Orden Cerrada")
                        st.rerun()
        else:
            st.info("No hay órdenes pendientes.")
            
        if st.checkbox("Ver Historial Cerrado"):
            concluidas = df_ots[df_ots['estado'] == 'Concluida']
            if not concluidas.empty:
                for i, row in concluidas.iterrows():
                    with st.expander(f"OT #{row['id']} - {row['descripcion']}"):
                        st.write(f"**Informe:** {row['comentarios_cierre']}")
                        if row['evidencia_url'] and "http" in row['evidencia_url']:
                            st.image(row['evidencia_url'], width=200)
    else:
        st.info("Sin registros.")
