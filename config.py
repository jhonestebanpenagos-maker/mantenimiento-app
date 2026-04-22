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
        st.error("⚠️ No se pudo configurar el servicio de imágenes. Contacte al administrador.")
        print(f"Error configurando Cloudinary: {e}")


# ==============================================================================
# 🎨 SISTEMA DE TEMAS
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

_TEMA_PREF_PATH = os.path.join(os.path.dirname(__file__), ".tema_actual")


def obtener_tema_actual() -> str:
    """Obtiene el tema guardado. Retorna la clave del tema."""
    # Primero: session state
    if 'tema_seleccionado' in st.session_state:
        return st.session_state['tema_seleccionado']

    # Segundo: archivo local persistente
    try:
        if os.path.exists(_TEMA_PREF_PATH):
            with open(_TEMA_PREF_PATH, "r") as f:
                tema = f.read().strip()
                if tema in TEMAS_DISPONIBLES:
                    st.session_state['tema_seleccionado'] = tema
                    return tema
    except Exception:
        pass

    # Default
    st.session_state['tema_seleccionado'] = "default"
    return "default"


def guardar_tema(tema_key: str):
    """Guarda la preferencia de tema."""
    if tema_key not in TEMAS_DISPONIBLES:
        return
    st.session_state['tema_seleccionado'] = tema_key
    try:
        with open(_TEMA_PREF_PATH, "w") as f:
            f.write(tema_key)
    except Exception:
        pass


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
        with st.expander("⚙️ Tema", expanded=False):
            for key, info in TEMAS_DISPONIBLES.items():
                es_activo = key == tema_actual
                estilo_btn = "primary" if es_activo else "secondary"
                label = f"✅ {info['nombre']}" if es_activo else info['nombre']

                if st.button(label, key=f"tema_{key}", use_container_width=True, type=estilo_btn):
                    guardar_tema(key)
                    st.rerun()

            st.caption("El tema se guarda automáticamente.")
