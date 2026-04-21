import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime


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
        st.error(f"Error validando usuario: {e}")
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
# 🔐 HASH DE CONTRASEÑAS (bcrypt)
# ==============================================================================
import bcrypt
import hashlib
import json
import os

# Ruta del archivo de auditoría local
_AUDIT_LOG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "auditoria.log")


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
# 📋 AUDITORÍA
# ==============================================================================
def registrar_auditoria(accion: str, usuario: str = "SISTEMA", detalle: str = ""):
    """Registra una acción en el log de auditoría (archivo + print)."""
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
        pass  # Si falla el archivo, al menos queda en print


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
