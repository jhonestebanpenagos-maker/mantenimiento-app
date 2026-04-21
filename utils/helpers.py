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
# 🔐 HASH DE CONTRASEÑAS
# ==============================================================================
import hashlib


def hashear_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()
