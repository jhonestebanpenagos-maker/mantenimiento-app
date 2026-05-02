import streamlit as st
import io
import urllib.parse
import qrcode
import cv2
import numpy as np
from utils.uploads import subir_imagen

# URL base del despliegue (actualizar si cambia)
BASE_URL_APP = "https://mantenimiento-app-fv9et6lbtpzrpbgjecqjfe.streamlit.app"


def generar_qr_activo(id_activo, nombre_activo):
    link = f"{BASE_URL_APP}/?id_activo_qr={id_activo}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return subir_imagen(img_byte_arr.getvalue(), "orion_codigos_qr")


def regenerar_todos_los_qrs():
    """Regenera los QR de TODOS los activos con la URL actual.
    Retorna (exitosos, fallidos, total)."""
    from utils.db import supabase
    try:
        res = supabase.table("activos").select("id, nombre").execute()
        if not res.data:
            return 0, 0, 0
        activos = res.data
    except Exception as e:
        print(f"Error consultando activos para regenerar QR: {e}")
        return 0, 0, 0

    exitosos = 0
    fallidos = 0
    for activo in activos:
        try:
            qr_url = generar_qr_activo(activo['id'], activo['nombre'])
            if qr_url:
                supabase.table("activos").update({"qr_url": qr_url}) \
                    .eq("id", activo['id']).execute()
                exitosos += 1
            else:
                fallidos += 1
        except Exception as e:
            print(f"Error regenerando QR para activo {activo['id']}: {e}")
            fallidos += 1

    return exitosos, fallidos, len(activos)


def leer_qr_imagen(uploaded_image):
    try:
        file_bytes = np.asarray(bytearray(uploaded_image.read()), dtype=np.uint8)
        img = cv2.imdecode(file_bytes, 1)
        detector = cv2.QRCodeDetector()
        data, bbox, _ = detector.detectAndDecode(img)
        if data:
            parsed_url = urllib.parse.urlparse(data)
            params = urllib.parse.parse_qs(parsed_url.query)
            if 'id_activo_qr' in params:
                return params['id_activo_qr'][0]
        return None
    except Exception as e:
        print(f"Error leyendo QR: {e}")
        return None
