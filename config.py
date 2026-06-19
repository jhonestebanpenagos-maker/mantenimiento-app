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
# 🎨 SISTEMA DE TEMAS (Optimizado para la Nube)
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
    """Obtiene el tema guardado en la sesión activa del usuario."""
    if 'tema_seleccionado' not in st.session_state:
        st.session_state['tema_seleccionado'] = "default"
    
    return st.session_state['tema_seleccionado']

def guardar_tema(tema_key: str):
    """Guarda la preferencia de tema solo para el usuario actual."""
    if tema_key in TEMAS_DISPONIBLES:
        st.session_state['tema_seleccionado'] = tema_key

def cargar_css():
    """Carga el CSS del tema actualmente seleccionado."""
    tema_key = obtener_tema_actual()
    tema = TEMAS_DISPONIBLES.get(tema_key, TEMAS_DISPONIBLES["default"])
    archivo_css = tema["archivo"]

    try:
        with open(archivo_css) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        # Fallback al tema default si el archivo no existe
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
            st.caption("Personaliza los colores (solo afecta tu sesión actual).")
            for key, info in TEMAS_DISPONIBLES.items():
                es_activo = key == tema_actual
                estilo_btn = "primary" if es_activo else "secondary"
                label = f"✅ {info['nombre']}" if es_activo else info['nombre']

                if st.button(label, key=f"tema_{key}", use_container_width=True, type=estilo_btn):
                    guardar_tema(key)
                    st.rerun()
