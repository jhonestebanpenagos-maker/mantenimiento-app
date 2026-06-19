import streamlit as st
import os
import json

# ==============================================================================
# ☁️ CONFIGURACIÓN DE CLOUDINARY
# ==============================================================================
def init_cloudinary():
    import cloudinary
    try:
        cloudinary.config(
            cloud_name=st.secrets["cloudinary"]["cloud_name"],
            api_key=st.secrets["cloudinary"]["api_key"],
            api_secret=st.secrets["cloudinary"]["api_secret"],
            secure=True
        )
    except KeyError:
        st.warning("⚠️ ADVERTENCIA: No se encontraron las credenciales de Cloudinary en secrets.toml.")
    except Exception as e:
        from utils.logger import logger
        logger.error(f"Error crítico configurando Cloudinary: {e}")
        st.error("⚠️ No se pudo configurar el servicio de imágenes. Contacte al administrador.")

# ==============================================================================
# 🎨 SISTEMA DE TEMAS (Vinculado a Base de Datos)
# ==============================================================================
TEMAS_DISPONIBLES = {
    "default": {
        "nombre": "🟠 Original (Naranja/Verde)",
        "archivo": "styles.css",
        "descripcion": "El tema original de ORIÓN"
    },
    "light": {
        "nombre": "⬜ Light Professional",
        "archivo": "styles_opcion_claro.css",
        "descripcion": "Fondo blanco, ideal para pantallas luminosas"
    }
}

def obtener_tema_actual() -> str:
    """Obtiene el tema guardado. Prioriza memoria, luego base de datos."""
    user_doc = st.session_state.get('user_doc')
    
    # 1. Si no hay usuario logueado (pantalla de login), siempre usar default
    if not user_doc:
        # Nos aseguramos de NO bloquear la memoria con el tema por defecto
        st.session_state.pop('tema_seleccionado', None)
        return "default"

    # 2. Si el usuario ya está logueado y su tema ya se cargó en memoria, lo usamos
    if 'tema_seleccionado' in st.session_state:
        return st.session_state['tema_seleccionado']
    
    # 3. Si el usuario está logueado pero recién abrió el navegador, buscar en BD
    try:
        from utils.db import supabase
        if supabase:
            res = supabase.table("usuarios").select("tema_visual").eq("documento", user_doc).execute()
            if res.data and res.data[0].get('tema_visual'):
                tema_bd = res.data[0]['tema_visual']
                if tema_bd in TEMAS_DISPONIBLES:
                    st.session_state['tema_seleccionado'] = tema_bd
                    return tema_bd
    except Exception as e:
        from utils.logger import logger
        logger.error(f"Aviso: No se pudo leer el tema de BD: {e}")

    # 4. Si la base de datos falla o no tiene tema registrado, aplicamos default
    st.session_state['tema_seleccionado'] = "default"
    return "default"

def guardar_tema(tema_key: str):
    """Guarda la preferencia de tema en memoria y en el perfil de base de datos."""
    if tema_key in TEMAS_DISPONIBLES:
        # 1. Guardar en memoria rápida
        st.session_state['tema_seleccionado'] = tema_key
        
        # 2. Guardar en base de datos de Supabase si hay un usuario conectado
        if st.session_state.get('user_doc'):
            try:
                from utils.db import supabase
                if supabase:
                    supabase.table("usuarios").update({"tema_visual": tema_key}).eq("documento", st.session_state['user_doc']).execute()
            except Exception as e:
                from utils.logger import logger
                logger.error(f"Error guardando tema en BD: {e}")

def cargar_css():
    """Carga el CSS del tema actualmente seleccionado."""
    tema_key = obtener_tema_actual()
    tema = TEMAS_DISPONIBLES.get(tema_key, TEMAS_DISPONIBLES["default"])
    archivo_css = tema["archivo"]

    try:
        with open(archivo_css) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        try:
            with open("styles.css") as f:
                st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
        except FileNotFoundError:
            st.warning("⚠️ No se encontró ningún archivo de estilos.")

def render_selector_tema():
    """Renderiza el selector de tema en el sidebar."""
    tema_actual = obtener_tema_actual()

    with st.sidebar:
        with st.expander("⚙️ Tema Visual", expanded=False):
            st.caption("Los colores se guardan en tu perfil personal.")
            for key, info in TEMAS_DISPONIBLES.items():
                es_activo = key == tema_actual
                estilo_btn = "primary" if es_activo else "secondary"
                label = f"✅ {info['nombre']}" if es_activo else info['nombre']

                if st.button(label, key=f"tema_{key}", use_container_width=True, type=estilo_btn):
                    guardar_tema(key)
                    st.rerun()
