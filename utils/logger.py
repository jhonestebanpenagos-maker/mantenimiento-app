import logging
import os
from logging.handlers import RotatingFileHandler

# 1. Crear una carpeta llamada 'logs' automáticamente si no existe
if not os.path.exists('logs'):
    os.makedirs('logs')

# 2. Configurar el nombre de nuestro "anotador"
logger = logging.getLogger("orion_logger")
logger.setLevel(logging.INFO)

# 3. Evitar que se dupliquen los mensajes si Streamlit recarga la página
if not logger.handlers:
    
    # Handler 1: Mostrar en la consola (Terminal)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)

    # Handler 2: Guardar en un archivo de texto (Máximo 5MB por archivo, guarda hasta 3 respaldos)
    file_handler = RotatingFileHandler('logs/orion_app.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
    file_handler.setLevel(logging.ERROR) # Al archivo solo enviamos los ERRORES críticos

    # 4. Darle un formato bonito y útil: Fecha - Nivel de Error - Archivo exacto - Mensaje
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s')
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    # Conectar los handlers al logger principal
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
