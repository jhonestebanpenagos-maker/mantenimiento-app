# ==============================================================================
# PROYECTO: ORIÓN - Mantenimiento Inteligente
# AUTOR: JHON ESTEBAN PENAGOS
# VERSIÓN: REFACTORIZADA EN MÓDULOS
# ==============================================================================
import streamlit as st
import pandas as pd
from datetime import datetime

# ==============================================================================
# 🚀 ARRANQUE
# ==============================================================================
st.set_page_config(page_title="Orión | Mantenimiento", layout="wide", initial_sidebar_state="collapsed")
st.write("Streamlit version:", st.__version__)

# Configuración
from config import init_cloudinary, cargar_css, render_selector_tema
from auth import check_login, logout
from utils.db import supabase, run_query
from utils.notifications import notificar_telegram

init_cloudinary()
cargar_css()

if not supabase:
    st.stop()

# ==============================================================================
# 🚀 INTERCEPTOR PÚBLICO (ACCESO QR)
# ==============================================================================
query_params = st.query_params
if "id_activo_qr" in query_params:
    id_qr = query_params["id_activo_qr"]
    try:
        datos_activo = supabase.table("activos").select("*").eq("id", id_qr).execute()
    except:
        st.error("Error de conexión.")
        st.stop()

    if datos_activo.data:
        activo = datos_activo.data[0]
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
        try:
            ots = supabase.table("ordenes").select("*").eq("activo_id", id_qr) \
                .order("id", desc=True).limit(5).execute()
            if ots.data:
                st.table(pd.DataFrame(ots.data)[['fecha_creacion', 'tipo_mantenimiento', 'estado']])
            else:
                st.info("Sin registros.")
        except:
            pass
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

with st.sidebar:
    st.markdown(f"""
        <div style="margin-bottom: 20px;">
            <p style="color: white; margin: 0; font-size: 1.1rem; font-weight: 600;">👋 {usuario}</p>
            <p style="color: #F59E0B; margin: 5px 0 0 0; font-size: 0.9rem;">{rol.upper()}</p>
        </div>
    """, unsafe_allow_html=True)

    # Indicador de sesión
    from auth import _sesion_expirada, SESSION_MAX_HOURS
    from datetime import datetime, timedelta
    creada = st.session_state.get('session_created_at')
    if creada:
        try:
            creada_dt = datetime.fromisoformat(creada) if isinstance(creada, str) else creada
            restante = timedelta(hours=SESSION_MAX_HOURS) - (datetime.now() - creada_dt)
            horas_rest = max(0, int(restante.total_seconds() // 3600))
            mins_rest = max(0, int((restante.total_seconds() % 3600) // 60))
            if restante.total_seconds() <= 0:
                st.error("⏰ Sesión expirada")
            elif restante.total_seconds() <= 3600:
                st.warning(f"⏰ Sesión: {mins_rest}m restantes")
            else:
                st.caption(f"🔒 Sesión activa: {horas_rest}h {mins_rest}m")
        except Exception:
            pass

    if st.button("🔓 Salir", use_container_width=True, type="secondary"):
        logout()

    st.divider()

    if 'current_page' not in st.session_state:
        st.session_state.current_page = "Tablero de Mando"

    if rol == "Admin":
        menu = [("🔍", "Búsqueda"), ("📊", "Tablero"), ("🏗️", "Jerarquía"), ("📦", "Inventario Activos"), ("🛠️", "Órdenes de Trabajo"), ("🔩", "Repuestos"), ("👤", "Usuarios")]
        valores = ["Busqueda Global", "Tablero de Mando", "Jerarquia Activos", "Inventario Activos", "Ordenes de Trabajo", "Repuestos", "Usuarios"]
    elif rol == "Programador":
        menu = [("🔍", "Búsqueda"), ("📊", "Tablero"), ("🏗️", "Jerarquía"), ("🛠️", "Órdenes de Trabajo"), ("🔩", "Repuestos"), ("👤", "Usuarios")]
        valores = ["Busqueda Global", "Tablero de Mando", "Jerarquia Activos", "Ordenes de Trabajo", "Repuestos", "Usuarios"]
    elif rol == "Tecnico":
        menu = [("🔍", "Búsqueda"), ("🛠️", "Órdenes de Trabajo")]
        valores = ["Busqueda Global", "Ordenes de Trabajo"]
    else:
        menu = []
        valores = []

    for (icono, texto), valor in zip(menu, valores):
        activo = st.session_state.current_page == valor
        tipo = "primary" if activo else "secondary"
        if st.button(f"{icono} {texto}", key=f"menu_{valor}", use_container_width=True, type=tipo):
            st.session_state.current_page = valor
            st.rerun()

    render_selector_tema()

    choice = st.session_state.current_page

# ==============================================================================
# 📄 RENDERIZAR PÁGINAS
# ==============================================================================
if choice == "Busqueda Global":
    from views.busqueda import render as render_busqueda
    render_busqueda()

elif choice == "Jerarquia Activos":
    from views.jerarquia import render as render_jerarquia
    render_jerarquia()

elif choice == "Tablero de Mando":
    from views.dashboard import render as render_dashboard
    render_dashboard()

elif choice == "Inventario Activos":
    from views.activos import render as render_activos
    render_activos()

elif choice == "Ordenes de Trabajo":
    from views.ordenes import render as render_ordenes
    render_ordenes()

elif choice == "Repuestos":
    from views.repuestos import render as render_repuestos
    render_repuestos()

elif choice == "Usuarios":
    from views.usuarios import render as render_usuarios
    render_usuarios()
