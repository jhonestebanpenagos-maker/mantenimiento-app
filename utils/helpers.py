import streamlit as st
import pandas as pd
import numpy as np
import os
import re
import json
import logging
import bcrypt
import hashlib
from datetime import datetime, timedelta


# ==============================================================================
# 🔔 SISTEMA DE NOTIFICACIONES EN UI
# ==============================================================================
def agregar_notificacion(tipo, mensaje):
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    st.session_state.notifications.append({'type': tipo, 'message': mensaje})


def mostrar_notificaciones():
    if 'notifications' not in st.session_state:
        st.session_state.notifications = []
    for notif in st.session_state.notifications[:]:
        if notif['type'] == 'success':
            st.success(f"✅ {notif['message']}")
        elif notif['type'] == 'error':
            st.error(f"❌ {notif['message']}")
        elif notif['type'] == 'warning':
            st.warning(f"⚠️ {notif['message']}")
        elif notif['type'] == 'delete':
            st.error(f"🗑️ {notif['message']}")
    st.session_state.notifications = []


# ==============================================================================
# 🧭 SISTEMA DE NAVEGACIÓN CON HISTORIAL
# ==============================================================================
def navegar_a(page, jump_target=None, jump_id=None):
    """Navega a una página guardando el historial para poder volver."""
    if 'nav_history' not in st.session_state:
        st.session_state.nav_history = []

    # Guardar estado actual antes de navegar
    current = st.session_state.get('current_page', 'Tablero de Mando')
    current_jump = st.session_state.get('jump_target')
    current_jump_id = st.session_state.get('jump_id')

    # No duplicar si ya estamos ahí
    if current == page and jump_target == current_jump and jump_id == current_jump_id:
        return

    st.session_state.nav_history.append({
        'page': current,
        'jump_target': current_jump,
        'jump_id': current_jump_id,
    })

    # Máximo 10 niveles de historial
    if len(st.session_state.nav_history) > 10:
        st.session_state.nav_history = st.session_state.nav_history[-10:]

    # Navegar
    st.session_state.current_page = page
    st.session_state.jump_target = jump_target
    st.session_state.jump_id = jump_id
    st.rerun()


def volver_atras():
    """Vuelve a la página anterior del historial. Retorna True si pudo volver."""
    history = st.session_state.get('nav_history', [])
    if not history:
        return False

    prev = history.pop()
    st.session_state.current_page = prev['page']
    st.session_state.jump_target = prev['jump_target']
    st.session_state.jump_id = prev['jump_id']
    st.rerun()
    return True


def tiene_historial():
    """Retorna True si hay historial de navegación para volver."""
    return len(st.session_state.get('nav_history', [])) > 0


# ==============================================================================
# 🔄 CONVERSIÓN DE TIPOS
# ==============================================================================
def convertir_tipos_python(data_dict):
    converted = {}
    for key, value in data_dict.items():
        if value is None:
            converted[key] = None
        elif isinstance(value, (pd.Timestamp, datetime)):
            converted[key] = value.isoformat()
        elif isinstance(value, (np.integer, np.int64)):
            converted[key] = int(value)
        elif isinstance(value, (np.floating, np.float64)):
            converted[key] = float(value)
        elif isinstance(value, (np.bool_, bool)):
            converted[key] = bool(value)
        elif isinstance(value, (np.ndarray, pd.Series)):
            converted[key] = value.tolist()
        else:
            converted[key] = value
    return converted


# ==============================================================================
# 🛡️ VALIDACIONES
# ==============================================================================
def validar_usuario_unico(nuevo_documento, id_ignorar=None):
    from utils.db import supabase
    try:
        res = supabase.table("usuarios").select("*").eq("documento", nuevo_documento).execute()
        if res.data:
            usuario_existente = res.data[0]
            if id_ignorar and str(usuario_existente['id']) == str(id_ignorar):
                return True
            return False
        return True
    except Exception as e:
        _logger.error(f"Error validando usuario: {e}")
        st.error("⚠️ No se pudo verificar el usuario. Intente nuevamente.")
        return False


def check_open_orders(user_id):
    from utils.db import supabase
    try:
        res = supabase.table("ordenes").select("id")\
            .eq("tecnico_asignado", user_id)\
            .in_("estado", ["Abierta", "Por Validar"])\
            .execute()
        return bool(res.data and len(res.data) > 0)
    except Exception as e:
        print(f"Error checking orders: {e}")
        return False


# ==============================================================================
# 🛠️ MANEJO DE ERRORES AMIGABLE
# ==============================================================================

# Logger centralizado
_logger = logging.getLogger("orion")
if not _logger.handlers:
    _logger.setLevel(logging.DEBUG)
    try:
        _log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
        os.makedirs(_log_dir, exist_ok=True)
        _fh = logging.FileHandler(os.path.join(_log_dir, "orion.log"), encoding="utf-8")
        _fh.setLevel(logging.DEBUG)
        _fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s — %(message)s"))
        _logger.addHandler(_fh)
    except Exception:
        pass  # Si falla el archivo, al menos loguea a consola


