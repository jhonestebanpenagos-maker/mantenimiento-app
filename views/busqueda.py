import streamlit as st
import pandas as pd
from utils.db import supabase


def render():
    st.title("🔍 BÚSQUEDA GLOBAL")
    st.caption("Busca en activos, órdenes de trabajo y repuestos con un solo término.")

    query = st.text_input(
        "¿Qué estás buscando?",
        placeholder="Ej: motor línea 2, cambio de filtro, rodamiento SKF...",
        key="global_search_input"
    )

    if not query or len(query.strip()) < 2:
        st.info("✍️ Escribe al menos 2 caracteres para buscar.")
        return

    query = query.strip()
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


def _buscar_activos(query):
    st.markdown("#### 📦 Activos")
    try:
        # Buscar por nombre, categoría, ubicación o área
        res_nom = supabase.table("activos").select("id, nombre, categoria, area, ubicacion") \
            .ilike("nombre", f"%{query}%").limit(10).execute()
        res_cat = supabase.table("activos").select("id, nombre, categoria, area, ubicacion") \
            .ilike("categoria", f"%{query}%").limit(10).execute()
        res_ubi = supabase.table("activos").select("id, nombre, categoria, area, ubicacion") \
            .ilike("ubicacion", f"%{query}%").limit(10).execute()

        # Combinar y deduplicar
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
                    if st.button("Ver detalle", key=f"search_act_{a['id']}", type="secondary"):
                        st.session_state.current_page = "Inventario Activos"
                        st.rerun()
        else:
            st.caption("Sin resultados")
    except Exception as e:
        st.caption(f"Error en búsqueda: activos")


def _buscar_ordenes(query):
    st.markdown("#### 🛠️ Órdenes de Trabajo")
    try:
        res_desc = supabase.table("ordenes").select("id, descripcion, estado, criticidad, tipo_mantenimiento, fecha_creacion") \
            .ilike("descripcion", f"%{query}%").limit(10).execute()

        resultados = res_desc.data if res_desc.data else []

        # También buscar por ID si el query es numérico
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
                    if st.button("Gestionar", key=f"search_ot_{o['id']}", type="secondary"):
                        st.session_state.current_page = "Ordenes de Trabajo"
                        st.session_state.jump_target = "orden"
                        st.session_state.jump_id = o['id']
                        st.rerun()
        else:
            st.caption("Sin resultados")
    except Exception as e:
        st.caption(f"Error en búsqueda: órdenes")


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
                    if st.button("Ver repuestos", key=f"search_rep_{r['id']}", type="secondary"):
                        st.session_state.current_page = "Repuestos"
                        st.rerun()
        else:
            st.caption("Sin resultados")
    except Exception as e:
        st.caption(f"Error en búsqueda: repuestos")
