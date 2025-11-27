import streamlit as st
import pandas as pd
import sqlite3
from datetime import datetime
import io

# 1. Configuración y Conexión a Base de Datos
st.set_page_config(page_title="Gestión de Mantenimiento", layout="wide")

def init_db():
    conn = sqlite3.connect('mantenimiento.db')
    c = conn.cursor()
    # Tabla Activos
    c.execute('''CREATE TABLE IF NOT EXISTS activos
                (id INTEGER PRIMARY KEY, nombre TEXT, ubicacion TEXT, categoria TEXT)''')
    # Tabla Ordenes de Trabajo (OT)
    c.execute('''CREATE TABLE IF NOT EXISTS ordenes
                (id INTEGER PRIMARY KEY, activo_id INTEGER, descripcion TEXT, 
                 criticidad TEXT, estado TEXT, fecha_creacion DATE, 
                 comentarios_cierre TEXT, evidencia BLOB)''')
    conn.commit()
    conn.close()

init_db()

# Funciones Auxiliares
def run_query(query, params=()):
    conn = sqlite3.connect('mantenimiento.db')
    c = conn.cursor()
    c.execute(query, params)
    if query.lower().startswith("select"):
        data = c.fetchall()
        conn.close()
        return data
    else:
        conn.commit()
        conn.close()

# --- INTERFAZ DE USUARIO ---

st.title("🛠️ Sistema de Gestión de Mantenimiento (CMMS)")

menu = ["Dashboard", "Gestión de Activos", "Crear Orden de Trabajo", "Mis OTs (Cierre)"]
choice = st.sidebar.selectbox("Menú Principal", menu)

# --- 1. DASHBOARD INTERACTIVO ---
if choice == "Dashboard":
    st.subheader("Tablero de Control")
    
    # Obtener datos
    data_ots = run_query("SELECT criticidad, estado FROM ordenes")
    if data_ots:
        df = pd.DataFrame(data_ots, columns=['Criticidad', 'Estado'])
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Total OTs", len(df))
        col2.metric("OTs Abiertas", len(df[df['Estado']=='Abierta']))
        col3.metric("OTs Concluidas", len(df[df['Estado']=='Concluida']))
        
        st.markdown("---")
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("### OTs por Estado")
            st.bar_chart(df['Estado'].value_counts())
            
        with c2:
            st.write("### Criticidad de Intervenciones")
            st.bar_chart(df['Criticidad'].value_counts())
    else:
        st.info("Aún no hay datos para mostrar en el Dashboard.")

    # La línea de imagen anterior ha sido eliminada.
    # st.markdown("-> Gráficos de barras y KPIs se muestran arriba.")

# --- 2. GESTIÓN DE ACTIVOS ---
elif choice == "Gestión de Activos":
    st.subheader("Registrar Nuevo Activo")
    nombre = st.text_input("Nombre del Equipo")
    ubicacion = st.text_input("Ubicación")
    categoria = st.selectbox("Categoría", ["Eléctrico", "Mecánico", "Infraestructura", "HVAC"])
    
    if st.button("Guardar Activo"):
        run_query("INSERT INTO activos (nombre, ubicacion, categoria) VALUES (?,?,?)", 
                  (nombre, ubicacion, categoria))
        st.success(f"Activo **{nombre}** creado correctamente")

    st.markdown("---")
    st.write("### Inventario Actual")
    activos = run_query("SELECT * FROM activos")
    df_activos = pd.DataFrame(activos, columns=['ID', 'Nombre', 'Ubicación', 'Categoría'])
    st.dataframe(df_activos)

# --- 3. CREAR ORDEN DE TRABAJO ---
elif choice == "Crear Orden de Trabajo":
    st.subheader("Generar Nueva OT")
    
    activos = run_query("SELECT id, nombre FROM activos")
    lista_activos = {f"{a[1]} (ID: {a[0]})": a[0] for a in activos}
    
    if lista_activos:
        activo_selec = st.selectbox("Seleccionar Activo", list(lista_activos.keys()))
        id_activo = lista_activos[activo_selec]
        
        descripcion = st.text_area("Descripción de la Falla / Plan")
        criticidad = st.select_slider("Criticidad", options=["Baja", "Media", "Alta", "Crítica"])
        
        if st.button("Generar OT"):
            run_query("INSERT INTO ordenes (activo_id, descripcion, criticidad, estado, fecha_creacion) VALUES (?,?,?,?,?)",
                      (id_activo, descripcion, criticidad, "Abierta", datetime.now()))
            st.success("Orden de trabajo generada y notificada.")
    else:
        st.warning("Primero debes crear activos.")

# --- 4. GESTIÓN DE OTs (Cierre y Soportes) ---
elif choice == "Mis OTs (Cierre)":
    st.subheader("Gestión y Cierre de Órdenes")
    
    # Filtro para ver solo abiertas
    ver_todas = st.checkbox("Ver OTs Concluidas también")
    query = "SELECT * FROM ordenes" if ver_todas else "SELECT * FROM ordenes WHERE estado != 'Concluida'"
    ots = run_query(query)
    
    if ots:
        df_ots = pd.DataFrame(ots, columns=['ID', 'Activo ID', 'Descripción', 'Criticidad', 'Estado', 'Fecha', 'Cierre', 'Evidencia'])
        st.dataframe(df_ots[['ID', 'Descripción', 'Criticidad', 'Estado', 'Fecha']])
        
        # Uso de st.data_editor para seleccionar una fila
        ot_ids = df_ots['ID'].tolist()
        
        # Asegurarse de que el input tenga un valor por defecto válido
        default_ot_id = ot_ids[0] if ot_ids else 1
        ot_id = st.number_input("ID de OT a gestionar", min_value=1, step=1, value=default_ot_id)

        action = st.radio("Acción", ["Actualizar Estado", "Adjuntar Soporte y Cerrar"])
        
        if action == "Actualizar Estado":
            nuevo_estado = st.selectbox("Nuevo Estado", ["En Proceso", "En Espera de Repuestos"])
            if st.button("Actualizar"):
                run_query("UPDATE ordenes SET estado=? WHERE id=?", (nuevo_estado, ot_id))
                st.success(f"OT **{ot_id}** actualizada a: **{nuevo_estado}**")
                # st.rerun() # Descomentar si quieres que se recargue la lista automáticamente
                
        elif action == "Adjuntar Soporte y Cerrar":
            comentario = st.text_area("Informe Técnico de Cierre")
            archivo = st.file_uploader("Adjuntar Foto/PDF de soporte")
            
            if st.button("Cerrar Orden"):
                # Se lee el binario del archivo
                blob_data = archivo.read() if archivo else None
                run_query("UPDATE ordenes SET estado='Concluida', comentarios_cierre=?, evidencia=? WHERE id=?", 
                          (comentario, blob_data, ot_id))
                st.balloons()
                st.success(f"OT **{ot_id}** Cerrada exitosamente. Verifique el Dashboard para las estadísticas actualizadas.")
    else:
        st.info("No hay órdenes pendientes.")
