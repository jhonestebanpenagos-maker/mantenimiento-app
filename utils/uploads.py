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
    Prioriza descargar los bytes primero (más confiable que URL directa)."""
    if not url or not isinstance(url, str) or len(url.strip()) < 10:
        return False

    url = url.strip()
    headers = {"User-Agent": "Mozilla/5.0 ORION-App/1.0"}

    # Intento 1: descargar bytes primero (más confiable, evita CORS/acceso)
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        print(f"[Cloudinary] requests status={resp.status_code}, len={len(resp.content)}")
        if resp.status_code == 200 and len(resp.content) > 100:
            st.image(resp.content, **kwargs)
            return True
        else:
            print(f"[Cloudinary] respuesta inválida: status={resp.status_code}")
    except Exception as e1:
        print(f"[Cloudinary] requests falló: {e1}")

    # Intento 2: st.image directo con URL (fallback)
    try:
        st.image(url, **kwargs)
        return True
    except Exception as e2:
        print(f"[Cloudinary] st.image(url) falló: {e2}")

    # Intento 3: URL limpia sin transformaciones
    if "/upload/" in url:
        try:
            parts = url.split("/upload/", 1)
            if len(parts) == 2:
                # Reconstruir URL sin transformaciones
                after_upload = parts[1]
                # Quitar prefijo de transformaciones (ej: w_1000,q_auto,f_auto/)
                segments = after_upload.split("/")
                if len(segments) > 1:
                    # Buscar el segmento de versión (v1234...) o el path del archivo
                    clean_path = "/".join(segments[1:]) if segments[0].startswith("v") and segments[0][1:].isdigit() else after_upload
                    simple_url = f"{parts[0]}/upload/{clean_path}"
                    print(f"[Cloudinary] intento URL limpia: {simple_url}")
                    resp3 = requests.get(simple_url, headers=headers, timeout=10)
                    if resp3.status_code == 200 and len(resp3.content) > 100:
                        st.image(resp3.content, **kwargs)
                        return True
        except Exception as e3:
            print(f"[Cloudinary] intento 3 falló: {e3}")

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
                access_mode="public"
            )
            url = respuesta.get("secure_url") or respuesta.get("url")
            print(f"[Cloudinary] Upload OK: {url}")
            return url
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
