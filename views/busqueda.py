import streamlit as st
import pandas as pd
from utils.db import supabase
from utils.helpers import navegar_a, registrar_acceso
from utils.nav_button import render_back_button


def render():
    st.title("🔍 BÚSQUEDA GLOBAL")
    render_back_button()
    st.caption("Busca en activos, órdenes de trabajo y repuestos con un solo término.")

    query = st.text_input(
        "¿Qué estás buscando?",
        placeholder="Ej: motor línea 2, cambio de filtro, rodamiento SKF...",
        key="global_search_input"
    )

    if not query or len(query.strip()) < 1:
        # Mostrar últimos accesos si existen
        _render_ultimos_accesos()
        st.info("✍️ Escribe al menos 1 carácter para buscar.")
        return

    query = query.strip()

    # Autocompletado: mostrar sugerencias rápidas mientras escribes
    if len(query) >= 1:
        _render_sugerencias(query)

    if len(query) < 2:
        return

    st.markdown(f"### Resultados para: *\"{query}\"*")
    st.markdown("---")

    # Buscar en paralelo las 3 entidades
    col_a, col_o, col_r = st.columns(3)

    # ── ACTIVOS ──
    with col_a:
        _buscar_activos(query)

    # ── ÓRDENES ──
    with col_o:
        _buscar_ordenes(query)

    # ── REPUESTOS ──
    with col_r:
        _buscar_repuestos(query)


# ==============================================================================
# 🕐 ÚLTIMOS ACCESOS
# ==============================================================================
def _render_ultimos_accesos():
    """Muestra los últimos items visitados desde búsqueda."""
    ultimos = st.session_state.get('ultimos_accesos', [])
    if not ultimos:
        return

    st.markdown("#### 🕐 Últimos Accesos")
    cols = st.columns(min(len(ultimos), 5))
    for i, item in enumerate(ultimos[:5]):
        with cols[i]:
            icono = {"activo": "🔧", "orden": "🛠️", "repuesto": "🔩"}.get(item['tipo'], "📋")
            if st.button(f"{icono} {item['nombre'][:20]}", key=f"ultimo_{i}", use_container_width=True):
                _navegar_a_item(item)


def _navegar_a_item(item):
    """Navega al módulo correcto y selecciona el item."""
    tipo = item['tipo']
    item_id = item['id']

    if tipo == 'activo':
        navegar_a("Inventario Activos", jump_target="activo", jump_id=item_id)
    elif tipo == 'orden':
        navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=item_id)
    elif tipo == 'repuesto':
        navegar_a("Repuestos", jump_target="repuesto", jump_id=item_id)


def _render_sugerencias(query):
    """Muestra sugerencias rápidas mientras el usuario escribe (1+ caracteres)."""
    try:
        # Buscar solo nombres de activos y IDs de órdenes (rápido, sin joins)
        res_act = supabase.table("activos").select("id, nombre").ilike("nombre", f"%{query}%").limit(5).execute()
        res_ord = supabase.table("ordenes").select("id, descripcion").ilike("descripcion", f"%{query}%").limit(5).execute()

        sugerencias = []
        if res_act.data:
            for a in res_act.data:
                sugerencias.append(("📦", f"Activo: {a['nombre']}", a['id'], "activo"))
        if res_ord.data:
            for o in res_ord.data:
                desc_corta = (o.get('descripcion', '') or '')[:50]
                sugerencias.append(("🛠️", f"OT #{o['id']}: {desc_corta}", o['id'], "orden"))

        if sugerencias:
            st.markdown("#### 💡 Sugerencias rápidas")
            cols = st.columns(min(len(sugerencias), 3))
            for i, (icono, texto, item_id, tipo) in enumerate(sugerencias[:6]):
                with cols[i % 3]:
                    if st.button(f"{icono} {texto[:35]}", key=f"sug_{tipo}_{item_id}", use_container_width=True):
                        if tipo == "activo":
                            navegar_a("Inventario Activos", jump_target="activo", jump_id=item_id)
                        elif tipo == "orden":
                            navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=item_id)
            st.markdown("---")
    except Exception:
        pass  # Sugerencias son opcionales, no mostrar error


