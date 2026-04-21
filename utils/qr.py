import streamlit as st
import io
import urllib.parse
import qrcode
import cv2
import numpy as np
from utils.uploads import subir_imagen


def generar_qr_activo(id_activo, nombre_activo):
    base_url = "https://mantenimiento-app-esw6r3vpeqxngz3ifyp5ey.streamlit.app"
    link = f"{base_url}/?id_activo_qr={id_activo}"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill='black', back_color='white')
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return subir_imagen(img_byte_arr.getvalue(), "orion_codigos_qr")


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
    except:
        return None