# Mapeo de excepciones conocidas a mensajes amigables
_ERROR_MAP = {
    "ConnectionRefusedError": "No se pudo conectar al servidor. Verifique su conexión a internet.",
    "TimeoutError": "La operación tardó demasiado. Intente nuevamente.",
    "requests.exceptions.ConnectionError": "No hay conexión al servidor. Verifique su red.",
    "requests.exceptions.Timeout": "El servidor tardó demasiado en responder.",
    "KeyError": "Faltan datos obligatorios en la solicitud.",
    "ValueError": "Los datos ingresados no son válidos.",
    "PermissionError": "No tiene permisos para realizar esta acción.",
}


def manejar_error(e: Exception, contexto: str = "", mostrar_usuario: bool = True) -> str:
    """
    Maneja una excepción de forma amigable.
    - Loguea el error real internamente (para debugging)
    - Retorna un mensaje amigable para el usuario
    - Si mostrar_usuario=True, muestra el mensaje en Streamlit automáticamente
    """
    error_tipo = type(e).__name__
    error_msg = str(e)

    # Log interno siempre (para ti, no para el usuario)
    _logger.error(f"[{contexto}] {error_tipo}: {error_msg}", exc_info=True)

    # Mensaje amigable
    mensaje = _ERROR_MAP.get(error_tipo)
    if not mensaje:
        # Buscar coincidencias parciales en el mapeo
        for clave, msg_amigable in _ERROR_MAP.items():
            if clave.lower() in error_msg.lower() or clave in error_tipo:
                mensaje = msg_amigable
                break

    if not mensaje:
        if contexto:
            mensaje = f"Ocurrió un problema al procesar: {contexto}. Intente nuevamente."
        else:
            mensaje = "Ocurrió un problema inesperado. Intente nuevamente."

    if mostrar_usuario:
        st.error(f"⚠️ {mensaje}")

    return mensaje


# Alias corto para usar inline
def error_amigable(e: Exception, contexto: str = ""):
    """Atajo: maneja error y lo muestra al usuario."""
    return manejar_error(e, contexto, mostrar_usuario=True)


# ==============================================================================
# 🔐 HASH DE CONTRASEÑAS (bcrypt) + POLÍTICA DE SEGURIDAD
# ==============================================================================


# Ruta del archivo de auditoría local
_AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "auditoria.log")

# Configuración de política de contraseñas
PASSWORD_MIN_LENGTH = 8
PASSWORD_REQUIRE_UPPER = True
PASSWORD_REQUIRE_LOWER = True
PASSWORD_REQUIRE_DIGIT = True
PASSWORD_REQUIRE_SPECIAL = False  # Opcional para no frustrar técnicos en campo


