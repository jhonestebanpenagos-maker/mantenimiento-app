# ==============================================================================
# PROYECTO: ORIÓN - Mantenimiento Inteligente
# AUTOR: JHON ESTEBAN PENAGOS
# VERSIÓN: REFACTORIZADA EN MÓDULOS + OPTIMIZADA
# ==============================================================================
import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta

# ==============================================================================
# 🚀 ARRANQUE
# ==============================================================================
st.set_page_config(page_title="Orión | Mantenimiento", layout="wide", initial_sidebar_state="collapsed")

# ── Imports de configuración y auth ──
from config import init_cloudinary, cargar_css, render_selector_tema
from auth import check_login, logout, SESSION_MAX_HOURS
from utils.db import supabase
from utils.notifications import notificar_telegram

# ── Imports de vistas (una sola vez al cargar el módulo) ──
from views.busqueda import render as render_busqueda
from views.jerarquia import render as render_jerarquia
from views.dashboard import render as render_dashboard
from views.activos import render as render_activos
from views.ordenes import render as render_ordenes
from views.repuestos import render as render_repuestos
from views.usuarios import render as render_usuarios

# ── Inicialización única ──
if 'app_initialized' not in st.session_state:
    init_cloudinary()
    st.session_state.app_initialized = True

# ── CSS se carga en CADA rerun (necesario para cambio de tema) ──
cargar_css()

if not supabase:
    st.error("Error de conexión a la base de datos.")
    st.stop()

# ==============================================================================
# 📦 FUNCIONES CACHEADAS
# ==============================================================================
@st.cache_data(ttl=300, show_spinner="Cargando activo...")
def cargar_activo_qr(activo_id: str):
    try:
        resultado = supabase.table("activos").select("*").eq("id", activo_id).execute()
        return resultado.data[0] if resultado.data else None
    except Exception as e:
        print(f"Error consultando activo QR: {e}")
        return None

@st.cache_data(ttl=300)
def cargar_historial_qr(activo_id: str):
    try:
        resultado = supabase.table("ordenes").select("*").eq("activo_id", activo_id) \
            .order("id", desc=True).limit(5).execute()
        return resultado.data if resultado.data else []
    except Exception as e:
        print(f"Error cargando historial QR: {e}")
        return []

