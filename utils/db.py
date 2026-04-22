# ==============================================================================
# utils/db.py — OPTIMIZADO
# ==============================================================================
import streamlit as st
import pandas as pd
from supabase import create_client, Client


# ==============================================================================
# 🔌 CONEXIÓN A SUPABASE
# ==============================================================================
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"❌ Configuración incompleta: falta la clave {e} en secrets.toml.")
        return None
    except Exception as e:
        st.error("❌ No se pudo conectar a la base de datos. Contacte al administrador.")
        print(f"Error conectando Supabase: {e}")
        return None


supabase = init_supabase()


# ==============================================================================
# 🔍 FUNCIONES DE CONSULTA
# ==============================================================================
def run_query(table_name, filters=None, order_by="id"):
    """
    Todas las tablas pasan por caché.
    - Tablas maestras: TTL 600s (cambian poco)
    - Tablas transaccionales: TTL 60s (cambian más seguido)
    """
    tablas_maestras = ["usuarios", "activos", "categorias", "ubicaciones", "inventario"]

    if table_name in tablas_maestras:
        return pd.DataFrame(_run_query_cached(table_name, tuple(filters.items()) if filters else None, order_by, ttl=600))
    else:
        return pd.DataFrame(_run_query_cached(table_name, tuple(filters.items()) if filters else None, order_by, ttl=60))


@st.cache_data(ttl=60, show_spinner=False)
def _run_query_cached(table_name, filters_tuple, order_by, ttl=60):
    """
    Consulta genérica cacheada.
    Recibe filters como tupla para que sea hashable por Streamlit.
    """
    try:
        query = supabase.table(table_name).select("*")
        if filters_tuple:
            for key, value in filters_tuple:
                if value is not None:
                    query = query.eq(key, value)
        res = query.order(order_by).execute()
        return res.data if res.data else []
    except Exception as e:
        print(f"Error en consulta {table_name}: {e}")
        return []


# ── Mantener compatibilidad con imports existentes ──
def _run_query_internal(table_name, filters, order_by):
    """Compatibilidad: redirige a _run_query_cached."""
    filters_tuple = tuple(filters.items()) if filters else None
    return _run_query_cached(table_name, filters_tuple, order_by)

def _run_query_live_data(table_name, filters, order_by):
    """Compatibilidad: redirige a _run_query_cached."""
    filters_tuple = tuple(filters.items()) if filters else None
    return _run_query_cached(table_name, filters_tuple, order_by)


# ==============================================================================
# 🚫 INVALIDAR CACHÉ (cuando se crea/actualiza/elimina un registro)
# ==============================================================================
def invalidate_cache(table_name: str):
    """Limpia el caché de una tabla específica después de una escritura."""
    _run_query_cached.clear()
    st.cache_data.clear()


# ==============================================================================
# 📄 CONSULTAS PAGINADAS
# ==============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def run_query_paginated(table_name, page=1, per_page=25, filters_tuple=None, order_by="id", desc=True):
    """
    Consulta con paginación real desde Supabase (cacheada).
    Retorna (data_list, total_registros, total_paginas).
    """
    try:
        # Conteo total
        count_q = supabase.table(table_name).select("id", count="exact")
        if filters_tuple:
            for key, value in filters_tuple:
                if value is not None:
                    if isinstance(value, list):
                        count_q = count_q.in_(key, value)
                    else:
                        count_q = count_q.eq(key, value)
        count_res = count_q.execute()
        total = count_res.count if count_res.count is not None else 0

        # Datos paginados
        offset = (page - 1) * per_page
        data_q = supabase.table(table_name).select("*")
        if filters_tuple:
            for key, value in filters_tuple:
                if value is not None:
                    if isinstance(value, list):
                        data_q = data_q.in_(key, value)
                    else:
                        data_q = data_q.eq(key, value)
        data_q = data_q.order(order_by, desc=desc).range(offset, offset + per_page - 1)
        data_res = data_q.execute()
        data = data_res.data if data_res.data else []

        total_paginas = max(1, (total + per_page - 1) // per_page)
        return data, total, total_paginas

    except Exception as e:
        print(f"Error en consulta paginada {table_name}: {e}")
        return [], 0, 0


def run_query_paginated_df(table_name, page=1, per_page=25, filters=None, order_by="id", desc=True):
    """Wrapper que convierte filters dict a tupla y retorna DataFrame."""
    filters_tuple = tuple(filters.items()) if filters else None
    data, total, total_paginas = run_query_paginated(table_name, page, per_page, filters_tuple, order_by, desc)
    return pd.DataFrame(data), total, total_paginas


def render_paginacion(key_prefix: str, pagina_actual: int, total_paginas: int, total_registros: int) -> int:
    """
    Renderiza controles de paginación. Retorna la página seleccionada.
    """
    if total_paginas <= 1:
        return pagina_actual

    c_info, c_nav = st.columns([2, 3])
    with c_info:
        st.caption(f"📄 Página {pagina_actual} de {total_paginas} — {total_registros} registros")

    with c_nav:
        c_prev, c_pg, c_next = st.columns([1, 2, 1])
        with c_prev:
            disabled_prev = pagina_actual <= 1
            if st.button("◀", key=f"{key_prefix}_prev", disabled=disabled_prev, use_container_width=True):
                return pagina_actual - 1
        with c_pg:
            nueva = st.number_input(
                "Página", min_value=1, max_value=total_paginas,
                value=pagina_actual, label_visibility="collapsed",
                key=f"{key_prefix}_page_input"
            )
            if nueva != pagina_actual:
                return nueva
        with c_next:
            disabled_next = pagina_actual >= total_paginas
            if st.button("▶", key=f"{key_prefix}_next", disabled=disabled_next, use_container_width=True):
                return pagina_actual + 1

    return pagina_actual