def validar_politica_password(password: str) -> tuple[bool, str]:
    """
    Valida que una contraseña cumpla la política de seguridad.
    Retorna (es_valida, mensaje_error).
    """
    if len(password) < PASSWORD_MIN_LENGTH:
        return False, f"La contraseña debe tener al menos {PASSWORD_MIN_LENGTH} caracteres."

    if PASSWORD_REQUIRE_UPPER and not re.search(r'[A-Z]', password):
        return False, "La contraseña debe incluir al menos una letra mayúscula."

    if PASSWORD_REQUIRE_LOWER and not re.search(r'[a-z]', password):
        return False, "La contraseña debe incluir al menos una letra minúscula."

    if PASSWORD_REQUIRE_DIGIT and not re.search(r'\d', password):
        return False, "La contraseña debe incluir al menos un número."

    if PASSWORD_REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>_\-+=\[\]\\;/~`]', password):
        return False, "La contraseña debe incluir al menos un carácter especial (!@#$%...)."

    return True, ""


def hashear_password(password: str) -> str:
    """Hashea una contraseña con bcrypt (salt automático)."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(rounds=12)).decode('utf-8')


def verificar_password(password: str, hash_almacenado: str) -> bool:
    """
    Verifica una contraseña contra su hash.
    Soporta migración automática de SHA-256 → bcrypt:
    - Si el hash es SHA-256 (64 chars hex), verifica con SHA-256
    - Si es bcrypt ($2b$...), verifica con bcrypt
    """
    # Detectar formato del hash
    if _es_sha256(hash_almacenado):
        # Hash antiguo SHA-256 — verificar y retornar True si coincide
        hash_sha256 = hashlib.sha256(password.encode()).hexdigest()
        return hash_sha256 == hash_almacenado
    else:
        # Hash bcrypt — verificar normalmente
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hash_almacenado.encode('utf-8'))
        except (ValueError, Exception):
            return False


def migrar_password_si_sha256(documento: str, password: str, hash_almacenado: str) -> str | None:
    """
    Si el hash es SHA-256 y el password es correcto,
    re-hashea con bcrypt y actualiza en BD.
    Retorna el nuevo hash si migró, None si no era necesario.
    """
    if not _es_sha256(hash_almacenado):
        return None  # Ya es bcrypt, no hacer nada

    hash_sha256 = hashlib.sha256(password.encode()).hexdigest()
    if hash_sha256 != hash_almacenado:
        return None  # Password incorrecto, no migrar

    # Migrar a bcrypt
    nuevo_hash = hashear_password(password)
    try:
        from utils.db import supabase
        supabase.table("usuarios").update({"password": nuevo_hash}).eq("documento", documento).execute()
        registrar_auditoria("MIGRACION", documento, "Password migrado de SHA-256 a bcrypt")
    except Exception as e:
        print(f"Error migrando password: {e}")
    return nuevo_hash


def _es_sha256(hash_str: str) -> bool:
    """Detecta si un hash es SHA-256 (64 caracteres hexadecimales)."""
    if not hash_str or len(hash_str) != 64:
        return False
    return all(c in '0123456789abcdef' for c in hash_str.lower())


# ==============================================================================
# 🔒 RATE LIMITING PERSISTENTE (server-side en Supabase)
# ==============================================================================

LOGIN_MAX_INTENTOS = 3
LOGIN_BLOQUEO_MINUTOS = 5


def verificar_bloqueo_login(documento: str) -> tuple[bool, int, str | None]:
    """
    Verifica si un documento está bloqueado por intentos fallidos.
    Retorna (está_bloqueado, intentos_actuales, bloqueado_hasta_iso).
    """
    try:
        res = supabase.table("login_attempts").select("*") \
            .eq("documento", documento).execute()
        if not res.data:
            return False, 0, None
        registro = res.data[0]
        bloqueado_hasta = registro.get('bloqueado_hasta')
        if bloqueado_hasta:
            if datetime.fromisoformat(str(bloqueado_hasta)) > datetime.now():
                return True, registro.get('intentos', 0), bloqueado_hasta
        return False, registro.get('intentos', 0), None
    except Exception as e:
        print(f"Error verificando bloqueo login: {e}")
        return False, 0, None  # No bloquear si falla la tabla


def registrar_intento_fallido(documento: str):
    """Registra un intento fallido. Bloquea si supera el máximo."""
    try:
        res = supabase.table("login_attempts").select("*") \
            .eq("documento", documento).execute()

        if res.data:
            intentos = res.data[0].get('intentos', 0) + 1
            bloqueado_hasta = None
            if intentos >= LOGIN_MAX_INTENTOS:
                bloqueado_hasta = (
                    datetime.now() + timedelta(minutes=LOGIN_BLOQUEO_MINUTOS)
                ).isoformat()
            supabase.table("login_attempts").update({
                "intentos": intentos,
                "bloqueado_hasta": bloqueado_hasta,
                "ultimo_intento": datetime.now().isoformat()
            }).eq("documento", documento).execute()
        else:
            supabase.table("login_attempts").insert({
                "documento": documento,
                "intentos": 1,
                "bloqueado_hasta": None,
                "ultimo_intento": datetime.now().isoformat()
            }).execute()
    except Exception as e:
        print(f"Error registrando intento fallido: {e}")


def limpiar_intentos_login(documento: str):
    """Limpia los intentos tras un login exitoso."""
    try:
        supabase.table("login_attempts").delete() \
            .eq("documento", documento).execute()
    except Exception as e:
        print(f"Error limpiando intentos login: {e}")


# ==============================================================================
# 📋 AUDITORÍA
# ==============================================================================
def registrar_auditoria(accion: str, usuario: str = "SISTEMA", detalle: str = ""):
    """Registra una acción en el log de auditoría (archivo + print + Supabase)."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{accion}] Usuario: {usuario} | {detalle}"

    # Print al servidor (visible en logs de Streamlit)
    print(f"🔍 AUDIT: {log_entry}")

    # Guardar en archivo local
    try:
        os.makedirs(os.path.dirname(_AUDIT_LOG_PATH), exist_ok=True)
        with open(_AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(log_entry + "\n")
    except Exception:
        pass

    # Backup a Supabase (solo acciones críticas para no saturar)
    if accion.startswith("CRITICA") or accion == "LOGIN" or accion == "MIGRACION":
        try:
            from utils.db import supabase
            if supabase:
                supabase.table("audit_log").insert({
                    "accion": accion,
                    "usuario": usuario,
                    "detalle": detalle,
                    "timestamp": datetime.now().isoformat()
                }).execute()
        except Exception:
            pass  # No fallar si la tabla audit_log no existe aún


def registrar_login(usuario: str, exito: bool, motivo: str = ""):
    """Registra un intento de login."""
    estado = "EXITOSO" if exito else "FALLIDO"
    detalle = f"Login {estado}"
    if motivo:
        detalle += f" — {motivo}"
    registrar_auditoria("LOGIN", usuario, detalle)


def registrar_accion_critica(accion: str, usuario: str, detalle: str = ""):
    """Registra acciones críticas (eliminar, cambiar rol, etc)."""
    registrar_auditoria(f"CRITICA/{accion}", usuario, detalle)