# ==============================================================================
# 🚀 INTERCEPTOR PÚBLICO (ACCESO QR)
# ==============================================================================
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    activo = cargar_activo_qr(id_qr)

    if activo:
        st.markdown(f"<h1 style='text-align: center;'>ORIÓN: {activo['nombre']}</h1>", unsafe_allow_html=True)
        st.markdown(f"""
            <div class="card-style">
                <span class="chart-header">Ficha Técnica</span>
                <p><strong>📍 Área:</strong> {activo.get('area', 'N/A')}</p>
                <p><strong>🏢 Ubicación:</strong> {activo['ubicacion']}</p>
                <p><strong>🔧 Categoría:</strong> {activo.get('categoria', 'N/A')}</p>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("<h3 style='margin-top:20px;'>Historial</h3>", unsafe_allow_html=True)
        ots_data = cargar_historial_qr(id_qr)
        if ots_data:
            st.table(pd.DataFrame(ots_data)[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
        else:
            st.info("Sin registros.")

        st.markdown("---")
        if st.button("🏠 Inicio"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error("❌ Activo no encontrado.")
        if st.button("Volver"):
            st.query_params.clear()
            st.rerun()
    st.stop()

# ==============================================================================
# 🔒 LOGIN
# ==============================================================================
if not check_login():
    st.stop()

# ==============================================================================
# 🚀 DASHBOARD PRIVADO
# ==============================================================================
rol = st.session_state['rol']
usuario = st.session_state['usuario']

# ── Menú según rol ──
MENUS = {
    "Admin": [
        ("🔍", "Búsqueda", "Busqueda Global"),
        ("📊", "Tablero", "Tablero de Mando"),
        ("🏗️", "Jerarquía", "Jerarquia Activos"),
        ("📦", "Inventario", "Inventario Activos"),
        ("🛠️", "Órdenes", "Ordenes de Trabajo"),
        ("🔩", "Repuestos", "Repuestos"),
        ("👤", "Usuarios", "Usuarios"),
    ],
    "Programador": [
        ("🔍", "Búsqueda", "Busqueda Global"),
        ("📊", "Tablero", "Tablero de Mando"),
        ("🏗️", "Jerarquía", "Jerarquia Activos"),
        ("🛠️", "Órdenes", "Ordenes de Trabajo"),
        ("🔩", "Repuestos", "Repuestos"),
        ("👤", "Usuarios", "Usuarios"),
    ],
    "Tecnico": [
        ("🔍", "Búsqueda", "Busqueda Global"),
        ("🛠️", "Órdenes", "Ordenes de Trabajo"),
    ],
}

# ── Calcular tiempo de sesión cada 60s ──
creada = st.session_state.get('session_created_at')
if creada:
    now = time.time()
    last_check = st.session_state.get('_session_check_ts', 0)

    if now - last_check > 60:
        try:
            creada_dt = datetime.fromisoformat(creada) if isinstance(creada, str) else creada
            restante = timedelta(hours=SESSION_MAX_HOURS) - (datetime.now() - creada_dt)
            st.session_state['_session_restante'] = restante
            st.session_state['_session_check_ts'] = now
        except Exception:
            pass

with st.sidebar:
    st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <p style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">👋 {usuario}</p>
            <p style="color: #F59E0B; margin: 5px 0 0 0; font-size: 0.9rem;">{rol.upper()}</p>
        </div>
    """, unsafe_allow_html=True)

    # ── Indicador de sesión ──
    restante = st.session_state.get('_session_restante')
    if restante:
        horas_rest = max(0, int(restante.total_seconds() // 3600))
        mins_rest = max(0, int((restante.total_seconds() % 3600) // 60))
        if restante.total_seconds() <= 0:
            st.error("⏰ Sesión expirada")
        elif restante.total_seconds() <= 3600:
            st.warning(f"⏰ Sesión: {mins_rest}m restantes")
        else:
            st.caption(f"🔒 Sesión activa: {horas_rest}h {mins_rest}m")

    if st.button("🔓 Salir", use_container_width=True, type="secondary"):
        logout()

    st.divider()

    # ── Menú de navegación ──
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Tablero de Mando"

    current = st.session_state.current_page
    for icono, texto, valor in MENUS.get(rol, []):
        tipo = "primary" if current == valor else "secondary"
        if st.button(f"{icono} {texto}", key=f"m_{valor}", use_container_width=True, type=tipo):
            st.session_state.current_page = valor
            st.session_state.jump_target = None
            st.session_state.jump_id = None
            st.rerun()

    # ── Indicador de ubicación ──
    st.divider()
    page_icons = {
        "Busqueda Global": "🔍", "Tablero de Mando": "📊", "Jerarquia Activos": "🏗️",
        "Inventario Activos": "📦", "Ordenes de Trabajo": "🛠️", "Repuestos": "🔩", "Usuarios": "👤"
    }
    icon = page_icons.get(current, "📋")
    st.caption(f"📍 {icon} {current}")

    # ── Últimos accesos ──
    ultimos = st.session_state.get('ultimos_accesos', [])
    if ultimos:
        with st.expander("🕐 Últimos vistos", expanded=False):
            for item in ultimos[:3]:
                tipo_icon = {"activo": "🔧", "orden": "🛠️", "repuesto": "🔩"}.get(item['tipo'], "📋")
                if st.button(f"{tipo_icon} {item['nombre'][:25]}", key=f"sb_last_{item['tipo']}_{item['id']}", use_container_width=True):
                    if item['tipo'] == 'activo':
                        st.session_state.current_page = "Inventario Activos"
                        st.session_state.jump_target = "activo"
                        st.session_state.jump_id = item['id']
                    elif item['tipo'] == 'orden':
                        st.session_state.current_page = "Ordenes de Trabajo"
                        st.session_state.jump_target = "orden"
                        st.session_state.jump_id = item['id']
                    elif item['tipo'] == 'repuesto':
                        st.session_state.current_page = "Repuestos"
                        st.session_state.jump_target = "repuesto"
                        st.session_state.jump_id = item['id']
                    st.rerun()

    render_selector_tema()

# ==============================================================================
# 🔄 RESOLVER JUMP TARGETS
# ==============================================================================
JUMP_MAP = {
    "activo": "Inventario Activos",
    "orden": "Ordenes de Trabajo",
    "ordenes_por_activo": "Ordenes de Trabajo",
    "crear_para_activo": "Ordenes de Trabajo",
    "preventivo": "Ordenes de Trabajo",
    "repuesto": "Repuestos",
}

jump = st.session_state.get('jump_target')
if jump and jump in JUMP_MAP:
    st.session_state.current_page = JUMP_MAP[jump]

choice = st.session_state.current_page

# ==============================================================================
# 📄 RENDERIZAR PÁGINAS
# ==============================================================================
PAGES = {
    "Busqueda Global": render_busqueda,
    "Tablero de Mando": render_dashboard,
    "Jerarquia Activos": render_jerarquia,
    "Inventario Activos": render_activos,
    "Ordenes de Trabajo": render_ordenes,
    "Repuestos": render_repuestos,
    "Usuarios": render_usuarios,
}

render_fn = PAGES.get(choice)
if render_fn:
    render_fn()
