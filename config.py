import streamlit as st
import os

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
        st.error(f"Error configurando Cloudinary: {e}")


# ==============================================================================
# 🎨 CARGA DE ESTILOS
# ==============================================================================
def cargar_css():
    try:
        with open("styles.css") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("⚠️ No se encontró el archivo styles.css en la carpeta.")
