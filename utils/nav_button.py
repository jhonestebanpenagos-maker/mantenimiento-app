import streamlit as st
from utils.helpers import tiene_historial, volver_atras


def render_back_button(label=None):
    """
    Renderiza un botón de 'volver' prominente en la parte superior del contenido.
    Solo aparece si hay historial de navegación.
    """
    if not tiene_historial():
        return

    # Detectar de dónde venimos para mostrar un label útil
    history = st.session_state.get('nav_history', [])
    if history and not label:
        prev_page = history[-1].get('page', '')
        page_labels = {
            "Busqueda Global": "🔍 Búsqueda",
            "Tablero de Mando": "📊 Tablero",
            "Inventario Activos": "📦 Inventario",
            "Ordenes de Trabajo": "🛠️ Órdenes",
            "Repuestos": "🔩 Repuestos",
            "Usuarios": "👤 Usuarios",
        }
        label = page_labels.get(prev_page, prev_page)

    btn_label = f"⬅️ Volver a {label}" if label else "⬅️ Volver"

    if st.button(btn_label, key="_btn_volver_inline", type="secondary"):
        volver_atras()
