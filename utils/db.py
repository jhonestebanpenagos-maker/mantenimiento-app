import streamlit as st
import pandas as pd
from supabase import create_client, Client

# IMPORTAMOS NUESTRO NUEVO LOGGER
from utils.logger import logger 

# =============================================================================
# 🔌 CONEXIÓN A SUPABASE
# =============================================================================
@st.cache_resource
def init_supabase():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except KeyError as e:
        st.error(f"❌ Configuración incompleta: falta la clave {e} en secrets.toml.")
        logger.error(f"Falta clave en secrets: {e}")
        return None
    except Exception as e:
        st.error("❌ No se pudo conectar a la base de datos. Contacte al administrador.")
        logger.error(f"Error crítico conectando Supabase: {e}")
        return None

supabase = init_supabase()

# =============================================================================
# 📦 CACHÉ INTELIGENTE (SEPARADO)
# =============================================================================
# 1. Caché de larga duración para Catálogos (Se guarda por 1 hora en memoria)
@st.cache_data(ttl=3600, show_spinner=False)
def _query_catalogo(table_name):
    try:
        res = supabase.table(table_name).select("*").execute()
        return res.data if res.data else []
    except Exception as e:
        logger.error(f"Error en catálogo '{table_name}': {e}")
        return []

# 2. Caché rápido para Órdenes y Bitácoras (Se limpia constantemente)
@st.cache_data(ttl=60, show_spinner=False)
def _query_dinamico(table_name, filters_tuple, order_by, limit):
    try:
        query = supabase.table(table_name).select("*")
        if filters_tuple:
            for key, value in filters_tuple:
                if value is not None:
                    query = query.eq(key, value)
        query = query.order(order_by)
        if limit:
            query = query.limit(limit)
        res = query.execute()
        return res.data if res.data else []
    except Exception as e:
        logger.error(f"Error en dinámico '{table_name}': {e}")
        return []

def run_query(table_name, filters=None, order_by="id", limit=5000):
    """Lee datos. Decide automáticamente si usar caché estático o dinámico."""
    CATALOGOS = ["usuarios", "activos", "repuestos", "planes_mantenimiento"]
    
    # Si es un catálogo (y no tiene filtros raros), usa el caché de 1 hora
    if table_name in CATALOGOS and not filters:
        data = _query_catalogo(table_name)
        df = pd.DataFrame(data)
        # Mantener compatibilidad de ordenamiento para no romper menús
        if not df.empty and order_by in df.columns:
            df = df.sort_values(by=order_by)
        if limit and not df.empty:
            df = df.head(limit)
        return df
        
    # Si es operativo (ordenes, bitácora) o tiene filtros, usar caché dinámico
    filters_tuple = tuple(filters.items()) if filters else None
    return pd.DataFrame(_query_dinamico(table_name, filters_tuple, order_by, limit))

# =============================================================================
# 🔍 CONSULTA CON FILTRADO SERVIDOR (OPTIMIZACIÓN)
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def _run_query_filtered_cached(table_name, select_fields, filters_tuple, order_by, limit):
    """Consulta con selección de campos y filtrado en servidor."""
    try:
        query = supabase.table(table_name).select(select_fields)
        if filters_tuple:
            for key, value in filters_tuple:
                if value is not None:
                    query = query.eq(key, value)
        query = query.order(order_by)
        if limit:
            query = query.limit(limit)
        res = query.execute()
        return res.data if res.data else []
    except Exception as e:
        logger.error(f"Error en consulta filtrada a '{table_name}': {e}")
        return []

def run_query_filtered(table_name, select_fields="*", filters=None, order_by="id", limit=100):
    filters_tuple = tuple(filters.items()) if filters else None
    return pd.DataFrame(_run_query_filtered_cached(table_name, select_fields, filters_tuple, order_by, limit))

# =============================================================================
# ✏️ ESCRITURA CON INVALIDACIÓN INTELIGENTE
# =============================================================================
def invalidate_cache(table_name: str = None):
    """Limpia el caché de forma selectiva para no saturar el servidor."""
    # 1. Las tablas operativas siempre se limpian para tener info fresca
    _query_dinamico.clear()
    _run_query_filtered_cached.clear()
    run_query_paginated.clear()
    
    # 2. SOLO limpiamos los catálogos si el usuario editó explícitamente uno de ellos
    CATALOGOS = ["usuarios", "activos", "repuestos", "planes_mantenimiento"]
    if table_name in CATALOGOS or table_name is None:
        _query_catalogo.clear()
        
    logger.info(f"🔄 Caché invalidado. Origen de la modificación: {table_name or 'Global'}")

def db_insert(table_name: str, data: dict):
    result = supabase.table(table_name).insert(data).execute()
    invalidate_cache(table_name)
    return result

def db_update(table_name: str, data: dict, id_field: str, id_value):
    result = supabase.table(table_name).update(data).eq(id_field, id_value).execute()
    invalidate_cache(table_name)
    return result

def db_upsert(table_name: str, data: dict):
    result = supabase.table(table_name).upsert(data).execute()
    invalidate_cache(table_name)
    return result

def db_delete(table_name: str, id_field: str, id_value):
    result = supabase.table(table_name).delete().eq(id_field, id_value).execute()
    invalidate_cache(table_name)
    return result

# =============================================================================
# 📄 CONSULTAS PAGINADAS
# =============================================================================
@st.cache_data(ttl=60, show_spinner=False)
def run_query_paginated(table_name, page=1, per_page=25, filters_tuple=None, order_by="id", desc=True):
    try:
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
        logger.error(f"Error de paginación en tabla '{table_name}': {e}")
        return [], 0, 0

def run_query_paginated_df(table_name, page=1, per_page=25, filters=None, order_by="id", desc=True):
    filters_tuple = tuple(filters.items()) if filters else None
    data, total, total_paginas = run_query_paginated(table_name, page, per_page, filters_tuple, order_by, desc)
    return pd.DataFrame(data), total, total_paginas

def render_paginacion(key_prefix: str, pagina_actual: int, total_paginas: int, total_registros: int) -> int:
    if total_paginas <= 1:
        return pagina_actual

    c_info, c_nav = st.columns([2, 3])
    with c_info:
        st.caption(f"📄 Página {pagina_actual} de {total_paginas} — {total_registros} registros")

    with c_nav:
        c_prev, c_pg, c_next = st.columns([1, 2, 1])
        with c_prev:
            if st.button("◀", key=f"{key_prefix}_prev", disabled=pagina_actual <= 1, use_container_width=True):
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
            if st.button("▶", key=f"{key_prefix}_next", disabled=pagina_actual >= total_paginas, use_container_width=True):
                return pagina_actual + 1

    return pagina_actual
