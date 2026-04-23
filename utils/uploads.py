import streamlit as st
import os
import time
import requests
import cloudinary.uploader
from utils.helpers import error_amigable


# ==============================================================================
# 🖼️ MOSTRAR IMAGEN DESDE CLOUDINARY
# ==============================================================================
def mostrar_imagen_cloudinary(url, **kwargs):
    """Muestra una imagen de Cloudinary de forma robusta.
    Intenta st.image(url) directo, y si falla descarga los bytes."""
    if not url or not isinstance(url, str) or len(url.strip()) < 10:
        return False
    try:
        st.image(url, **kwargs)
        return True
    except Exception:
        pass
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200 and len(resp.content) > 100:
            st.image(resp.content, **kwargs)
            return True
    except Exception:
        pass
    return False


# ==============================================================================
# 📤 SUBIDA DE IMÁGENES
# ==============================================================================
def subir_imagen(archivo, carpeta="orion_evidencias"):
    """Sube imágenes a Cloudinary. Retorna la URL segura (https)."""
    if archivo:
        try:
            file_to_upload = archivo.getvalue() if hasattr(archivo, 'getvalue') else archivo
            respuesta = cloudinary.uploader.upload(
                file_to_upload,
                folder=carpeta,
                resource_type="image",
                transformation=[
                    {'width': 1000, 'crop': "limit"},
                    {'quality': "auto"},
                    {'fetch_format': "auto"}
                ]
            )
            return respuesta.get("secure_url")
        except Exception as e:
            error_amigable(e, "subir imagen")
            return None
    return None


# ==============================================================================
# 📤 SUBIDA DE ARCHIVOS GENÉRICOS
# ==============================================================================
def subir_archivo_generico(archivo):
    """Sube archivos forzando acceso PÚBLICO para evitar el error 401."""
    if archivo:
        try:
            nombre_original = archivo.name.lower()
            ext_imagenes = ('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp')
            es_imagen_visual = nombre_original.endswith(ext_imagenes)

            if es_imagen_visual:
                tipo_recurso = "image"
                carpeta = "orion_evidencias"
                public_id_manual = None
                use_unique = True
            else:
                tipo_recurso = "raw"
                carpeta = "orion_documentos"
                nombre_base, extension = os.path.splitext(archivo.name)
                nombre_limpio = "".join(c for c in nombre_base if c.isalnum() or c in ('_', '-')).strip()
                timestamp = int(time.time())
                public_id_manual = f"{nombre_limpio}_{timestamp}{extension}"
                use_unique = False

            respuesta = cloudinary.uploader.upload(
                archivo.getvalue(),
                folder=carpeta,
                resource_type=tipo_recurso,
                public_id=public_id_manual,
                use_filename=True,
                unique_filename=use_unique,
                type="upload",
                access_mode="public"
            )
            return respuesta.get("secure_url")
        except Exception as e:
            error_amigable(e, "subir archivo")
            return None
    return None