def _buscar_activos(query):
    st.markdown("#### 📦 Activos")
    try:
        res_nom = supabase.table("activos").select("id, nombre, categoria, area, ubicacion") \
            .ilike("nombre", f"%{query}%").limit(10).execute()
        res_cat = supabase.table("activos").select("id, nombre, categoria, area, ubicacion") \
            .ilike("categoria", f"%{query}%").limit(10).execute()
        res_ubi = supabase.table("activos").select("id, nombre, categoria, area, ubicacion") \
            .ilike("ubicacion", f"%{query}%").limit(10).execute()

        todos = {}
        for res in [res_nom, res_cat, res_ubi]:
            if res.data:
                for item in res.data:
                    todos[item['id']] = item

        resultados = list(todos.values())
        if resultados:
            st.success(f"**{len(resultados)}** encontrado(s)")
            for a in resultados[:8]:
                with st.expander(f"🔧 {a['nombre']}", expanded=False):
                    st.caption(f"📍 {a.get('area', 'N/A')} / {a.get('ubicacion', 'N/A')}")
                    st.caption(f"🔧 {a.get('categoria', 'N/A')}")
                    if st.button("📋 Ver ficha completa", key=f"search_act_{a['id']}", type="primary"):
                        registrar_acceso('activo', a['id'], a['nombre'])
                        navegar_a("Inventario Activos", jump_target="activo", jump_id=a['id'])
                    if st.button("🛠️ Ver sus órdenes", key=f"search_act_ord_{a['id']}", type="secondary"):
                        registrar_acceso('activo', a['id'], a['nombre'])
                        navegar_a("Ordenes de Trabajo", jump_target="ordenes_por_activo", jump_id=a['id'])
        else:
            st.caption("Sin resultados")
    except Exception as e:
        st.caption(f"Error en búsqueda: activos")
        print(f"Error búsqueda activos: {e}")


def _buscar_ordenes(query):
    st.markdown("#### 🛠️ Órdenes de Trabajo")
    try:
        res_desc = supabase.table("ordenes").select("id, descripcion, estado, criticidad, tipo_mantenimiento, fecha_creacion") \
            .ilike("descripcion", f"%{query}%").limit(10).execute()

        resultados = res_desc.data if res_desc.data else []

        if query.isdigit():
            res_id = supabase.table("ordenes").select("id, descripcion, estado, criticidad, tipo_mantenimiento, fecha_creacion") \
                .eq("id", int(query)).execute()
            if res_id.data:
                for item in res_id.data:
                    if item['id'] not in [r['id'] for r in resultados]:
                        resultados.append(item)

        if resultados:
            st.success(f"**{len(resultados)}** encontrada(s)")
            for o in resultados[:8]:
                icono = "✅" if o['estado'] == 'Concluida' else "🔨" if o['estado'] == 'Abierta' else "🧐"
                with st.expander(f"{icono} OT #{o['id']} — {o.get('descripcion', '')[:40]}...", expanded=False):
                    st.caption(f"Estado: {o['estado']} | Criticidad: {o.get('criticidad', 'N/A')}")
                    st.caption(f"Tipo: {o.get('tipo_mantenimiento', 'N/A')}")
                    st.caption(f"Fecha: {o.get('fecha_creacion', '')[:10]}")
                    if st.button("⚙️ Gestionar", key=f"search_ot_{o['id']}", type="primary"):
                        registrar_acceso('orden', o['id'], f"OT #{o['id']}")
                        navegar_a("Ordenes de Trabajo", jump_target="orden", jump_id=o['id'])
        else:
            st.caption("Sin resultados")
    except Exception as e:
        st.caption(f"Error en búsqueda: órdenes")
        print(f"Error búsqueda órdenes: {e}")


def _buscar_repuestos(query):
    st.markdown("#### 🔩 Repuestos")
    try:
        res_nom = supabase.table("repuestos").select("id, nombre, referencia, categoria, stock_actual, stock_minimo") \
            .ilike("nombre", f"%{query}%").limit(10).execute()
        res_ref = supabase.table("repuestos").select("id, nombre, referencia, categoria, stock_actual, stock_minimo") \
            .ilike("referencia", f"%{query}%").limit(10).execute()

        todos = {}
        for res in [res_nom, res_ref]:
            if res.data:
                for item in res.data:
                    todos[item['id']] = item

        resultados = list(todos.values())
        if resultados:
            st.success(f"**{len(resultados)}** encontrado(s)")
            for r in resultados[:8]:
                stock = r.get('stock_actual', 0)
                minimo = r.get('stock_minimo', 0)
                icono = "🔴" if stock == 0 else "🟡" if stock <= minimo else "🟢"
                with st.expander(f"{icono} {r['nombre']}", expanded=False):
                    st.caption(f"Ref: {r.get('referencia', 'N/A')} | Cat: {r.get('categoria', 'N/A')}")
                    st.caption(f"Stock: {stock} / mín: {minimo}")
                    if st.button("📦 Ver en inventario", key=f"search_rep_{r['id']}", type="primary"):
                        registrar_acceso('repuesto', r['id'], r['nombre'])
                        navegar_a("Repuestos", jump_target="repuesto", jump_id=r['id'])
        else:
            st.caption("Sin resultados")
    except Exception as e:
        st.caption(f"Error en búsqueda: repuestos")
        print(f"Error búsqueda repuestos: {e}")
