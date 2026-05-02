import streamlit as st
import time
import uuid
from datetime import datetime, timedelta
from utils.db import supabase
from utils.helpers import (
    hashear_password, verificar_password, migrar_password_si_sha256,
    agregar_notificacion, registrar_login, error_amigable,
    verificar_bloqueo_login, registrar_intento_fallido, limpiar_intentos_login,
    LOGIN_MAX_INTENTOS, LOGIN_BLOQUEO_MINUTOS,
)

# Duración máxima de sesión (horas)
SESSION_MAX_HOURS = 8


# ==============================================================================
# 🚀 SVG DE ORIÓN
# ==============================================================================
def render_orion_svg(color):
    ORION_SVG = f"""
        <svg width="250" height="250" viewBox="0 0 400 400" fill="none" xmlns="http://www.w3.org/2000/svg">
            <style>
                .star {{ fill: white; filter: drop-shadow(0 0 2px white); }}
                .belt {{ stroke: {color}; filter: drop-shadow(0 0 5px {color}); stroke-width: 2; opacity: 0.8; }}
                .line {{ stroke: {color}; stroke-width: 1; opacity: 0.4; }}
            </style>
            <path class="line" d="M100 150 L200 50 L300 150 L250 250 L150 250 L100 150 Z"/>
            <line class="belt" x1="160" y1="180" x2="200" y2="200"/>
            <line class="belt" x1="200" y1="200" x2="240" y2="220"/>
            <circle class="star" cx="200" cy="50"  r="5"/>
            <circle class="star" cx="100" cy="150" r="4"/>
            <circle class="star" cx="240" cy="220" r="6"/>
            <circle class="star" cx="200" cy="200" r="6"/>
            <circle class="star" cx="160" cy="180" r="6"/>
            <circle class="star" cx="300" cy="150" r="5"/>
            <circle class="star" cx="250" cy="250" r="7"/>
        </svg>
    """
    st.markdown(f"""
        <div style="display: flex; justify-content: center; margin-bottom: -30px;">
            {ORION_SVG}
        </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# 🚀 INICIALIZAR SESSION STATE
# ==============================================================================
def init_session_state():
    defaults = {
        'usuario': None,
        'rol': None,
        'user_doc': None,
        'session_token': None,
        'session_created_at': None,
        'sla_alertas_count': 0,
    }
    for key, default in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default


# ==============================================================================
# 🔓 LOGOUT
# ==============================================================================
def logout():
    usuario = st.session_state.get('usuario', 'DESCONOCIDO')
    registrar_login(usuario, exito=False, motivo="Sesión cerrada por el usuario")
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.session_state['user_doc'] = None
    st.session_state['session_token'] = None
    st.session_state['session_created_at'] = None
    st.session_state['sla_verificado'] = False
    st.session_state['sla_alertas_count'] = 0
    st.rerun()


# ==============================================================================
# 🔄 VERIFICACIÓN DE SESIÓN
# ==============================================================================
def _sesion_expirada() -> bool:
    """Verifica si la sesión actual ha expirado."""
    creada = st.session_state.get('session_created_at')
    if not creada:
        return True
    try:
        if isinstance(creada, str):
            creada_dt = datetime.fromisoformat(creada)
        else:
            creada_dt = creada
        return datetime.now() - creada_dt > timedelta(hours=SESSION_MAX_HOURS)
    except Exception:
        return True


def _forzar_cierre_sesion(motivo: str):
    """Fuerza el cierre de sesión por expiración u otro motivo."""
    usuario = st.session_state.get('usuario', 'DESCONOCIDO')
    registrar_login(usuario, exito=False, motivo=motivo)
    st.session_state['usuario'] = None
    st.session_state['rol'] = None
    st.session_state['user_doc'] = None
    st.session_state['session_token'] = None
    st.session_state['session_created_at'] = None


def try_restore_session():
    """Verifica si ya hay una sesión activa y válida en session_state."""
    if st.session_state['usuario'] is not None:
        if _sesion_expirada():
            _forzar_cierre_sesion(f"Sesión expirada (>{SESSION_MAX_HOURS}h)")
            st.rerun()
        return


# ==============================================================================
# 🔒 PANTALLA DE LOGIN
# ==============================================================================
def show_login():
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        render_orion_svg("#F59E0B")
        st.markdown(f"""
            <h1 style='text-align: center; font-size: 3.5rem; margin-bottom: -15px; text-shadow: 0 0 10px #F59E0B;'>ORIÓN</h1>
            <p style='text-align: center; color: #E5E7EB; font-size: 1.2rem; letter-spacing: 2px; margin-top: 5px; margin-bottom: 20px; font-weight: 300;'>
                PLATAFORMA INTEGRAL DE MANTENIMIENTO
            </p>
        """, unsafe_allow_html=True)
        st.markdown(f"""
            <div class='card-style' style='padding: 10px; margin-top: 0px; margin-bottom: 30px; text-align: center; font-size: 0.85em; color:#F59E0B; border: none; box-shadow: none; background: transparent;'>
                <p style='margin: 0;'>Desarrollado por: <b>Jhonestebanpenagos@gmail.com</b></p>
            </div>
            <hr style="border: none; height: 1px; background: linear-gradient(90deg, transparent, #F59E0B, transparent); margin-bottom: 30px;">
        """, unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center; margin-bottom: 20px;'>ACCESO DE USUARIOS</h3>", unsafe_allow_html=True)

        with st.form("login_form"):
            documento = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("ACCEDER AL SISTEMA", type="primary", use_container_width=True)

            if submitted:
                # ── Rate limiting persistente (server-side en Supabase) ──
                documento_limpio = (documento or "").strip()
                if not documento_limpio:
                    st.error("Ingrese su documento de identidad.")
                    st.stop()

                bloqueado, intentos_actuales, bloqueado_hasta = verificar_bloqueo_login(documento_limpio)

                if bloqueado:
                    try:
                        restante = datetime.fromisoformat(bloqueado_hasta) - datetime.now()
                        segundos_totales = max(0, int(restante.total_seconds()))
                        minutos = segundos_totales // 60
                        segundos = segundos_totales % 60
                        st.error(f"🔒 Cuenta bloqueada. Intenta en {minutos}m {segundos}s.")
                    except Exception:
                        st.error("🔒 Cuenta bloqueada por demasiados intentos. Intenta más tarde.")
                    st.stop()

                with st.spinner("Conectando y validando credenciales..."):
                    try:
                        # Buscar usuario SOLO por documento (no por hash)
                        response = supabase.table("usuarios").select("*") \
                            .eq("documento", documento_limpio) \
                            .execute()

                        if response.data:
                            user = response.data[0]
                            hash_almacenado = user.get('password', '')

                            # Verificar contraseña con soporte dual (bcrypt / SHA-256 legacy)
                            if verificar_password(password, hash_almacenado):
                                # Migración automática si el hash es SHA-256
                                migrar_password_si_sha256(documento_limpio, password, hash_almacenado)

                                registrar_login(documento_limpio, exito=True, motivo="Credenciales válidas")
                                limpiar_intentos_login(documento_limpio)

                                st.session_state['usuario'] = user['nombre']
                                st.session_state['rol'] = user['rol']
                                st.session_state['user_doc'] = documento_limpio
                                st.session_state['session_created_at'] = datetime.now().isoformat()
                                st.session_state['session_token'] = str(uuid.uuid4())
                                st.rerun()
                            else:
                                registrar_login(documento_limpio, exito=False, motivo="Contraseña incorrecta")
                                registrar_intento_fallido(documento_limpio)
                                # Re-verificar para mostrar estado actualizado
                                _, intentos_actualizados, _ = verificar_bloqueo_login(documento_limpio)
                                restantes = LOGIN_MAX_INTENTOS - intentos_actualizados
                                if restantes <= 0:
                                    st.error(f"🔒 Demasiados intentos. Cuenta bloqueada por {LOGIN_BLOQUEO_MINUTOS} minutos.")
                                else:
                                    st.error(f"❌ Usuario o contraseña incorrectos. Te quedan {restantes} intento(s).")
                        else:
                            # Usuario no existe — igual registramos el intento
                            # (usar documento para no revelar si existe o no)
                            registrar_login(documento_limpio, exito=False, motivo="Credenciales inválidas")
                            registrar_intento_fallido(documento_limpio)
                            _, intentos_actualizados, _ = verificar_bloqueo_login(documento_limpio)
                            restantes = LOGIN_MAX_INTENTOS - intentos_actualizados
                            if restantes <= 0:
                                st.error(f"🔒 Demasiados intentos. Cuenta bloqueada por {LOGIN_BLOQUEO_MINUTOS} minutos.")
                            else:
                                st.error(f"❌ Usuario o contraseña incorrectos. Te quedan {restantes} intento(s).")
                    except Exception as e:
                        registrar_login(documento_limpio, exito=False, motivo=f"Error: {type(e).__name__}")
                        error_amigable(e, "iniciar sesión")
    st.stop()


# ==============================================================================
# 🔐 CHECK LOGIN (retorna True si autenticado)
# ==============================================================================
def check_login():
    init_session_state()
    try_restore_session()
    if st.session_state['usuario'] is None:
        show_login()
        return False
    return True
